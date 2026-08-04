from __future__ import annotations

import pytest
from botocore.exceptions import EndpointConnectionError

from app import storage


class FailingStorage:
    def put(self, key: str, content: bytes) -> None:
        return None

    def get(self, key: str) -> bytes | None:
        return None

    def delete(self, key: str) -> None:
        raise EndpointConnectionError(endpoint_url="http://minio:9000")

    def healthcheck(self) -> None:
        return None


def test_failed_delete_is_buffered_before_error_propagates(monkeypatch):
    buffered: list[str] = []
    monkeypatch.setattr(storage, "record_failed_storage_deletion", lambda key: buffered.append(key) or True)
    wrapped = storage.BufferedDeleteStorage(FailingStorage())

    with pytest.raises(EndpointConnectionError):
        wrapped.delete("external/orphan.webp")

    assert buffered == ["external/orphan.webp"]
