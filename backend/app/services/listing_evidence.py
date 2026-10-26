"""Small, conservative policy grammar; not a general natural-language parser.

Only complete standalone clauses are recognized. Unhandled language stays in
the description for a future extractor; it never becomes a positive permission.
These internal evidence types are not a persistence or public API contract.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

POLICY_FIELDS = (
    "pets_allowed",
    "children_allowed",
    "smoking_allowed",
    "room_capacity",
    "couples_allowed",
    "students_only",
    "smoking_indoors_allowed",
    "smoking_outdoors_allowed",
)
EvidenceSource = Literal["title", "description", "structured"]
FactStatus = Literal["unknown", "explicit", "conditional", "conflict"]


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    source: EvidenceSource
    quote: str = Field(min_length=1, max_length=512)
    provider_field: str | None = Field(default=None, max_length=120)


class PolicyFact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    status: FactStatus = "unknown"
    value: StrictBool | StrictInt | None = None
    evidence: tuple[EvidenceSpan, ...] = ()

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.status == "unknown":
            if self.value is not None or self.evidence:
                raise ValueError("Unknown facts cannot carry a value or evidence")
        elif not self.evidence:
            raise ValueError("Known facts require evidence")
        if self.status == "explicit" and self.value is None:
            raise ValueError("Explicit facts require a value")
        if self.status in {"conditional", "conflict"} and self.value is not None:
            raise ValueError("Conditional/conflicting facts have no unconditional value")
        if type(self.value) is int and not 1 <= self.value <= 99:
            raise ValueError("Capacity outside supported evidence range")
        return self


def _fold(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", value.casefold()) if not unicodedata.combining(c))


# Deliberately bounded phrases. fullmatch avoids marketing/quotation prefixes,
# partial matches inside negations, and dropping trailing conditions.
_RULES = (
    ("pets_allowed", True, r"(?:se (?:admiten|aceptan) mascotas|mascotas permitidas|pets allowed)"),
    ("pets_allowed", False, r"(?:no se (?:admiten|aceptan) mascotas|no mascotas|mascotas no|no pets)"),
    ("children_allowed", True, r"(?:se (?:aceptan|admiten) ninos|ninos permitidos|children allowed)"),
    ("children_allowed", False, r"(?:no se (?:admiten|aceptan) ninos|sin ninos|no ninos|no children)"),
    ("couples_allowed", False, r"(?:no se (?:admiten|aceptan) parejas|no couples)"),
    ("couples_allowed", True, r"(?:se (?:admiten|aceptan) parejas|couples allowed)"),
    ("smoking_allowed", False, r"(?:no fumar|no fumadores|prohibido fumar|no smoking)"),
    ("smoking_allowed", True, r"(?:se permite fumar|fumadores permitidos|smoking allowed)"),
    ("students_only", True, r"(?:solo estudiantes|students only)"),
)
_CONDITIONAL = (
    # Species restrictions qualify the global pets policy in either order.
    # Keep arbitrary trailing scope as evidence rather than promising that all
    # animals are allowed (or all are forbidden).
    ("pets_allowed", (
        r"(?:(?:solo|solamente|unicamente|only|no|sin) (?:small )?"
        r"(?:mascotas|perros|gatos|dogs|cats|pets)\b.*|(?:dogs|cats) (?:are )?not allowed\b.*|mascotas a consultar)"
    )),
    ("children_allowed", r"ninos a consultar"),
    ("smoking_allowed", r"(?:no fumar (?:dentro del piso|en el piso)|se permite fumar (?:solo )?en la terraza)"),
)
_NUMBERS = {"una": 1, "un": 1, "one": 1, "dos": 2, "two": 2, "tres": 3, "cuatro": 4}


def extract_policy_evidence(*, title: str = "", description: str = "") -> dict[str, PolicyFact]:
    matches: dict[str, list[PolicyFact]] = {field: [] for field in POLICY_FIELDS}
    texts: tuple[tuple[EvidenceSource, str], ...] = (("title", title), ("description", description))
    previous_fields: tuple[str, ...] = ()
    pending_condition: EvidenceSpan | None = None
    for source, text in texts:
        for clause_match in re.finditer(r"([^.!?;\n]+)([.!?;\n]+|$)", text):
            clause, ending = clause_match.groups()
            quote = " ".join(clause.split()).strip()
            if not quote or len(quote) > 512 or "?" in ending or "¿" in quote:
                previous_fields = ()
                pending_condition = None
                continue
            folded = _fold(quote)
            span = EvidenceSpan(source=source, quote=quote)
            matched_fields: set[str] = set()

            def add(
                field: str,
                value: bool | int | None,
                *,
                conditional: bool = False,
                evidence: EvidenceSpan = span,
                fields: set[str] = matched_fields,
            ) -> None:
                fields.add(field)
                matches[field].append(
                    PolicyFact(
                        status="conditional" if conditional else "explicit",
                        value=value,
                        evidence=(evidence,),
                    )
                )

            for field, value, pattern in _RULES:
                if re.fullmatch(pattern, folded):
                    add(field, value)
            for field, pattern in _CONDITIONAL:
                if field not in matched_fields and re.fullmatch(pattern, folded):
                    add(field, None, conditional=True)
            if re.fullmatch(r"no fumar (?:dentro del piso|en el piso)", folded):
                add("smoking_indoors_allowed", False)
            if re.fullmatch(r"se permite fumar (?:solo )?en la terraza", folded):
                add("smoking_outdoors_allowed", True)
            capacity = re.fullmatch(
                r"(?:habitacion para|para|hasta|maximo) (\d{1,2}|una|un|dos|tres|cuatro) personas?",
                folded,
            )
            if capacity:
                token = capacity.group(1)
                number = int(token) if token.isdigit() else _NUMBERS[token]
                if 1 <= number <= 99:
                    add("room_capacity", number)
            # An adjacent condition can qualify a permission OR a denial, before
            # or after it. Independent recognized rules keep their own meaning;
            # unrelated clauses/questions clear this short-range context.
            is_condition = not matched_fields and re.match(
                r"(?:solo|solamente|unicamente|only|except|excepto|salvo|a consultar|"
                r"con autorizacion|previa autorizacion|sujeto a|subject to|with prior approval)\b", folded,
            )
            if is_condition:
                for field in previous_fields:
                    add(field, None, conditional=True)
                if not previous_fields:
                    pending_condition = span
            elif matched_fields:
                if pending_condition is not None:
                    for field in tuple(matched_fields):
                        add(field, None, conditional=True, evidence=pending_condition)
                pending_condition = None
            else:
                pending_condition = None
            previous_fields = tuple(matched_fields)
    result = {}
    for field, facts in matches.items():
        if not facts:
            result[field] = PolicyFact()
            continue
        values = {(type(fact.value), fact.value) for fact in facts if fact.status == "explicit"}
        status: FactStatus = (
            "conflict"
            if len(values) > 1
            else ("conditional" if any(fact.status == "conditional" for fact in facts) else "explicit")
        )
        result[field] = PolicyFact(
            status=status,
            value=facts[0].value if status == "explicit" else None,
            evidence=tuple(span for fact in facts for span in fact.evidence),
        )
    return result
