from sqlalchemy import text

from app.database import engine
from app.models import Base
from app.cache import get_redis_pool


async def reset_database():
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)


async def reset_redis():
    pool = await get_redis_pool()
    try:
        await pool.flushdb()
    finally:
        await pool.aclose()