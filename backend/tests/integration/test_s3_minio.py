from __future__ import annotations

import os
from uuid import uuid4

import pytest

from app.storage import S3Storage

pytestmark = [pytest.mark.integration, pytest.mark.s3]


def test_minio_put_read_delete_roundtrip():
    endpoint = os.getenv("S3_ENDPOINT_URL")
    bucket = os.getenv("S3_BUCKET")
    access_key = os.getenv("S3_ACCESS_KEY")
    secret_key = os.getenv("S3_SECRET_KEY")
    if not all([endpoint, bucket, access_key, secret_key]):
        pytest.skip("S3-compatible test credentials are not configured")
    storage = S3Storage(
        bucket=bucket,
        endpoint_url=endpoint,
        region=os.getenv("S3_REGION", "us-east-1"),
        access_key=access_key,
        secret_key=secret_key,
        force_path_style=True,
    )
    storage.healthcheck()
    key = f"integration/{uuid4().hex}.webp"
    payload = b"s3-roundtrip"
    storage.put(key, payload)
    assert storage.get(key) == payload
    storage.delete(key)
    assert storage.get(key) is None
