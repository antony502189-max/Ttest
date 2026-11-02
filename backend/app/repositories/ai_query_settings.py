"""Transaction-local settings for the verified AI query path."""
from sqlalchemy import text


async def configure_ai_query(session):
    # These short correlated queries spend more on JIT compilation than they
    # save. LOCAL restores the caller's setting on commit, rollback or cancel,
    # including reuse of the same physical pool connection.
    await session.execute(text("SET LOCAL jit = off").execution_options(ai_query_config=True))
