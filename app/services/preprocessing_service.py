"""Preprocessing service for chat upload payloads."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.utils import apply_full_preprocessing, filter_messages_by_timeframe, parse_whatsapp_txt_bytes

_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".txt", ".zip"})
_SKIP_ZIP_SUFFIXES: tuple[str, ...] = (".vcf",)
_ALLOWED_TIMEFRAMES: frozenset[str] = frozenset({"all", "week", "month", "year"})


def validate_upload_meta(filename: str, timeframe: str) -> tuple[str, str]:
    """Validate filename extension and timeframe values."""
    normalized_filename = filename.strip()
    normalized_timeframe = timeframe.strip().lower()

    if not normalized_filename:
        raise ValueError("Field 'filename' wajib diisi.")

    ext = Path(normalized_filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise ValueError("Format file tidak didukung. Gunakan .txt atau .zip.")

    if normalized_timeframe and normalized_timeframe not in _ALLOWED_TIMEFRAMES:
        raise ValueError("timeframe tidak valid. Gunakan: all, week, month, atau year.")

    return normalized_filename, normalized_timeframe or "all"


def validate_upload_size(content: bytes) -> None:
    """Validate empty payload and maximum raw upload size."""
    if not content:
        raise ValueError("Konten file kosong.")

    if len(content) > settings.max_file_size_bytes:
        raise ValueError(f"Ukuran file melebihi batas {settings.MAX_FILE_SIZE_MB} MB.")


def extract_messages(filename: str, content: bytes) -> list[dict]:
    """Parse chat rows from txt/zip payload bytes."""
    ext = Path(filename).suffix.lower()

    if ext == ".zip":
        _check_zip_safety(content)
        messages = _parse_zip(content)
    else:
        messages = parse_whatsapp_txt_bytes(content)

    if not messages:
        raise ValueError("Tidak ada pesan yang berhasil diparsing dari file.")

    return messages


def prepare_messages(messages: list[dict], timeframe: str) -> list[dict]:
    """Filter chat by timeframe and apply text preprocessing pipeline."""
    bounds = _get_date_bounds(messages)
    if bounds is None:
        raise ValueError("Tidak ada timestamp valid pada data chat.")

    _earliest, latest = bounds

    normalized_timeframe = timeframe.strip().lower()
    if normalized_timeframe in {"", "all"}:
        filtered = messages
    else:
        filtered, _ = filter_messages_by_timeframe(
            messages,
            timeframe=normalized_timeframe,
            anchor_date=latest.date(),
        )

    if not filtered:
        raise ValueError("Tidak ada pesan pada timeframe yang dipilih.")

    preprocessed, _stats = apply_full_preprocessing(filtered)
    if not preprocessed:
        raise ValueError("Tidak ada pesan tersisa setelah preprocessing.")

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

    tanggal = str(row.get("tanggal", "")).strip()
    waktu = str(row.get("waktu", "")).strip()
    if tanggal and waktu:
        for fmt in ("%d/%m/%y %I.%M %p", "%d/%m/%y %H.%M", "%d/%m/%y %H:%M"):
            try:
                return datetime.strptime(f"{tanggal} {waktu}", fmt)
            except ValueError:
                continue

    return None


def _check_zip_safety(content: bytes) -> None:
    max_bytes = settings.ZIP_MAX_EXTRACTED_MB * 1024 * 1024

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            total_extracted = sum(
                i.file_size
                for i in zf.infolist()
                if not i.is_dir() and not i.filename.lower().endswith(_SKIP_ZIP_SUFFIXES)
            )
    except zipfile.BadZipFile as exc:
        raise ValueError("File ZIP tidak valid atau rusak.") from exc

    if total_extracted > max_bytes:
        raise ValueError(
            f"Konten ZIP melebihi batas {settings.ZIP_MAX_EXTRACTED_MB} MB."
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
    except zipfile.BadZipFile as exc:
        raise ValueError("File ZIP tidak valid atau rusak.") from exc

    return rows
