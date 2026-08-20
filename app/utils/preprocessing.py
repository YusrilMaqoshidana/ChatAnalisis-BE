"""
Utility module for WhatsApp message pre-processing based on b_preprocessing_web.ipynb.
Separates cleaning paths for IndoBERTweet Embedding (retains context) and c-TF-IDF / BM25 (highly normalized).
"""

import re
import emoji
import hashlib
import unicodedata
import pandas as pd
from Sastrawi.StopWordRemover.StopWordRemoverFactory import StopWordRemoverFactory

# Initialize Sastrawi Stopword List
factory = StopWordRemoverFactory()
sastrawi_stopwords = set(factory.get_stop_words())

specific_words = {"user", "amp", "wa", "whatsapp", "chat", "chatnya", "grup", "group"}
all_stopwords = sastrawi_stopwords.union(specific_words)

# Slang normalization dictionary
normalization_dict = {
    "yg": "yang", "ga": "tidak", "gak": "tidak", "nggak": "tidak", "gk": "tidak",
    "aja": "saja", "deh": "saja", "sih": "saja", "dong": "saja", "kok": "saja",
    "iya": "ya", "jg": "juga", "loh": "saja", "ya": "ya", "yah": "ya", "y": "ya",
    "ok": "oke", "oke": "oke", "okay": "oke", "sip": "oke", "siap": "oke",
    "nah": "nah", "nih": "ini", "tuh": "itu", "kan": "kan", "mah": "saja",
    "lah": "saja", "eh": "eh", "wkwk": "tertawa", "wk": "tertawa", "haha": "tertawa",
    "hehe": "tertawa", "hihi": "tertawa", "lol": "tertawa", "lmao": "tertawa",
    "thanks": "terima kasih", "thx": "terima kasih", "makasih": "terima kasih", "mksh": "terima kasih"
}

def clean_system_notifications(text: str) -> str:
    """Remove system notifications / deleted messages / omitted media."""
    system_patterns = [
        r"this message was deleted",
        r"you deleted this message",
        r"pesan ini telah dihapus",
        r"anda telah menghapus pesan ini",
        r"anda menghapus pesan ini",
        r"pesan ini dihapus oleh admin",
        r"pesan ini dihapus",
        r"missed voice call",
        r"missed video call",
        r"panggilan suara tak terjawab",
        r"panggilan video tak terjawab",
        r"panggilan suara",
        r"panggilan video",
        r"panggilan tak terjawab",
        r"missed call",
        r"media omitted",
        r"media tidak disertakan",
        r"image omitted",
        r"gambar tidak disertakan",
        r"video omitted",
        r"video tidak disertakan",
        r"sticker omitted",
        r"stiker tidak disertakan",
        r"audio omitted",
        r"audio tidak disertakan",
        r"gif omitted",
        r"gif tidak disertakan",
        r"document omitted",
        r"dokumen tidak disertakan",
        r"contact omitted",
        r"kontak tidak disertakan",
        r"location omitted",
        r"lokasi tidak disertakan",
        r"poll omitted",
        r"jajak pendapat tidak disertakan"
    ]
    for pattern in system_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return text

def normalize_repeated_chars(text: str) -> str:
    """Reduce 3 or more consecutive identical characters to 2.
    E.g., 'bangeeeet' -> 'bangeet'"""
    return re.sub(r"(.)\1{2,}", r"\1\1", text)

def anonymize_sensitive_data(text: str) -> str:
    """Anonymize emails and phone numbers in the text body."""
    if not isinstance(text, str):
        return text
    # Mask email addresses
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    text = re.sub(email_pattern, "", text)

    # Mask general phone numbers (not starting with @ to avoid double-masking mentions)
    phone_pattern = r"(?<!@)\b\+?\d{1,3}[-.\s]?\(?\d{1,3}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b"
    text = re.sub(phone_pattern, "@USER", text)
    return text

def clean_for_embedding(text: str) -> str:
    """
    Preprocess text for IndoBERTweet Embedding:
    - Retains context, punctuation, stopwords (No ❌).
    - Cleans URLs, system notifications, lowercase, demojizes emojis, slang, repeated characters.
    """
    if pd.isna(text):
        return ""
    text = str(text)

    # 1. Hapus pesan sistem
    text = clean_system_notifications(text)

    # 2. Hapus text metadata di dalam kurung siku/kurung (seperti media metadata)
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"\[.*?\]", "", text)

    # 3. Hapus hashtag
    text = re.sub(r"#\S+", "", text)

    # 4. Hapus URL
    text = re.sub(r"https?://\S+|www\.\S+", "", text)

    # 5. Lowercase (case folding)
    text = text.lower()

    # 6. Normalisasi Unicode dan Spasi
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"\s+", " ", text).strip()

    # 7. Anonimisasi data sensitif (email, telepon)
    text = anonymize_sensitive_data(text)

    # 8. Demojize emoji (mengubah emoji menjadi teks seperti :smiling_face:)
    text = emoji.demojize(text, delimiters=(" ", " "))

    # 9. Normalisasi karakter berulang
    text = normalize_repeated_chars(text)

    # 10. Normalisasi slang
    words = text.split()
    normalized_words = [normalization_dict.get(w, w) for w in words]
    text = " ".join(normalized_words)

    # Normalisasi spasi akhir
    return re.sub(r"\s+", " ", text).strip()

def clean_for_tfidf(embedding_clean_text: str) -> str:
    """
    Preprocess text for c-TF-IDF / BM25 representation.
    Takes output of clean_for_embedding and adds:
    - Stopword removal
    - Punctuation removal (keeps only a-z and spaces)
    - Meaningless token cleaning (removes tokens with length < 2 or non-alphabet remnants)
    """
    if not embedding_clean_text:
        return ""

    # 1. Hapus tanda baca/karakter non-alphabet (menyisakan huruf a-z dan spasi saja)
    text_cleaned = re.sub(r"[^a-z\s]", " ", embedding_clean_text)

    # 2. Tokenisasi untuk stopword removal & pembersihan token tidak bermakna
    words = text_cleaned.split()
    filtered_words = []
    for w in words:
        # Stopword removal & clean meaningless single characters (token < 2)
        if w not in all_stopwords and len(w) >= 2:
            filtered_words.append(w)

    return " ".join(filtered_words)

def has_min_words(text: str, min_words: int = 3) -> bool:
    """Check if the text has at least the minimum number of words."""
    if pd.isna(text):
        return False
    return len(str(text).split()) >= min_words

def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preprocess dataframe containing WhatsApp messages.
    Splits text processing into:
    1. Pesan_Embedding: Raw context (with stopwords & punctuation) for IndoBERTweet embeddings.
    2. Pesan_TFIDF: Highly normalized tokens (no stopwords or punctuation) for c-TF-IDF.
    """
    df = df.copy()

    # Normalize column names mapping if needed
    if "pesan" in df.columns:
        df["Pesan"] = df["pesan"]
    elif "Pesan" in df.columns:
        df["pesan"] = df["Pesan"]
    else:
        df["pesan"] = ""
        df["Pesan"] = ""

    # Hapus baris kosong/nan di kolom pesan asli sebelum drop duplikat
    df = df.dropna(subset=["pesan"])
    df = df[df["pesan"].str.strip().ne("")].copy()

    # Hapus pesan yang mengandung file kontak/vcf Merpati Rent Car Jember
    df = df[~df["pesan"].str.contains(".vcf", case=False, na=False, regex=False)].copy()

    # 1. Hapus duplikat pesan (Hapus duplikat: ✅)
    df = df.drop_duplicates(subset=["pesan"]).reset_index(drop=True)

    # 2. Anonimisasi Pengirim dan Mention pada Pesan Secara Bersamaan
    # Ekstrak unique senders
    unique_senders = df["pengirim"].dropna().unique()
    senders_to_anonymize = [
        str(s).strip() for s in unique_senders
        if not str(s).startswith("User-") and str(s).strip() != ""
    ]

    # Urutkan berdasarkan panjang karakter menurun agar tidak parsial (e.g. @Yusril Maqoshidana)
    senders_to_anonymize.sort(key=len, reverse=True)

    # Buat map mapping pengirim -> anonymized
    sender_map = {}
    for s in senders_to_anonymize:
        h = hashlib.sha256(s.encode("utf-8")).hexdigest()[:4]
        # Deteksi jika nomor telepon
        phone_match = re.search(r"\+?\d[\d\-\s]{8,}\d", s)
        if phone_match:
            digits = re.sub(r"\D", "", s)
            last_4 = digits[-4:] if len(digits) >= 4 else digits
            anon_name = f"User-{h}·{last_4}"
        else:
            anon_name = f"User-{h}"
        sender_map[s] = anon_name

    # Terapkan anonymization ke kolom pengirim
    if sender_map:
        df["pengirim"] = df["pengirim"].map(lambda x: sender_map.get(str(x).strip(), x))
        if "Pesan" in df.columns:
            # Fungsi untuk meng-anonimkan mention di pesan
            def anonymize_mentions(text: str) -> str:
                if not isinstance(text, str):
                    return text
                for orig_name, anon_name in sender_map.items():
                    escaped_name = re.escape(orig_name)
                    # Match pattern "@name" atau "@ name" (case-insensitive)
                    pattern = r"@\s*" + escaped_name
                    text = re.sub(pattern, f"@{anon_name}", text, flags=re.IGNORECASE)
                return text

            df["pesan"] = df["pesan"].apply(anonymize_mentions)
            df["Pesan"] = df["pesan"]

    # 3. Bersihkan teks menggunakan 1 jalur pemrosesan tunggal
    df["Pesan_Preprocessed"] = df["pesan"].apply(clean_for_embedding)

    # 4. Cleanup whitespace & filter data kosong
    df["Pesan_Preprocessed"] = df["Pesan_Preprocessed"].apply(lambda x: re.sub(r"\s+", " ", str(x)).strip())

    # Filter data: minimal 3 kata pada kolom Pesan_Preprocessed agar data yang di-cluster memiliki substansi
    df = df[df["Pesan_Preprocessed"].apply(lambda x: len(x.split()) >= 3)].copy()

    # Berikan alias kolom untuk kompatibilitas ke bagian lain yang membacanya
    df["Pesan_Embedding"] = df["Pesan_Preprocessed"]
    df["Pesan_TFIDF"] = df["Pesan_Preprocessed"]

    return df
