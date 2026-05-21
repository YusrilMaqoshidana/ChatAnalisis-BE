"""
Redis cache helpers.
====================
Helper ringan untuk read/write payload Redis yang dipakai oleh queue/ARQ.
"""

import json
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings

REDIS_PAYLOAD_TTL_SECONDS = 60 * 60


def _redis_settings() -> RedisSettings:
    """Parse REDIS_URL → RedisSettings untuk ARQ."""
    parsed = urlparse(settings.REDIS_URL)
    database = int(parsed.path.lstrip("/") or 0)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=database,
    )


async def get_redis_pool():
    """Buat pool Redis untuk operasi cache/queue."""
    return await create_pool(_redis_settings())


async def cache_set_json(key: str, value: list[dict], ttl: int = REDIS_PAYLOAD_TTL_SECONDS) -> None:
    """Simpan payload JSON dengan TTL."""
    pool = await get_redis_pool()
    try:
        await pool.set(key, json.dumps(value, default=str), ex=ttl)
    finally:
        await pool.aclose()


async def cache_get_json(key: str):
    """Ambil payload JSON dari Redis."""
    pool = await get_redis_pool()
    try:
        raw_value = await pool.get(key)
        if raw_value is None:
            return None
        if isinstance(raw_value, bytes):
            raw_value = raw_value.decode("utf-8")
        return json.loads(raw_value)
    finally:
        await pool.aclose()
