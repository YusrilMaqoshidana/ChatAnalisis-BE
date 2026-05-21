from datetime import date, datetime


def _subtract_year(anchor: date) -> date:
    try:
        return anchor.replace(year=anchor.year - 1)
    except ValueError:
        return anchor.replace(month=2, day=28, year=anchor.year - 1)


def _parse_chat_datetime(row: dict) -> datetime | None:
    timestamp_value = row.get("timestamp")

    if isinstance(timestamp_value, datetime):
        return timestamp_value

    if isinstance(timestamp_value, str):
        normalized_timestamp = timestamp_value.strip()
        if normalized_timestamp:
            try:
                return datetime.fromisoformat(normalized_timestamp)
            except ValueError:
                pass

    # Fallback backward compatibility (format lama tanggal + waktu)
    tanggal = str(row.get("tanggal", "")).strip()
    waktu = str(row.get("waktu", "")).strip()
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
    messages: list[dict],
    timeframe: str = "year",
    anchor_date: date | None = None,
) -> tuple[list[dict], int]:
    normalized_timeframe = timeframe.lower().strip()
    if normalized_timeframe not in {"week", "month", "year"}:
        normalized_timeframe = "year"

    anchor = anchor_date or date.today()
    selected: list[tuple[datetime | None, dict]] = []

    for row in messages:
        chat_dt = _parse_chat_datetime(row)

        # Untuk timeframe tertentu, skip jika parsing datetime gagal
        if chat_dt is None:
            continue

        chat_date = chat_dt.date()

        # Cek kriteria timeframe
        if normalized_timeframe == "week":
            # Bandingkan ISO calendar (year, week number) dari chat_date vs today
            if chat_date.isocalendar()[:2] == anchor.isocalendar()[:2]:
                selected.append((chat_dt, row))
        elif normalized_timeframe == "month":
            # Bandingkan year + month
            if chat_date.year == anchor.year and chat_date.month == anchor.month:
                selected.append((chat_dt, row))
        elif normalized_timeframe == "year":
            # Bandingkan 1 tahun terakhir dari anchor date
            if _subtract_year(anchor) <= chat_date <= anchor:
                selected.append((chat_dt, row))

    # Sort descending by datetime (terbaru dulu) agar preprocessing prioritas data terbaru
    selected.sort(key=lambda item: item[0] or datetime.min, reverse=True)

    filtered_messages = [row for _, row in selected]
    filtered_out_count = len(messages) - len(filtered_messages)

    return filtered_messages, filtered_out_count
