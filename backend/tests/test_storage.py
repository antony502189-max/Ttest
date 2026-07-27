import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from app.storage import LocalStorage


def test_local_storage_round_trip_and_delete() -> None:
    root = Path("var") / f"pytest-storage-{uuid4().hex}"
    try:
        storage = LocalStorage(root)
        storage.put("images/example.webp", b"webp")

        assert storage.get("images/example.webp") == b"webp"
        storage.delete("images/example.webp")
        assert storage.get("images/example.webp") is None
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_local_storage_rejects_path_traversal() -> None:
    storage = LocalStorage(Path("var") / f"pytest-storage-{uuid4().hex}")

    with pytest.raises(ValueError, match="inside the media root"):
        storage.put("../outside.webp", b"nope")
