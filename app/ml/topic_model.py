"""
Modified BERTopic model factory.
===============================
Konfigurasi model topic modeling untuk pipeline chat analysis.
"""

from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.cluster import Birch
from sklearn.feature_extraction.text import CountVectorizer
from sentence_transformers import SentenceTransformer
from umap import UMAP

from bertopic import BERTopic

try:
    from bertopic.vectorizers import ClassTfidfTransformer
except ImportError:  # pragma: no cover - fallback for older/newer bertopic layouts
    from bertopic.vectorizers._ctfidf import ClassTfidfTransformer


class BM25Transformer(ClassTfidfTransformer):
    """
    Custom BM25 Transformer untuk BERTopic.

    Mengimplementasikan BM25 scoring dengan parameter:
    - k1: term frequency saturation
    - b: document length normalization
    """

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

        self._idf = np.log((self._N - df + 0.5) / (df + 0.5))
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
    """
    Build BERTopic model dengan komponen modifikasi:
    - IndoBERTweet embeddings
    - UMAP 5D
    - Birch clustering
    - CountVectorizer bigram
    - BM25Transformer untuk c-TF-IDF
    """
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


__all__ = ["BM25Transformer", "build_modified_bertopic_model"]
