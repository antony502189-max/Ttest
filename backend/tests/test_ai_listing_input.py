from uuid import UUID

import pytest
from pydantic import ValidationError

from app.services.ai_listing_input import ProviderFact, build_listing_evidence_input, clean_evidence_text
from app.services.listing_evidence import EvidenceSpan


def packet(**overrides):
    args = {
        "source_identifier": "Flatio:123",
        "canonical_listing_identifier": UUID(int=1),
        "title": "Habitación",
        "description": "No se admiten mascotas. Solo estudiantes.",
        "property_category": "room",
        "rental_category": "long",
    }
    return build_listing_evidence_input(**(args | overrides))


def test_input_cleans_contacts_scripts_and_chrome_preserving_conditions():
    value = packet(
        description=(
            "<nav>Se admiten mascotas</nav><script>cookie=secret</script>"
            "<p>No se admiten mascotas. Solo mascotas pequeñas.</p>"
            "<p>Se permite fumar en la terraza</p><p>Contacto: María Pérez</p>"
            "<p>María Pérez +34 612 345 678 maria@example.test https://example.test/contact?token=secret</p>"
        ),
        advertiser_name="María Pérez",
    )
    serialized = value.deterministic_json()
    for private in ("secret", "María", "612", "maria@", "https://", "<script", "cookie"):
        assert private not in serialized
    assert "No se admiten mascotas" in value.description
    assert "Solo mascotas pequeñas" in value.description
    assert value.policy_evidence["pets_allowed"].status == "conditional"
    assert value.policy_evidence["smoking_allowed"].status == "conditional"


def test_hash_ignores_contact_and_routing_changes_but_not_policy_change():
    first = packet(description="No pets. +34 612 345 678 first@example.test")
    second = packet(
        description="No pets. +34 699 111 222 second@example.test",
        canonical_listing_identifier=UUID(int=2),
        source_identifier="Flatio:456",
    )
    assert first.content_hash == second.content_hash
    assert first.content_hash != packet(description="Pets allowed.").content_hash
    assert packet().deterministic_json() == packet().deterministic_json()


def test_contact_sentence_does_not_remove_following_denial_on_same_line():
    value = packet(description="Contacto: María Pérez. No se admiten mascotas.", advertiser_name="María Pérez")
    assert "María" not in value.description
    assert value.policy_evidence["pets_allowed"].value is False


def test_provider_facts_are_typed_evidenced_and_deterministic():
    def fact(field, value):
        return ProviderFact(
            field=field,
            value=value,
            evidence=EvidenceSpan(
                source="structured",
                provider_field="listing." + field,
                quote=str(value),
            ),
        )

    a, b = fact("pets_allowed", False), fact("room_capacity", 4)
    assert packet(provider_facts=(a, b)).content_hash == packet(provider_facts=(b, a, a)).content_hash
    assert packet(provider_facts=(a,)).content_hash != packet(provider_facts=(b,)).content_hash
    with pytest.raises(ValidationError):
        fact("pets_allowed", 1)
    with pytest.raises(ValidationError):
        fact("room_capacity", True)
    with pytest.raises(ValidationError):
        fact("room_capacity", 0)
    with pytest.raises(ValidationError):
        fact("phone", "12345")


def test_empty_description_and_unreliable_language_stay_explicitly_unknown():
    value = packet(description="<script>tracking</script>")
    assert value.data_status == "insufficient_source_data"
    assert value.source_language is None
    assert value.policy_evidence["pets_allowed"].status == "unknown"
    assert packet(description="+34 612 345 678 owner@example.test").data_status == "insufficient_source_data"


@pytest.mark.parametrize("field,value,quote,status", [
    ("pets_allowed", False, "false", "ready"),
    ("room_capacity", 2, "2", "ready"),
    ("furnished", False, "false", "ready"),
    ("empadronamiento_allowed", True, "true", "insufficient_source_data"),
    ("pets_allowed", True, "owner@example.test", "insufficient_source_data"),
])
def test_typed_structured_evidence_can_replace_missing_description(field, value, quote, status):
    fact = ProviderFact(field=field, value=value, evidence=EvidenceSpan(
        source="structured", provider_field="rules.value", quote=quote))
    result = packet(description="", provider_facts=(fact,))
    assert result.data_status == status
    assert result.policy_evidence["pets_allowed"].status == "unknown"


def test_input_rejects_oversize_text_and_untyped_provider_payloads():
    with pytest.raises(ValidationError):
        packet(description="a" * 30_001)
    with pytest.raises(ValueError):
        packet(source_identifier="owner@example.test")
    with pytest.raises(ValidationError):
        packet(provider_facts=({"raw_html": "private"},))


def test_photos_and_raw_payload_are_outside_the_input_contract():
    with pytest.raises(TypeError):
        packet(photos=["https://example.test/image.jpg"])
    with pytest.raises(TypeError):
        packet(raw_payload={"cookie": "secret"})


@pytest.mark.parametrize("delimiter", [".", ";", "!", "\n"])
def test_link_redaction_preserves_following_conflicting_denial(delimiter):
    description = f"Pets allowed. https://example.test/x{delimiter} No pets."
    value = packet(description=description)
    fact = value.policy_evidence["pets_allowed"]
    assert fact.status == "conflict" and fact.value is None
    assert "No pets" in [span.quote for span in fact.evidence]
    assert "https://" not in value.deterministic_json()
    assert clean_evidence_text(value.description) == value.description


@pytest.mark.parametrize("text", ["Pets allowed? No.", "Pets allowed. Only with prior approval."])
def test_packet_does_not_promote_questions_or_conditions(text):
    fact = packet(description=text).policy_evidence["pets_allowed"]
    assert fact.status in {"unknown", "conditional"} and fact.value is None


@pytest.mark.parametrize(
    "text,field",
    [
        ("No pets. Except small dogs.", "pets_allowed"),
        ("No smoking. Except on the terrace.", "smoking_allowed"),
        ("Se admiten mascotas. No perros.", "pets_allowed"),
        ("Pets allowed. No dogs.", "pets_allowed"),
        ("Solo gatos. Se admiten mascotas.", "pets_allowed"),
    ],
)
def test_packet_retains_exception_and_species_scope(text, field):
    value = packet(description=text)
    fact = value.policy_evidence[field]
    assert fact.status == "conditional" and fact.value is None
    assert len(fact.evidence) == 2


@pytest.mark.parametrize("tag", ["nav", "footer", "header", "aside", "form", "noscript"])
def test_nested_hidden_tags_keep_outer_content_hidden(tag):
    value = f"<{tag}><{tag}>inner</{tag}>DO_NOT_EXPORT</{tag}><p>No pets.</p>"
    assert clean_evidence_text(value) == "No pets."
    result = packet(description=value)
    assert "DO_NOT_EXPORT" not in result.deterministic_json()
    assert result.policy_evidence["pets_allowed"].value is False


def test_different_nested_hidden_tags_close_in_stack_order():
    value = "<header><nav>inner</nav>private A<footer>private B</footer>private C</header><p>Room text</p>"
    assert clean_evidence_text(value) == "Room text"


@pytest.mark.parametrize("markup", [
    "<nav><nav>inner</nav>DO_NOT_EXPORT<p>Still private</p>",
    "<nav><footer>inner</nav>DO_NOT_EXPORT</footer><p>Ambiguous suffix</p>",
    "<header></footer>DO_NOT_EXPORT</header><p>Ambiguous suffix</p>",
    "<nav/>DO_NOT_EXPORT<p>Ambiguous suffix</p>",
    "<form><header/>DO_NOT_EXPORT</form><p>Ambiguous suffix</p>",
    "<nav><footer>DO_NOT_EXPORT</nav></footer></nav><p>Ambiguous suffix</p>",
])
def test_malformed_hidden_markup_fails_closed(markup):
    assert clean_evidence_text("<p>Public prefix</p>" + markup) == "Public prefix"


def test_void_elements_and_stray_closing_tags_do_not_hide_valid_listing_text():
    assert clean_evidence_text("</nav><p>No pets.<br/>No smoking.</p>") == "No pets.\nNo smoking."
    assert clean_evidence_text("<nav>private<br/><img src='x'></nav><p>Room text</p>") == "Room text"


@pytest.mark.parametrize("tag", ["script", "style", "iframe"])
def test_raw_text_hidden_elements_do_not_export_markup_looking_content(tag):
    assert clean_evidence_text(f"<{tag}>private<nav>private</nav></{tag}><p>Room text</p>") == "Room text"
