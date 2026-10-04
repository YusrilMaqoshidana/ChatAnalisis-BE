import os
import hashlib
import logging
from typing import List, Tuple
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.core.device import setup_cpu_environment, get_target_device

logger = logging.getLogger(__name__)

# Global in-memory LRU hash cache for text embeddings
# Key: SHA256(text), Value: numpy vector (dim 768)
_EMBEDDING_CACHE: dict[str, np.ndarray] = {}
_CACHE_MAX_SIZE = 50000

def get_text_hash(text: str) -> str:
    """Generate SHA256 hex digest for a text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def get_sentence_transformer_model() -> SentenceTransformer:
    """Load SentenceTransformer model on CPU."""
    setup_cpu_environment()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    local_model_path = os.path.join(base_dir, "models", "indobertweet-base-uncased")
    model_path = local_model_path if os.path.exists(local_model_path) else "indolem/indobertweet-base-uncased"

    logger.info(f"[CPU Embedding] Loading SentenceTransformer from: {model_path}")
    device = get_target_device()
    model = SentenceTransformer(model_path, device=device.type)
    
    if hasattr(model, "max_seq_length"):
        model.max_seq_length = settings.MAX_SEQ_LENGTH
        
    return model

def compute_embeddings_cpu(docs: List[str]) -> Tuple[SentenceTransformer, np.ndarray]:
    """
    Compute embeddings on CPU with:
    - Text hash caching
    - Length sorting to reduce zero-padding overhead
    - torch.inference_mode()
    """
    if not docs:
        model = get_sentence_transformer_model()
        return model, np.empty((0, 768), dtype=np.float32)

    # 1. Check in-memory hash cache
    uncached_indices: List[int] = []
    uncached_texts: List[str] = []
    cached_hits = 0

    embeddings = np.zeros((len(docs), 768), dtype=np.float32)

    for idx, text in enumerate(docs):
        text_hash = get_text_hash(text)
        if text_hash in _EMBEDDING_CACHE:
            embeddings[idx] = _EMBEDDING_CACHE[text_hash]
            cached_hits += 1
        else:
            uncached_indices.append(idx)
            uncached_texts.append(text)

    logger.info(f"[CPU Embedding] Total docs: {len(docs)}, Cache hits: {cached_hits}, Uncached: {len(uncached_texts)}")

    model = get_sentence_transformer_model()

    if uncached_texts:
        # 2. Sort uncached texts by length to minimize batch padding overhead
        sorted_order = np.argsort([len(t) for t in uncached_texts])
        sorted_texts = [uncached_texts[i] for i in sorted_order]

        batch_size = settings.EMBEDDING_BATCH_SIZE
        
        with torch.inference_mode():
            sorted_computed = model.encode(
                sorted_texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )

        # Restore original uncached list order and populate main embeddings + cache
        for sorted_idx, orig_uncached_idx in enumerate(sorted_order):
            vector = sorted_computed[sorted_idx]
            original_doc_idx = uncached_indices[orig_uncached_idx]
            text = uncached_texts[orig_uncached_idx]
            
            embeddings[original_doc_idx] = vector

            # Update cache (evict LRU if max size exceeded)
            if len(_EMBEDDING_CACHE) >= _CACHE_MAX_SIZE:
                # Remove oldest entry
                first_key = next(iter(_EMBEDDING_CACHE))
                del _EMBEDDING_CACHE[first_key]
            _EMBEDDING_CACHE[get_text_hash(text)] = vector

    return model, embeddings
