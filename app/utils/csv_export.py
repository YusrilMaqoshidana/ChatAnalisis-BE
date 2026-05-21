"""
CSV Export Module
=================
Berfungsi untuk export hasil parsing chat ke format CSV.
"""

import csv
import io
from datetime import datetime


def _format_csv_value(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if value is None:
        return ""
    return str(value)


def whatsapp_rows_to_csv(content_rows: list[dict[str, object]]) -> str:
    """
    Konversi hasil parse chat menjadi CSV string.

    Header: timestamp, pengirim, pesan

    Args:
        content_rows: List of dict berisi rows (hasil dari parsing atau preprocessing)

    Returns:
        String CSV with newline delimiter

    Examples:
        >>> rows = [
        ...     {"timestamp": datetime(2026, 4, 5, 21, 51), "pengirim": "Budi", "pesan": "Halo"},
        ... ]
        >>> csv_str = whatsapp_rows_to_csv(rows)
        >>> "timestamp,pengirim,pesan" in csv_str
        True
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "pengirim", "pesan"])

    for row in content_rows:
        writer.writerow([
            _format_csv_value(row.get("timestamp", "")),
            row.get("pengirim", ""),
            row.get("pesan", ""),
        ])

    return output.getvalue()
