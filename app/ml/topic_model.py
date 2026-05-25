"""
Modified BERTopic model factory.
===============================
Konfigurasi model topic modeling untuk pipeline chat analysis.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from bertopic import BERTopic
from minio import Minio
from scipy.sparse import csr_matrix, diags
from sentence_transformers import SentenceTransformer
from sklearn.cluster import Birch
from sklearn.feature_extraction.text import CountVectorizer
from umap import UMAP

from app.config import settings

try:
    from bertopic.vectorizers import ClassTfidfTransformer
except ImportError:  # pragma: no cover - fallback for older/newer bertopic layouts
    from bertopic.vectorizers._ctfidf import ClassTfidfTransformer


class BM25Transformer(ClassTfidfTransformer):
    """Custom BM25 Transformer untuk BERTopic."""

    def __init__(self, k1: float = 1.5, b: float = 0.75, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.k1 = k1
        self.b = b

    def fit(self, X, y=None, multiplier=None):
        """Fit BM25 model pada class-term matrix."""
        if hasattr(X, "toarray"):
            X_dense = X.toarray()
        else:
            X_dense = np.array(X)

        n_samples, _ = X_dense.shape

        if multiplier is not None:
            multiplier = np.array(multiplier).reshape(-1, 1)
            X_dense = X_dense * multiplier

        doc_lengths = X_dense.sum(axis=1)
        self._avgdl = doc_lengths.mean() if len(doc_lengths) > 0 and doc_lengths.mean() > 0 else 1.0
        df = (X_dense > 0).sum(axis=0)
        self._N = n_samples

        self._idf = np.asarray(np.log((self._N - df + 0.5) / (df + 0.5))).ravel()
        # Provide a sparse diagonal IDF matrix expected by some callers
        # (e.g., ClassTfidfTransformer implementations). Build it with an
        # explicit single offset so large vocabularies do not trigger
        # SciPy shape/offset ambiguity.
        self._idf_diag = diags([self._idf], [0], shape=(self._idf.size, self._idf.size), format="csr")
        # sklearn-compatible attribute
        self.idf_ = np.array(self._idf, copy=True)
        self.class_term_matrix_ = csr_matrix(X_dense)
        return self

    def transform(self, X, y=None):
        """Transform class-term matrix menjadi BM25 scores."""
        if hasattr(X, "toarray"):
            X_dense = X.toarray()
        else:
            X_dense = np.array(X)

        n_samples, n_features = X_dense.shape
        bm25_scores = np.zeros((n_samples, n_features))

        for i in range(n_samples):
            tf = X_dense[i, :]
            doc_len = tf.sum()

            if self._avgdl > 0:
                norm = 1.0 - self.b + self.b * (doc_len / self._avgdl)
            else:
                norm = 1.0

            numerator = tf * (self.k1 + 1.0)
            denominator = tf + self.k1 * norm
            denominator = np.where(denominator == 0, 1.0, denominator)

            bm25_scores[i, :] = self._idf * (numerator / denominator)

        return csr_matrix(bm25_scores)


def build_modified_bertopic_model() -> BERTopic:
    """Build BERTopic model dengan komponen modifikasi."""
    embedding_model = SentenceTransformer("indolem/indobertweet-base-uncased")
    umap_model = UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
    )
    cluster_model = Birch(
        n_clusters=None,
        threshold=0.4,
        branching_factor=50,
    )
    vectorizer_model = CountVectorizer(ngram_range=(1, 2))
    bm25_model = BM25Transformer(k1=1.5, b=0.75, reduce_frequent_words=True)

    topic_model_kwargs = {
        "embedding_model": embedding_model,
        "umap_model": umap_model,
        "vectorizer_model": vectorizer_model,
        "ctfidf_model": bm25_model,
        "calculate_probabilities": False,
        "verbose": False,
    }

    try:
        return BERTopic(cluster_model=cluster_model, **topic_model_kwargs)
    except TypeError:
        return BERTopic(hdbscan_model=cluster_model, **topic_model_kwargs)


def _minio_client() -> Minio:
    """Create configured MinIO client."""
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )


def _bucket_name() -> str:
    """Return the configured MinIO bucket name."""
    return settings.MINIO_BUCKET.strip()


def _model_prefix() -> str:
    """Normalize configured MinIO model prefix."""
    return settings.MINIO_MODEL_PATH.strip("/")


def _object_name(prefix: str, relative_path: str) -> str:
    """Build object name for a file stored under the model prefix."""
    return f"{prefix}/{relative_path.replace(os.sep, '/').lstrip('/')}"


def _ensure_bucket(client: Minio) -> None:
    """Create bucket when it does not exist yet."""
    bucket = _bucket_name()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def _list_model_objects(client: Minio, prefix: str) -> list[str]:
    """List all object names under the configured model prefix."""
    bucket = _bucket_name()
    objects: list[str] = []

    for item in client.list_objects(bucket, prefix=prefix, recursive=True):
        if item.object_name:
            objects.append(item.object_name)

    return objects


def _download_model_from_minio_sync() -> BERTopic | None:
    """Download the persisted BERTopic model from MinIO if it exists."""
    client = _minio_client()
    _ensure_bucket(client)

    prefix = _model_prefix()
    object_names = _list_model_objects(client, prefix)
    if not object_names:
        return None

    with tempfile.TemporaryDirectory() as temp_dir:
        model_root = Path(temp_dir)

        for object_name in object_names:
            relative_name = object_name[len(prefix):].lstrip("/")
            target_path = model_root / relative_name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            client.fget_object(_bucket_name(), object_name, str(target_path))

        return BERTopic.load(str(model_root))


def _save_model_to_minio_sync(model: BERTopic) -> None:
    """Persist BERTopic model into MinIO, replacing existing objects."""
    client = _minio_client()
    _ensure_bucket(client)

    prefix = _model_prefix()
    bucket = _bucket_name()

    for object_name in _list_model_objects(client, prefix):
        client.remove_object(bucket, object_name)

    with tempfile.TemporaryDirectory() as temp_dir:
        model_root = Path(temp_dir) / "model"
        model.save(
            str(model_root),
            serialization="safetensors",
            save_ctfidf=True,
            save_embedding_model=True,
        )

        for file_path in model_root.rglob("*"):
            if not file_path.is_file():
                continue

            relative_path = file_path.relative_to(model_root).as_posix()
            object_name = _object_name(prefix, relative_path)
            client.fput_object(bucket, object_name, str(file_path))


def _encode_documents_sync(model: BERTopic | None, documents: list[str]) -> Any:
    """Encode documents using the model embedding backend when available."""
    if model is None or not getattr(model, "embedding_model", None):
        return None

    embedding_model = model.embedding_model
    if hasattr(embedding_model, "encode"):
        return embedding_model.encode(documents, show_progress_bar=False)

    return None


def _update_model_sync(
    model: BERTopic | None,
    documents: list[str],
) -> tuple[BERTopic, list[int], Any, str]:
    """Train or incrementally update a BERTopic model."""
    if model is None:
        model = build_modified_bertopic_model()
        embeddings = _encode_documents_sync(model, documents)
        topics, probabilities = model.fit_transform(documents, embeddings=embeddings)
        return model, [int(topic) for topic in topics], probabilities, "trained"

    embeddings = _encode_documents_sync(model, documents)

    if hasattr(model, "partial_fit"):
        model.partial_fit(documents, embeddings=embeddings)
        topics, probabilities = model.transform(documents, embeddings=embeddings)
        return model, [int(topic) for topic in topics], probabilities, "updated"

    topics, probabilities = model.fit_transform(documents, embeddings=embeddings)
    return model, [int(topic) for topic in topics], probabilities, "refit"


async def load_model_from_minio() -> BERTopic | None:
    """Load persisted BERTopic model from MinIO."""
    return await asyncio.to_thread(_download_model_from_minio_sync)


async def save_model_to_minio(model: BERTopic) -> None:
    """Save BERTopic model into MinIO, replacing previous version."""
    await asyncio.to_thread(_save_model_to_minio_sync, model)


async def update_model(
    model: BERTopic | None,
    documents: list[str],
) -> tuple[BERTopic, list[int], Any, str]:
    """Fit a new model or incrementally update an existing one."""
    return await asyncio.to_thread(_update_model_sync, model, documents)


__all__ = [
    "BM25Transformer",
    "build_modified_bertopic_model",
    "load_model_from_minio",
    "save_model_to_minio",
    "update_model",
]
