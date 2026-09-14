import io
import logging
import pandas as pd

from app.infrastructure.storage import read_file

logger = logging.getLogger(__name__)

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

def get_leaderboard(session_id: str, limit: int = 10) -> list[dict]:
    """
    Retrieve the leaderboard of active senders from local storage.
       
    Args:
        session_id: The session ID for the leaderboard query.
        limit: Max number of senders to retrieve.
        
    Returns:
        A list of dictionaries representing the leaderboard.
    """
    try:
        object_name = f"{session_id}_labeled.csv"
        csv_bytes = read_file(object_name)
        df = pd.read_csv(io.BytesIO(csv_bytes), dtype=str)
        return calculate_leaderboard_pandas(df, limit=limit)
    except Exception as exc:
        logger.error(f"Failed to fetch leaderboard from Local Storage: {exc}")
        return []

