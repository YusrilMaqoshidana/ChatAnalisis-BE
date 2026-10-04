import os
import gc
import hashlib
import logging
import threading
from typing import List, Tuple
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.core.device import resolve_device

logger = logging.getLogger(__name__)

# Global in-memory LRU hash cache for text embeddings
_EMBEDDING_CACHE: dict[str, np.ndarray] = {}
_CACHE_MAX_SIZE = 50000

# Concurrency lock to restrict GPU execution to 1 job at a time
_GPU_SEMAPHORE = threading.Semaphore(1)

def get_text_hash(text: str) -> str:
    """Generate SHA256 hex digest for a text string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load_sentence_transformer_model(device: torch.device) -> SentenceTransformer:
    """Load SentenceTransformer model on the specified device (cuda / cpu)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    local_model_path = os.path.join(base_dir, "models", "indobertweet-base-uncased")
    model_path = local_model_path if os.path.exists(local_model_path) else "indolem/indobertweet-base-uncased"

    logger.info(f"[Embedding Service] Loading SentenceTransformer on {device} from: {model_path}")
    model = SentenceTransformer(model_path, device=device.type)
    if hasattr(model, "max_seq_length"):
        model.max_seq_length = settings.MAX_SEQ_LENGTH
    return model

def _encode_cpu_fallback(docs: List[str], target_indices: List[int], full_embeddings: np.ndarray):
    """Fallback execution on CPU for uncached documents."""
    logger.info(f"[CPU Fallback] Executing embedding encoding on CPU for {len(docs)} documents.")
    model = load_sentence_transformer_model(torch.device("cpu"))
    
    sorted_order = np.argsort([len(t) for t in docs])
    sorted_texts = [docs[i] for i in sorted_order]

    with torch.inference_mode():
        sorted_computed = model.encode(
            sorted_texts,
            batch_size=settings.GPU_INITIAL_BATCH_SIZE,
            show_progress_bar=False,
            convert_to_numpy=True
        )

    for sorted_idx, orig_doc_idx in enumerate(sorted_order):
        vector = sorted_computed[sorted_idx]
        original_idx = target_indices[orig_doc_idx]
        text = docs[orig_doc_idx]
        
        full_embeddings[original_idx] = vector
        if len(_EMBEDDING_CACHE) >= _CACHE_MAX_SIZE:
            _EMBEDDING_CACHE.pop(next(iter(_EMBEDDING_CACHE)))
        _EMBEDDING_CACHE[get_text_hash(text)] = vector

    return model, full_embeddings

def compute_embeddings_adaptive(session_id: str, docs: List[str]) -> Tuple[SentenceTransformer, np.ndarray]:
    """
    Compute embeddings with:
    - Text hash caching
    - Length sorting
    - GPU Semaphore (max 1 concurrent GPU job)
    - FP16 Autocast & Adaptive OOM batch halving
    - Automatic CPU fallback on persistent OOM
    """
    if not docs:
        device = resolve_device(session_id)
        model = load_sentence_transformer_model(device)
        return model, np.empty((0, 768), dtype=np.float32)

    # 1. Check in-memory hash cache
    uncached_indices: List[int] = []
    uncached_texts: List[str] = []
    cached_hits = 0

    full_embeddings = np.zeros((len(docs), 768), dtype=np.float32)

    for idx, text in enumerate(docs):
        text_hash = get_text_hash(text)
        if text_hash in _EMBEDDING_CACHE:
            full_embeddings[idx] = _EMBEDDING_CACHE[text_hash]
            cached_hits += 1
        else:
            uncached_indices.append(idx)
            uncached_texts.append(text)

    logger.info(f"[JOB {session_id}] Total docs: {len(docs)}, Cache hits: {cached_hits}, Uncached: {len(uncached_texts)}")

    if not uncached_texts:
        device = resolve_device(session_id)
        model = load_sentence_transformer_model(device)
        return model, full_embeddings

    target_device = resolve_device(session_id)

    if target_device.type == "cpu":
        return _encode_cpu_fallback(uncached_texts, uncached_indices, full_embeddings)

    # 2. Acquire GPU Semaphore for single-job GPU execution
    with _GPU_SEMAPHORE:
        logger.info(f"[JOB {session_id}] Acquired GPU semaphore for embedding execution.")
        batch_size = settings.GPU_INITIAL_BATCH_SIZE

        # Sort uncached texts by length to minimize batch padding overhead
        sorted_order = np.argsort([len(t) for t in uncached_texts])
        sorted_texts = [uncached_texts[i] for i in sorted_order]

        model = load_sentence_transformer_model(target_device)

        while batch_size >= 4:
            try:
                torch.cuda.empty_cache()
                gc.collect()

                logger.info(f"[JOB {session_id}] Attempting GPU encoding with batch_size={batch_size} (FP16 autocast)...")
                with torch.inference_mode(), torch.cuda.amp.autocast():
                    sorted_computed = model.encode(
                        sorted_texts,
                        batch_size=batch_size,
                        show_progress_bar=False,
                        convert_to_numpy=True
                    )

                # Population & Caching
                for sorted_idx, orig_doc_idx in enumerate(sorted_order):
                    vector = sorted_computed[sorted_idx]
                    original_idx = uncached_indices[orig_doc_idx]
                    text = uncached_texts[orig_doc_idx]
                    
                    full_embeddings[original_idx] = vector
                    if len(_EMBEDDING_CACHE) >= _CACHE_MAX_SIZE:
                        _EMBEDDING_CACHE.pop(next(iter(_EMBEDDING_CACHE)))
                    _EMBEDDING_CACHE[get_text_hash(text)] = vector

                torch.cuda.empty_cache()
                gc.collect()
                return model, full_embeddings

            except torch.cuda.OutOfMemoryError as exc:
                logger.warning(
                    f"[JOB {session_id} OOM ALERT] Caught torch.cuda.OutOfMemoryError at batch_size={batch_size}. "
                    f"Halving batch size to {batch_size // 2} and retrying..."
                )
                torch.cuda.empty_cache()
                gc.collect()
                batch_size = batch_size // 2

        logger.warning(
            f"[JOB {session_id} FALLBACK ALERT] GPU OOM persisted at min batch size (<4). "
            f"Switching remaining execution to CPU."
        )
        torch.cuda.empty_cache()
        gc.collect()
        return _encode_cpu_fallback(uncached_texts, uncached_indices, full_embeddings)
