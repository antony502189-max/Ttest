from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from app.services import address_geography as geography
from app.spain_provinces import imported_province_code

MADRID = {"id": "official-test-madrid-portal", "type": "portal", "countryCode": "011", "muniCode": "28079",
          "provinceCode": "28", "postalCode": "28013", "muni": "Madrid", "poblacion": "Madrid",
          "address": "CALLE MAYOR 1, Madrid", "lat": 40.41646, "lng": -3.70466}


def test_all_8132_ine_municipalities_have_distinct_five_digit_codes():
    assert len(geography.MUNICIPALITIES) == 8132
    assert geography.MUNICIPALITIES["28079"] == "Madrid"
    assert "28065" in geography.MUNICIPALITIES  # Getafe is not Madrid municipality.
    assert all(len(code) == 5 and code.isascii() and code.isdigit() for code in geography.MUNICIPALITIES)


def test_imported_structured_province_requires_consistent_country_and_coordinates():
    item = SimpleNamespace(province="Madrid", country="ES", latitude=40.4168, longitude=-3.7038)
    assert imported_province_code(item) == "28"
    item.latitude, item.longitude = 41.38, 2.17
    with pytest.raises(ValueError, match="conflicts"):
        imported_province_code(item)
    item.latitude = item.longitude = None
    assert imported_province_code(item) == "28"
    item.country = "FR"
    with pytest.raises(ValueError, match="country"):
        imported_province_code(item)


@pytest.mark.asyncio
async def test_server_resolves_address_without_trusting_postcode_or_coordinates(monkeypatch):
    monkeypatch.setattr(geography, "address_candidates", AsyncMock(return_value=[MADRID]))
    accepted = await geography.verify_address("Calle Mayor 1", "28013", "Madrid", latitude=40.4168, longitude=-3.7038)
    assert accepted.municipality_code == "28079" and accepted.province_code == "28"
    for street, postcode, city, lat, lng in [
        ("Calle Mayor 1", "08001", "Madrid", 40.4168, -3.7038),
        ("Calle Mayor 1", "28013", "Madrid", 41.38, 2.17),
        ("Fake Street 1", "28013", "Madrid", 40.4168, -3.7038),
        ("Calle Mayor 2", "28013", "Madrid", 40.4168, -3.7038),
        ("Calle Mayor 1", "", "Madrid", 40.4168, -3.7038),
        ("Calle Mayor 1", "garbage", "Madrid", 40.4168, -3.7038),
    ]:
        with pytest.raises(HTTPException) as error:
            await geography.verify_address(street, postcode, city, latitude=lat, longitude=lng)
        assert error.value.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("change", [{"countryCode": "FR"}, {"muniCode": "99999"}, {"provinceCode": "08"},
                                    {"type": "municipio"}, {"lat": float("nan")}])
async def test_ambiguous_foreign_or_non_address_provider_evidence_is_rejected(monkeypatch, change):
    monkeypatch.setattr(geography, "address_candidates", AsyncMock(return_value=[{**MADRID, **change}]))
    with pytest.raises(HTTPException):
        await geography.verify_address("Calle Mayor 1", "28013", "Madrid")


@pytest.mark.asyncio
async def test_real_transport_contract_uses_postcode_filter_and_does_not_log_private_address(monkeypatch, caplog):
    def handler(request):
        assert request.url.params["q"] == "Calle Mayor 1, Madrid"
        assert request.url.params["cod_postal_filter"] == "28013"
        assert request.url.host == "www.cartociudad.es"
        return httpx.Response(200, json=[MADRID])
    monkeypatch.setattr(geography, "PublicNetworkAsyncClient", lambda **kwargs: httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    with caplog.at_level("INFO", logger="httpx"):
        result = await geography.verify_address("Calle Mayor 1", "28013", "Madrid")
    assert result.municipality_code == "28079"
    assert "Calle" not in caplog.text and "28013" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status,content", [(503, b"provider failure"), (200, b"x" * 65537), (200, b"{}")],
                         ids=["unavailable", "oversized", "malformed"])
async def test_geocoder_failure_is_bounded_and_never_grants_unverified_geography(monkeypatch, status, content):
    monkeypatch.setattr(geography, "PublicNetworkAsyncClient", lambda **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, content=content))))
    with pytest.raises(HTTPException) as error:
        await geography.verify_address("Private street 123", "28013", "Madrid")
    assert error.value.status_code == 503
    assert "Private street" not in error.value.detail
