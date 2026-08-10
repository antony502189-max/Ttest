from pathlib import Path


def test_restored_home_reference_controls_are_loaded_and_stable() -> None:
    root = Path(__file__).resolve().parents[2]
    main = (root / "src" / "main.tsx").read_text(encoding="utf-8")
    mobile_cards = (root / "src" / "mobile-home-mode-cards.css").read_text(encoding="utf-8")
    home_search = (root / "src" / "components" / "home-mandatory-search.tsx").read_text(encoding="utf-8")
    mobile_icons = (root / "src" / "reference-occupant-icons.ts").read_text(encoding="utf-8")

    assert "./mobile-home-mode-cards.css" in main
    assert "./reference-occupant-icons.css" in main
    assert "./reference-occupant-icons" in main

    assert "min-height: 13.8rem" in mobile_cards
    assert "content: 'HABITACIONES'" in mobile_cards
    assert "content: 'LARGA ESTANCIA'" in mobile_cards
    assert "content: 'TURÍSTICAS'" in mobile_cards
    assert "#70b700" in mobile_cards
    assert "#c60083" in mobile_cards

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
    asset_files = ("person.ts", "couple.ts", "man.ts", "woman.ts", "family.ts", "pets.ts", "any.ts")
    for filename in asset_files:
        source = (asset_dir / filename).read_text(encoding="utf-8")
        assert "data:image/webp;base64," in source

    assert "Sin restricción" in home_search
    assert "Sin restricciones" not in home_search

    for mobile_key in ("one", "two", "man", "woman", "children", "pets", "unrestricted"):
        assert f"{mobile_key}:" in mobile_icons
    assert "MutationObserver" in mobile_icons
    assert "m2-reference-occupant-icon" in mobile_icons
    assert "row.querySelector('b')?.remove()" in mobile_icons
