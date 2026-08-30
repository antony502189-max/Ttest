from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import engine

pytestmark = pytest.mark.integration

# These objects are owned by Alembic itself or the PostGIS extension rather
# than by the application ORM. They must not be interpreted as application
# schema drift.
IGNORED_REFLECTED_TABLES = {
    "alembic_version",
    "geography_columns",
    "geometry_columns",
    "spatial_ref_sys",
}

# The original 0001/0009 migrations created these server-defaulted timestamp
# columns without NOT NULL. The ORM has always treated them as required values,
# but tightening historical production columns in this hardening PR would be a
# contract migration and could narrow rollback compatibility. Keep this exact,
# directional exception until a dedicated backfill + NOT NULL contract migration
# is explicitly approved. All other nullability drift remains fail-closed.
LEGACY_DB_NULLABLE_ORM_REQUIRED_COLUMNS = {
    ("auth_sessions", "issued_at"),
    ("listing_views", "created_at"),
    ("listings", "created_at"),
    ("listings", "updated_at"),
    ("users", "created_at"),
    ("users", "updated_at"),
}

# Historical migrations intentionally own several physical indexes/check
# constraints that are not mirrored one-for-one in ORM metadata. The parity
# contract therefore focuses on destructive/high-risk drift that must never be
# silently accepted: tables, columns, column types and nullability.
SCHEMA_CONTRACT_DIFF_KINDS = {
    "add_table",
    "remove_table",
    "add_column",
    "remove_column",
    "modify_type",
    "modify_nullable",
}


def _include_application_object(
    object_: Any,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: Any,
) -> bool:
    del object_, compare_to
    return not (reflected and type_ == "table" and name in IGNORED_REFLECTED_TABLES)


def _flatten_diffs(value: Any) -> Iterator[tuple[Any, ...]]:
    """Yield Alembic diff tuples from its occasionally nested result shape."""
    if isinstance(value, tuple):
        yield value
        return
    if isinstance(value, list):
        for item in value:
            yield from _flatten_diffs(item)


def _is_documented_legacy_nullable_diff(diff: tuple[Any, ...]) -> bool:
    """Ignore only the known DB-nullable -> ORM-required historical mismatch."""
    if len(diff) < 7 or str(diff[0]) != "modify_nullable":
        return False
    table_name = str(diff[2])
    column_name = str(diff[3])
    existing_nullable = diff[-2]
    metadata_nullable = diff[-1]
    return (
        (table_name, column_name) in LEGACY_DB_NULLABLE_ORM_REQUIRED_COLUMNS
        and existing_nullable is True
        and metadata_nullable is False
    )


def _describe_diff(diff: tuple[Any, ...]) -> str:
    kind = str(diff[0]) if diff else "unknown"
    if kind in {"add_table", "remove_table"} and len(diff) >= 2:
        table = getattr(diff[1], "name", repr(diff[1]))
        return f"{kind}: {table}"
    if kind in {"add_column", "remove_column"} and len(diff) >= 4:
        column = getattr(diff[3], "name", repr(diff[3]))
        return f"{kind}: {diff[2]}.{column}"
    if kind in {"modify_type", "modify_nullable"} and len(diff) >= 4:
        return f"{kind}: {diff[2]}.{diff[3]}"
    return repr(diff)


async def test_migrated_postgresql_schema_matches_application_column_contract() -> None:
    """Fail when a migrated PostgreSQL database drifts from application models.

    Production CI applies the complete Alembic chain before running integration
    tests. This test therefore validates the schema produced by the migrations,
    not an in-memory/mock representation. It specifically closes the gap left
    by ``alembic/env.py`` intentionally ignoring non-table autogenerate noise.
    """

    async with engine.connect() as connection:
        def compare(sync_connection):
            context = MigrationContext.configure(
                sync_connection,
                opts={
                    "include_object": _include_application_object,
                    "compare_type": True,
                    "compare_server_default": False,
                },
            )
            return compare_metadata(context, Base.metadata)

        raw_diffs = await connection.run_sync(compare)

    contract_diffs = [
        diff
        for diff in _flatten_diffs(raw_diffs)
        if diff
        and str(diff[0]) in SCHEMA_CONTRACT_DIFF_KINDS
        and not _is_documented_legacy_nullable_diff(diff)
    ]

    assert not contract_diffs, (
        "PostgreSQL schema drifted from the application table/column contract:\n"
        + "\n".join(f"- {_describe_diff(diff)}" for diff in contract_diffs)
    )
