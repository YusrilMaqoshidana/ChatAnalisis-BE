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


def parse_whatsapp_txt_content(content: str) -> list[dict[str, str]]:
    """
    Parse konten txt export WhatsApp menjadi list pesan terstruktur.

    Setiap pesan berisi:
    - tanggal: DD/MM/YY
    - waktu: HH.MM AM/PM
    - pengirim: Nama pengirim atau "SYSTEM" untuk notifikasi
    - pesan: Isi pesan (support multi-line continuation)

    Args:
        content: String isi file txt

    Returns:
        List of dict berisi setiap pesan dengan keys: tanggal, waktu, pengirim, pesan

    Examples:
        >>> txt = "05/04/26 9.51 PM - Budi: Halo"
        >>> msgs = parse_whatsapp_txt_content(txt)
        >>> msgs[0]["pengirim"]
        "Budi"
    """
    rows: list[dict[str, str]] = []
    current_message: dict[str, str] | None = None

    for raw_line in content.splitlines():
        line = _normalize_whatsapp_line(raw_line)
        if not line:
            continue

        # Cek apakah baris ini awal pesan baru (format: tanggal waktu - pengirim: pesan)
        match = WHATSAPP_MESSAGE_PATTERN.match(line)
        if match:
            # Simpan pesan sebelumnya jika ada
            if current_message:
                rows.append(current_message)

            date, time, am_pm, sender, message = match.groups()
            current_message = {
                "tanggal": date,
                "waktu": f"{time} {am_pm}",
                "pengirim": sender,
                "pesan": message,
            }
            continue

        # Tangani notifikasi sistem yang tetap punya timestamp, tapi tidak punya ":"
        system_match = WHATSAPP_SYSTEM_LINE_PATTERN.match(line)
        if system_match:
            if current_message:
                rows.append(current_message)

            date, time, am_pm, message = system_match.groups()
            current_message = {
                "tanggal": date,
                "waktu": f"{time} {am_pm}",
                "pengirim": "SYSTEM",
                "pesan": message,
            }
            continue

        # Jika bukan awal pesan baru, tambahkan sebagai lanjutan pesan sebelumnya
        if current_message:
            current_message["pesan"] = f"{current_message['pesan']} {line}".strip()

    # Simpan pesan terakhir
    if current_message:
        rows.append(current_message)

    return rows


def parse_whatsapp_txt_bytes(content: bytes, encoding: str = "utf-8") -> list[dict[str, str]]:
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
