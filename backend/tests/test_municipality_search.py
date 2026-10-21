import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models import Listing
from app.repositories.listings import apply_search_filters
from app.schemas.listings import ListingSearchRequest
from app.spain_municipalities import MUNICIPALITIES, municipality_aliases, normalized_municipality
from app.services.notifications import _saved_search_payload
from types import SimpleNamespace


def test_catalogue_covers_all_municipalities_and_both_canary_provinces():
    assert len(MUNICIPALITIES) == 8132
    assert MUNICIPALITIES['38001'] == 'Adeje'
    assert MUNICIPALITIES['38004'] == 'Arafo'
    assert 'La Orotava' in municipality_aliases('Orotava, La')


@pytest.mark.parametrize('code', ['38001', '38004', '44009'])
def test_municipality_search_scopes_city_and_province_together(code):
    payload = ListingSearchRequest(query='España', provinceCode=code[:2], municipalityCode=code)
    statement = apply_search_filters(select(Listing), payload).compile(dialect=postgresql.dialect())
    assert code[:2] in statement.params.values()
    assert [normalized_municipality(alias) for alias in municipality_aliases(MUNICIPALITIES[code])] in statement.params.values()
    assert 'city' in str(statement)
    assert f'%{MUNICIPALITIES[code]}%' not in statement.params.values()


@pytest.mark.parametrize('payload', [
    {'municipalityCode': '99999'}, {'municipalityCode': '38001', 'provinceCode': '35'},
    {'municipalityCode': '3800'},
])
def test_invalid_municipality_or_conflicting_province_is_rejected(payload):
    with pytest.raises(ValueError):
        ListingSearchRequest(**payload)


def test_saved_municipality_alerts_do_not_expand_to_the_entire_province():
    search = SimpleNamespace(query='Santa Cruz de Tenerife', province_code='38', rental_mode='long',
                             filters={'municipalityCode': '38038'}, polygon=[])
    payload = _saved_search_payload(search)
    assert payload is not None
    assert payload.municipalityCode == '38038'
    assert payload.provinceCode == '38'


def test_accents_and_ine_article_aliases_match_imported_city_names():
    assert normalized_municipality('Güímar') == normalized_municipality('Guimar')
    assert normalized_municipality('Guía de Isora') == normalized_municipality('Guia de Isora')
    assert 'La Laguna' in municipality_aliases('San Cristóbal de La Laguna')
