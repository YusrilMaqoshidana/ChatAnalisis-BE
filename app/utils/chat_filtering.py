"""
Chat Filtering Module
======================
Berfungsi untuk filter pesan berdasarkan timeframe (week, month, year, all).

Konteks penggunaan:
- Preprocessing data chat besar biasanya lebih efisien jika dibatasi timeframe
- Default: all (semua data)
- Data diurutkan descending by datetime (terbaru dulu)
"""

from datetime import date, datetime
from typing import Literal


def _parse_chat_datetime(row: dict[str, str]) -> datetime | None:
    """
    Parse field tanggal + waktu dari hasil parsing chat menjadi datetime object.

    Format yang didukung:
    - DD/MM/YY HH.MM AM/PM
    - DD/MM/YY HH.MM
    - DD/MM/YY HH:MM

    Args:
        row: Dict hasil parsing chat dengan keys "tanggal" dan "waktu"

    Returns:
        datetime object atau None jika parse gagal

    Examples:
        >>> row = {"tanggal": "05/04/26", "waktu": "9.51 PM"}
        >>> dt = _parse_chat_datetime(row)
        >>> dt.day
        5
    """
    tanggal = row.get("tanggal", "").strip()
    waktu = row.get("waktu", "").strip()
    if not tanggal or not waktu:
        return None

    raw_value = f"{tanggal} {waktu}"
    for fmt in ("%d/%m/%y %I.%M %p", "%d/%m/%y %H.%M", "%d/%m/%y %H:%M"):
        try:
            return datetime.strptime(raw_value, fmt)
        except ValueError:
            continue
    return None


def filter_messages_by_timeframe(
    messages: list[dict[str, str]],
    timeframe: Literal["week", "month", "year", "all"] = "all",
) -> tuple[list[dict[str, str]], int]:
    """
    Filter pesan berdasarkan timeframe relatif ke hari ini.

    Ketentuan:
    - week: Hanya pesan dalam minggu kalender yang sama dengan hari ini (ISO calendar)
    - month: Hanya pesan dalam bulan yang sama dengan hari ini
    - year: Hanya pesan dalam tahun yang sama dengan hari ini
    - all: Semua pesan (tidak ada filter tanggal)

    Data diurutkan descending by datetime sehingga yang terbaru diproses duluan.

    Args:
        messages: List of dict hasil parsing chat
        timeframe: Pilihan rentang waktu (default: "all")

    Returns:
        Tuple (filtered_messages, filtered_out_count) dimana:
        - filtered_messages: List pesan yang masuk kriteria timeframe
        - filtered_out_count: Jumlah pesan yang terbuang

    Examples:
        >>> messages = [
        ...     {"tanggal": "06/04/26", "waktu": "10.00 AM", ...},
        ...     {"tanggal": "01/01/26", "waktu": "10.00 AM", ...},
        ... ]
        >>> filtered, dropped = filter_messages_by_timeframe(messages, timeframe="month")
        >>> len(filtered)
        1
        >>> dropped
        1
    """
    normalized_timeframe: str = timeframe.lower().strip()  # type: ignore
    if normalized_timeframe not in {"week", "month", "year", "all"}:
        normalized_timeframe = "all"

    today = date.today()
    selected: list[tuple[datetime | None, dict[str, str]]] = []

    for row in messages:
        chat_dt = _parse_chat_datetime(row)

        # Untuk "all", masukkan semua (tidak peduli datetime parsing success atau fail)
        if normalized_timeframe == "all":
            selected.append((chat_dt, row))
            continue

        # Untuk timeframe tertentu, skip jika parsing datetime gagal
        if chat_dt is None:
            continue

        chat_date = chat_dt.date()

        # Cek kriteria timeframe
        if normalized_timeframe == "week":
            # Bandingkan ISO calendar (year, week number) dari chat_date vs today
            if chat_date.isocalendar()[:2] == today.isocalendar()[:2]:
                selected.append((chat_dt, row))
        elif normalized_timeframe == "month":
            # Bandingkan year + month
            if chat_date.year == today.year and chat_date.month == today.month:
                selected.append((chat_dt, row))
        elif normalized_timeframe == "year":
            # Bandingkan year saja
            if chat_date.year == today.year:
                selected.append((chat_dt, row))

    # Sort descending by datetime (terbaru dulu) agar preprocessing prioritas data terbaru
    selected.sort(key=lambda item: item[0] or datetime.min, reverse=True)

    filtered_messages = [row for _, row in selected]
    filtered_out_count = len(messages) - len(filtered_messages)

    return filtered_messages, filtered_out_count
