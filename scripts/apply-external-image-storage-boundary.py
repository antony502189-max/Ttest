from __future__ import annotations

import hashlib
from pathlib import Path

SOURCE = Path("backend/app/services/external_import.py")
TEST = Path("backend/tests/integration/test_external_import_transaction_boundaries.py")
EXPECTED_SOURCE_SHA256 = "f4d5d1b00b5323adccb26f162617d7c0ce7c81fc89f843f12c9ef8e81e47602e"
EXPECTED_TEST_SHA256 = "e5e489444bc8778260d784fc585fe40d5e0285851ef25e457dfcd495bd8f3b7d"
EXPECTED_RESULT_SOURCE_SHA256 = "348196491d5f6d2dfefe1d10407f4e1e481e508db770b1a58ed8f8ae2525207f"
EXPECTED_RESULT_TEST_SHA256 = "7f23699d64289a2290c258201ae310de30a27552f7343b2c40518616935071c9"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, found {count}")
    return text.replace(old, new, 1)


def patch_source() -> None:
    if digest(SOURCE) != EXPECTED_SOURCE_SHA256:
        raise SystemExit("external_import.py no longer matches the reviewed source")
    text = SOURCE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import httpx\nfrom fastapi import HTTPException\n",
        "import httpx\n"
        "from botocore.exceptions import BotoCoreError, ClientError  # type: ignore[import-untyped]\n"
        "from fastapi import HTTPException\n",
        label="botocore imports",
    )
    text = replace_once(
        text,
        "                    except OSError:\n"
        "                        logger.exception(\n"
        "                            \"external_image_storage_failed\",",
        "                    except (OSError, BotoCoreError, ClientError):\n"
        "                        logger.exception(\n"
        "                            \"external_image_storage_failed\",",
        label="storage put boundary",
    )
    text = replace_once(
        text,
        "                    except OSError:\n"
        "                        logger.exception(\n"
        "                            \"external_image_cleanup_failed\",",
        "                    except (OSError, BotoCoreError, ClientError):\n"
        "                        logger.exception(\n"
        "                            \"external_image_cleanup_failed\",",
        label="storage cleanup boundary",
    )
    SOURCE.write_text(text, encoding="utf-8")
    if digest(SOURCE) != EXPECTED_RESULT_SOURCE_SHA256:
        raise SystemExit("patched external_import.py checksum mismatch")


def patch_test() -> None:
    if digest(TEST) != EXPECTED_TEST_SHA256:
        raise SystemExit("transaction-boundary test no longer matches the reviewed source")
    text = TEST.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "import pytest\nfrom sqlalchemy import select\n",
        "import pytest\n"
        "from botocore.exceptions import EndpointConnectionError\n"
        "from sqlalchemy import select\n",
        label="test botocore import",
    )
    text = replace_once(
        text,
        "class RecordingStorage:\n",
        "class FailingS3Storage:\n"
        "    def put(self, key: str, content: bytes) -> None:\n"
        "        raise EndpointConnectionError(endpoint_url=\"http://minio:9000\")\n\n"
        "    def delete(self, key: str) -> None:\n"
        "        raise EndpointConnectionError(endpoint_url=\"http://minio:9000\")\n\n\n"
        "class RecordingStorage:\n",
        label="failing storage fixture",
    )
    marker = "\n\nasync def test_reconciliation_probes_run_without_database_transaction(monkeypatch):\n"
    new_test = """

async def test_s3_failure_skips_image_without_aborting_listing_import(monkeypatch):
    normalized = b"unavailable-s3-image"
    checksum = hashlib.sha256(normalized).hexdigest()

    async with SessionLocal() as session:
        async def image_hashes(urls: list[str]) -> set[str]:
            assert not session.in_transaction()
            return set()

        async def prepared_image(client, url: str) -> importer.PreparedExternalImage:
            assert not session.in_transaction()
            return importer.PreparedExternalImage(
                content=normalized,
                width=16,
                height=16,
                checksum=checksum,
                perceptual_hash="2" * 16,
            )

        monkeypatch.setattr(importer, "public_image_hashes", image_hashes)
        monkeypatch.setattr(importer, "download_external_image", prepared_image)
        monkeypatch.setattr(importer, "get_storage", FailingS3Storage)

        item = external_item(
            source="Idealista",
            external_id="s3-failure-boundary",
            url="https://www.idealista.com/inmueble/s3-failure-boundary/",
            photos=["https://images.example.test/unavailable.webp"],
        )
        assert await importer.upsert(session, item) == "imported"
        assert not session.in_transaction()

        source_record = await session.scalar(
            select(ExternalListingSource).where(
                ExternalListingSource.source_name == item.source_name,
                ExternalListingSource.external_id == item.external_id,
            )
        )
        assert source_record is not None
        attached_count = len(
            (
                await session.scalars(
                    select(ListingImage.id).where(
                        ListingImage.listing_id == source_record.canonical_listing_id
                    )
                )
            ).all()
        )
        persisted_asset = await session.scalar(
            select(MediaAsset.id).where(MediaAsset.checksum == checksum)
        )
        assert attached_count == 0
        assert persisted_asset is None
"""
    text = replace_once(text, marker, new_test + marker, label="S3 failure regression")
    TEST.write_text(text, encoding="utf-8")
    if digest(TEST) != EXPECTED_RESULT_TEST_SHA256:
        raise SystemExit("patched transaction-boundary test checksum mismatch")


def main() -> None:
    patch_source()
    patch_test()


if __name__ == "__main__":
    main()
