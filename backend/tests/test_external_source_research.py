"""Research guardrails for sources that are deliberately not production adapters yet."""

from __future__ import annotations

import os

import httpx
import pytest

from app.external_sources import configured_sources


@pytest.mark.parametrize(
    ("name", "research_url"),
    [
        ("yaencontre", "https://www.yaencontre.com/alquiler/habitacion/santa-cruz-de-tenerife"),
        ("habitaclia", "https://www.habitaclia.com/alquiler-habitacion-santa_cruz_de_tenerife.htm"),
    ],
)
def test_room_source_research_candidates_are_not_enabled_without_a_stable_public_room_route(name: str, research_url: str):
    """Document candidate routes while preventing accidental production crawling."""
    assert name not in {source.name.casefold() for source in configured_sources()}
    assert research_url.startswith("https://")


@pytest.mark.skipif(os.getenv("RUN_LIVE_EXTERNAL_SOURCE_TESTS") != "1", reason="opt-in public route research")
@pytest.mark.parametrize(
    "research_url",
    [
        "https://www.yaencontre.com/alquiler/habitacion/santa-cruz-de-tenerife",
        "https://www.habitaclia.com/alquiler-habitacion-santa_cruz_de_tenerife.htm",
    ],
)
def test_candidate_room_routes_are_research_only_and_never_a_production_import_contract(research_url: str):
    response = httpx.get(research_url, follow_redirects=True, timeout=25, headers={"User-Agent": "112233.es room aggregator"})
    assert response.status_code < 500
