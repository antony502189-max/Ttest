"""Conservative public-source housing evidence; no legacy card defaults.

Only exact official city identities, explicit source route category and complete
standalone amenity/policy clauses become facts. Missing fields stay unknown.
"""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse

from ..schemas.ai_listing_facts import EvidenceSpan, digest
from ..spain_municipalities import MUNICIPALITIES, normalized_municipality, unique_municipality_aliases
from .ai_fact_bridge import PreparedFactInput, _observation
from .ai_listing_input import clean_evidence_text
from .ai_pisocompartido_price import prepare_price

VERSION = "pisocompartido-housing.v1"
ALIASES = {}
for _code in MUNICIPALITIES:
    for _alias in unique_municipality_aliases(_code):
        ALIASES[_alias] = _code

# Complete clauses only. No positive extraction from a negated or qualified
# sentence, no assumption that an absent amenity/policy means false.
CLAUSES = {
    "amueblado": ("furnished", True), "amueblada": ("furnished", True),
    "habitación amueblada": ("furnished", True), "habitacion amueblada": ("furnished", True),
    "sin amueblar": ("furnished", False), "gastos incluidos": ("bills_included", True),
    "gastos no incluidos": ("bills_included", False), "balcón": ("balcony", True),
    "balcon": ("balcony", True), "con balcón": ("balcony", True),
    "sin balcón": ("balcony", False), "terraza": ("terrace", True),
    "con terraza": ("terrace", True), "sin terraza": ("terrace", False),
}
POLICY = {"se admiten mascotas": ("pets", True), "no se admiten mascotas": ("pets", False),
          "mascotas permitidas": ("pets", True), "no mascotas": ("pets", False),
          "se admiten niños": ("children", True), "no se admiten niños": ("children", False),
          "se admiten parejas": ("couples", True), "no se admiten parejas": ("couples", False)}
POLICY.update({"no se aceptan mascotas": ("pets", False), "no se permiten parejas": ("couples", False)})
CLAUSES.update({"incluye gastos": ("bills_included", True), "balcón propio": ("balcony", True)})
AMENITIES = {"wifi": "wifi", "ascensor": "lift", "aire acondicionado": "air_conditioning", "parking": "parking"}


class HousingHTML(HTMLParser):
    """Read complete published detail list items, never filters/nav/related ads."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.clauses = [], set()

    def handle_starttag(self, tag, attrs):
        if tag not in {"br", "hr", "meta", "link", "img", "input", "wbr", "source"}:
            self.stack.append((tag, dict(attrs), []))

    def handle_data(self, data):
        for _, _, chunks in self.stack:
            chunks.append(data)

    def handle_endtag(self, tag):
        indices = [i for i, (t, _, _) in enumerate(self.stack) if t == tag]
        if not indices:
            return
        index = indices[-1]
        _, _, chunks = self.stack[index]
        classes = set().union(*(set(a.get("class", "").split()) for _, a, _ in self.stack))
        hidden = any(t in {"script", "style", "nav", "form", "template"} or "hidden" in a
                     or a.get("aria-hidden") == "true" or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", a.get("style", ""), re.IGNORECASE) for t, a, _ in self.stack)
        text = " ".join(" ".join(chunks).casefold().split())
        if (tag == "li" and "seccionesFichaAnuncio" in classes
                and classes & {"contCaract", "contTwocols"} and not hidden
                and not classes & {"disabled", "off", "inactive"}
                and (text in CLAUSES or text in POLICY or text in AMENITIES
                     or re.fullmatch(r"fianza: (?:0|[1-9][0-9]{0,5})(?:[.,][0-9]{1,2})? €", text))):
            self.clauses.add(text)
        self.stack = self.stack[:index]


def minimize_source(value, source_url):
    """Return only positive-recognition evidence, never full source prose."""
    if not isinstance(value, dict) or set(value) - {"city", "title", "description", "html"}:
        raise ValueError("HOUSING_SOURCE_FIELDS_INVALID")
    if any(v is not None and (not isinstance(v, str) or len(v) > (524288 if k == "html" else 32768)) for k, v in value.items()):
        raise ValueError("HOUSING_SOURCE_FIELDS_INVALID")
    result = {}
    city = normalized_municipality(value.get("city") or "").replace("_", " ")
    # Exact reviewed source-route alias, not removal of arbitrary suffixes.
    if city == "santa cruz de tenerife capital":
        city = "santa cruz de tenerife"
    if city in ALIASES:
        result["municipality"] = {"code": ALIASES[city], "quote": city}
    url = urlparse(source_url)
    if url.scheme == "https" and url.hostname in {"www.pisocompartido.com", "pisocompartido.com"} and re.fullmatch(r"/habitacion/[a-zA-Z0-9_-]+/?", url.path):
        result["category"] = {"kind": "room", "quote": "PisoCompartido /habitacion/ source route"}
    html = HousingHTML()
    html.feed(value.get("html") or "")
    html.close()
    clauses = set(html.clauses)
    # A following sentence can qualify the previous statement. Do not turn a
    # question, exception, quotation or approval condition into a guarantee.
    context = " ".join(clean_evidence_text(value.get(k) or "").casefold() for k in ("title", "description"))
    if re.search(r"[?¿\"“”]|\b(?:excepto|salvo|consultar|consulta|condicionado|condiciones|pero|aunque|quizás|quiza)\b|\bsi (?:el|la|se|lo)\b", context):
        if clauses:
            result["clauses"] = sorted(clauses)
        return result
    for key in ("title", "description"):
        text = clean_evidence_text(value.get(key) or "").casefold()
        for clause in re.split(r"[.!?;\n|•]+", text):
            clause = " ".join(clause.split()).strip()
            if clause in CLAUSES or clause in POLICY:
                clauses.add(clause)
    if clauses:
        result["clauses"] = sorted(clauses)
    return result


def prepare_housing(snapshot):
    base = prepare_price(snapshot)
    value = json.loads(snapshot.normalized_json).get("housing_evidence")
    if value is None:
        return base
    if not isinstance(value, dict) or set(value) - {"municipality", "category", "clauses"}:
        raise ValueError("HOUSING_EVIDENCE_INVALID")
    fields, facts = dict(base.sanitized_fields), list(base.facts)
    fields["metadata.housing_extractor"] = VERSION

    def add(key, typed, quote, qualifiers=None, policy=False):
        path = "housing." + key + "." + digest(quote)[:12]
        fields["structured." + path] = quote
        evidence = EvidenceSpan(field="structured", provider_field=path, quote=quote, start=0, end=len(quote))
        facts.append(_observation(snapshot.reference, key=key,
            status="explicit_deny" if policy and not typed["allowed"] else "explicit_allow",
            value=typed, qualifiers=qualifiers or {}, evidence=[evidence], origin="source_structured"))

    if "municipality" in value:
        city = value["municipality"]
        if set(city) != {"code", "quote"} or ALIASES.get(city["quote"]) != city["code"]:
            raise ValueError("HOUSING_CITY_EVIDENCE_INVALID")
        add("geography", {"kind": "geography", "province_code": city["code"][:2], "municipality_code": city["code"]}, city["quote"])
    if "category" in value:
        if value["category"] != {"kind": "room", "quote": "PisoCompartido /habitacion/ source route"}:
            raise ValueError("HOUSING_CATEGORY_EVIDENCE_INVALID")
        add("accommodation", {"kind": "category", "value": "room"}, value["category"]["quote"])
    for clause in value.get("clauses", []):
        if clause in CLAUSES:
            key, allowed = CLAUSES[clause]
            add(key, {"kind": "boolean", "value": allowed}, clause)
        elif clause in POLICY:
            key, allowed = POLICY[clause]
            add(key, {"kind": "policy", "allowed": allowed}, clause, policy=True)
        elif clause in AMENITIES:
            add("amenity", {"kind": "boolean", "value": True}, clause, {"amenity_code": AMENITIES[clause]})
        elif re.fullmatch(r"fianza: (?:0|[1-9][0-9]{0,5})(?:[.,][0-9]{1,2})? €", clause):
            add("deposit", {"kind": "money", "amount": clause.split()[1].replace(",", "."), "currency": "EUR", "period": "one_off"}, clause)
        else:
            raise ValueError("HOUSING_CLAUSE_EVIDENCE_INVALID")
    # The shared resolver receives contradictions as separate supported facts.
    # Merge same-key/scope evidence before constructing one batch identity.
    from .ai_fact_bridge import _merge
    facts = _merge(facts, snapshot.reference)
    source = base.source.model_copy(update={"content_hash": digest(fields), "extractor_version": VERSION})
    return PreparedFactInput(source, tuple(sorted(fields.items())), tuple(f.model_dump_json() for f in facts))
