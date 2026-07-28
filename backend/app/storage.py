from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Protocol

from .core.config import get_settings


class Storage(Protocol):
    def put(self, key: str, content: bytes) -> None: ...
    def get(self, key: str) -> bytes | None: ...
    def delete(self, key: str) -> None: ...
    def healthcheck(self) -> None: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def put(self, key: str, content: bytes) -> None:
        destination = self._path(key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.is_file() else None

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
    ):
        try:
            import boto3  # type: ignore[import-not-found,import-untyped]
            from botocore.config import Config  # type: ignore[import-not-found,import-untyped]
            from botocore.exceptions import ClientError  # type: ignore[import-not-found,import-untyped]
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
                s3={"addressing_style": "path" if force_path_style else "virtual"},
            ),
        )

    def put(self, key: str, content: bytes) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType="image/webp",
            CacheControl="public, max-age=31536000, immutable",
        )

    def get(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.client_error as error:
            if error.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def healthcheck(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET is required for STORAGE_BACKEND=s3")
        return S3Storage(
            settings.s3_bucket,
            settings.s3_endpoint_url,
            settings.s3_region,
            settings.s3_access_key,
            settings.s3_secret_key,
            settings.s3_force_path_style,
        )
    return LocalStorage(settings.media_root)
