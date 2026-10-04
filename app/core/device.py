import os
import logging
import torch
from app.config import settings

logger = logging.getLogger(__name__)

def setup_cpu_environment() -> None:
    """Configure PyTorch CPU threading and environment settings."""
    num_threads = settings.TORCH_NUM_THREADS
    if num_threads <= 0:
        num_threads = os.cpu_count() or 4
    torch.set_num_threads(num_threads)
    logger.info(f"[CPU] Configured PyTorch CPU threads: {num_threads}")

def get_target_device() -> torch.device:
    """Always return CPU device on cpu branch."""
    return torch.device("cpu")
