from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.messages import thread_list_query, thread_messages


def test_thread_list_query_is_bounded_and_offset():
    query = thread_list_query(
        UUID("00000000-0000-4000-8000-000000000001"),
        limit=100,
        offset=25,
    )
    sql = str(query.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "LIMIT 100" in sql
    assert "OFFSET 25" in sql


@pytest.mark.asyncio
async def test_message_page_returns_newest_bounded_page_in_display_order():
    now = datetime.now(UTC)
    newest = SimpleNamespace(id=uuid4(), created_at=now)
    older = SimpleNamespace(id=uuid4(), created_at=now)

    class Result:
        def all(self):
            # Database order is newest first.
            return [newest, older]

    class Session:
        statement = None

        async def scalars(self, statement):
            self.statement = statement
            return Result()

    session = Session()
    rows = await thread_messages(session, uuid4(), limit=2, offset=3)  # type: ignore[arg-type]

    assert rows == [older, newest]
    sql = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "LIMIT 2" in sql
    assert "OFFSET 3" in sql
