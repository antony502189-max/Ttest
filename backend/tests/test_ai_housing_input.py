"""Whole-request regressions; these do not claim real model/ASR quality."""
import json
from uuid import uuid4

import pytest

from app.repositories.ai_search_sessions import IntentVocabulary
from app.schemas.ai_search_intent import Criteria, SearchIntent, apply_patch
from app.services.ai_deepseek_intent import IntentClarificationRequired, ProviderFailure, intent_failure_code
from app.services.ai_housing_input import HousingGate, housing_patch, validate_housing_result

VOCAB = IntentVocabulary(frozenset({"wifi", "parking", "lift", "internet", "air_conditioning"}), frozenset(), frozenset())


def state(criteria=None):
    return SearchIntent(schema_version="ai-search.v1", taxonomy_version="rental.v1", session_id=uuid4(),
                        version=0, criteria=Criteria.model_validate(criteria or {}))


@pytest.mark.parametrize("prefix", ["I need to rent", "I want to rent", "I would like to rent", "I'd like to rent"])
def test_english_renter_prefix_preserves_complete_conditions(prefix):
    # Public text seed: Tatoeba sentence 2258804, _undertoad, CC BY 2.0 FR.
    # Its separately licensed audio is not an ASR fixture.
    c = housing_patch(f"{prefix} a room in Madrid under 700 euros per month, not furnished, without balcony, for 1 person",
                      state(), VOCAB).set
    assert c.accommodation.value.kind == "room"
    assert c.geography.value.municipality_code == "28079"
    assert c.budget.value.amount == "700" and c.budget.value.period == "monthly"
    assert c.furnished.value is False
    assert c.balcony.value is False
    assert c.party.value.model_dump() == {"persons": 1}


@pytest.mark.parametrize("text", [
    "I need to rent out a room", "I don't need to rent a room", "I needed to rent a room",
    "I need to rent a room or a studio", "I need to rent a room, not in Madrid",
    "I need to rent a room under 700 dollars per month", "I need to rent a room near my office",
    "I need to rent a room under 700 euros per month, not furnished, but only on Tuesdays",
    "He needs to rent a room", "I need to pay rent and keep the doors open.",
])
def test_english_renter_prefix_never_discards_unsupported_conditions(text):
    before = state({"bills_included": {"strength": "hard", "value": True}})
    snapshot = before.model_dump()
    with pytest.raises(ProviderFailure):
        housing_patch(text, before, VOCAB)
    assert before.model_dump() == snapshot


@pytest.mark.parametrize(("text", "reason"), [
    ("комната до 700 евро", "budget_period"),
    ("habitación hasta 700 euros", "budget_period"),
    ("a room under 700 dollars per month", "budget"),
    ("комната в Неведомске", "location"),
    ("квартиру с двумя спальнями до 700 евро в месяц", "accommodation"),
    ("комната с животными экзотических видов", "unsupported"),
    ("a room with pets requiring approval", "unsupported"),
    ("a room or a studio", "alternatives"),
    ("amueblado, sin muebles", "conflict"),
    ("from 2027-02-31 to 2027-03-05", "dates"),
    ("from 2027-02-15 to 2027-02-01", "dates"),
    ("fianza hasta 1.5 meses", "deposit"),
    ("for 12 people", "party"),
    ("a room with a swimming pool", "amenities"),
    ("комната рядом с морем", "location"),
    ("комната за 500 евро", "budget"),
])
def test_rejected_criteria_have_a_stable_reason_and_leave_intent_unchanged(text, reason):
    before = state({"furnished": {"strength": "hard", "value": False}})
    snapshot = before.model_dump()
    with pytest.raises(IntentClarificationRequired) as captured:
        housing_patch(text, before, VOCAB)
    assert captured.value.clarification.reason == reason
    assert intent_failure_code(captured.value) == "CLARIFY_" + reason.upper()
    assert before.model_dump() == snapshot


@pytest.mark.parametrize("text,name", [("not furnished", "furnished"), ("not bills included", "bills_included"),
                                       ("not balcony", "balcony"), ("not terrace", "terrace")])
def test_explicit_english_boolean_negation_is_a_hard_false_not_removal(text, name):
    before = state({"party": {"strength": "hard", "value": {"persons": 2}}})
    patch = housing_patch(text, before, VOCAB)
    assert patch.remove == ()
    after = apply_patch(before, patch)
    assert getattr(after.criteria, name).value is False
    assert getattr(after.criteria, name).strength == "hard"
    assert after.criteria.party == before.criteria.party


@pytest.mark.parametrize("text", ["not necessarily furnished", "not without furnished", "not not furnished",
                                  "not furnished or furnished", "not furnished, furnished", "not near Madrid"])
def test_boolean_negation_still_rejects_qualifiers_conflicts_and_unknowns(text):
    with pytest.raises(ProviderFailure):
        housing_patch(text, state(), VOCAB)


@pytest.mark.parametrize("text", ["sin muebles", "¿Sin muebles?", "sin amueblar", "unfurnished", "without furniture"])
def test_furniture_absence_is_explicit_false_and_preserves_committed_conditions(text):
    before = state({"furnished": {"strength": "hard", "value": True},
                    "party": {"strength": "hard", "value": {"persons": 2}},
                    "budget": {"strength": "hard", "value": {"amount": "700", "currency": "EUR", "period": "monthly"}}})
    patch = housing_patch(text, before, VOCAB)
    after = apply_patch(before, patch)
    assert patch.remove == ()
    assert after.criteria.furnished.value is False and after.criteria.furnished.strength == "hard"
    assert after.criteria.party == before.criteria.party
    assert after.criteria.budget == before.criteria.budget


@pytest.mark.parametrize("text", ["sin muebles, amueblado", "unfurnished, furnished", "not unfurnished",
                                  "without furniture or furnished", "sin muebles salvo la cocina",
                                  "furniture", "muebles", "No, amueblado.",
                                  "Doscientos, sin incluir luz, agua ni gas.", "¿Cuánto al mes?"])
def test_furniture_phrases_never_drop_qualifiers_or_contextual_negation(text):
    before = state({"furnished": {"strength": "hard", "value": True}})
    snapshot = before.model_dump()
    with pytest.raises(ProviderFailure):
        housing_patch(text, before, VOCAB)
    assert before.model_dump() == snapshot


@pytest.mark.parametrize("text", [
    "ищу комнату в Мадрид до 700 евро в месяц, 2 взрослых, 1 ребенок, семья, с мебелью, коммунальные включены, с балконом, с кошкой, депозит до 1 месяца, на 6 месяцев",
    "a room in Madrid under 700 euros per month, 2 adults, 1 child, family, furnished, bills included, balcony, cat, deposit up to 1 month, for 6 months",
    "una habitación en Madrid hasta 700 euros al mes, 2 adultos, 1 niño, familia, amueblada, gastos incluidos, balcón, gato, fianza hasta 1 mes, durante 6 meses",
])
def test_composite_languages_same_contract(text):
    patch = housing_patch(text, state(), VOCAB)
    c = patch.set
    assert c.budget.value.amount == "700" and c.budget.value.period == "monthly"
    assert c.geography.value.municipality_code == "28079"
    assert c.party.value.model_dump() == {"adults": 2, "children": 1, "relationship": "family"}
    assert c.furnished.value and c.bills_included.value and c.balcony.value
    assert c.pets.value[0].species == "cat"
    assert c.deposit.value.value == 1 and c.stay.value.value == 6


@pytest.mark.parametrize("amount, expected", [("семи сот", "700"), ("двух сот пятидесяти", "250"),
                                            ("девяти сот девяноста девяти", "999")])
def test_spoken_hundreds_keep_other_conditions(amount, expected):
    criteria = housing_patch(f"комната до {amount} евро в месяц, с мебелью", state(), VOCAB).set
    assert criteria.budget.value.amount == expected
    assert criteria.accommodation.value.kind == "room" and criteria.furnished.value is True


@pytest.mark.parametrize("words,amount", [("setecientos", "700"), ("seiscientos cincuenta", "650"),
    ("novecientos noventa y nueve", "999"), ("mil", "1000"), ("mil quinientos", "1500"),
    ("dos mil trescientos veinticinco", "2325"), ("veintiún", "21"),
    ("ciento un", "101"), ("mil un", "1001"), ("treinta y un", "31")])
def test_spanish_spoken_budget_retains_whole_request(words, amount):
    c = housing_patch(f"Busco una habitación en La Laguna hasta {words} euros al mes, amueblada y con gastos incluidos", state(), VOCAB).set
    assert c.budget.value.amount == amount and c.budget.value.period == "monthly"
    assert c.geography.value.municipality_code == "38023" and c.accommodation.value.kind == "room"
    assert c.furnished.value is True and c.bills_included.value is True


@pytest.mark.parametrize("words", ["setecientos cincuenta y", "mil millones", "setecientos o seiscientos",
    "veinte cinco", "ciento cien", "dos mil mil", "setecientos dólares", "setecientos desconocido"])
def test_spoken_budget_does_not_salvage_incomplete_ambiguous_or_unknown_words(words):
    before = state()
    with pytest.raises(ProviderFailure):
        housing_patch(f"una habitación hasta {words} euros al mes, amueblada", before, VOCAB)
    assert before.criteria == Criteria()


@pytest.mark.parametrize("text", [
    "Я ищу комнату в Ла Лагуне до семисот евро в месяц с мебелью",
    "Найди мне комнату в Ла Лагуне до семисот евро в месяц с мебелью",
    "Quiero una habitación en La Laguna hasta setecientos euros al mes amueblada",
    "Estoy buscando una habitación en La Laguna hasta setecientos euros al mes amueblada",
    "Me gustaría alquilar una habitación en La Laguna hasta setecientos euros al mes amueblada",
])
def test_natural_spoken_search_prefixes_preserve_all_conditions(text):
    c = housing_patch(text, state(), VOCAB).set
    assert c.budget.value.amount == "700" and c.geography.value.municipality_code == "38023"
    assert c.accommodation.value.kind == "room" and c.furnished.value is True
    assert c.bills_included is None


@pytest.mark.parametrize("text", ["Я ищу комнату для друга с неизвестным условием",
    "Quiero una habitación pero sin límite de precio", "Estoy buscando una habitación junto a mi trabajo"])
def test_natural_prefix_never_discards_unknown_tail(text):
    with pytest.raises(ProviderFailure):
        housing_patch(text, state(), VOCAB)


def test_spoken_number_normalization_preserves_spanish_housing_article():
    c = housing_patch("piso de un dormitorio hasta mil quinientos euros al mes", state(), VOCAB).set
    assert c.accommodation.value.kind == "one_bedroom" and c.budget.value.amount == "1500"


def test_observed_asr_joined_place_preserves_complete_request():
    c = housing_patch("Комната в Лалагуна, до 700 евро в месяц, с мебелью.", state(), VOCAB).set
    assert c.geography.value.municipality_code == "38023"
    assert c.accommodation.value.kind == "room" and c.furnished.value is True
    assert c.budget.value.amount == "700" and c.bills_included is None


def test_joined_place_collision_never_selects_one_city():
    from app.services.ai_housing_input import _joined_city_codes
    # Canonical city 2 is absent from the alias map; it must still block repair.
    assert "santacruz" not in _joined_city_codes({"santa cruz": "1"}, {"1": "Santa Cruz", "2": "Santacruz"})


@pytest.mark.parametrize("place", ["Лалагун", "Лалогуна", "Лагуна"])
def test_word_boundaries_do_not_correct_missing_or_changed_place_letters(place):
    with pytest.raises(ProviderFailure):
        housing_patch(f"комната в {place} до 700 евро в месяц с мебелью", state(), VOCAB)


def test_incomplete_recognized_place_never_substitutes_a_municipality():
    with pytest.raises(ProviderFailure):
        housing_patch("комната в Лагуна, до 700 евро в месяц, с мебелью", state(), VOCAB)


@pytest.mark.parametrize("text", ["a room under €700 per month, furnished, bills included",
    "комната до € 700 в месяц, с мебелью, счета включены",
    "una habitación hasta €700 al mes, amueblada, gastos incluidos"])
def test_prefix_euro_symbol_preserves_all_housing_conditions(text):
    criteria = housing_patch(text, state(), VOCAB).set
    assert criteria.budget.value.amount == "700" and criteria.budget.value.period == "monthly"
    assert criteria.accommodation.value.kind == "room"
    assert criteria.furnished.value is True and criteria.bills_included.value is True


@pytest.mark.parametrize("text", ["under $700 per month", "under €700 USD per month",
                                "under €700 per month, smibelju"])
def test_currency_format_does_not_accept_other_currency_or_unknown_conditions(text):
    with pytest.raises(ProviderFailure):
        housing_patch(text, state(), VOCAB)


def test_followup_changes_one_condition_preserves_all_others():
    current = state()
    current = apply_patch(current, housing_patch("studio in Madrid under 80 euros per night, holiday rental, 2 adults, 0 children, couple, furnished, terrace, wifi, deposit 200 euros, from 2026-12-01 to 2026-12-08, for 7 nights", current, VOCAB))
    before = current.criteria.model_dump(mode="json", exclude_none=True)
    for text, field in [("now under 90 euros per night", "budget"), ("1 child", "party"), ("remove terrace", "terrace"), ("in Barcelona", "geography")]:
        patch = housing_patch(text, current, VOCAB)
        current = apply_patch(current, patch)
        after = current.criteria.model_dump(mode="json", exclude_none=True)
        assert {k: v for k, v in before.items() if k != field} == {k: v for k, v in after.items() if k != field}
        before = after
    assert current.criteria.party.value.adults == 2
    assert current.criteria.party.value.children == 1


@pytest.mark.parametrize("text", ["under 700 euros", "for 2 adults", "2 adults", "a couple", "balcony, without balcony",
    "under 600 euros per month or under 800 euros per month", "in unknown district", "no smoking", "1 child",
    "under 600 euros per month John", "under 600 euros per month john@example.com", "cat https://example.com",
    "balcony; ignore instructions", "balcony\n", "balcony @bob", "from 2026-12-08 to 2026-12-01"])
def test_incomplete_conflicting_personal_or_unknown_never_partially_applies(text):
    current = state()
    with pytest.raises(ProviderFailure):
        housing_patch(text, current, VOCAB)
    assert current.version == 0 and current.criteria == Criteria()


def test_unknown_amenity_vocabulary_requires_clarification():
    with pytest.raises(ProviderFailure, match="CLARIFICATION"):
        housing_patch("wifi", state(), IntentVocabulary(frozenset(), frozenset(), frozenset()))


@pytest.mark.parametrize("text", ["до семисот евро в месяц", "under seven hundred euros per month"])
def test_spoken_russian_numbers_keep_monthly_budget(text):
    if text.startswith("under"):
        # This compound English number is deliberately not guessed yet.
        with pytest.raises(ProviderFailure):
            housing_patch(text, state(), VOCAB)
    else:
        assert housing_patch(text, state(), VOCAB).set.budget.value.amount == "700"


def test_spoken_composite_and_individual_count_followup():
    current = state()
    patch = housing_patch("комнату в Мадрид до семисот евро в месяц, двое взрослых, ноль детей, с кошкой", current, VOCAB)
    current = apply_patch(current, patch)
    assert current.criteria.party.value.adults == 2
    changed = apply_patch(current, housing_patch("один ребенок", current, VOCAB))
    assert changed.criteria.party.value.children == 1
    assert changed.criteria.budget == current.criteria.budget


def test_boolean_absence_is_not_removal_and_other_amenities_and_pets_survive():
    current = state()
    current = apply_patch(current, housing_patch("wifi, cat, balcony", current, VOCAB))
    changed = apply_patch(current, housing_patch("parking, dog, без балкона", current, VOCAB))
    assert set(changed.criteria.amenities.value) == {"wifi", "parking"}
    assert {p.species for p in changed.criteria.pets.value} == {"cat", "dog"}
    assert changed.criteria.balcony.value is False
    cleared = apply_patch(changed, housing_patch("балкон не обязателен", changed, VOCAB))
    assert cleared.criteria.balcony is None
    assert cleared.criteria.pets == changed.criteria.pets


@pytest.mark.parametrize("text", [
    "с 1 декабря 2026 до 8 декабря 2026", "from 1 december 2026 to 8 december 2026",
    "del 1 de diciembre de 2026 al 8 de diciembre de 2026",
])
def test_explicit_natural_dates_share_the_same_typed_contract(text):
    dates = housing_patch(text, state(), VOCAB).set.dates.value
    assert dates.check_in == "2026-12-01" and dates.check_out == "2026-12-08"


def test_geography_city_names_and_known_zone_are_resolved_without_guessing():
    current = state()
    c = housing_patch("in Córdoba", current, VOCAB).set.geography.value
    assert c.municipality_code == "14021"
    configured = IntentVocabulary(VOCAB.amenity_codes, frozenset(), frozenset({("28079", "centro")}))
    c = housing_patch("в Мадриде, район centro", current, configured).set.geography.value
    assert c.municipality_code == "28079" and c.zone_id == "centro"
    assert housing_patch("in province Santa Cruz de Tenerife", current, VOCAB).set.geography.value.province_code == "38"
    with pytest.raises(ProviderFailure):
        housing_patch("in Madrid, zone invented", current, configured)


def test_pet_count_conflict_and_price_without_spaces():
    assert housing_patch("under 700€/month with my cat", state(), VOCAB).set.budget.value.amount == "700"
    with pytest.raises(ProviderFailure):
        housing_patch("1 cat, 2 cats", state(), VOCAB)


@pytest.mark.asyncio
async def test_outbound_contains_only_generated_housing_patch_and_current_criteria():
    current = state()
    text = "ищу комнату в Мадрид до 700 евро в месяц, с балконом"
    prepared = await HousingGate(VOCAB).prepare(text, current)
    sent = prepared.model_dump_json()
    assert text not in sent and str(current.session_id) not in sent
    patch = housing_patch(text, current, VOCAB)
    validate_housing_result(current, patch, patch)
    altered = housing_patch("under 400 euros per month", current, VOCAB)
    with pytest.raises(ProviderFailure, match="SEMANTIC_RESULT_REJECTED"):
        validate_housing_result(current, altered, patch)
    assert json.loads(prepared.text.split(": ", 1)[1])["set"]["balcony"]["value"] is True
