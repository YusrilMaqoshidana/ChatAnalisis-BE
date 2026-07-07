"""
Utility module for WhatsApp message pre-processing.
"""

import re
import emoji
import pandas as pd

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_MENTION_RE = re.compile(
    r"(?<!\S)"          # tidak didahului non-spasi
    r"@"                # awalan @
    r"(?:\+?\d+)"       # kode negara: +62 atau 62
    r"(?:[\s\-]\d+)*"   # sisa nomor: bisa dipisah spasi atau strip
    r"|(?<!\S)@\S+"     # fallback: @username biasa tanpa spasi
)
_ELONGATION_RE = re.compile(r'(\w+?)\1{2,}')
_MULTISPACE_RE = re.compile(r"\s+")

def remove_url(text: str) -> str:
    """Hapus URL dari pesan"""
    if pd.isna(text):
        return ""
    text = str(text)
    text = _URL_RE.sub("", text)
    text = re.sub(r" +", " ", text)
    return text.strip()

def replace_mention(text: str) -> str:
    """Normalisasi mention menjadi @USER"""
    if pd.isna(text):
        return ""
    return _MENTION_RE.sub("@USER", str(text)).strip()

def remove_emoji(text: str) -> str:
    """
    Hapus semua emoji dari teks, termasuk emoji multi-codepoint.
    Gunakan library emoji untuk mendeteksi dan mengganti dengan string kosong.
    """
    if pd.isna(text):
        return ""
    text = str(text)
    try:
        # replace_emoji(text, replace='') akan menghapus semua emoji
        text = emoji.replace_emoji(text, replace='')
    except AttributeError:
        # Fallback untuk versi lama: gunakan emoji.get_emoji_regexp()
        try:
            text = emoji.get_emoji_regexp().sub('', text)
        except AttributeError:
            # Fallback if neither works (e.g. library api changes drastically)
            pass
    # Bersihkan spasi ganda yang mungkin timbul
    text = re.sub(r' +', ' ', text)
    return text.strip()

def to_lowercase(text: str) -> str:
    """Ubah teks menjadi lowercase"""
    if pd.isna(text):
        return ""
    return str(text).lower().strip()

def normalize_elongation(text: str) -> str:
    """Normalisasi elongasi kata (pengulangan karakter)"""
    if pd.isna(text):
        return ""
    text = str(text)
    return _ELONGATION_RE.sub(r'\1\1', text)

def has_min_words(text: str, min_words: int = 3) -> bool:
    """Cek apakah teks mengandung minimal kata yang ditentukan"""
    if pd.isna(text):
        return False
    words = str(text).split()
    return len(words) >= min_words

def cleanup_whitespace(text: str) -> str:
    """
    Rapikan whitespace:
    - multiple spaces -> single space
    - trim awal/akhir
    """
    if pd.isna(text):
        return ""
    text = str(text)
    text = _MULTISPACE_RE.sub(" ", text)
    return text.strip()

def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocess dataframe containing WhatsApp messages.

    Steps:
    1. HTML tag removal
    2. URL removal
    3. Mention normalization
    4. Emoji removal
    5. Lowercase normalization
    6. Elongation normalization
    7. Minimum word filtering (3 words)
    8. Whitespace cleanup and empty row removal
    """
    df = df.copy()

    # Ensure "pesan" exists and create "Pesan" as standard alias
    if "pesan" in df.columns:
        df["Pesan"] = df["pesan"]
    elif "Pesan" in df.columns:
        df["pesan"] = df["Pesan"]
    else:
        df["pesan"] = ""
        df["Pesan"] = ""

    # Initialize Pesan_Preprocessed
    df["Pesan_Preprocessed"] = df["pesan"].fillna("").astype(str)

    # 1. HTML tag removal
    total_sebelum = len(df)
    edited_count = df['Pesan_Preprocessed'].str.contains(r'<.*?>', regex=True, na=False).sum()
    df['Pesan_Preprocessed'] = df['Pesan_Preprocessed'].apply(
        lambda x: re.sub(r'<.*?>', '', str(x)).strip() if pd.notna(x) else x
    )
    total_sesudah = len(df)
    print("── Hapus HTML Tags ───────────────────────────────────")
    print(f"Total baris sebelum  : {total_sebelum:,}")
    print(f"Pesan mengandung HTML: {edited_count:,}")
    print(f"Total baris sesudah  : {total_sesudah:,}")

    # 2. URL removal
    sebelum = df["Pesan_Preprocessed"].copy()
    df["Pesan_Preprocessed"] = df["Pesan_Preprocessed"].apply(remove_url)
    mask = sebelum != df["Pesan_Preprocessed"]
    url_count = mask.sum()
    print("── Hapus URL ─────────────────────────────────────────")
    print(f"Total baris          : {len(df):,}")
    print(f"Pesan mengandung URL : {url_count:,}")
    print(f"Persentase terdampak : {url_count / len(df) * 100 if len(df) > 0 else 0:.2f}%")

    # 3. Mention Normalization
    sebelum = df['Pesan_Preprocessed'].copy()
    df['Pesan_Preprocessed'] = df['Pesan_Preprocessed'].apply(replace_mention)
    mask = sebelum != df['Pesan_Preprocessed']
    mention_count = mask.sum()
    print("── Normalisasi Mention ───────────────────────────────")
    print(f"Total baris            : {len(df):,}")
    print(f"Baris mengandung mention: {mention_count:,}")
    print(f"Persentase             : {mention_count / len(df) * 100 if len(df) > 0 else 0:.2f}%")

    # 4. Emoji removal
    sebelum = df['Pesan_Preprocessed'].copy()
    df['Pesan_Preprocessed'] = df['Pesan_Preprocessed'].apply(remove_emoji)
    mask = sebelum != df['Pesan_Preprocessed']
    emoji_count = mask.sum()
    print("── Penghapusan Emoji ──────────────────────────────────")
    print(f"Total baris           : {len(df):,}")
    print(f"Baris mengandung emoji: {emoji_count:,}")
    print(f"Persentase            : {emoji_count / len(df) * 100 if len(df) > 0 else 0:.2f}%")

    # 5. Lowercase
    df["Pesan_Preprocessed"] = df["Pesan_Preprocessed"].apply(to_lowercase)

    # 6. Elongation normalization
    sebelum = df['Pesan_Preprocessed'].copy()
    df['Pesan_Preprocessed'] = df['Pesan_Preprocessed'].apply(normalize_elongation)
    mask = sebelum != df['Pesan_Preprocessed']
    elongation_count = mask.sum()
    print("── Normalisasi Elongasi ───────────────────────────────")
    print(f"Total baris             : {len(df):,}")
    print(f"Baris mengalami elongasi: {elongation_count:,}")
    print(f"Persentase              : {elongation_count / len(df) * 100 if len(df) > 0 else 0:.2f}%")

    # 7. Minimum 3 Words Filter
    total_sebelum = len(df)
    mask_pendek = ~df["Pesan_Preprocessed"].apply(lambda x: has_min_words(x, 3))
    pendek_count = mask_pendek.sum()
    df.loc[mask_pendek, "Pesan_Preprocessed"] = ""
    print("── Filter Minimum 3 Kata ─────────────────────────────")
    print(f"Total baris              : {total_sebelum:,}")
    print(f"Pesan_Preprocessed dikosongkan: {pendek_count:,}")
    print(f"Persentase terdampak     : {pendek_count / total_sebelum * 100 if total_sebelum > 0 else 0:.2f}%")

    # 8. Cleanup whitespace & remove empty
    df["Pesan_Preprocessed"] = df["Pesan_Preprocessed"].apply(cleanup_whitespace)
    df = df[df["Pesan_Preprocessed"].str.strip().ne("")].copy()
    return df
