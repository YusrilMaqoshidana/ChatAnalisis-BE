"""
File Utilities
==============
Helper functions untuk operasi file.

Best Practice:
- Utility functions harus stateless dan reusable
- Validasi dilakukan di sini agar bisa dipakai di mana saja
"""

import uuid
from datetime import datetime
from pathlib import Path

from app.core.config import settings


def generate_unique_filename(original_filename: str) -> str:
    """
    Generate nama file unik untuk menghindari overwrite.
    Format: YYYYMMDD_uuid8chars_originalname

    Args:
        original_filename: Nama file asli dari client

    Returns:
        Nama file yang sudah diunikkan
    """
    date_prefix = datetime.now().strftime("%Y%m%d")
    unique_id = uuid.uuid4().hex[:8]
    return f"{date_prefix}_{unique_id}_{original_filename}"


def validate_file_extension(filename: str) -> bool:
    """
    Validasi apakah ekstensi file diperbolehkan.

    Args:
        filename: Nama file yang akan divalidasi

    Returns:
        True jika ekstensi diperbolehkan
    """
    extension = Path(filename).suffix.lower()
    return extension in settings.ALLOWED_EXTENSIONS


def validate_file_size(size_bytes: int) -> bool:
    """
    Validasi apakah ukuran file tidak melebihi batas.

    Args:
        size_bytes: Ukuran file dalam bytes

    Returns:
        True jika ukuran file dalam batas yang diperbolehkan
    """
    return size_bytes <= settings.max_file_size_bytes


def format_file_size(size_bytes: int) -> str:
    """
    Format ukuran file ke human-readable string.

    Args:
        size_bytes: Ukuran file dalam bytes

    Returns:
        String format seperti "1.5 MB", "200.0 KB"
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def get_allowed_extensions_str() -> str:
    """Return string daftar ekstensi yang diperbolehkan untuk error message."""
    return ", ".join(settings.ALLOWED_EXTENSIONS)
