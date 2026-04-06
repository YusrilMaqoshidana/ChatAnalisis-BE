"""
Format Utilities Module
=======================
Berfungsi untuk format dan konversi satuan (ukuran file, dll).
"""


def format_file_size(size_bytes: int) -> str:
    """
    Format ukuran file ke human-readable string.

    Konversi:
    - < 1024 B: "512 B"
    - < 1 MB: "200.0 KB"
    - < 1 GB: "10.0 MB"
    - >= 1 GB: "1.5 GB"

    Args:
        size_bytes: Ukuran dalam bytes

    Returns:
        String human-readable (e.g., "10.0 MB")

    Examples:
        >>> format_file_size(512)
        '512 B'
        >>> format_file_size(204800)
        '200.0 KB'
        >>> format_file_size(10485760)
        '10.0 MB'
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
