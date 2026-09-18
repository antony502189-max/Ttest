import pytest
from pydantic import ValidationError

from app.content_safety import contains_listing_link
from app.schemas.listings import ListingPatch, ListingWrite


@pytest.mark.parametrize(
    "value",
    [
        "https://evil.example/path",
        "hxxp://evil.com/login",
        "h t t p s : / / evil.com",
        "www.evil.com",
        "evil.com/path",
        "evil[.]com",
        "evil(.)com",
        "evil[dot]com",
        "evil dot com",
        "evil punto es",
        "evil . com",
        "https%3A%2F%2Fevil.com",
        "evil&#46;com",
        "evil。com",
        "ev\u200bil.com",
        "127.0.0.1:8080",
        "[2001:db8::1]",
        "пример.рф",
        "xn--e1afmkfd.xn--p1ai",
        "javascript:alert(1)",
        "data:text/html,test",
        "mailto:someone@example.com",
        "tel:+34900123456",
        "sms:+34900123456",
        "magnet:?xt=urn:btih:deadbeef",
        "ipfs://bafybeigdyrzt/path",
        "tg://resolve?domain=example",
        "https%253A%252F%252Fevil.com",
        "ｈｔｔｐｓ：／／ｅｖｉｌ．ｃｏｍ",
        "h\u200btt\u200bps://evil.com",
        "login.secure.evil.xyz/reset",
        "evil{dot}com",
        "evil [ . ] com",
        "user@evil.com",
        "evil.com:8443/login",
    ],
)
def test_link_detector_rejects_direct_and_obfuscated_destinations(value: str) -> None:
    assert contains_listing_link(value)


@pytest.mark.parametrize(
    "value",
    [
        "Piso amplio. Cocina reformada y Wi-Fi incluido.",
        "La habitación mide 12.5 m² y está a 5 min. del tranvía.",
        "Contacta mediante los botones de teléfono o WhatsApp del anuncio.",
        "Incluye 100 €/mes de gastos.",
        "Dr. House es la referencia del propietario.",
        "p. ej. cerca del tranvía",
    ],
)
def test_link_detector_allows_normal_listing_prose(value: str) -> None:
    assert not contains_listing_link(value)


def valid_listing(**overrides) -> dict:
    values = {
        "title": "Habitación luminosa en Adeje",
        "city": "Adeje",
        "area": "Centro",
        "approximateAddress": "Centro · ubicación aproximada",
        "rentalMode": "long",
        "monthlyPrice": 700,
        "latitude": 28.122,
        "longitude": -16.731,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "Habitación en evil.com"),
        ("area", "Centro evil[.]com"),
        ("description", "Más información en https://evil.com/login"),
        ("homeDescription", "Normas completas en evil dot com"),
    ],
)
def test_listing_write_rejects_links_in_public_free_text(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match=rf"{field} must not contain links"):
        ListingWrite(**valid_listing(**{field: value}))


def test_listing_write_rejects_links_hidden_in_public_list_values() -> None:
    with pytest.raises(ValidationError, match=r"amenities must not contain links"):
        ListingWrite(**valid_listing(amenities=["Wi-Fi", "evil[.]com"]))


def test_listing_patch_cannot_bypass_link_filter() -> None:
    with pytest.raises(ValidationError, match=r"description must not contain links"):
        ListingPatch(description="Pago seguro en h t t p s : / / evil.com")


def test_safe_listing_content_remains_valid() -> None:
    listing = ListingWrite(
        **valid_listing(
            description="Habitación luminosa, tranquila y bien comunicada con el tranvía.",
            homeDescription="No se permite fumar. Respeta el descanso por la noche.",
        )
    )
    assert listing.description.startswith("Habitación luminosa")
