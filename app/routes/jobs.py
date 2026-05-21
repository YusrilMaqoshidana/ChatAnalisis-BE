"""
Topics Router
=============
POST /topics/train  — upload chat → fit_transform (model baru)
POST /topics/infer  — upload chat → transform (pakai model yang sudah ada)
"""

import asyncio
import io
import logging
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Job
from app.queue import enqueue_train, enqueue_infer
from app.schemas import JobResponse, JobStatusResponse
from app.utils import (
    apply_full_preprocessing,
    filter_messages_by_timeframe,
    format_file_size,
    parse_whatsapp_txt_bytes,
)

router = APIRouter(prefix="/topics", tags=["Topics"])
limiter = Limiter(key_func=get_remote_address)
logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".txt", ".zip"})
_SKIP_ZIP_SUFFIXES: tuple[str, ...] = (".vcf",)


# ---------------------------------------------------------------------------
# POST /topics/train
# ---------------------------------------------------------------------------

@router.post(
    "/train",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Train model baru dari file chat",
)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def train(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """
    Upload file chat WhatsApp (.txt / .zip) → parsing → preprocessing
    → payload disimpan sementara di Redis → worker jalankan fit_transform().

    Return job_id untuk polling status.
    """
    logger.info("[train] upload diterima: filename=%s", file.filename)
    messages = await _extract_messages(file)
    logger.info("[train] parsing selesai: parsed_messages=%d", len(messages))

    messages = _prepare_train_messages(messages)
    logger.info("[train] preprocessing selesai: final_messages=%d", len(messages))

    job_id = await enqueue_train(messages, db)
    logger.info("[train] enqueue selesai: job_id=%s status=queued", job_id)

    return JobResponse(
        job_id=job_id,
        type="train",
        status="queued",
    )


# ---------------------------------------------------------------------------
# POST /topics/infer
# ---------------------------------------------------------------------------

@router.post(
    "/infer",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Infer topik menggunakan model yang sudah ada",
)
@limiter.limit(settings.RATE_LIMIT_UPLOAD)
async def infer(
    request: Request,
    file: UploadFile = File(...),
    topic_model_id: str = Form(..., alias="model_id", description="UUID model hasil train sebelumnya"),
    timeframe: Literal["week", "month", "year"] = Form(default="year"),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """
    Upload file chat WhatsApp (.txt / .zip) → parsing → preprocessing
    → payload disimpan sementara di Redis → worker jalankan transform()
    menggunakan model yang sudah ada.

    Return job_id untuk polling status.
    """
    # Validasi model_id adalah UUID yang valid
    try:
        uuid.UUID(topic_model_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="model_id tidak valid, harus berformat UUID.",
        )

    messages = await _extract_messages(file)
    messages = _prepare_infer_messages(messages, timeframe)

    job_id = await enqueue_infer(messages, topic_model_id, db)

    return JobResponse(
        job_id=job_id,
        type="infer",
        status="queued",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Cek status job train/infer",
)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)) -> JobStatusResponse:
    """Return status job terbaru untuk polling progress background task."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="job_id tidak valid, harus berformat UUID.",
        )

    result = await db.execute(select(Job).where(Job.id == job_uuid))
    job = result.scalars().first()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job tidak ditemukan.",
        )

    return JobStatusResponse(
        job_id=str(job.id),
        type=job.type,
        status=job.status,
        error_msg=job.error_msg,
        model_id=str(job.model_id) if job.model_id else None,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

async def _extract_messages(file: UploadFile) -> list[dict]:
    """Validasi, baca, parse file chat. Raise HTTPException jika gagal."""
    # 1. Validasi nama file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nama file tidak boleh kosong.",
        )

    # 2. Validasi ekstensi
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Format '{ext or '(tanpa ekstensi)'}' tidak didukung. "
                "Gunakan file .txt atau .zip."
            ),
        )

    # 3. Baca ke memori dengan timeout
    try:
        content = await asyncio.wait_for(
            file.read(),
            timeout=settings.UPLOAD_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail=(
                f"Upload melebihi batas waktu ({settings.UPLOAD_TIMEOUT_SECONDS}s). "
                "Coba dengan file yang lebih kecil."
            ),
        )

    # 4. Validasi ukuran
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Ukuran file ({format_file_size(len(content))}) melebihi batas "
                f"({settings.MAX_FILE_SIZE_MB} MB)."
            ),
        )

    # 5. Parse
    if ext == ".zip":
        _check_zip_bomb(content)
        messages = _parse_zip(content)
    else:
        messages = parse_whatsapp_txt_bytes(content)

    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak ada pesan yang berhasil diparsing dari file ini.",
        )

    return messages


def _prepare_train_messages(messages: list[dict]) -> list[dict]:
    """Preprocess semua pesan yang di-upload untuk train tanpa pembatasan timeframe."""
    preprocessed, _ = apply_full_preprocessing(messages)

    if not preprocessed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak ada pesan tersisa setelah preprocessing.",
        )

    return preprocessed


def _prepare_infer_messages(messages: list[dict], timeframe: str) -> list[dict]:
    """Filter timeframe lalu preprocessing untuk infer."""
    bounds = _get_date_bounds(messages)
    if bounds is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak ada pesan dengan timestamp valid.",
        )

    _, latest = bounds

    filtered, _ = filter_messages_by_timeframe(
        messages,
        timeframe=timeframe,
        anchor_date=latest.date(),
    )
    preprocessed, _ = apply_full_preprocessing(filtered)

    if not preprocessed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak ada pesan tersisa setelah preprocessing dan filter timeframe.",
        )

    return preprocessed


def _get_date_bounds(messages: list[dict]) -> tuple[datetime, datetime] | None:
    dates = [_parse_dt(m) for m in messages]
    dates = [d for d in dates if d is not None]
    if not dates:
        return None
    return min(dates), max(dates)


def _parse_dt(row: dict) -> datetime | None:
    ts = row.get("timestamp")
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str) and ts.strip():
        try:
            return datetime.fromisoformat(ts.strip())
        except ValueError:
            pass
    # Fallback format lama
    tanggal = str(row.get("tanggal", "")).strip()
    waktu = str(row.get("waktu", "")).strip()
    if tanggal and waktu:
        for fmt in ("%d/%m/%y %I.%M %p", "%d/%m/%y %H.%M", "%d/%m/%y %H:%M"):
            try:
                return datetime.strptime(f"{tanggal} {waktu}", fmt)
            except ValueError:
                continue
    return None


def _check_zip_bomb(content: bytes) -> None:
    max_bytes = settings.ZIP_MAX_EXTRACTED_MB * 1024 * 1024
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            total = sum(
                i.file_size for i in zf.infolist()
                if not i.is_dir() and not i.filename.lower().endswith(_SKIP_ZIP_SUFFIXES)
            )
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ZIP tidak valid atau rusak.",
        )
    if total > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Konten ZIP ({format_file_size(total)}) melebihi batas "
                f"({settings.ZIP_MAX_EXTRACTED_MB} MB). Kemungkinan zip bomb."
            ),
        )


def _parse_zip(content: bytes) -> list[dict]:
    rows: list[dict] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for info in zf.infolist():
                name = info.filename.lower()
                if info.is_dir() or name.endswith(_SKIP_ZIP_SUFFIXES):
                    continue
                if not name.endswith(".txt"):
                    continue
                rows.extend(parse_whatsapp_txt_bytes(zf.read(info)))
    except zipfile.BadZipFile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File ZIP tidak valid atau rusak.",
        )
    return rows