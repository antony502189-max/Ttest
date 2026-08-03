from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.session import engine

pytestmark = pytest.mark.integration


async def test_asyncpg_connections_receive_execution_budgets() -> None:
    async with engine.connect() as connection:
        statement_timeout = await connection.scalar(text("SELECT current_setting('statement_timeout')"))
        lock_timeout = await connection.scalar(text("SELECT current_setting('lock_timeout')"))

    # PostgreSQL normalizes equivalent values to human-readable forms.
    assert statement_timeout in {"1min", "60s", "60000ms"}
    assert lock_timeout in {"10s", "10000ms"}
