from pathlib import Path


def test_restored_home_reference_controls_are_loaded_and_stable() -> None:
    root = Path(__file__).resolve().parents[2]
    main = (root / "src" / "main.tsx").read_text(encoding="utf-8")
    mobile_cards = (root / "src" / "mobile-home-mode-cards.css").read_text(encoding="utf-8")
    reference_icons = (root / "src" / "reference-occupant-icons.css").read_text(encoding="utf-8")
    home_search = (root / "src" / "components" / "home-mandatory-search.tsx").read_text(encoding="utf-8")
    listing_access = (root / "src" / "lib" / "listing-access.ts").read_text(encoding="utf-8")
    reference_ui = (root / "src" / "reference-occupant-icons.ts").read_text(encoding="utf-8")
    object_urls = (root / "src" / "assets" / "occupants" / "object-url.ts").read_text(encoding="utf-8")
    asset_index = (root / "src" / "assets" / "occupants" / "index.ts").read_text(encoding="utf-8")
    pages_workflow = (root / ".github" / "workflows" / "pages-preview.yml").read_text(encoding="utf-8")

    assert "./mobile-home-mode-cards.css" in main
    assert "./reference-occupant-icons.css" in main
    assert "./reference-occupant-icons" in main

    assert "min-height: 13.8rem" in mobile_cards
    assert "content: attr(data-reference-title)" in mobile_cards
    assert "content: attr(data-reference-subtitle)" in mobile_cards
    assert "#70b700" in mobile_cards
    assert "#c60083" in mobile_cards
    assert ".m2-mode-switch > button.is-active::after" in mobile_cards
    assert "translateY(2px) scale(.95)" in mobile_cards
    assert "inset 0 0 0 4px #74b900" in mobile_cards
    assert "inset 0 0 0 4px #c60083" in mobile_cards

    assert ".m2-custom-occupant-list > button.is-selected .m2-reference-occupant-icon" in reference_icons
    assert "border-color: #d2ff3f" in reference_icons
    assert "transform: scale(1.07)" in reference_icons
    assert "width: 3.35rem" in reference_icons
    assert "height: 3.35rem" in reference_icons

    assert "HABITACIONES" in reference_ui
    assert "LARGA ESTANCIA" in reference_ui
    assert "TURÍSTICAS" in reference_ui
    assert "ROOMS" in reference_ui
    assert "LONG STAY" in reference_ui
    assert "КОМНАТЫ" in reference_ui
    assert "ДОЛГОСРОЧНО" in reference_ui
    assert "button.querySelector<HTMLElement>('span:last-child')" in reference_ui
    assert "labelTarget.dataset.referenceTitle = labels.title" in reference_ui
    assert "labelTarget.dataset.referenceSubtitle = labels.subtitle" in reference_ui
    assert "button.setAttribute('aria-label', `${labels.title} ${labels.subtitle}`)" in reference_ui

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
    asset_files = (
        "person.ts",
        "couple.ts",
        "man.ts",
        "woman.ts",
        "family-ref.ts",
        "pets-ref.ts",
        "any-ref.ts",
    )
    for filename in asset_files:
        source = (asset_dir / filename).read_text(encoding="utf-8")
        assert "data:image/webp;base64," in source

    assert "from './family-ref'" in asset_index
    assert "from './pets-ref'" in asset_index
    assert "from './any-ref'" in asset_index

    for label in (
        "1 persona",
        "2 personas (pareja/amigos)",
        "Con niños",
        "2 people (couple/friends)",
        "With children",
        "2 человека (пара/друзья)",
        "Можно с ребёнком",
        "Sin restricción",
    ):
        assert label in home_search
    assert "useI18n" in home_search
    assert "value: 'two-people'" in home_search
    assert "value: 'with-children'" in home_search

    assert "'two-people'" in listing_access
    assert "'with-children'" in listing_access
    assert "case 'two-people':" in listing_access
    assert "case 'with-children':" in listing_access
    assert "roomCapacity = '2'" in listing_access
    assert "children = 'Sí'" in listing_access
    assert "tenantRequirements: []" in listing_access
    assert "if (value === 'couple') return 'two-people'" in listing_access
    assert "if (value === 'family') return 'with-children'" in listing_access

    assert "URL.createObjectURL" in object_urls
    assert "new Blob" in object_urls
    assert "occupantObjectUrl" in home_search
    assert "occupantObjectUrl" in reference_ui

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

    assert "VITE_ENABLE_MOCK_MODE: '1'" in pages_workflow
    assert "VITE_GOOGLE_MAPS_TEST_SDK: '1'" in pages_workflow
    assert "VITE_BASE_PATH: /Ttest/" in pages_workflow
