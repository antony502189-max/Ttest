"""Index external-import history retention and baseline lookups.

Revision ID: 0029_import_run_retention
Revises: 0028_data_retention_indexes
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0029_import_run_retention"
down_revision: str | None = "0028_data_retention_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_external_import_runs_finished_at",
        "external_import_runs",
        ["finished_at"],
        unique=False,
    )
    op.create_index(
        "ix_external_import_runs_source_result_finished_at",
        "external_import_runs",
        ["source_name", "result", "finished_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_import_runs_source_result_finished_at",
        table_name="external_import_runs",
    )
    op.drop_index("ix_external_import_runs_finished_at", table_name="external_import_runs")
