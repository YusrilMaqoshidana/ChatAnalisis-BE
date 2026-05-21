import re
from functools import lru_cache

try:
    import emoji
except ImportError:
    emoji = None

try:
    from indoNLP.preprocessing import pipeline as indonlp_pipeline, replace_slang, replace_word_elongation
except ImportError:
    indonlp_pipeline = None


# Konstanta privat
_INVISIBLE_CHARS: tuple[str, ...] = ("\u2068", "\u2069", "\u202a", "\u202b", "\u202c", "\u200e", "\u200f")
_SPACE_LIKE_CHARS: tuple[str, ...] = ("\u00a0", "\u202f", "\u2009", "\u2007")

# Regex patterns untuk normalisasi
_WHATSAPP_TAG_RE = re.compile(r"<[^>]{3,50}>", flags=re.IGNORECASE)
_MENTION_PHONE_RE = re.compile(r"@[\+\d][\d\s\-\(\)]+")
_MENTION_NAME_RE = re.compile(
    r"(?<!\w)@(?:~)?[\w][\w.\-]*\b"
)
_URL_RE = re.compile(r"https?://\S+|www\.\S+")

# Setup indoNLP pipeline jika tersedia
if indonlp_pipeline and replace_word_elongation and replace_slang:
    _INDONLP_PIPE = indonlp_pipeline([replace_word_elongation, replace_slang])
else:
    _INDONLP_PIPE = None


def remove_whatsapp_tags(text: str) -> str:
    return _WHATSAPP_TAG_RE.sub("", text).strip()


def clean_invisible(text: str) -> str:
    for ch in _INVISIBLE_CHARS:
        text = text.replace(ch, "")
    for ch in _SPACE_LIKE_CHARS:
        text = text.replace(ch, " ")
    return text


def preprocess_text(text: str) -> str:
    text = text.lower()
    text = clean_invisible(text)
    text = _MENTION_PHONE_RE.sub("@USER", text)
    text = _MENTION_NAME_RE.sub("@USER", text)
    text = _URL_RE.sub("HTTPURL", text)
    if emoji:
        text = emoji.demojize(text, delimiters=(" ", " "))
    return text.strip()


def preprocess_batch(messages: list[str]) -> list[str]:
    return [preprocess_text(message) for message in messages]


@lru_cache(maxsize=20000)
def _normalize_with_indonlp(text: str) -> str:
    if not _INDONLP_PIPE:
        return text
    try:
        return _INDONLP_PIPE(text)
    except Exception:
        return text


@lru_cache(maxsize=50000)
def _cached_preprocess_text(text: str) -> str:
    return preprocess_text(text)


def apply_full_preprocessing(messages: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """
    Apply full preprocessing pipeline ke list pesan.

    Pipeline:
    1. Filter pesan SYSTEM (pengirim == "SYSTEM")
    2. Hapus tag WhatsApp
    3. Normalisasi indoNLP + preprocess teks
    4. Hapus duplikat berdasarkan pesan preprocessed

    Args:
        messages: List of dict hasil parsing chat

    Returns:
        Tuple (processed_rows, stats) dimana:
        - processed_rows: List pesan setelah preprocessing + field pesan_preprocessed
        - stats: Dict berisi raw_count, system_filtered_count, duplicates_removed_count,
                 empty_filtered_count, final_count

    Examples:
        >>> messages = [{"pesan": "hello", "pengirim": "User"}]
        >>> rows, stats = apply_full_preprocessing(messages)
        >>> stats["final_count"]
        1
    """
    processed_rows: list[dict] = []
    seen_preprocessed: set[str] = set()

    system_filtered_count = 0
    duplicates_removed_count = 0
    empty_filtered_count = 0

    for row in messages:
        pengirim = row.get("pengirim", "").strip()

        # Filter keras: jika pengirim SYSTEM, langsung buang
        if pengirim.upper() == "SYSTEM":
            system_filtered_count += 1
            continue

        raw_message = row.get("pesan", "")
        cleaned_message = clean_invisible(raw_message)
        cleaned_message = remove_whatsapp_tags(cleaned_message)
        cleaned_message = cleaned_message.strip()

        if not cleaned_message:
            empty_filtered_count += 1
            continue

        # Normalisasi dengan indoNLP lalu preprocess
        normalized_message = _normalize_with_indonlp(cleaned_message)
        preprocessed_message = _cached_preprocess_text(normalized_message)
        if not preprocessed_message:
            empty_filtered_count += 1
            continue

        # Hapus duplikat berdasarkan pesan preprocessed
        if preprocessed_message in seen_preprocessed:
            duplicates_removed_count += 1
            continue

        seen_preprocessed.add(preprocessed_message)

        processed_row = {
            "timestamp": row.get("timestamp"),
            "pengirim": row.get("pengirim", ""),
            "pesan": cleaned_message,
            "pesan_preprocessed": preprocessed_message,
        }
        processed_rows.append(processed_row)

    stats = {
        "raw_count": len(messages),
        "system_filtered_count": system_filtered_count,
        "duplicates_removed_count": duplicates_removed_count,
        "empty_filtered_count": empty_filtered_count,
        "final_count": len(processed_rows),
    }

    return processed_rows, stats
