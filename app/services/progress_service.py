"""Progress service backed by Redis."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.infrastructure.redis.redis_client import close_redis_client, get_redis_client


class ProgressService:
    """Store and retrieve asynchronous job progress states."""

    @staticmethod
    def _key(job_id: str) -> str:
        return f"job:{job_id}"

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    async def set_progress(self, job_id: str, status: str, progress: int, message: str) -> dict[str, Any]:
        """Create or update progress state for a job."""
        redis = get_redis_client()
        key = self._key(job_id)

        try:
            existing_raw = await redis.get(key)
            existing = json.loads(existing_raw) if existing_raw else {}
            created_at = existing.get("created_at", self._now_iso())

            payload: dict[str, Any] = {
                "job_id": job_id,
                "status": status,
                "progress": max(0, min(100, progress)),
                "message": message,
                "created_at": created_at,
                "updated_at": self._now_iso(),
            }

            await redis.set(key, json.dumps(payload), ex=settings.PROGRESS_TTL_SECONDS)
            return payload
        finally:
            await close_redis_client(redis)

    async def get_progress(self, job_id: str) -> dict[str, Any] | None:
        """Fetch progress state for a job."""
        redis = get_redis_client()

        try:
            raw = await redis.get(self._key(job_id))
            if not raw:
                return None
            return json.loads(raw)
        finally:
            await close_redis_client(redis)

    async def set_done(self, job_id: str, message: str = "Training selesai") -> dict[str, Any]:
        """Mark job as done at 100 percent."""
        return await self.set_progress(job_id=job_id, status="done", progress=100, message=message)

    async def set_error(self, job_id: str, message: str) -> dict[str, Any]:
        """Mark job as failed while preserving the latest progress state."""
        current = await self.get_progress(job_id)
        progress = int(current.get("progress", 0)) if current else 0
        return await self.set_progress(job_id=job_id, status="error", progress=progress, message=message)
