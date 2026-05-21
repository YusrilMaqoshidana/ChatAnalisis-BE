import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import REDIS_PAYLOAD_TTL_SECONDS, cache_set_json, get_redis_pool
from app.models import Job


async def enqueue_train(messages: list[dict], db: AsyncSession) -> str:
    """Simpan payload → buat job → enqueue train_task. Return job_id."""
    job_id = str(uuid.uuid4())
    redis_key = f"payload:{job_id}"

    # 1. Simpan payload ke Redis (TTL 1 jam)
    await cache_set_json(redis_key, messages, ttl=REDIS_PAYLOAD_TTL_SECONDS)

    # 2. INSERT job ke database
    job = Job(
        id=uuid.UUID(job_id),
        type="train",
        status="queued",
    )
    db.add(job)
    await db.commit()

    # 3. Enqueue ARQ task
    pool = await get_redis_pool()
    try:
        await pool.enqueue_job("train_task", redis_key, job_id)
    finally:
        await pool.aclose()

    return job_id


async def enqueue_infer(messages: list[dict], model_id: str, db: AsyncSession) -> str:
    """Simpan payload → buat job → enqueue infer_task. Return job_id."""
    job_id = str(uuid.uuid4())
    redis_key = f"payload:{job_id}"

    # 1. Simpan payload ke Redis (TTL 1 jam)
    await cache_set_json(redis_key, messages, ttl=REDIS_PAYLOAD_TTL_SECONDS)

    # 2. INSERT job ke database
    job = Job(
        id=uuid.UUID(job_id),
        type="infer",
        status="queued",
        model_id=uuid.UUID(model_id),
    )
    db.add(job)
    await db.commit()

    # 3. Enqueue ARQ task
    pool = await get_redis_pool()
    try:
        await pool.enqueue_job("infer_task", redis_key, job_id, model_id)
    finally:
        await pool.aclose()

    return job_id