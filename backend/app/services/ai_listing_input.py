"""Offline evidence packet preparation. No provider, queue, DB or public API.

The caller must supply listing text, never a complete provider page. The cleaner
is a minimization boundary, not a claim to recognize every person's name.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from html.parser import HTMLParser
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from ..schemas.ai_evidence_support import SUPPORTED_PROVIDER_FIELDS, has_evidence_text
from .listing_evidence import EvidenceSpan, PolicyFact, extract_policy_evidence


class _ListingText(HTMLParser):
    HIDDEN_TAGS = frozenset({"script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hidden: list[str] = []
        self.invalid_hidden = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.HIDDEN_TAGS:
            self.hidden.append(tag)
        elif not self.hidden and not self.invalid_hidden and tag in {"p", "div", "br", "li", "section"}:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        # In HTML, '/>' does not close a non-void nav/form/etc. Treat ambiguous
        # hidden self-closing markup as an opening, not permission to export.
        if tag in self.HIDDEN_TAGS:
            self.handle_starttag(tag, attrs)
        else:
            super().handle_startendtag(tag, attrs)

    def handle_endtag(self, tag):
        if self.hidden and tag in self.HIDDEN_TAGS:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            else:
                # Do not recover a malformed hidden boundary by exposing its
                # remaining text, even if later tags happen to balance.
                self.invalid_hidden = True
        elif not self.hidden and not self.invalid_hidden and tag in {"p", "div", "li", "section"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden and not self.invalid_hidden:
            self.parts.append(data)


def clean_evidence_text(value: str, *, advertiser_name: str | None = None) -> str:
    parser = _ListingText()
    parser.feed(html.unescape(value))
    parser.close()
    text = "".join(parser.parts)
    # Deliberately remove all hyperlinks, handles and likely phone numbers,
    # including contacts without labels. Keep negation/conditional text.
    text = re.sub(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", "[contact]", text)
    def redact_link(match: re.Match[str]) -> str:
        # URL matches also consume prose punctuation. Preserve the delimiter so
        # a following denial still forms its own clause after redaction.
        value = match.group(0)
        suffix = value[len(value.rstrip(".!?;")):]
        return "[link]" + suffix

    text = re.sub(r"(?i)(?:https?://|www\.)[^\s<>]+", redact_link, text)
    text = re.sub(r"(?<!\w)@[\w.-]+", "[contact]", text)
    text = re.sub(r"(?<!\w)\+?\d(?:[\s().-]*\d){6,14}(?!\w)", "[contact]", text)
    text = re.sub(
        r"(?i)\b(?:cookie|token|authorization|api[_-]?key)\s*[:=]\s*[^\s;]+",
        "[secret]",
        text,
    )
    text = re.sub(
        r"(?im)^\s*(?:contacto|contact|anunciante|advertiser|nombre)\s*:[^.\n]*(?:\.|$)",
        "[contact].",
        text,
    )
    if advertiser_name and advertiser_name.strip():
        text = re.sub(re.escape(advertiser_name.strip()), "[advertiser]", text, flags=re.IGNORECASE)
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip()).strip()


class ProviderFact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    field: Literal[
        "pets_allowed",
        "children_allowed",
        "smoking_allowed",
        "room_capacity",
        "couples_allowed",
        "furnished",
        "bills_included",
        "empadronamiento_allowed",
        "amenities",
    ]
    value: StrictBool | StrictInt | tuple[str, ...]
    evidence: EvidenceSpan

    @model_validator(mode="after")
    def validate_fact(self):
        if self.evidence.source != "structured" or not self.evidence.provider_field:
            raise ValueError("Provider facts require a named structured provider field")
        if self.field == "room_capacity":
            if type(self.value) is not int or not 1 <= self.value <= 99:
                raise ValueError("Capacity must be an integer from 1 to 99")
        elif self.field == "amenities":
            allowed = {"wifi", "internet", "balcony", "terrace", "parking", "lift", "air_conditioning"}
            if not isinstance(self.value, tuple) or not self.value or not set(self.value) <= allowed:
                raise ValueError("Unsupported structured amenity")
        elif type(self.value) is not bool:
            raise ValueError("Policy values must be booleans")
        return self


class ListingEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    schema_version: Literal["listing-evidence-v1"] = "listing-evidence-v1"
    source_identifier: str = Field(min_length=1, max_length=120)
    canonical_listing_identifier: UUID
    title: str = Field(max_length=500)
    description: str = Field(max_length=30_000)
    property_category: Literal["room", "studio", "one_bedroom", "unknown"]
    rental_category: Literal["long", "holiday"]
    source_language: Literal["es", "en", "ru", "mixed"] | None = None
    provider_facts: tuple[ProviderFact, ...] = ()
    policy_evidence: dict[str, PolicyFact]
    data_status: Literal["ready", "insufficient_source_data"]
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    def deterministic_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def build_listing_evidence_input(
    *,
    source_identifier: str,
    canonical_listing_identifier: UUID,
    title: str,
    description: str,
    property_category: Literal["room", "studio", "one_bedroom", "unknown"],
    rental_category: Literal["long", "holiday"],
    provider_facts: tuple[ProviderFact, ...] = (),
    source_language: Literal["es", "en", "ru", "mixed"] | None = None,
    advertiser_name: str | None = None,
) -> ListingEvidenceInput:
    """Build from explicitly selected listing fields; never pass raw_payload.

    IDs route the eventual result but do not affect content_hash. A future
    reconciler computes this after import commit from the durable snapshot;
    a queue should key source record + hash + extractor/schema version.
    """
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}(?::[A-Za-z0-9_-]{1,55})?", source_identifier):
        raise ValueError("Source identifier must be an opaque provider/record key")
    title = clean_evidence_text(title, advertiser_name=advertiser_name)
    description = clean_evidence_text(description, advertiser_name=advertiser_name)
    sanitized_facts = []
    for fact in provider_facts:
        # This accepts validated typed facts only, never a provider dictionary.
        fact = ProviderFact.model_validate(fact)
        evidence = EvidenceSpan(
            source="structured",
            provider_field=fact.evidence.provider_field,
            quote=clean_evidence_text(fact.evidence.quote, advertiser_name=advertiser_name),
        )
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.\[\]-]{0,119}", evidence.provider_field or ""):
            raise ValueError("Invalid provider field path")
        value = tuple(sorted(set(fact.value))) if isinstance(fact.value, tuple) else fact.value
        sanitized_facts.append(ProviderFact(field=fact.field, value=value, evidence=evidence))
    facts = tuple(sorted({fact.model_dump_json() for fact in sanitized_facts}))
    ordered = tuple(ProviderFact.model_validate_json(fact) for fact in facts)
    policies = extract_policy_evidence(title=title, description=description)
    content = {
        "schema_version": "listing-evidence-v1",
        "title": title,
        "description": description,
        "property_category": property_category,
        "rental_category": rental_category,
        "source_language": source_language,
        "provider_facts": [fact.model_dump(mode="json") for fact in ordered],
    }
    digest = hashlib.sha256(
        json.dumps(
            content,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return ListingEvidenceInput(
        source_identifier=source_identifier,
        canonical_listing_identifier=canonical_listing_identifier,
        title=title,
        description=description,
        property_category=property_category,
        rental_category=rental_category,
        source_language=source_language,
        provider_facts=ordered,
        policy_evidence=policies,
        data_status="ready" if has_evidence_text(description) or any(
            f.field in SUPPORTED_PROVIDER_FIELDS and has_evidence_text(f.evidence.quote) for f in ordered
        ) else "insufficient_source_data",
        content_hash=digest,
    )
