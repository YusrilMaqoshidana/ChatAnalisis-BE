
"""
File Utilities Package
======================
Orchestrator untuk chat parsing, preprocessing, filtering, dan export.

Struktur modul:
- chat_parsing.py: Parsing raw WhatsApp TXT ke format terstruktur
- chat_preprocessing.py: Normalisasi, cleaning, dan deduplication
- chat_filtering.py: Filter berdasarkan timeframe (week/month/year/all)
- csv_export.py: Export ke CSV
- format_utils.py: Utility formatting (file size, dll)

Gunakan functions dibawah untuk workflow lengkap.

Contoh penggunaan:
    1. Upload file .txt -> parse_whatsapp_txt_bytes(file_bytes)
    2. Filter by timeframe -> filter_messages_by_timeframe(messages, timeframe="week")
    3. Apply preprocessing -> apply_full_preprocessing(filtered_messages)
    4. Export ke CSV -> whatsapp_rows_to_csv(processed_rows)
"""

# Re-export dari submodules untuk kemudahan akses
from app.utils.chat_filtering import filter_messages_by_timeframe
from app.utils.chat_parsing import (
    clean_invisible,
    parse_whatsapp_txt_bytes,
    parse_whatsapp_txt_content,
)
from app.utils.chat_preprocessing import apply_full_preprocessing
from app.utils.csv_export import whatsapp_rows_to_csv
from app.utils.format_utils import format_file_size

__all__ = [
    # Parsing
    "parse_whatsapp_txt_bytes",
    "parse_whatsapp_txt_content",
    "clean_invisible",
    # Filtering
    "filter_messages_by_timeframe",
    # Preprocessing
    "apply_full_preprocessing",
    # Export
    "whatsapp_rows_to_csv",
    # Format
    "format_file_size",
]
