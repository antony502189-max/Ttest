"""Whole-request housing minimization into the existing typed intent contract.

Only generated schema values leave the process. Unconsumed words, ambiguous
alternatives and contradictory clauses reject the entire request before IO.
This is a conservative language boundary, not clearance for arbitrary user text.
"""
import json
import re
from decimal import Decimal

from ..schemas.ai_search_intent import IntentPatch, apply_patch
from ..spain_municipalities import MUNICIPALITIES, normalized_municipality, unique_municipality_aliases
from ..spain_provinces import PROVINCE_CODES
from .ai_deepseek_intent import OutboundIntentInput, ProviderFailure, _criteria_state
from .ai_housing_numbers import AMOUNTS


def clarification():
    raise ProviderFailure("INTENT_CLARIFICATION_REQUIRED")


def _fold(value):
    return value.casefold().replace("ё", "е").strip()


CITY_CODES = {}
for _code in MUNICIPALITIES:
    for _alias in unique_municipality_aliases(_code):
        CITY_CODES[_alias] = _code
    if normalized_municipality(MUNICIPALITIES[_code]) in unique_municipality_aliases(_code):
        CITY_CODES[_fold(MUNICIPALITIES[_code])] = _code
CITY_CODES.update({"мадрид": "28079", "барселона": "08019", "валенсия": "46250",
                   "мадриде": "28079", "барселоне": "08019", "валенсии": "46250",
                   "санта крус де тенерифе": "38038", "санта-крус-де-тенерифе": "38038",
                   "ла лагуна": "38023", "ла-лагуна": "38023"})
CITY_PATTERN = "|".join(re.escape(v) for v in sorted(CITY_CODES, key=len, reverse=True))
PROVINCES = {v.casefold(): k for k, v in PROVINCE_CODES.items()} | {normalized_municipality(v): k for k, v in PROVINCE_CODES.items()}
PROVINCE_PATTERN = "|".join(re.escape(v) for v in sorted(PROVINCES, key=len, reverse=True))
MONTHS = {}
for _names in ("january february march april may june july august september october november december",
               "января февраля марта апреля мая июня июля августа сентября октября ноября декабря",
               "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre"):
    MONTHS.update({v: i for i, v in enumerate(_names.split(), 1)})
MONTH_PATTERN = "(?:" + "|".join(MONTHS) + ")"

BOOL_WORDS = {
    "furnished": ("furnished", "amueblado", "amueblada", "с мебелью", "меблированная", "меблированную", "мебели"),
    "bills_included": ("bills included", "gastos incluidos", "коммунальные включены", "с коммунальными", "коммунальные платежи включены"),
    "balcony": ("balcony", "balcon", "balcón", "балкон", "балконом", "балкона"),
    "terrace": ("terrace", "terraza", "терраса", "террасой", "террасу", "террасы"),
}
ACCOMMODATION = {
    "room": ("a room", "room", "rooms", "una habitación", "una habitacion", "habitación", "habitacion", "habitaciones", "комната", "комнату"),
    "shared_room": ("shared room", "habitación compartida", "общая комната", "место в комнате"),
    "studio": ("a studio", "studio", "estudio", "студия", "студию"),
    "one_bedroom": ("1 bedroom apartment", "one-bedroom apartment", "piso de un dormitorio", "квартира с 1 спальней", "квартиру с 1 спальней"),
}
PERIODS = {"monthly": ("per month", "/month", "al mes", "/mes", "в месяц", "/мес"),
           "nightly": ("per night", "/night", "por noche", "за ночь", "в сутки", "за сутки"),
           "weekly": ("per week", "/week", "por semana", "за неделю", "в неделю")}
NUMBERS = AMOUNTS | {word: i for i, word in enumerate(["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"])}
NUMBERS.update({word: i for i, word in enumerate(["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez"])})
NUMBERS.update({"ноль": 0, "двое": 2, "два": 2, "две": 2, "одна": 1, "одной": 1, "одним": 1})
NUMBER_PATTERN = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(v) for v in sorted(NUMBERS, key=len, reverse=True)) + r")(?![\w-])")
AMENITIES = {"wifi": ("wifi", "wi-fi", "вайфай"), "internet": ("internet", "интернет", "интернетом"),
             "parking": ("parking", "aparcamiento", "парковка", "парковкой"),
             "lift": ("lift", "elevator", "ascensor", "лифт", "лифтом"),
             "air_conditioning": ("air conditioning", "aire acondicionado", "кондиционер", "кондиционером")}
REMOVALS = {"budget": ("budget", "presupuesto", "бюджет", "ограничение бюджета", "ограничения бюджета"),
            "geography": ("location", "ubicación", "место", "местоположение"),
            "party": ("party", "жильцов", "состав жильцов"),
            "pets": ("pets", "mascotas", "животных"),
            "smoking": ("smoking", "курение"),
            "deposit": ("deposit", "fianza", "депозит"),
            "dates": ("dates", "fechas", "даты"), "stay": ("stay", "срок"),
            "accommodation": ("housing type", "тип жилья"),
            **{k: v for k, v in BOOL_WORDS.items()}, "amenities": ("amenities", "удобства")}


def _alternatives(words):
    return "(?:" + "|".join(re.escape(v) for v in sorted(words, key=len, reverse=True)) + ")"


def housing_patch(text, current, vocabulary):
    """Parse all clauses atomically; unrelated committed criteria survive patching."""
    if (type(text) is not str or not 1 <= len(text) <= 2000
            or any(ord(c) < 32 for c in text)):
        raise ProviderFailure("INTENT_UNSUPPORTED")
    remaining = _fold(text).rstrip(".!?").strip()
    remaining = NUMBER_PATTERN.sub(lambda m: str(NUMBERS[m[0]]), remaining)
    # Reject alternatives rather than choosing one side or weakening a hard rule.
    if re.search(r"\b(?:or|или|либо|o)\b", remaining):
        clarification()
    remaining = re.sub(r"^(?:(?:find|show|busco|ищу|нужна|нужен|нужно|покажи|теперь|now|ahora)\s+)+", "", remaining)
    changes, removed, amenity_values = {}, set(), []
    strength = "hard"
    party_counts = {}
    relationship = None
    party_strength = None
    amenity_strength = None
    named_pets = {}

    def put(name, value):
        criterion = {"strength": strength, "value": value}
        if name in removed or (name in changes and changes[name] != criterion):
            clarification()
        changes[name] = criterion

    def take(pattern):
        return re.match("(?:" + pattern + r")(?=$|[\s,;.!])", remaining)

    iterations = 0
    while remaining:
        iterations += 1
        if iterations > 60:
            clarification()
        delimiter = re.match(r"^(?:\s*[,;.]\s*(?:(?:and|и|y)\s+)?|\s+(?:(?:and|и|y)\s+)?)", remaining)
        if delimiter:
            remaining = remaining[delimiter.end():]
            if not remaining:
                break
        preference = take(r"preferably|preferiblemente|желательно")
        if preference:
            strength = "soft"
            remaining = remaining[preference.end():].lstrip()
            continue
        matched = None
        for name, words in REMOVALS.items():
            verbs = r"(?:remove(?: the)?|quita|убери|без)" if name in {"budget", "pets"} else r"(?:remove(?: the)?|quita|убери)"
            matched = take(verbs + " " + _alternatives(words) + r"(?: limit)?")
            if not matched:
                matched = take(_alternatives(words) + r" (?:is not necessary|не обязателен|не обязательна|не нужен|не нужна)")
            if matched:
                if name in changes:
                    clarification()
                removed.add(name)
                break
        if matched:
            pass
        else:
            for mode, words in {"long": ("long term", "long-term", "larga temporada", "долгосрочно", "долгосрочная аренда"),
                                "holiday": ("holiday rental", "vacation rental", "alquiler vacacional", "посуточно", "краткосрочная аренда")}.items():
                matched = take(_alternatives(words))
                if matched:
                    put("rental_mode", mode)
                    break
        if not matched:
            for kind, words in sorted(ACCOMMODATION.items(), key=lambda item: -max(map(len, item[1]))):
                matched = take(_alternatives(words))
                if matched:
                    put("accommodation", {"kind": kind})
                    break
        if not matched:
            # Period must be explicit. No monthly/nightly conversion or mode inference.
            for period, words in PERIODS.items():
                matched = take(r"(?:under|up to|budget up to|hasta|menos de|до|бюджет до|не дороже) ([1-9][0-9]{0,5}(?:[.,][0-9]{1,2})?)(?: ?(?:euros?|eur|евро|€))?\s*" + _alternatives(words))
                if matched:
                    put("budget", {"amount": matched[1].replace(",", "."), "currency": "EUR", "period": period})
                    break
        if not matched:
            matched = take(r"(?:(?:in|en|в) )?(?:province|provincia de|провинция|провинции) (" + PROVINCE_PATTERN + r")")
            if matched:
                put("geography", {"province_code": PROVINCES[matched[1]]})
        if not matched:
            matched = take(r"(?:in|en|в) (?:(?:городе|город) )?(" + CITY_PATTERN + r")")
            if matched:
                code = CITY_CODES[matched[1]]
                put("geography", {"province_code": code[:2], "municipality_code": code})
        if not matched:
            matched = take(r"(?:zone|district|район|районе|zona) ([a-z0-9][a-z0-9_-]*)")
            if matched:
                geography = changes.get("geography", {}).get("value") or (current.criteria.geography.value.model_dump(exclude_none=True) if current.criteria.geography else {})
                if (geography.get("municipality_code"), matched[1]) not in vocabulary.zones:
                    clarification()
                geography = geography | {"zone_id": matched[1]}
                # Zone refines the explicitly selected or retained municipality.
                changes["geography"] = {"strength": strength, "value": geography}
        if not matched:
            matched = take(r"(?:for |para |для )?([1-9]|10) (adults?|adultos?|взрослых|взрослые|взрослый|взрослого)")
            if matched:
                if "adults" in party_counts and party_counts["adults"] != int(matched[1]):
                    clarification()
                party_counts["adults"] = int(matched[1])
                if party_strength and party_strength != strength:
                    clarification()
                party_strength = strength
        if not matched:
            matched = take(r"(0|[1-9]|10) (children|child|niños?|ninos?|детей|ребенок|ребенка)")
            if matched:
                if "children" in party_counts and party_counts["children"] != int(matched[1]):
                    clarification()
                party_counts["children"] = int(matched[1])
                if party_strength and party_strength != strength:
                    clarification()
                party_strength = strength
        if not matched:
            for rel, words in {"couple": ("a couple", "couple", "pareja", "пара", "пары"),
                               "family": ("family", "familia", "семья", "семьи"),
                               "friends": ("friends", "amigos", "друзья", "друзей")}.items():
                matched = take(_alternatives(words))
                if matched:
                    if relationship and relationship != rel:
                        clarification()
                    relationship = rel
                    if party_strength and party_strength != strength:
                        clarification()
                    party_strength = strength
                    break
        if not matched:
            for name, words in BOOL_WORDS.items():
                negative = take(r"(?:without|sin|без) " + _alternatives(words))
                positive = take(r"(?:(?:with|con|с) )?" + _alternatives(words))
                matched = negative or positive
                if matched:
                    put(name, not bool(negative))
                    break
        if not matched:
            for code, words in AMENITIES.items():
                matched = take(r"(?:(?:with|con|с) )?" + _alternatives(words))
                if matched:
                    if code not in vocabulary.amenity_codes:
                        clarification()
                    amenity_values.append(code)
                    if amenity_strength and amenity_strength != strength:
                        clarification()
                    amenity_strength = strength
                    break
        if not matched:
            matched = take(r"(?:deposit|fianza|депозит) (?:up to |hasta |до )?(0|[1-9][0-9]{0,5}(?:[.,][0-9]{1,2})?) (eur|euros|евро|€|months?|mes|meses|месяц|месяца|месяцев)")
            if matched:
                amount, unit = matched[1].replace(",", "."), matched[2]
                if unit in {"eur", "euros", "евро", "€"}:
                    put("deposit", {"kind": "money", "amount": amount, "currency": "EUR", "period": "one_off"})
                elif Decimal(amount) == int(Decimal(amount)):
                    put("deposit", {"kind": "quantity", "value": int(Decimal(amount)), "unit": "months"})
                else:
                    clarification()
        if not matched:
            date_part = r"([0-9]{1,2}) (?:de )?(" + MONTH_PATTERN + r") (?:de )?([0-9]{4})"
            matched = take(r"(?:from|с|del) " + date_part + r" (?:to|до|по|al) " + date_part)
            if matched:
                put("dates", {"check_in": f"{matched[3]}-{MONTHS[matched[2]]:02d}-{int(matched[1]):02d}",
                              "check_out": f"{matched[6]}-{MONTHS[matched[5]]:02d}-{int(matched[4]):02d}"})
        if not matched:
            matched = take(r"(?:from |с |del )?(\d{4}-\d{2}-\d{2}) (?:to|до|al) (\d{4}-\d{2}-\d{2})")
            if matched:
                put("dates", {"check_in": matched[1], "check_out": matched[2]})
        if not matched:
            matched = take(r"(?:for|на|durante) ([1-9][0-9]{0,3}) (nights?|noches|ночей|ночи|months?|mes|meses|месяц|месяца|месяцев)")
            if matched:
                put("stay", {"value": int(matched[1]), "unit": "nights" if matched[2] in {"night", "nights", "noches", "ночей", "ночи"} else "months"})
        if not matched:
            for species, words in {"dog": ("dog", "dogs", "perro", "perros", "собакой", "собака", "собаки"),
                                   "cat": ("cat", "cats", "gato", "gatos", "котом", "кошкой", "кошка", "кошки")}.items():
                matched = take(r"(?:(?:with|con|с) )?(?:(?:a|my|mi|un|una|моей|моим) )?(?:(1|[2-9]|10) )?(?:(small|medium|large|маленькой|средней|большой) )?" + _alternatives(words))
                if matched:
                    size = {"маленькой": "small", "средней": "medium", "большой": "large"}.get(matched[2], matched[2]) or "unspecified"
                    pet = {"species": species, "size": size, "count": int(matched[1] or 1)}
                    if (species, size) in named_pets and named_pets[species, size] != pet:
                        clarification()
                    named_pets[species, size] = pet
                    previous = changes.get("pets", {}).get("value", [p.model_dump() for p in current.criteria.pets.value] if current.criteria.pets else [])
                    if "pets" in removed:
                        clarification()
                    # A new species does not erase an existing other pet. A
                    # named species/size updates its own count only.
                    previous = [p for p in previous if (p["species"], p["size"]) != (species, size)]
                    changes["pets"] = {"strength": strength, "value": [*previous, pet]}
                    break
        if not matched:
            for scope, words in {"indoors": ("smoking indoors", "fumar dentro", "курение в помещении"),
                                 "outdoors": ("smoking outdoors", "fumar fuera", "курение на улице"),
                                 "balcony": ("smoking on balcony", "курение на балконе"),
                                 "terrace": ("smoking on terrace", "курение на террасе")}.items():
                matched = take(_alternatives(words))
                if matched:
                    put("smoking", {"scope": scope})
                    break
        if not matched:
            clarification()
        remaining = remaining[matched.end():]
        strength = "hard"
    if party_counts or relationship:
        previous = current.criteria.party.value.model_dump() if current.criteria.party else {}
        # A follow-up may change adults/children/relationship individually.
        # A new party must specify both counts (including explicit zero children).
        party = previous | party_counts
        if not {"adults", "children"} <= party.keys():
            clarification()
        party["relationship"] = relationship or previous.get("relationship", "unspecified")
        strength = party_strength or "hard"
        put("party", party)
    if amenity_values:
        strength = amenity_strength or "hard"
        previous = current.criteria.amenities.value if current.criteria.amenities else ()
        put("amenities", sorted(set(amenity_values) | set(previous)))
    try:
        patch = IntentPatch.model_validate_json(json.dumps({"schema_version": "ai-search.v1",
            "session_id": str(current.session_id), "expected_version": current.version,
            "set": changes, "remove": sorted(removed)}))
        candidate = apply_patch(current, patch)
        vocabulary.validate(candidate.criteria)
    except (ValueError, TypeError):
        clarification()
    if _criteria_state(candidate.criteria) == _criteria_state(current.criteria):
        raise ProviderFailure("INTENT_NO_CHANGE")
    return patch


def canonical_patch(patch):
    return json.dumps(patch.model_dump(mode="json", include={"set", "remove"}, exclude_none=True),
                      sort_keys=True, ensure_ascii=True, separators=(",", ":"))


class HousingGate:
    def __init__(self, vocabulary):
        self.vocabulary = vocabulary

    async def prepare(self, text, current):
        patch = housing_patch(text, current, self.vocabulary)
        # Explicit schema-generated conditions only; no raw request/history,
        # identity, address, listing, source data or user-selected catalog code.
        return OutboundIntentInput(schema_version="ai-intent-input.v1", provider="deepseek",
            purpose="intent_patch", text="Apply this rental criteria patch: " + canonical_patch(patch),
            criteria=current.criteria)


def validate_housing_result(current, actual, expected):
    if (_criteria_state(apply_patch(current, actual).criteria)
            != _criteria_state(apply_patch(current, expected).criteria)):
        raise ProviderFailure("PILOT_SEMANTIC_RESULT_REJECTED")
