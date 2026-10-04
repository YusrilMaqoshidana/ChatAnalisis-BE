import os
import logging
import torch
from app.config import settings

logger = logging.getLogger(__name__)

def get_vram_info_mb() -> tuple[float, float]:
    """Return (free_mb, total_mb) VRAM for CUDA device 0."""
    if torch.cuda.is_available():
        try:
            free_bytes, total_bytes = torch.cuda.mem_get_info()
            return free_bytes / (1024 * 1024), total_bytes / (1024 * 1024)
        except Exception as e:
            logger.warning(f"Failed to query VRAM info: {e}")
    return 0.0, 0.0

def resolve_device(session_id: str = "") -> torch.device:
    """
    Resolve target device (auto | cuda | cpu) with free VRAM check and explicit job logging.
    """
    mode = settings.DEVICE.lower()
    prefix = f"[JOB {session_id}] " if session_id else ""

    if mode == "cpu":
        logger.info(f"{prefix}Device mode set to CPU explicitly.")
        return torch.device("cpu")

    if not torch.cuda.is_available():
        logger.info(f"{prefix}CUDA is not available on system. Selected device: CPU")
        return torch.device("cpu")

    free_mb, total_mb = get_vram_info_mb()
    device_name = torch.cuda.get_device_name(0)

    if mode in ("auto", "cuda"):
        if free_mb < settings.MIN_FREE_VRAM_MB:
            logger.warning(
                f"{prefix}[FALLBACK ALERT] Free VRAM ({free_mb:.1f} MB) on {device_name} is below threshold ({settings.MIN_FREE_VRAM_MB} MB). "
                f"Falling back to CPU device for execution."
            )
            return torch.device("cpu")

        logger.info(
            f"{prefix}Selected device: CUDA ({device_name}) | Free VRAM: {free_mb:.1f} MB / Total: {total_mb:.1f} MB"
        )
        return torch.device("cuda")

    logger.info(f"{prefix}Fallback to default device: CPU")
    return torch.device("cpu")
