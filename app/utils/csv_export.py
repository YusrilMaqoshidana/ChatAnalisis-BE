"""
CSV Export Module
=================
Berfungsi untuk export hasil parsing chat ke format CSV.
"""

import csv
import io


def whatsapp_rows_to_csv(content_rows: list[dict[str, str]]) -> str:
    """
    Konversi hasil parse chat menjadi CSV string.

    Header: Tanggal, Waktu, Pengirim, Pesan

    Args:
        content_rows: List of dict berisi rows (hasil dari parsing atau preprocessing)

    Returns:
        String CSV with newline delimiter

    Examples:
        >>> rows = [
        ...     {"tanggal": "05/04/26", "waktu": "9.51 PM", "pengirim": "Budi", "pesan": "Halo"},
        ... ]
        >>> csv_str = whatsapp_rows_to_csv(rows)
        >>> "Tanggal,Waktu,Pengirim,Pesan" in csv_str
        True
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Tanggal", "Waktu", "Pengirim", "Pesan"])

    for row in content_rows:
        writer.writerow([
            row.get("tanggal", ""),
            row.get("waktu", ""),
            row.get("pengirim", ""),
            row.get("pesan", ""),
        ])

    return output.getvalue()
