from __future__ import annotations

import io
import json
import logging
import pandas as pd
from typing import Dict, List

from fastapi import (
    APIRouter, 
    File, 
    Form, 
    HTTPException, 
    UploadFile, 
    status, 
    BackgroundTasks
)
from fastapi.responses import StreamingResponse
import asyncio

from app.infrastructure.sse import progress_history, sse_manager
from app.services import analysis_service
from app.schemas import (
    BaseResponse,
    ResultsSummaryDTO,
    TopicDetailDTO,
    MessageContextDTO
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analysis"])

def validate_session_id(session_id: str) -> None:
    import re
    if not session_id or not re.match(r"^[a-zA-Z0-9_-]+$", session_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ID Sesi tidak valid (hanya alfanumerik, dash, dan underscore yang diperbolehkan)."
        )

@router.post(
    "/analysis",
    response_model=BaseResponse[dict],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
async def analyze_chat(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: str = Form(...),
    startDate: str = Form(None),
    endDate: str = Form(None),
) -> BaseResponse[dict]:
    """
    Process Chat CSV file in background:
    - Slice by startDate and endDate.
    - Save slice to local storage.
    - Run the pre-processing and BERTopic pipeline asynchronously.
    - Returns immediately to prevent HTTP timeouts.
    """
    # Validate session_id to prevent path traversal
    validate_session_id(session_id)

    # 1. Validate file extension
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format file tidak didukung. Harap upload file CSV."
        )

    # 2. Read file content
    try:
        content_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membaca file: {str(exc)}"
        )

    if not content_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File kosong."
        )

    # 3. Parse CSV and filter by date using Pandas
    try:
        content_str = content_bytes.decode("utf-8", errors="ignore")
        df_raw = pd.read_csv(io.StringIO(content_str), dtype=str)
        
        if df_raw.empty or len(df_raw.columns) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV tidak valid atau kosong."
            )
        
        df_raw.columns = [c.strip() for c in df_raw.columns]
        
        ts_candidates = ["timestamp", "tanggal", "datetime", "date", "created_at"]
        sender_candidates = ["pengirim", "sender", "author", "name", "username"]
        msg_candidates = ["pesan", "message", "text", "content", "body"]
        
        ts_col = None
        sender_col = None
        msg_col = None
        
        for col in df_raw.columns:
            col_lower = col.lower()
            if not ts_col and any(cand in col_lower for cand in ts_candidates):
                ts_col = col
            if not sender_col and any(cand in col_lower for cand in sender_candidates):
                sender_col = col
            if not msg_col and any(cand in col_lower for cand in msg_candidates):
                msg_col = col
                
        if not ts_col and len(df_raw.columns) > 0:
            ts_col = df_raw.columns[0]
        if not sender_col and len(df_raw.columns) > 1:
            sender_col = df_raw.columns[1]
        if not msg_col and len(df_raw.columns) > 2:
            msg_col = df_raw.columns[2]

        df = pd.DataFrame()
        df["timestamp"] = df_raw[ts_col] if ts_col else ""
        df["pengirim"] = df_raw[sender_col] if sender_col else ""
        df["pesan"] = df_raw[msg_col] if msg_col else ""
        
        parsed_dates = df["timestamp"].apply(analysis_service.parse_date)
        
        start_dt = analysis_service.parse_date(startDate) if startDate else None
        end_dt = analysis_service.parse_date(endDate) if endDate else None
        if end_dt and len(endDate.strip()) <= 10:
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)

        mask_date = pd.Series(True, index=df.index)
        if start_dt or end_dt:
            valid_dates = parsed_dates.notna()
            mask_date = mask_date & valid_dates
            if start_dt:
                mask_date = mask_date & (parsed_dates >= start_dt)
            if end_dt:
                mask_date = mask_date & (parsed_dates <= end_dt)
                
        df = df[mask_date].copy()
        df["timestamp"] = parsed_dates[mask_date].apply(
            lambda dt: dt.isoformat(sep=" ", timespec="seconds") if pd.notna(dt) else ""
        )
        
        df = df.reset_index(drop=True)
        df["index"] = df.index
        df = df[["index", "timestamp", "pengirim", "pesan"]]
        
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gagal memproses CSV: {str(exc)}"
        )

    original_csv_str = df.to_csv(index=False)
    original_csv_bytes = original_csv_str.encode("utf-8")

    # Initialize progress history for this session
    progress_history[session_id] = [
        {"step_id": 1, "status": "completed", "time_elapsed": "10ms"},
        {"step_id": 2, "status": "running"}
    ]

    # Add task to background executor
    from app.infrastructure.storage import cleanup_old_files
    background_tasks.add_task(cleanup_old_files)
    background_tasks.add_task(
        analysis_service.run_analysis_pipeline_task,
        session_id,
        df,
        original_csv_bytes
    )

    return BaseResponse(
        status="success",
        message="Analisis obrolan berhasil dieksekusi dan disimpan.",
        data={
            "session_id": session_id,
            "original_filename": f"{session_id}.csv",
            "bucket": "local",
            "original_row_count": len(df),
        }
    )

@router.get("/api/analysis/events/{session_id}")
async def sse_endpoint(session_id: str):
    """Server-Sent Events endpoint to subscribe to real-time analysis progress logs."""
    validate_session_id(session_id)
    queue = sse_manager.get_queue(session_id)
    
    async def event_generator():
        try:
            # 1. Send all past progress first (if any)
            if session_id in progress_history:
                for event in progress_history[session_id]:
                    yield f"data: {json.dumps(event)}\n\n"
                    # If already completed or failed, close the stream
                    if event.get("done") or event.get("status") == "failed":
                        return
            
            # 2. Wait for new events from the background task
            while True:
                message = await queue.get()
                yield f"data: {json.dumps(message)}\n\n"
                
                # If the pipeline is done or failed, close the connection
                if message.get("done") or message.get("status") == "failed":
                    break
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            sse_manager.remove_queue(session_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get(
    "/api/results/{jobId}",
    response_model=BaseResponse[ResultsSummaryDTO],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def get_results_summary(jobId: str) -> BaseResponse[ResultsSummaryDTO]:
    """Retrieve summarized topic modeling results for the session/job."""
    validate_session_id(jobId)
    summary = analysis_service.get_results_summary(jobId)
    return BaseResponse(
        status="success",
        message="Ringkasan hasil analisis berhasil diambil.",
        data=summary
    )

@router.delete(
    "/api/results/{jobId}",
    response_model=BaseResponse[dict],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def delete_results(jobId: str) -> BaseResponse[dict]:
    """Delete all objects stored in local storage associated with the given jobId/session_id."""
    validate_session_id(jobId)
    data = analysis_service.delete_results(jobId)
    return BaseResponse(
        status="success",
        message="Hasil analisis berhasil dihapus dari storage.",
        data=data
    )

@router.get(
    "/api/results/{jobId}/topics/{topicId}",
    response_model=BaseResponse[TopicDetailDTO],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def get_topic_detail(jobId: str, topicId: int) -> BaseResponse[TopicDetailDTO]:
    """Retrieve detailed messages belonging to a specific topic cluster."""
    validate_session_id(jobId)
    detail = analysis_service.get_topic_detail(jobId, topicId)
    return BaseResponse(
        status="success",
        message=f"Detail klaster topik {topicId} berhasil diambil.",
        data=detail
    )

@router.get(
    "/api/results/{jobId}/messages/{messageId}/context",
    response_model=BaseResponse[MessageContextDTO],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
def get_message_context(jobId: str, messageId: str) -> BaseResponse[MessageContextDTO]:
    """Retrieve chronological context (timeline) around a specific message."""
    validate_session_id(jobId)
    context = analysis_service.get_message_context(jobId, messageId)
    return BaseResponse(
        status="success",
        message="Konteks percakapan berhasil diambil.",
        data=context
    )
