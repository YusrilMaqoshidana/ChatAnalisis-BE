"""
Utility module for generating a leaderboard of active senders.
Provides both direct Pandas/in-memory processing and a high-performance Redis Sorted Set implementation.
"""

import io
import logging
import redis
import pandas as pd
from minio import Minio

from app.config import settings

logger = logging.getLogger(__name__)

def _get_redis_client() -> redis.Redis | None:
    """Initialize Redis client with configuration from settings."""
    try:
        if not settings.REDIS_URL:
            return None
        return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    except Exception as exc:
        logger.warning(f"Failed to connect to Redis: {exc}")
        return None

def _get_minio_client() -> Minio:
    """Initialize MinIO client with configuration from settings."""
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )

def calculate_leaderboard_pandas(df: pd.DataFrame, limit: int = 10) -> list[dict]:
    """
    Calculate the leaderboard of active senders using Pandas in memory.
    
    Args:
        df: DataFrame containing the WhatsApp messages (must have 'pengirim' column).
        limit: Max number of senders to return in the leaderboard.
        
    Returns:
        A list of dictionaries containing rank, username, and message_count.
    """
    if df.empty or "pengirim" not in df.columns:
        return []
    
    # Exclude empty senders if any
    df_clean = df[df["pengirim"].fillna("").str.strip() != ""]
    
    # Calculate counts
    counts = df_clean["pengirim"].value_counts()
    
    leaderboard = []
    for i, (sender, count) in enumerate(counts.head(limit).items()):
        leaderboard.append({
            "rank": i + 1,
            "username": sender,
            "message_count": int(count)
        })
    
    return leaderboard

def save_leaderboard_to_redis(session_id: str, df: pd.DataFrame) -> bool:
    """
    Store the sender activity leaderboard in a Redis Sorted Set (ZSET).
    
    Args:
        session_id: The session ID corresponding to the chat upload.
        df: DataFrame containing the WhatsApp messages (must have 'pengirim' column).
        
    Returns:
        True if successfully saved to Redis, False otherwise.
    """
    r = _get_redis_client()
    if r is None:
        return False
    
    if df.empty or "pengirim" not in df.columns:
        return False
    
    redis_key = f"leaderboard:{session_id}"
    
    try:
        # Exclude empty senders if any
        df_clean = df[df["pengirim"].fillna("").str.strip() != ""]
        counts = df_clean["pengirim"].value_counts()
        
        if counts.empty:
            return False
            
        # Delete any existing key first
        r.delete(redis_key)
        
        # Redis ZADD takes a mapping of {member: score}
        # Standard sorted sets sort ascending, so scores represent message counts
        mapping = {str(sender): int(count) for sender, count in counts.items()}
        
        r.zadd(redis_key, mapping)
        
        # Set expiration to prevent memory leaks
        r.expire(redis_key, settings.PROGRESS_TTL_SECONDS)
        return True
        
    except Exception as exc:
        logger.error(f"Error saving leaderboard to Redis: {exc}")
        return False

def get_leaderboard(session_id: str, limit: int = 10) -> list[dict]:
    """
    Retrieve the leaderboard of active senders.
    
    This function implements a read-through cache mechanism:
    1. Attempts to retrieve leaderboard from Redis (fast).
    2. If Redis is unavailable or the key does not exist, it downloads the preprocessed 
       CSV file (post_processing_{session_id}.csv) from MinIO, recalculates the leaderboard,
       saves it to Redis for subsequent calls, and returns it.
       
    Args:
        session_id: The session ID for the leaderboard query.
        limit: Max number of senders to retrieve.
        
    Returns:
        A list of dictionaries representing the leaderboard.
    """
    redis_key = f"leaderboard:{session_id}"
    r = _get_redis_client()
    
    # 1. Try to read from Redis
    if r is not None:
        try:
            # ZREVRANGE fetches sorted set elements descending (highest score first)
            # scores=True returns tuple of (member, score)
            zset_data = r.zrevrange(redis_key, 0, limit - 1, withscores=True)
            if zset_data:
                leaderboard = []
                for idx, (username, score) in enumerate(zset_data):
                    leaderboard.append({
                        "rank": idx + 1,
                        "username": username,
                        "message_count": int(score)
                    })
                return leaderboard
        except Exception as exc:
            logger.warning(f"Error reading leaderboard from Redis, falling back: {exc}")

    # 2. Cache miss or Redis offline: Read from MinIO
    try:
        client = _get_minio_client()
        bucket_name = settings.MINIO_BUCKET
        object_name = f"post_processing_{session_id}.csv"
        
        # Download file from MinIO
        response = client.get_object(bucket_name, object_name)
        try:
            csv_bytes = response.read()
            df = pd.read_csv(io.BytesIO(csv_bytes), dtype=str)
        finally:
            response.close()
            response.release_conn()
            
        # Recalculate
        leaderboard = calculate_leaderboard_pandas(df, limit=limit)
        
        # Store in Redis asynchronously/safely for the next request
        if leaderboard:
            save_leaderboard_to_redis(session_id, df)
            
        return leaderboard
        
    except Exception as exc:
        logger.error(f"Failed to fetch leaderboard from MinIO/Pandas fallback: {exc}")
        return []
