from __future__ import annotations

import logging

from redis import Redis
from redis.asyncio import from_url
from redis.exceptions import RedisError

from .config import get_settings

logger = logging.getLogger(__name__)
FAILED_STORAGE_DELETIONS_KEY = "ttest:failed-storage-deletions"


def record_failed_storage_deletion(storage_key: str) -> bool:
    """Best-effort durable handoff when object deletion fails outside a DB transaction."""
    settings = get_settings()
    if not storage_key or not settings.redis_url:
        return False
    client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        return bool(client.sadd(FAILED_STORAGE_DELETIONS_KEY, storage_key))
    except RedisError:
        logger.exception("failed_storage_deletion_buffer_write_failed")
        return False
    finally:
        client.close()


async def read_failed_storage_deletions(limit: int) -> list[str]:
    settings = get_settings()
    if limit < 1 or not settings.redis_url:
        return []
    client = from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        cursor = 0
        result: list[str] = []
        while len(result) < limit:
            cursor, members = await client.sscan(
                FAILED_STORAGE_DELETIONS_KEY,
                cursor=cursor,
                count=limit - len(result),
            )
            result.extend(str(member) for member in members)
            if cursor == 0:
                break
        return result[:limit]
    except RedisError:
        logger.exception("failed_storage_deletion_buffer_read_failed")
        return []
    finally:
        await client.aclose()


async def acknowledge_failed_storage_deletions(storage_keys: list[str]) -> None:
    settings = get_settings()
    if not storage_keys or not settings.redis_url:
        return
    client = from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        await client.srem(FAILED_STORAGE_DELETIONS_KEY, *storage_keys)
    except RedisError:
        # PostgreSQL already contains idempotent jobs. Leaving Redis members in
        # place only causes a safe duplicate handoff on the next iteration.
        logger.exception("failed_storage_deletion_buffer_ack_failed")
    finally:
        await client.aclose()
