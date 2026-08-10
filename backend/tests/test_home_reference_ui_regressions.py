from pathlib import Path


def test_restored_home_reference_controls_are_loaded_and_stable() -> None:
    root = Path(__file__).resolve().parents[2]
    main = (root / "src" / "main.tsx").read_text(encoding="utf-8")
    mobile_cards = (root / "src" / "mobile-home-mode-cards.css").read_text(encoding="utf-8")
    home_search = (root / "src" / "components" / "home-mandatory-search.tsx").read_text(encoding="utf-8")
    reference_ui = (root / "src" / "reference-occupant-icons.ts").read_text(encoding="utf-8")
    asset_index = (root / "src" / "assets" / "occupants" / "index.ts").read_text(encoding="utf-8")

    assert "./mobile-home-mode-cards.css" in main
    assert "./reference-occupant-icons.css" in main
    assert "./reference-occupant-icons" in main

    assert "min-height: 13.8rem" in mobile_cards
    assert "content: attr(data-reference-title)" in mobile_cards
    assert "content: attr(data-reference-subtitle)" in mobile_cards
    assert "#70b700" in mobile_cards
    assert "#c60083" in mobile_cards

    assert "HABITACIONES" in reference_ui
    assert "LARGA ESTANCIA" in reference_ui
    assert "TURÍSTICAS" in reference_ui
    assert "ROOMS" in reference_ui
    assert "LONG STAY" in reference_ui
    assert "КОМНАТЫ" in reference_ui
    assert "ДОЛГОСРОЧНО" in reference_ui
    assert "button.setAttribute('aria-label', labels.aria)" in reference_ui

    asset_names = (
        "occupantPersonIcon",
        "occupantCoupleIcon",
        "occupantManIcon",
        "occupantWomanIcon",
        "occupantFamilyIcon",
        "occupantPetsIcon",
        "occupantAnyIcon",
    )
    for asset in asset_names:
        assert asset in home_search

    asset_dir = root / "src" / "assets" / "occupants"
    asset_files = ("person.ts", "couple.ts", "man.ts", "woman.ts", "family-ref.ts", "pets-ref.ts", "any-ref.ts")
    for filename in asset_files:
        source = (asset_dir / filename).read_text(encoding="utf-8")
        assert "data:image/webp;base64," in source

    assert "from './family-ref'" in asset_index
    assert "from './pets-ref'" in asset_index
    assert "from './any-ref'" in asset_index
    assert "Una persona" in home_search
    assert "Sin restricción" in home_search

    for mobile_key in ("one", "two", "man", "woman", "children", "pets", "unrestricted"):
        assert f"{mobile_key}:" in reference_ui
    assert "MutationObserver" in reference_ui
    assert "mutation.addedNodes" in reference_ui
    assert "characterData: true" in reference_ui
    assert "closest('.m2-mode-switch')" in reference_ui
    assert "document.addEventListener('click'" in reference_ui
    assert "m2-occupant-trigger" in reference_ui
    assert "m2-reference-occupant-icon" in reference_ui
    assert "row.querySelector('b')?.remove()" in reference_ui
