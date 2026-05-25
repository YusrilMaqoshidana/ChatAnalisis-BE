"""REST endpoints for async topic training and progress lookup."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.schemas import BaseResponse, JobProgressResponse
from app.services.preprocessing_service import validate_upload_meta, validate_upload_size
from app.services.progress_service import ProgressService
from app.services.topic_model_service import TopicModelService
from app.services.topic_training_service import TopicTrainingService

router = APIRouter(prefix="/topics", tags=["Topics"])

_progress_service = ProgressService()
_topic_model_service = TopicModelService()
_training_service = TopicTrainingService(
    progress_service=_progress_service,
    topic_model_service=_topic_model_service,
)


@router.post(
    "/train",
    response_model=BaseResponse[dict],
    response_model_exclude_none=True,
    status_code=status.HTTP_202_ACCEPTED,
)
async def train_topics(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    timeframe: str = Form(default=""),
) -> BaseResponse[dict]:
    """Accept upload and start async BERTopic training job in background."""
    filename = file.filename or ""

    try:
        filename, normalized_timeframe = validate_upload_meta(filename, timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        content = await asyncio.wait_for(file.read(), timeout=settings.UPLOAD_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=f"Upload melebihi batas waktu ({settings.UPLOAD_TIMEOUT_SECONDS}s).",
        ) from exc

    try:
        validate_upload_size(content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    job_id = str(uuid.uuid4())
    await _progress_service.set_progress(job_id, "processing", 5, "Validating upload")

    background_tasks.add_task(
        _training_service.process_training_job,
        job_id,
        filename,
        normalized_timeframe,
        content,
    )

    return BaseResponse(
        status="success",
        message="Training started",
        data={"job_id": job_id},
    )


@router.get(
    "/progress/{job_id}",
    response_model=BaseResponse[JobProgressResponse],
    response_model_exclude_none=True,
)
async def get_training_progress(job_id: str) -> BaseResponse[JobProgressResponse]:
    """Return current progress state for an async training job."""
    payload = await _progress_service.get_progress(job_id)

    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job tidak ditemukan")

    return BaseResponse(
        status="success",
        message="Job progress",
        data=JobProgressResponse(
            job_id=str(payload.get("job_id", job_id)),
            status=str(payload.get("status", "unknown")),
            progress=int(payload.get("progress", 0)),
            message=str(payload.get("message", "")),
        ),
    )
