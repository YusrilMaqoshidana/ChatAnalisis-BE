"""Redis client helpers for progress tracking."""

from __future__ import annotations

from redis.asyncio import Redis

from app.config import settings


def get_redis_client() -> Redis:
    """Create async Redis client for application state operations."""
    return Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis_client(client: Redis) -> None:
    """Close async Redis client safely."""
    await client.aclose()
