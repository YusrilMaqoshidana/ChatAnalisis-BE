"""
Chat Parsing Module
===================
Berfungsi parsing raw text export WhatsApp menjadi format terstruktur.

Format yang didukung:
- DD/MM/YY HH.MM AM/PM - Pengirim: Pesan
- DD/MM/YY HH.MM AM/PM - Pesan Sistem (tanpa separator ":")

Fitur:
- Normalize spasi unicode dari export WhatsApp
- Handle pesan multi-line (message continuation)
- Deteksi pesan sistem dan notifikasi whatsapp
"""

import re
from datetime import datetime


# Konstanta privat
_INVISIBLE_CHARS: tuple[str, ...] = ("\u2068", "\u2069", "\u202a", "\u202b", "\u202c", "\u200e", "\u200f")
_SPACE_LIKE_CHARS: tuple[str, ...] = ("\u00a0", "\u202f", "\u2009", "\u2007")

# Pola regex untuk parsing pesan WhatsApp
WHATSAPP_MESSAGE_PATTERN = re.compile(
    r"^(\d{2}/\d{2}/\d{2})\s+(\d{1,2}\.\d{2})\s*([AP]M)\s-\s(.*?):\s(.*)$"
)

# Pola untuk notifikasi sistem (tanpa ":" setelah pengirim)
WHATSAPP_SYSTEM_LINE_PATTERN = re.compile(
    r"^(\d{2}/\d{2}/\d{2})\s+(\d{1,2}\.\d{2})\s*([AP]M)\s-\s(.+)$"
)


def clean_invisible(text: str) -> str:
    """
    Hapus karakter unicode tidak terlihat.

    Karakter seperti zero-width, directional marks, dan narrow spaces
    sering muncul di export WhatsApp dan mengganggu parsing regex.

    Args:
        text: String input

    Returns:
        String yang sudah dibersihkan dari karakter invisible.

    Examples:
        >>> clean_invisible("hello\u200eworld")
        "helloworld"
    """
    for ch in _INVISIBLE_CHARS:
        text = text.replace(ch, "")
    for ch in _SPACE_LIKE_CHARS:
        text = text.replace(ch, " ")
    return text


def _normalize_whatsapp_line(text: str) -> str:
    """Normalisasi satu baris chat: cleanup spasi, invisible chars."""
    normalized = text
    for ch in _SPACE_LIKE_CHARS:
        normalized = normalized.replace(ch, " ")
    normalized = clean_invisible(normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _build_timestamp(
    date_str: str,
    time_str: str,
    am_pm: str
) -> datetime:
    """
    Convert WhatsApp date + time menjadi datetime object.
    """

    raw = f"{date_str} {time_str} {am_pm}"

    return datetime.strptime(
        raw,
        "%d/%m/%y %I.%M %p"
    )


def parse_whatsapp_txt_content(
    content: str
) -> list[dict]:

    rows: list[dict] = []

    current_message: dict | None = None

    for raw_line in content.splitlines():

        line = _normalize_whatsapp_line(raw_line)

        if not line:
            continue

        # Pesan biasa
        match = WHATSAPP_MESSAGE_PATTERN.match(line)

        if match:

            if current_message:
                rows.append(current_message)

            date, time, am_pm, sender, message = match.groups()

            timestamp = _build_timestamp(
                date,
                time,
                am_pm
            )

            current_message = {
                "timestamp": timestamp,
                "pengirim": sender,
                "pesan": message,
            }

            continue

        # System message
        system_match = WHATSAPP_SYSTEM_LINE_PATTERN.match(line)

        if system_match:

            if current_message:
                rows.append(current_message)

            date, time, am_pm, message = system_match.groups()

            timestamp = _build_timestamp(
                date,
                time,
                am_pm
            )

            current_message = {
                "timestamp": timestamp,
                "pengirim": "SYSTEM",
                "pesan": message,
            }

            continue

        # Multiline continuation
        if current_message:
            current_message["pesan"] = (
                f"{current_message['pesan']} {line}"
            ).strip()

    if current_message:
        rows.append(current_message)

    return rows


def parse_whatsapp_txt_bytes(content: bytes, encoding: str = "utf-8") -> list[dict]:
    """
    Parse bytes konten WhatsApp menjadi list pesan terstruktur.

    Args:
        content: Bytes isi file txt
        encoding: Encoding yang digunakan (default: utf-8)

    Returns:
        List of dict seperti parse_whatsapp_txt_content()
    """
    decoded = content.decode(encoding=encoding, errors="replace")
    return parse_whatsapp_txt_content(decoded)
