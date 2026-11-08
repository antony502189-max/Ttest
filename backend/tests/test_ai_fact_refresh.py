"""Fail-closed configuration bounds; no database or actual HTTP connections."""

from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from lab.ai_fact_refresh import SyntheticDetailRefresh, SyntheticRefreshPolicy

POLICY = SyntheticRefreshPolicy("synthetic", "example.invalid", 10, 131_072, 1, 10, 20, 30)


@pytest.mark.parametrize("field,value", [("source_name", "idealista"), ("source_name", "synthetic.bad"),
    ("host", "example.com"), ("host", "localhost"), ("host", "https://example.invalid"),
    ("max_requests", 0), ("max_requests", 101), ("max_requests", True),
    ("max_payload_bytes", 0), ("max_payload_bytes", 131_073), ("timeout_seconds", 0),
    ("timeout_seconds", 31), ("max_operations", 0), ("max_operations", 1001),
    ("max_total_requests", 0), ("max_total_requests", 1001), ("max_total_requests", True),
    ("request_lease_seconds", 0), ("request_lease_seconds", 1), ("request_lease_seconds", 3601)])
def test_invalid_or_unbounded_detail_policy_is_refused(field, value):
    with pytest.raises(ValueError):
        replace(POLICY, **{field: value})


def supervisor():
    return SimpleNamespace(_binding=lambda: None, journal=SimpleNamespace(binding="owned-unit-config"),
        coordinator=SimpleNamespace(sources={"synthetic": object()}, pipeline=SimpleNamespace(sessions=object())))


@pytest.mark.parametrize("cohort", [(), [], (("not-uuid", "not-uuid"),), ((uuid4(),),),
    ((uuid4(), uuid4(), uuid4()),), tuple((uuid4(), uuid4()) for _ in range(101))])
def test_invalid_or_unbounded_cohort_is_refused(cohort):
    with pytest.raises(ValueError, match="cohort"):
        SyntheticDetailRefresh(supervisor(), policy=POLICY, cohort=cohort,
            transport=httpx.MockTransport(lambda request: None), mock_bundle_sha256="a" * 64)


def test_duplicate_source_grants_are_refused():
    source = uuid4()
    with pytest.raises(ValueError, match="cohort"):
        SyntheticDetailRefresh(supervisor(), policy=POLICY, cohort=((source, uuid4()), (source, uuid4())),
            transport=httpx.MockTransport(lambda request: None), mock_bundle_sha256="a" * 64)


async def test_actual_network_transport_is_refused_without_io():
    transport = httpx.AsyncHTTPTransport()
    try:
        with pytest.raises(ValueError, match="MockTransport"):
            SyntheticDetailRefresh(supervisor(), policy=POLICY, cohort=((uuid4(), uuid4()),),
                transport=transport, mock_bundle_sha256="a" * 64)
    finally:
        await transport.aclose()


def test_mock_transport_subclass_cannot_override_network_boundary():
    class OtherTransport(httpx.MockTransport):
        pass

    with pytest.raises(ValueError, match="MockTransport"):
        SyntheticDetailRefresh(supervisor(), policy=POLICY, cohort=((uuid4(), uuid4()),),
            transport=OtherTransport(lambda request: None), mock_bundle_sha256="a" * 64)
