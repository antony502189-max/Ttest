from app.services.external_import import SourceRunCounters, completed_source_contract
from app.workers.external_listings import _successful_source_names


def counters(
    *,
    result: str = "success",
    discovered: int = 1,
    fetched: int = 1,
    accepted: int = 1,
) -> SourceRunCounters:
    value = SourceRunCounters(
        {
            "discovered_urls": discovered,
            "fetched_details": fetched,
            "accepted_rooms": accepted,
        }
    )
    value.result = result
    return value


def test_completed_source_contract_requires_a_valid_room_detail() -> None:
    assert completed_source_contract(counters())
    assert not completed_source_contract(counters(discovered=0))
    assert not completed_source_contract(counters(fetched=0))
    assert not completed_source_contract(counters(accepted=0))


def test_worker_counts_only_useful_successful_sources() -> None:
    result = {
        "Fotocasa": counters(),
        "ThinkSpain": counters(discovered=0),
        "Idealista": counters(result="blocked"),
    }
    assert _successful_source_names(result) == ["Fotocasa"]


def test_partial_source_never_counts_as_healthy() -> None:
    assert _successful_source_names({"Pisos": counters(result="partial")}) == []
