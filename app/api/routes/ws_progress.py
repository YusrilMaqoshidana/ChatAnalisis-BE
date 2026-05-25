"""WebSocket endpoint for streaming background job progress updates."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.schemas import WSProgressMessage
from app.services.progress_service import ProgressService

router = APIRouter(tags=["Topics"])

_progress_service = ProgressService()
_POLL_SECONDS = 1.0
_KEEPALIVE_SECONDS = 10.0


@router.websocket("/topics/ws/{job_id}")
async def stream_training_progress(websocket: WebSocket, job_id: str) -> None:
    """Stream progress updates for a training job until it reaches a terminal state."""
    await websocket.accept()

    last_payload: str | None = None
    loop = asyncio.get_running_loop()
    last_sent = loop.time()

    try:
        while True:
            payload = await _progress_service.get_progress(job_id)

            if payload is None:
                await websocket.send_json(
                    WSProgressMessage(status="error", message="Job tidak ditemukan").model_dump(exclude_none=True)
                )
                return

            serialized = json.dumps(payload, sort_keys=True)
            now = loop.time()
            # Send update if payload changed or if keepalive interval passed
            if serialized != last_payload or (now - last_sent) >= _KEEPALIVE_SECONDS:
                await websocket.send_json(
                    WSProgressMessage(
                        status=str(payload.get("status", "unknown")),
                        message=str(payload.get("message", "")),
                        data=payload,
                    ).model_dump(exclude_none=True)
                )
                last_payload = serialized
                last_sent = now

            status = str(payload.get("status", "")).lower()
            if status in {"done", "error"}:
                return

            await asyncio.sleep(_POLL_SECONDS)
    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except Exception:
            return
