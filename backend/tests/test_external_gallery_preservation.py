import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services import external_import, external_removal


def test_preservation_keeps_existing_gallery_without_network_or_storage(monkeypatch):
    class Session:
        commits = 0

        async def scalar(self, _query):
            return 5

        async def commit(self):
            self.commits += 1

    def forbidden_storage():
        raise AssertionError("existing production gallery must not be reconciled")

    monkeypatch.setattr(external_import, "get_settings", lambda: SimpleNamespace(
        external_import_preserve_existing_data=True,
    ))
    monkeypatch.setattr(external_import, "get_storage", forbidden_storage)
    session = Session()
    asyncio.run(external_import.import_images(session, uuid4(), uuid4(), ["https://example.test/new.jpg"]))
    assert session.commits == 1


def test_preservation_allows_empty_gallery_to_reach_import_settings(monkeypatch):
    class Session:
        commits = 0

        async def scalar(self, _query):
            return 0

        async def commit(self):
            self.commits += 1

    monkeypatch.setattr(external_import, "get_settings", lambda: SimpleNamespace(
        external_import_preserve_existing_data=True,
        external_import_download_images=False,
    ))
    session = Session()
    asyncio.run(external_import.import_images(session, uuid4(), uuid4(), ["https://example.test/new.jpg"]))
    assert session.commits == 2


@pytest.mark.parametrize("reason", ["rejected", "source_retired", "removed"])
def test_preservation_does_not_close_historical_source_records(monkeypatch, reason):
    monkeypatch.setattr(external_import, "get_settings", lambda: SimpleNamespace(
        external_import_preserve_existing_data=True,
    ))
    row = SimpleNamespace(current_status="active", removed_reason=None)
    before = dict(vars(row))
    # An object without DB methods makes any query or write fail this test.
    assert asyncio.run(external_import.deactivate_source_record(object(), row, reason)) == 0
    assert vars(row) == before


@pytest.mark.parametrize("state", ["removed", "expired", "not_found"])
def test_preservation_blocks_physical_purge_even_when_removal_is_enabled(monkeypatch, state):
    monkeypatch.setattr(external_removal, "get_settings", lambda: SimpleNamespace(
        external_import_preserve_existing_data=True,
        external_removal_check_enabled=True,
    ))
    outcome = asyncio.run(external_removal.purge_confirmed_removed_source(object(), uuid4(), state))
    assert outcome and all(value == 0 for value in outcome.values())


def test_price_rejection_does_not_rewrite_existing_source_in_preservation_mode(monkeypatch):
    class Session:
        async def scalar(self, _query):
            return row

        async def commit(self):
            pass

    row = SimpleNamespace(scope_key="santa_cruz", current_status="active", normalized_payload={"price": 1200})
    item = SimpleNamespace(room_capacity=None, source_name="Pisos", external_id="old", source_url="https://example.test/old")
    before = dict(vars(row))
    monkeypatch.setattr(external_import, "get_settings", lambda: SimpleNamespace(
        external_import_preserve_existing_data=True,
    ))
    monkeypatch.setattr(external_import, "imported_price_allowed", lambda _: False)
    assert asyncio.run(external_import.upsert(Session(), item)) == "rejected_invalid_price"
    assert vars(row) == before


def test_preservation_rechecks_gallery_after_download_before_any_delete(monkeypatch):
    asset = SimpleNamespace(id=uuid4(), checksum="checksum")
    listing = SimpleNamespace(external_image_urls=["https://example.test/old.jpg"])
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[0, listing]),
        scalars=AsyncMock(side_effect=[
            SimpleNamespace(all=lambda: [asset]),
            SimpleNamespace(all=lambda: [uuid4()]),
        ]),
        commit=AsyncMock(), rollback=AsyncMock(), execute=AsyncMock(),
        in_transaction=lambda: False,
    )
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=object())
    client.__aexit__ = AsyncMock(return_value=False)
    cleanup = AsyncMock()
    monkeypatch.setattr(external_import, "get_settings", lambda: SimpleNamespace(
        external_import_preserve_existing_data=True,
        external_import_download_images=True,
        external_import_max_concurrency_per_source=1,
        external_import_request_timeout_seconds=1,
    ))
    monkeypatch.setattr(external_import.httpx, "AsyncClient", lambda **_: client)
    monkeypatch.setattr(external_import, "get_storage", object)
    monkeypatch.setattr(external_import, "download_external_image", AsyncMock(return_value=
        external_import.PreparedExternalImage(b"image", 1, 1, "checksum", "phash")))
    monkeypatch.setattr(external_import, "_delete_external_objects", cleanup)
    asyncio.run(external_import.import_images(session, uuid4(), uuid4(), ["https://example.test/new.jpg"]))
    session.rollback.assert_awaited_once()
    session.execute.assert_not_awaited()
    assert cleanup.await_args.args[1] == set()
