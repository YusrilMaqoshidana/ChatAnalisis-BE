import logging
import pandas as pd

logger = logging.getLogger(__name__)

def calculate_hourly_activity(df: pd.DataFrame) -> list[dict]:
    """
    Tujuan: Menghitung total frekuensi pesan untuk setiap jam (0 sampai 23)
    guna melihat pola waktu teraktif dalam obrolan chat.
    """
    if df.empty or "timestamp" not in df.columns:
        return []
    df = df.copy()
    df["parsed_time"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df_clean = df.dropna(subset=["parsed_time"])
    if df_clean.empty:
        return []
    hourly_counts = df_clean.groupby(df_clean["parsed_time"].dt.hour).size()
    hourly_data = []
    for h in range(24):
        count = int(hourly_counts.get(h, 0))
        hourly_data.append({"hour": h, "count": count})
    return hourly_data
