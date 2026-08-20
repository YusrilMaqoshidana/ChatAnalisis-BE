import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Determine the project root directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR / "storage"

# Create storage directory if it doesn't exist
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

def get_file_path(filename: str) -> Path:
    """Get absolute path for a filename within the storage directory, preventing path traversal."""
    safe_filename = os.path.basename(filename)
    resolved_storage_dir = STORAGE_DIR.resolve()
    resolved_path = (resolved_storage_dir / safe_filename).resolve()
    
    # Path traversal check
    if not resolved_path.is_relative_to(resolved_storage_dir):
        raise ValueError(f"Path traversal detected: {filename}")
        
    return resolved_path

def save_file(filename: str, content: bytes) -> None:
    """Save content bytes to a file in the local storage."""
    try:
        file_path = get_file_path(filename)
        with open(file_path, "wb") as f:
            f.write(content)
        logger.info(f"Saved file to local storage: {filename}")
    except Exception as e:
        logger.error(f"Failed to save file {filename}: {e}")
        raise e

def read_file(filename: str) -> bytes:
    """Read content bytes from a file in local storage."""
    file_path = get_file_path(filename)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {filename}")
    try:
        with open(file_path, "rb") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read file {filename}: {e}")
        raise e

def delete_file(filename: str) -> None:
    """Delete a file from local storage if it exists."""
    try:
        file_path = get_file_path(filename)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted file from local storage: {filename}")
    except Exception as e:
        logger.warning(f"Failed to delete file {filename}: {e}")

import time

def cleanup_old_files(max_age_hours: float = 24.0) -> None:
    """Scans storage directory and deletes files older than max_age_hours."""
    try:
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        resolved_storage_dir = STORAGE_DIR.resolve()
        for file_path in resolved_storage_dir.iterdir():
            if file_path.is_file():
                file_mtime = file_path.stat().st_mtime
                if (now - file_mtime) > max_age_seconds:
                    try:
                        file_path.unlink()
                        logger.info(f"Automatically cleaned up old file: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Failed to delete old file {file_path.name}: {e}")
    except Exception as e:
        logger.error(f"Error during automatic cleanup: {e}")
