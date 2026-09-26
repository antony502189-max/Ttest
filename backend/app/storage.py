from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]

from .core.config import get_settings
from .core.media_keys import storage_keys_for_asset
from .core.storage_failure_buffer import record_failed_storage_deletion


class Storage(Protocol):
    def put(self, key: str, content: bytes, content_type: str = "image/webp") -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def get_range(self, key: str, start: int, end: int) -> bytes | None: ...
    def delete(self, key: str) -> None: ...
    def healthcheck(self) -> None: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def put(self, key: str, content: bytes, content_type: str = "image/webp") -> None:
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None

    def get_range(self, key: str, start: int, end: int) -> bytes | None:
        path = self._path(key)
        if not path.is_file():
            return None
        with path.open("rb") as handle:
            handle.seek(start)
            return handle.read(end - start + 1)

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def healthcheck(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        probe = self.root / ".healthcheck"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)

    def _path(self, key: str) -> Path:
        root = self.root.resolve()
        path = (root / key).resolve()
        if root not in path.parents and path != root:
            raise ValueError("Storage key must stay inside the media root")
        return path


class S3Storage:
    def __init__(
        self,
        bucket: str,
        endpoint_url: str,
        region: str,
        access_key: str,
        secret_key: str,
        force_path_style: bool = True,
        *,
        connect_timeout_seconds: int = 3,
        read_timeout_seconds: int = 10,
        max_attempts: int = 3,
        max_pool_connections: int = 32,
    ):
        try:
            import boto3  # type: ignore[import-not-found,import-untyped]
            from botocore.config import Config  # type: ignore[import-not-found,import-untyped]
        except ImportError as error:  # pragma: no cover - configuration error
            raise RuntimeError("boto3 is required for STORAGE_BACKEND=s3") from error
        self.bucket = bucket
        self.client_error = ClientError
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            region_name=region or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            config=Config(
                signature_version="s3v4",
                connect_timeout=connect_timeout_seconds,
                read_timeout=read_timeout_seconds,
                retries={"max_attempts": max_attempts, "mode": "standard"},
                max_pool_connections=max_pool_connections,
                s3={"addressing_style": "path" if force_path_style else "virtual"},
            ),
        )

    def put(self, key: str, content: bytes, content_type: str = "image/webp") -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            CacheControl="public, max-age=31536000, immutable",
        )

    def get(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.client_error as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def get_range(self, key: str, start: int, end: int) -> bytes | None:
        try:
            body = self.client.get_object(
                Bucket=self.bucket,
                Key=key,
                Range=f"bytes={start}-{end}",
            )["Body"]
            try:
                return body.read(end - start + 1)
            finally:
                body.close()
        except self.client_error as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def healthcheck(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


class BufferedDeleteStorage:
    """Record failed physical deletes before propagating the storage error."""

    def __init__(self, delegate: Storage):
        self.delegate = delegate

    def put(self, key: str, content: bytes, content_type: str = "image/webp") -> None:
        self.delegate.put(key, content, content_type)

    def get(self, key: str) -> bytes | None:
        return self.delegate.get(key)

    def get_range(self, key: str, start: int, end: int) -> bytes | None:
        return self.delegate.get_range(key, start, end)

    def delete(self, key: str) -> None:
        try:
            for storage_key in storage_keys_for_asset(key):
                self.delegate.delete(storage_key)
        except (OSError, BotoCoreError, ClientError):
            # Retry the root key: derived deletes are idempotent and will be
            # attempted again with the original on the deletion worker.
            record_failed_storage_deletion(key)
            raise

    def healthcheck(self) -> None:
        self.delegate.healthcheck()


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET is required for STORAGE_BACKEND=s3")
        storage: Storage = S3Storage(
            settings.s3_bucket,
            settings.s3_endpoint_url,
            settings.s3_region,
            settings.s3_access_key,
            settings.s3_secret_key,
            settings.s3_force_path_style,
            connect_timeout_seconds=settings.s3_connect_timeout_seconds,
            read_timeout_seconds=settings.s3_read_timeout_seconds,
            max_attempts=settings.s3_max_attempts,
            max_pool_connections=settings.s3_max_pool_connections,
        )
    else:
        storage = LocalStorage(settings.media_root)
    return BufferedDeleteStorage(storage)
