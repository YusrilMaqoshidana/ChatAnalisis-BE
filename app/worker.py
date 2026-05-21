"""
Background Job Tasks
===================
ARQ worker tasks untuk async processing.

Task membaca payload dari Redis key yang sama dengan queue.py.
Train membuat model BERTopic modifikasi, infer memuat model yang sudah disimpan.
"""

from __future__ import annotations

import logging
import uuid
from importlib import import_module
from pathlib import Path

from arq.connections import RedisSettings
from sqlalchemy import select

from app.cache import _redis_settings, cache_get_json
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Job


logger = logging.getLogger(__name__)


async def _load_payload(redis_key: str) -> list[dict]:
    payload = await cache_get_json(redis_key)
    if payload is None:
        raise RuntimeError(f"Payload Redis tidak ditemukan untuk key: {redis_key}")

    if not isinstance(payload, list):
        raise RuntimeError(f"Payload Redis harus berupa list, key: {redis_key}")

    return payload


def _extract_documents(messages: list[dict]) -> list[str]:
    documents: list[str] = []

    for row in messages:
        if not isinstance(row, dict):
            continue

        text = str(row.get("pesan_preprocessed") or row.get("pesan") or "").strip()
        if text:
            documents.append(text)

    return documents


def _model_path(model_id: str) -> Path:
    return Path(settings.MODEL_DIR) / model_id


def _ensure_model_dir() -> Path:
    model_dir = Path(settings.MODEL_DIR)
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir


async def _update_job_status(job_id: str, status: str, error_msg: str | None = None) -> None:
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Job).where(Job.id == job_uuid))
        job = result.scalars().first()
        if job is None:
            return

        job.status = status
        job.error_msg = error_msg
        await session.commit()
        logger.info("[job:%s] status -> %s", job_id, status)


async def _build_modified_model():
    try:
        topic_model_module = import_module("app.ml.topic_model")
    except ImportError as exc:  # pragma: no cover - depends on NLP stack
        raise RuntimeError(
            "Dependency BERTopic/NLP belum tersedia. Jalankan install requirements terlebih dahulu."
        ) from exc

    return topic_model_module.build_modified_bertopic_model()


async def train_task(ctx, redis_key: str, job_id: str) -> dict:
    """
    Train BERTopic model dengan messages yang disimpan di Redis.

    Args:
        ctx: Context ARQ (tidak dipakai saat ini).
        redis_key: Key Redis yang berisi payload messages.
        job_id: Identifier job untuk tracing.
    """
    logger.info("[train:%s] start redis_key=%s", job_id, redis_key)
    await _update_job_status(job_id, "running")

    try:
        logger.info("[train:%s] load payload", job_id)
        messages = await _load_payload(redis_key)

        logger.info("[train:%s] extract documents from payload=%d", job_id, len(messages))
        documents = _extract_documents(messages)

        if not documents:
            raise RuntimeError(f"Tidak ada pesan preprocessed yang bisa dipakai train untuk key: {redis_key}")

        logger.info("[train:%s] build BERTopic model", job_id)
        topic_model = await _build_modified_model()

        logger.info("[train:%s] fit_transform documents=%d", job_id, len(documents))
        topics, _probabilities = topic_model.fit_transform(documents)

        model_dir = _ensure_model_dir()
        model_path = model_dir / job_id
        logger.info("[train:%s] save model path=%s", job_id, model_path)
        topic_model.save(str(model_path))

        await _update_job_status(job_id, "done")
        logger.info("[train:%s] done topic_count=%d", job_id, len({topic for topic in topics if topic != -1}))

        return {
            "job_id": job_id,
            "task": "train_task",
            "redis_key": redis_key,
            "message_count": len(documents),
            "topic_count": len({topic for topic in topics if topic != -1}),
            "model_path": str(model_path),
            "status": "trained",
        }
    except Exception as exc:
        logger.exception("[train:%s] error: %s", job_id, exc)
        await _update_job_status(job_id, "error", str(exc))
        raise


async def infer_task(ctx, redis_key: str, job_id: str, model_id: str) -> dict:
    """
    Run inference pada model tertentu menggunakan payload dari Redis.

    Args:
        ctx: Context ARQ (tidak dipakai saat ini).
        redis_key: Key Redis yang berisi payload messages.
        job_id: Identifier job untuk tracing.
        model_id: UUID model yang akan dipakai infer.
    """
    await _update_job_status(job_id, "running")

    try:
        messages = await _load_payload(redis_key)
        documents = _extract_documents(messages)

        if not documents:
            raise RuntimeError(f"Tidak ada pesan preprocessed yang bisa dipakai infer untuk key: {redis_key}")

        model_path = _model_path(model_id)
        if not model_path.exists():
            raise RuntimeError(f"Model tidak ditemukan di path: {model_path}")

        try:
            bertopic_module = import_module("bertopic")
        except ImportError as exc:  # pragma: no cover - depends on NLP stack
            raise RuntimeError(
                "Dependency BERTopic/NLP belum tersedia. Jalankan install requirements terlebih dahulu."
            ) from exc

        topic_model = bertopic_module.BERTopic.load(str(model_path))
        topics, probabilities = topic_model.transform(documents)

        await _update_job_status(job_id, "done")

        return {
            "job_id": job_id,
            "task": "infer_task",
            "redis_key": redis_key,
            "model_id": model_id,
            "message_count": len(documents),
            "topic_count": len({topic for topic in topics if topic != -1}),
            "topics": [int(topic) for topic in topics],
            "probabilities": probabilities.tolist() if hasattr(probabilities, "tolist") and probabilities is not None else None,
            "status": "inferred",
        }
    except Exception as exc:
        await _update_job_status(job_id, "error", str(exc))
        raise


# ARQ job definitions
class WorkerSettings:
    functions = [train_task, infer_task]
    redis_settings: RedisSettings = _redis_settings()
    cron_jobs = []
