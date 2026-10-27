from datetime import datetime

def parse_date(date_str: str) -> datetime | None:
    """
    Tujuan: Mengonversi berbagai format string tanggal dari chat WhatsApp
    menjadi objek datetime Python standar.
    """
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
