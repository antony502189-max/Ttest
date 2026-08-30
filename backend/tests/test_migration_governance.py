from __future__ import annotations

import hashlib
import json
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_ROOT = BACKEND_ROOT / "alembic"
BASELINE_PATH = ALEMBIC_ROOT / "rollback-compatibility-baseline.json"
RELEASED_MIGRATIONS_PATH = ALEMBIC_ROOT / "released-migration-blobs.json"


def _script_directory() -> ScriptDirectory:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ALEMBIC_ROOT))
    return ScriptDirectory.from_config(config)


def _linear_revision_chain(script: ScriptDirectory) -> list:
    heads = script.get_heads()
    assert len(heads) == 1, f"Alembic must have exactly one head, found: {heads}"

    revisions = list(script.walk_revisions(base="base", head=heads[0]))
    by_revision = {revision.revision: revision for revision in revisions}
    assert len(by_revision) == len(revisions), "Alembic revision IDs must be unique"

    chain = []
    current = by_revision[heads[0]]
    visited: set[str] = set()
    while current is not None:
        assert current.revision not in visited, f"Alembic cycle detected at {current.revision}"
        visited.add(current.revision)
        chain.append(current)
        parent = current.down_revision
        assert parent is None or isinstance(parent, str), (
            "Production migrations must remain a single linear expand-compatible chain; "
            f"{current.revision} has parents {parent!r}"
        )
        if parent is None:
            current = None
            continue
        assert parent in by_revision, f"Migration {current.revision} references missing parent {parent}"
        current = by_revision[parent]

    assert len(visited) == len(revisions), (
        "Every migration must belong to the single production chain; "
        f"chain={len(visited)}, discovered={len(revisions)}"
    )
    return chain


def _git_blob_sha(path: Path) -> str:
    """Return the SHA-1 Git uses for a file blob; this is an identity check, not crypto."""
    content = path.read_bytes()
    header = f"blob {len(content)}\0".encode()
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(header)
    digest.update(content)
    return digest.hexdigest()


def test_alembic_graph_is_one_complete_linear_chain() -> None:
    _linear_revision_chain(_script_directory())


def test_rollback_baseline_is_an_immutable_ancestor_of_head() -> None:
    script = _script_directory()
    chain = _linear_revision_chain(script)
    chain_ids = [revision.revision for revision in chain]

    manifest = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline = manifest.get("baseline_revision")
    hashes = manifest.get("files")

    assert isinstance(baseline, str) and baseline, "rollback baseline_revision must be a non-empty string"
    assert isinstance(hashes, dict) and hashes, "rollback baseline files map must be non-empty"
    assert baseline in chain_ids, f"rollback baseline {baseline} is not an ancestor of the current head"

    baseline_index = chain_ids.index(baseline)
    frozen_revisions = chain[baseline_index:]
    expected_files = {Path(revision.path).name for revision in frozen_revisions}
    assert set(hashes) == expected_files, (
        "rollback baseline must freeze exactly the migration history through its declared revision; "
        f"missing={sorted(expected_files - set(hashes))}, extra={sorted(set(hashes) - expected_files)}"
    )

    for revision in frozen_revisions:
        path = Path(revision.path)
        expected_hash = hashes[path.name]
        assert isinstance(expected_hash, str) and len(expected_hash) == 64, (
            f"rollback baseline contains an invalid SHA-256 for {path.name}"
        )
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, f"deployed migration history changed: {path.name}"


def test_released_post_baseline_migrations_are_immutable() -> None:
    """Freeze released revisions not yet folded into the rollback SHA-256 baseline.

    The rollback compatibility manifest currently has its own deployment
    promotion lifecycle. This independent Git-blob manifest prevents already
    released 0033+ migrations from being rewritten while that baseline catches
    up. Future schema changes must use a new Alembic revision.
    """
    script = _script_directory()
    chain = _linear_revision_chain(script)
    chain_ids = [revision.revision for revision in chain]

    baseline_manifest = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    baseline = baseline_manifest.get("baseline_revision")
    released_manifest = json.loads(RELEASED_MIGRATIONS_PATH.read_text(encoding="utf-8"))
    frozen_through = released_manifest.get("frozen_through_revision")
    blobs = released_manifest.get("files")

    assert isinstance(baseline, str) and baseline in chain_ids
    assert isinstance(frozen_through, str) and frozen_through in chain_ids
    assert isinstance(blobs, dict) and blobs

    head_side = chain_ids.index(frozen_through)
    baseline_side = chain_ids.index(baseline)
    assert head_side < baseline_side, (
        f"released migration freeze {frozen_through} must be newer than rollback baseline {baseline}"
    )

    released_revisions = chain[head_side:baseline_side]
    expected_files = {Path(revision.path).name for revision in released_revisions}
    assert set(blobs) == expected_files, (
        "released migration manifest must freeze exactly the post-baseline range; "
        f"missing={sorted(expected_files - set(blobs))}, extra={sorted(set(blobs) - expected_files)}"
    )

    for revision in released_revisions:
        path = Path(revision.path)
        expected_blob = blobs[path.name]
        assert isinstance(expected_blob, str) and len(expected_blob) == 40, (
            f"released migration manifest contains an invalid Git blob SHA for {path.name}"
        )
        assert _git_blob_sha(path) == expected_blob, f"released migration history changed: {path.name}"
