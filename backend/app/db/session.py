from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.config import Settings, get_settings


def database_server_settings(settings: Settings) -> dict[str, str]:
    """Apply execution budgets to every asyncpg application connection."""
    return {
        "statement_timeout": f"{settings.database_statement_timeout_ms}ms",
        "lock_timeout": f"{settings.database_lock_timeout_ms}ms",
        "idle_in_transaction_session_timeout": f"{settings.database_idle_transaction_timeout_ms}ms",
    }


settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout_seconds,
    pool_recycle=settings.database_pool_recycle_seconds,
    pool_use_lifo=True,
    connect_args={"server_settings": database_server_settings(settings)},
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
