"""
Utility module for generating daily message activity data (Daily Graph).
Designed for line charts where the X-axis is the date (YYYY-MM-DD) and the Y-axis is the message count.
"""

import io
import logging
import pandas as pd
from minio import Minio

from app.config import settings

logger = logging.getLogger(__name__)

def _get_minio_client() -> Minio:
    """Initialize MinIO client with configuration from settings."""
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )

def calculate_daily_graph_pandas(df: pd.DataFrame, fill_missing: bool = True) -> list[dict]:
    """
    Calculate the daily message counts from a DataFrame.
    
    Args:
        df: DataFrame containing WhatsApp messages (must have 'timestamp' column).
        fill_missing: If True, fills in dates with 0 messages between the min and max dates.
        
    Returns:
        A list of dictionaries with 'date' (string in YYYY-MM-DD format) and 'count' (integer).
    """
    if df.empty or "timestamp" not in df.columns:
        return []
    
    # 1. Convert timestamp column to datetime
    # We use errors='coerce' to safely skip unparseable datetimes
    df = df.copy()
    df["parsed_time"] = pd.to_datetime(df["timestamp"], errors="coerce")
    
    # Drop rows with unparseable timestamps
    df_clean = df.dropna(subset=["parsed_time"])
    
    if df_clean.empty:
        return []
        
    # Extract date part
    df_clean["date_only"] = df_clean["parsed_time"].dt.date
    
    # Group by date and count messages
    daily_counts = df_clean.groupby("date_only").size()
    
    # 2. Fill missing dates with 0 if requested
    if fill_missing and len(daily_counts) > 1:
        min_date = daily_counts.index.min()
        max_date = daily_counts.index.max()
        # Generate complete date range
        full_date_range = pd.date_range(start=min_date, end=max_date).date
        # Reindex series with full range, filling missing values with 0
        daily_counts = daily_counts.reindex(full_date_range, fill_value=0)
    else:
        # Just sort the dates if we are not filling missing ones
        daily_counts = daily_counts.sort_index()
        
    # 3. Format output
    daily_graph_data = []
    for date_val, count in daily_counts.items():
        daily_graph_data.append({
            "date": date_val.strftime("%Y-%m-%d"),
            "count": int(count)
        })
        
    return daily_graph_data

def get_daily_graph(session_id: str, fill_missing: bool = True) -> list[dict]:
    """
    Retrieve daily message counts for a session by downloading its preprocessed file from MinIO.
    
    Args:
        session_id: The session ID corresponding to the chat upload.
        fill_missing: If True, fills in dates with 0 messages between the min and max dates.
        
    Returns:
        A list of dictionaries with 'date' and 'count' fields sorted chronologically.
    """
    try:
        client = _get_minio_client()
        bucket_name = settings.MINIO_BUCKET
        object_name = f"post_processing_{session_id}.csv"
        
        # Download preprocessed file from MinIO
        response = client.get_object(bucket_name, object_name)
        try:
            csv_bytes = response.read()
            df = pd.read_csv(io.BytesIO(csv_bytes), dtype=str)
        finally:
            response.close()
            response.release_conn()
            
        # Calculate daily counts
        return calculate_daily_graph_pandas(df, fill_missing=fill_missing)
        
    except Exception as exc:
        logger.error(f"Failed to fetch daily graph data from MinIO: {exc}")
        return []
