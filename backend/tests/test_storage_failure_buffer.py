from __future__ import annotations

from io import BytesIO
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


def test_s3_storage_requests_and_reads_only_the_selected_bytes():
    class Body(BytesIO):
        def __init__(self):
            super().__init__(b"2345EXTRA")
            self.requested: int | None = None

        def read(self, size: int = -1) -> bytes:
            self.requested = size
            return super().read(size)

    class Client:
        def __init__(self):
            self.body = Body()
            self.kwargs: dict = {}

        def get_object(self, **kwargs):
            self.kwargs = kwargs
            return {"Body": self.body}

    store = object.__new__(storage.S3Storage)
    store.bucket = "media"
    store.client = Client()

    assert store.get_range("owner/video.mp4", 2, 5) == b"2345"
    assert store.client.kwargs == {"Bucket": "media", "Key": "owner/video.mp4", "Range": "bytes=2-5"}
    assert store.client.body.requested == 4
    assert store.client.body.closed
