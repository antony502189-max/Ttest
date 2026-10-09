import asyncio
from types import SimpleNamespace
from uuid import uuid4

from app.services import external_import


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
        external_import_preserve_existing_galleries=True,
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
        external_import_preserve_existing_galleries=True,
        external_import_download_images=False,
    ))
    session = Session()
    asyncio.run(external_import.import_images(session, uuid4(), uuid4(), ["https://example.test/new.jpg"]))
    assert session.commits == 2
