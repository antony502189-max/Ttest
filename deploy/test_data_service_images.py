"""Regression tests for legacy stateful-image upgrade compatibility."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("data-service-images.py")
SPEC = importlib.util.spec_from_file_location("data_service_images", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_repository_name_ignores_tag_but_keeps_registry_port() -> None:
    assert MODULE.repository_name("postgis/postgis:16-3.4") == "postgis/postgis"
    assert MODULE.repository_name("registry.example:5000/team/image:1") == "registry.example:5000/team/image"


def test_canonical_digest_reference_removes_a_tag_before_the_digest() -> None:
    assert (
        MODULE.canonical_digest_reference("postgis/postgis:16-3.4@sha256:abc")
        == "postgis/postgis@sha256:abc"
    )


def test_resolve_local_digest_uses_matching_repository_digest() -> None:
    completed = SimpleNamespace(
        returncode=0,
        stdout='["postgis/postgis@sha256:abc", "other/image@sha256:def"]',
    )
    with patch.object(MODULE.subprocess, "run", return_value=completed):
        assert MODULE.resolve_local_digest("postgis/postgis:16-3.4") == "postgis/postgis@sha256:abc"


def test_resolve_local_digest_rejects_ambiguous_legacy_image() -> None:
    completed = SimpleNamespace(
        returncode=0,
        stdout='["redis@sha256:abc", "redis@sha256:def"]',
    )
    with patch.object(MODULE.subprocess, "run", return_value=completed):
        try:
            MODULE.resolve_local_digest("redis:7.4-alpine")
        except SystemExit as exc:
            assert "exactly one immutable digest" in str(exc)
        else:
            raise AssertionError("ambiguous digest resolution must fail closed")
