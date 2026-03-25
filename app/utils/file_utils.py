"""
File Utilities
==============
Helper functions untuk operasi file.
"""


def format_file_size(size_bytes: int) -> str:
    """
    Format ukuran file ke human-readable string.

    Examples:
        >>> format_file_size(512)       # '512 B'
        >>> format_file_size(204800)    # '200.0 KB'
        >>> format_file_size(10485760)  # '10.0 MB'
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
