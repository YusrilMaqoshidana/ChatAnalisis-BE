from typing import Any, Dict, List, Tuple
import logging
import numpy as np
from umap import UMAP
from bertopic import BERTopic
from sklearn.feature_extraction.text import CountVectorizer

from app.infrastructure.model_manager import get_model_manager
from app.utils.topic_modeling import (
    SHARED_UMAP_PARAMS,
    ImprovedBirch3Jurnal,
    BM25Representation,
    STOPWORDS,
    calculate_topic_diversity,
    calculate_npmi,
    calculate_embedding_density,
    calculate_intra_topic_similarity
)

logger = logging.getLogger(__name__)

class TopicModelingService:
    """
    Kumpulan fungsi untuk menjalankan pemodelan topik:
    Mulai dari ekstraksi embedding, reduksi dimensi, klasterisasi BIRCH,
    hingga integrasi BERTopic dan evaluasi metrik topik.
    """

    @staticmethod
    def encode_documents(docs: List[str]) -> Tuple[Any, np.ndarray]:
        """Tujuan: Mengubah teks pesan menjadi vektor numerik (embedding) menggunakan IndoBERTweet."""
        manager = get_model_manager()
        embedder = manager.get_model()
        embeddings = manager.encode(docs)
        return embedder, embeddings

    @staticmethod
    def reduce_dimensions(embeddings: np.ndarray) -> Tuple[UMAP, np.ndarray]:
        """Tujuan: Mereduksi dimensi vektor embedding menggunakan algoritma UMAP agar lebih efisien diklasterkan."""
        umap_model = UMAP(**SHARED_UMAP_PARAMS)
        reduced = umap_model.fit_transform(embeddings)
        return umap_model, reduced

    @staticmethod
    def cluster_embeddings(reduced_embeddings: np.ndarray) -> Tuple[ImprovedBirch3Jurnal, List[int]]:
        """Tujuan: Mengelompokkan vektor pesan ke dalam klaster topik menggunakan algoritma BIRCH."""
        birch_model = ImprovedBirch3Jurnal(
            threshold="auto",
            branching_factor=50,
            n_clusters=None,
            alpha=2.0,
            min_cluster_size=5,
            metric="cosine"
        )
        topics = birch_model.fit_predict(reduced_embeddings)
        return birch_model, topics

    @staticmethod
    def fit_bertopic(
        docs: List[str],
        embeddings: np.ndarray,
        topics: List[int],
        birch_model: Any,
        umap_model: UMAP,
        embedder: Any
    ) -> Tuple[BERTopic, List[Dict[str, Any]], List[int]]:
        """
        Tujuan: Melatih model BERTopic dengan representasi BM25 untuk mengekstrak
        kata kunci representatif pada setiap kelompok topik yang terbentuk.
        """
        vectorizer_model = CountVectorizer(stop_words=list(STOPWORDS), ngram_range=(1, 2))
        bm25_model = BM25Representation(vectorizer=vectorizer_model, k1=1.2, b=0.5)

        topic_model = BERTopic(
            embedding_model=embedder,
            umap_model=umap_model,
            hdbscan_model=birch_model,
            vectorizer_model=vectorizer_model,
            ctfidf_model=bm25_model
        )
        topic_model.fit(docs, embeddings=embeddings, y=topics)

        # Gabungkan topik yang terlalu kecil jika jumlah topik mencukupi
        unique_non_outliers = set(topic_model.topics_) - {-1}
        if len(unique_non_outliers) > 1:
            topic_model.reduce_topics(docs, nr_topics='auto')

        # Ekstraksi kata kunci per topik berbasis BM25
        bm25_model.fit(docs)

        def bm25_get_topic(topic_id: int):
            if topic_id == -1:
                return [("Lain-lain", 0.0)]
            indices = np.where(np.array(topic_model.topics_) == topic_id)[0]
            if len(indices) == 0:
                return [("unknown", 0.0)]
            res = bm25_model.extract_topics(indices.tolist(), top_n=10)
            return res if res else [("unknown", 0.0)]

        topic_model.get_topic = bm25_get_topic

        # Perbarui representasi internal topik pada model
        unique_topics = set(topic_model.topics_)
        topic_model.topic_representations_ = {}
        for tid in unique_topics:
            if tid == -1:
                topic_model.topic_representations_[-1] = [("Lain-lain", 0.0)]
                continue
            res = bm25_get_topic(tid)
            topic_model.topic_representations_[tid] = res if res else [("unknown", 0.0)]

        # Bentuk daftar topik beserta label ringkas dan jumlah pesannya
        topics_info = topic_model.get_topic_info()
        topics_list: List[Dict[str, Any]] = []
        for _, row in topics_info.iterrows():
            tid = int(row['Topic'])
            if tid == -1:
                continue
            kws = [word for word, _ in topic_model.get_topic(tid)[:6]]
            label = ", ".join(kws[:3]).title()
            count = int(row['Count'])
            topics_list.append({
                "topic_id": tid,
                "label": label,
                "message_count": count,
                "keywords": kws
            })

        updated_topics = [int(t) for t in topic_model.topics_]
        return topic_model, topics_list, updated_topics

    @staticmethod
    def evaluate_metrics(
        topic_model: BERTopic,
        docs: List[str],
        topics: List[int],
        embeddings: np.ndarray,
        mode: str = "fast"
    ) -> Dict[str, float]:
        """
        Tujuan: Menghitung metrik evaluasi pemodelan topik:
        1. Topic Diversity: Mengukur keberagaman kosakata antar-topik
        2. c-NPMI: Mengukur koherensi semantik kata-kata dalam satu topik
        3. Embedding Density: Mengukur kerapatan klaster pada ruang embedding
        4. Intra-Topic Similarity: Mengukur kemiripan antar-dokumen dalam satu topik
        """
        if mode == "fast":
            return {
                "topic_diversity": 0.0,
                "c_npmi": 0.0,
                "embedding_density": 0.0,
                "intra_topic_similarity": 0.0,
            }

        diversity, topic_words_list, _ = calculate_topic_diversity(topic_model)
        npmi = calculate_npmi(docs, topic_words_list, topic_model.vectorizer_model)
        ed = calculate_embedding_density(
            embeddings=embeddings,
            labels=np.array(topics),
            topic_model=topic_model,
            docs=docs,
            vectorizer_model=topic_model.vectorizer_model
        )
        its = calculate_intra_topic_similarity(embeddings, np.array(topics))

        return {
            "topic_diversity": round(float(diversity), 4),
            "c_npmi": round(float(npmi), 4) if npmi is not None else 0.0,
            "embedding_density": round(float(ed), 4) if ed is not None else 0.0,
            "intra_topic_similarity": round(float(its), 4) if its is not None else 0.0,
        }
