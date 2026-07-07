"""REST endpoint for simple chat analysis."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from minio import Minio
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration
from minio.commonconfig import Filter

from app.config import settings
from app.schemas import BaseResponse

router = APIRouter(tags=["Analysis"])

def _minio_client() -> Minio:
    """Create configured MinIO client."""
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )

def _ensure_bucket_with_lifecycle(client: Minio, bucket_name: str) -> None:
    """Ensure bucket exists and has lifecycle policy for auto delete (1 day)."""
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
    
    # Configure lifecycle for auto-delete after 1 day
    try:
        rule = Rule(
            rule_id="auto-delete-rule",
            status="Enabled",
            expiration=Expiration(days=1),
            rule_filter=Filter(prefix="")
        )
        config = LifecycleConfig([rule])
        client.set_bucket_lifecycle(bucket_name, config)
    except Exception as e:
        # Don't fail the request if lifecycle policy can't be set (e.g. MinIO mock/offline policy limits)
        print(f"Warning: Failed to set bucket lifecycle: {e}")

def parse_date(date_str: str) -> datetime | None:
    """Parse date string into datetime object with multiple format support."""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S", 
        "%Y-%m-%d %H:%M", 
        "%Y-%m-%d", 
        "%d/%m/%Y %H:%M:%S", 
        "%d/%m/%Y %H:%M", 
        "%d/%m/%Y",
        "%d/%m/%y %I.%M %p",
        "%d/%m/%y %H.%M",
        "%d/%m/%y %H:%M"
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None

@router.post(
    "/analysis",
    response_model=BaseResponse[dict],
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
)
async def analyze_chat(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    startDate: str = Form(None),
    endDate: str = Form(None),
) -> BaseResponse[dict]:
    """
    Process Chat CSV file:
    - Slice by startDate and endDate.
    - Keep only index, timestamp, pengirim, pesan columns.
    - Save to MinIO as '{session_id}.csv' (original context)
    - Run WhatsApp message pre-processing steps.
    - Save pre-processed files as 'post_processing_{session_id}.csv' and 'post_preprocessing_{session_id}.csv'.
    """
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
        import pandas as pd
        from app.utils.preprocessing import preprocess_dataframe

        content_str = content_bytes.decode("utf-8", errors="ignore")
        df_raw = pd.read_csv(io.StringIO(content_str), dtype=str)
        
        if df_raw.empty or len(df_raw.columns) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="CSV tidak valid atau kosong."
            )
        
        # Clean column names
        df_raw.columns = [c.strip() for c in df_raw.columns]
        
        # Mapping headers
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
                
        # Fallback to column order if not matched
        if not ts_col and len(df_raw.columns) > 0:
            ts_col = df_raw.columns[0]
        if not sender_col and len(df_raw.columns) > 1:
            sender_col = df_raw.columns[1]
        if not msg_col and len(df_raw.columns) > 2:
            msg_col = df_raw.columns[2]

        # Extract mapped columns
        df = pd.DataFrame()
        df["timestamp"] = df_raw[ts_col] if ts_col else ""
        df["pengirim"] = df_raw[sender_col] if sender_col else ""
        df["pesan"] = df_raw[msg_col] if msg_col else ""
        
        # Date parsing and filtering
        parsed_dates = df["timestamp"].apply(parse_date)
        
        start_dt = parse_date(startDate) if startDate else None
        end_dt = parse_date(endDate) if endDate else None
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
        
        # Standardize timestamp string
        df["timestamp"] = parsed_dates[mask_date].apply(
            lambda dt: dt.isoformat(sep=" ", timespec="seconds") if pd.notna(dt) else ""
        )
        
        # Add index
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

    # 4. Generate CSV for original context
    original_csv_str = df.to_csv(index=False)
    original_csv_bytes = original_csv_str.encode("utf-8")

    # 5. Run preprocessing pipeline
    try:
        df_preprocessed = preprocess_dataframe(df)
        cols_to_save = ["index", "timestamp", "pengirim", "pesan", "Pesan_Preprocessed"]
        # Ensure we only export columns that exist
        cols_to_save = [c for c in cols_to_save if c in df_preprocessed.columns]
        preprocessed_csv_str = df_preprocessed[cols_to_save].to_csv(index=False)
        preprocessed_csv_bytes = preprocessed_csv_str.encode("utf-8")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menjalankan preprocessing: {str(exc)}"
        )

    # 6. Save/Upload all files to MinIO
    try:
        client = _minio_client()
        bucket_name = settings.MINIO_BUCKET
        _ensure_bucket_with_lifecycle(client, bucket_name)
        
        # Original context file
        orig_object_name = f"{session_id}.csv"
        client.put_object(
            bucket_name=bucket_name,
            object_name=orig_object_name,
            data=io.BytesIO(original_csv_bytes),
            length=len(original_csv_bytes),
            content_type="text/csv",
        )
        
        # Preprocessed files (uploaded as post_processing_{session_id}.csv and post_preprocessing_{session_id}.csv)
        post_proc_object_name = f"post_processing_{session_id}.csv"
        client.put_object(
            bucket_name=bucket_name,
            object_name=post_proc_object_name,
            data=io.BytesIO(preprocessed_csv_bytes),
            length=len(preprocessed_csv_bytes),
            content_type="text/csv",
        )
        
        post_preproc_object_name = f"post_preprocessing_{session_id}.csv"
        client.put_object(
            bucket_name=bucket_name,
            object_name=post_preproc_object_name,
            data=io.BytesIO(preprocessed_csv_bytes),
            length=len(preprocessed_csv_bytes),
            content_type="text/csv",
        )
        
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengunggah ke MinIO: {str(exc)}"
        )

    return BaseResponse(
        status="success",
        message="Analisis dan pre-processing selesai, disimpan di MinIO",
        data={
            "session_id": session_id,
            "original_filename": orig_object_name,
            "preprocessed_filename": post_proc_object_name,
            "bucket": bucket_name,
            "original_row_count": len(df),
            "preprocessed_row_count": len(df_preprocessed),
        }
    )

