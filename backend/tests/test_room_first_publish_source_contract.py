"""Regression contracts for room-first fields and their legacy-accessibility compatibility."""

from pathlib import Path

PUBLISH_SOURCE = (Path(__file__).resolve().parents[2] / "src" / "pages" / "PublishPage.tsx").read_text(encoding="utf-8")


def test_publish_editor_preserves_all_supported_room_types():
    assert 'listing.roomType === "Estudio" ? "Estudio"' in PUBLISH_SOURCE
    assert '{ value: "Habitación individual", title: "Habitación privada"' in PUBLISH_SOURCE
    assert '{ value: "Habitación compartida", title: "Habitación compartida"' in PUBLISH_SOURCE
    assert '{ value: "Estudio", title: "Estudio"' in PUBLISH_SOURCE


def test_publish_room_first_fields_keep_stable_accessible_contracts():
    for contract in (
        'aria-label="Tamaño aproximado"',
        'aria-label="Personas que viven en casa"',
        'aria-label="Capacidad de la habitación"',
        'aria-label="Alquiler mensual"',
        'aria-label="Precio por noche"',
        'aria-label="Precio por semana"',
        'aria-label="Precio por mes"',
        'label="Requisito para la persona inquilina"',
        'label="Personas que ya viven en esta habitación"',
        'label="Número de camas"',
        'label="Aseo / WC"',
    ):
        assert contract in PUBLISH_SOURCE


def test_publish_capacity_changes_keep_beds_and_occupancy_coherent():
    for contract in (
        'Math.ceil(roomCapacity / placesPerBed)',
        'Math.min(current.currentRoomResidents, roomCapacity - 1)',
        'value === "bed" ? Math.max(current.bedCount, current.roomCapacity)',
        'Math.ceil(current.roomCapacity / placesPerBed)',
    ):
        assert contract in PUBLISH_SOURCE
