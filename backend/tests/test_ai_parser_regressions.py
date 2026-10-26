from dataclasses import replace

import pytest

from app.external_sources import NormalizedListing, public_detail_fields


def item(**overrides):
    return replace(
        NormalizedListing(
            source_name="Fixture",
            external_id="123",
            source_url="https://example.test/123",
            title="Habitación en Adeje",
            description="Habitación en piso compartido.",
            city="Adeje",
            area="Adeje",
            rental_mode="long",
            source_price_text="600 €/mes",
            price_amount=600,
            price_currency="EUR",
            price_period="month",
            price_is_from=False,
        ),
        **overrides,
    )


@pytest.mark.parametrize(
    "field,before,after",
    [
        ("pets_allowed", True, False),
        ("children_allowed", True, False),
        ("smoking_allowed", True, False),
        ("room_capacity", 1, 4),
        ("furnished", True, False),
        ("bills_included", True, False),
        ("bathroom", None, "Baño privado"),
        ("kitchen", None, "Cocina privada"),
        ("room_size_m2", None, 18),
        ("tenant_requirement", None, "single-woman"),
        ("empadronamiento_allowed", None, False),
        ("weekly_price_amount", None, 300),
        ("price_amount", 600, 650),
    ],
)
def test_optional_only_changes_invalidate_import_fingerprint(field, before, after):
    assert item(**{field: before}).fingerprint != item(**{field: after}).fingerprint


@pytest.mark.parametrize("field", ["pets_allowed", "children_allowed", "smoking_allowed", "furnished"])
def test_unknown_is_distinct_from_false_in_fingerprint(field):
    assert item(**{field: None}).fingerprint != item(**{field: False}).fingerprint


def test_scoped_smoking_permission_is_not_unconditional_permission():
    assert public_detail_fields({"description": "Se permite fumar en la terraza"})["smoking_allowed"] is None


def test_contradictory_pets_rules_are_not_silently_resolved():
    assert public_detail_fields({"description": "Se aceptan mascotas. No se admiten mascotas."})["pets_allowed"] is None


def test_fingerprint_ignores_unrelated_raw_payload():
    assert item().fingerprint == item(raw_payload={"unrelated": "page chrome"}).fingerprint
