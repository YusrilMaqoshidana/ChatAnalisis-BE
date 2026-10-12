import os
import logging
from typing import Optional, List
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

class ModelManager:
    """
    Singleton Manager untuk SentenceTransformer (IndoBERTweet).
    Menghilangkan overhead cold-start pemuatan model berulang di setiap request,
    serta menangani deteksi hardware adaptif (GPU CUDA vs CPU Multi-core).
    """
    _instance: Optional["ModelManager"] = None
    _model: Optional[SentenceTransformer] = None
    _device: Optional[str] = None

    def __new__(cls) -> "ModelManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def device(self) -> str:
        if self._device is None:
            config_device = getattr(settings, "TORCH_DEVICE", "auto").lower()
            if config_device == "auto":
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            elif config_device in ("cuda", "cpu"):
                self._device = config_device if (config_device != "cuda" or torch.cuda.is_available()) else "cpu"
            else:
                self._device = "cpu"
        return self._device

    def load_model(self) -> SentenceTransformer:
        """Memuat model IndoBERTweet ke dalam memori (singleton)."""
        if self._model is not None:
            return self._model

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        local_model_path = os.path.join(base_dir, "models", "indobertweet-base-uncased")
        model_name = local_model_path if os.path.exists(local_model_path) else "indolem/indobertweet-base-uncased"

        target_device = self.device
        logger.info(f"Menginisialisasi IndoBERTweet pada device: {target_device.upper()} (sumber: {model_name})")

        try:
            if target_device == "cuda":
                torch.cuda.empty_cache()

            self._model = SentenceTransformer(model_name, device=target_device)
            logger.info(f"IndoBERTweet berhasil dimuat ke dalam memori ({target_device.upper()}).")
        except Exception as e:
            logger.error(f"Gagal memuat model ke device {target_device}: {e}. Mencoba fallback ke CPU...")
            self._device = "cpu"
            self._model = SentenceTransformer(model_name, device="cpu")
            logger.info("IndoBERTweet berhasil dimuat dengan fallback CPU.")

        return self._model

    def get_model(self) -> SentenceTransformer:
        """Mengambil instance model yang sudah aktif."""
        if self._model is None:
            return self.load_model()
        return self._model

    def encode(self, docs: List[str], batch_size: Optional[int] = None) -> np.ndarray:
        """Menghasilkan embedding dokumen dengan manajemen batch dan memori."""
        model = self.get_model()

        if batch_size is None:
            default_bs = getattr(settings, "EMBEDDING_BATCH_SIZE", 64)
            # Tingkatkan throughput jika di GPU CUDA
            batch_size = default_bs if self.device != "cuda" else max(default_bs, 128)

        embeddings = model.encode(
            docs,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True
        )

        if self.device == "cuda":
            torch.cuda.empty_cache()

        return embeddings

    def cleanup(self) -> None:
        """Membersihkan alokasi memori saat shutdown."""
        if self._model is not None:
            del self._model
            self._model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("ModelManager dibersihkan.")

def get_model_manager() -> ModelManager:
    """Helper untuk mendapatkan singleton instance ModelManager."""
    return ModelManager()
