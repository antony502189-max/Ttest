from __future__ import annotations

from pathlib import Path

import pytest
from botocore.exceptions import EndpointConnectionError

from app import storage


class FailingStorage:
    def put(self, key: str, content: bytes, content_type: str = "image/webp") -> None:
        return None

    def get(self, key: str) -> bytes | None:
        return None

    def get_range(self, key: str, start: int, end: int) -> bytes | None:
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


def test_local_storage_reads_only_requested_range(tmp_path: Path):
    local = storage.LocalStorage(tmp_path)
    local.put("user/video.mp4", b"0123456789", "video/mp4")

    assert local.get_range("user/video.mp4", 2, 5) == b"2345"
    assert local.get_range("user/missing.mp4", 0, 1) is None
