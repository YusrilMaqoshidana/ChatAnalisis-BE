"""
Utility module for BERTopic modeling and evaluation.
Implements the proposed pipeline: IndoBERTweet + UMAP + BIRCH Clustering + evaluation metrics.
"""

import os
import logging
from typing import List, Tuple, Dict, Optional
import numpy as np
import pandas as pd
from scipy.special import gammaln
from sentence_transformers import SentenceTransformer
from umap import UMAP
from sklearn.cluster import Birch
from sklearn.metrics.pairwise import cosine_similarity
from bertopic import BERTopic
from gensim.corpora.dictionary import Dictionary
from gensim.models.coherencemodel import CoherenceModel
import gc
import torch

logger = logging.getLogger(__name__)

from bertopic.vectorizers import ClassTfidfTransformer
from scipy.sparse import csr_matrix
import emoji

# ==========================================
# CUSTOM STOPWORDS FOR WHATSAPP CORPUS
# ==========================================

FORMAL_ID = {
    "yang", "di", "dan", "atau", "dari", "ke", "itu", "ini", "saja", "tidak",
    "ada", "with", "dengan", "adalah", "akan", "atas", "oleh", "sebagai", "pada",
    "para", "tersebut", "sebuah", "bahwa", "dalam", "tanpa", "setelah",
    "sebelum", "karena", "kalau", "jika", "agar", "supaya", "hingga",
    "sampai", "hanya", "juga", "untuk", "buat", "namun", "tapi", "tetapi",
    "walaupun", "meskipun", "sehingga", "maka", "lalu", "kemudian", "serta",
    "yaitu", "yakni", "apabila", "bila", "seperti", "bagai", "bagaikan",
    "adapun", "demikian", "begitu", "seolah", "seakan", "andai", "andaikan",
    "sedangkan", "melainkan", "kecuali", "selain", "termasuk", "berupa",
    "secara", "guna", "demi", "akibat", "sebab", "asal", "asalkan",
    "bahkan", "justru", "pula", "lagi", "lagipula", "apalagi", "bahwasanya",
    "diri", "sendiri", "masing", "setiap", "tiap", "semua", "seluruh",
    "segala", "beberapa", "sebagian", "banyak", "sedikit", "lebih",
    "kurang", "paling", "sangat", "amat", "cukup", "terlalu", "makin",
    "semakin", "kian", "agak",
}

DEIKTIK_TANYA = {
    "sini", "situ", "sana", "disini", "disitu", "disana", "kemari", "kesini",
    "kesitu", "kesana", "apa", "apakah", "siapa", "kenapa", "mengapa",
    "bagaimana", "gimana", "kapan", "dimana", "darimana", "kemana", "mana",
    "berapa", "kah",
    "waktu", "saat", "ketika", "sekarang", "nanti", "besok", "kemarin",
    "dulu", "tadi", "sedang", "masih", "sudah", "belum", "akan", "pernah",
    "selalu", "sering", "jarang", "kadang", "biasanya", "langsung",
    "sekali", "kembali", "terus", "mulai",
}

PRONOMINA_SAPAAN = {
    "aku", "saya", "gue", "gua", "gw", "ku", "kau", "kamu", "kalian",
    "kita", "kami", "dia", "beliau", "mereka", "nya", "diriku", "kau",
    "anda", "orang",
    "kak", "kakk", "kakak", "bang", "mas", "bro", "guys", "ka", "user",
}

PARTIKEL_FILLER = {
    "ya", "yaa", "yaaa", "iya", "iyaa", "sih", "deh", "dong", "nih", "kan",
    "kok", "lho", "loh", "lah", "toh", "eh", "ehh", "oh", "ohh", "ah",
    "hmm", "nah", "wah", "duh", "aduh", "halo", "hai", "haii",
    "wkwk", "wkwkw", "wkwkwk", "wkwkwkw", "wkwkwkwk", "hahaha", "haha",
    "hehe", "hehehe", "xixixi",
    "btw", "oke", "ok", "okay", "yuk", "yuks", "makanya", "soalnya",
    "pokoknya", "intinya", "maksudnya", "kayaknya", "kayanya", "sebenarnya",
    "sebenernya", "beneran", "bener", "betul", "emang",
    "emg", "memang", "justru", "cuma", "cuman", "hanya", "doang",
}

SINGKATAN_GAUL = {
    "gitu", "gini", "klo", "kalo", "kayak", "kaya", "kyk", "kek", "tp",
    "tpi", "sm", "ama", "dr", "dll", "org", "jd", "blm", "udh", "udah",
    "skrg", "bgt", "banget", "aja", "ga", "gak", "nggak", "ngga", "enggak",
    "engga", "gaada", "gatau", "tau", "tahu", "krn", "karna", "utk",
    "yg", "dgn", "sdh", "blom", "dlu", "abis", "trus", "trs", "lg",
    "pake", "pakai", "bikin", "bilang", "nyari", "cari", "liat", "lihat",
    "denger", "dengar", "nanya", "tanya", "inget", "ingat", "lupa",
    "dapet", "dapat", "sempet", "sempat", "sampe", "sampai", "ampe",
    "kalian", "temen", "teman", "punya", "boleh", "harus", "perlu",
    "bisa", "mau", "pengen", "pengin", "ingin", "coba", "biar", "biarin",
    "gapapa", "gpp", "gada", "adain", "ngomong", "bahas", "share",
    "join", "izin", "perkenalan", "perkenalkan", "kenal", "kenapa",
}

FUNGSI_TAMBAHAN = {
    "jadi", "sama", "baru", "bukan", "mungkin", "suka", "tertawa", "cukup",
    "hal", "kali", "bakal", "padahal", "berarti", "seru", "kata",
    "katanya", "an", "satu", "dua", "tiga", "pas", "kasih", "lain",
    "salah", "tentang", "malah", "terima", "hari", "si", "nama", "namanya"
}

ENGLISH_NOISE = {
    "the", "of", "and", "to", "a", "is", "it", "in", "you", "that", "but",
    "no", "for", "this", "my", "me", "so", "as", "all", "on", "by", "not",
    "like", "with", "just", "good", "see", "thank", "thanks", "welcome",
    "current", "self", "i", "s", "d", "v", "m", "t", "book",
}

EMOJI_WORDS = {
    info["en"].strip(":").lower()
    for _, info in emoji.EMOJI_DATA.items()
    if "en" in info
}

PLATFORM_NOISE = {
    "clan", "bookclan", "grup", "group", "ig", "wa", "admin",
}

STOPWORDS = (
    FORMAL_ID
    | DEIKTIK_TANYA
    | PRONOMINA_SAPAAN
    | PARTIKEL_FILLER
    | SINGKATAN_GAUL
    | FUNGSI_TAMBAHAN
    | ENGLISH_NOISE
    | EMOJI_WORDS
    | PLATFORM_NOISE
)

class BirchWithOutliers(Birch):
    """
    Custom BIRCH Clustering model with outlier detection using distance percentile thresholding
    and dwarf cluster cleanup.
    """
    def __init__(
        self,
        threshold: float = 0.5,
        branching_factor: int = 50,
        n_clusters=None,
        outlier_percentile: float = 85.0, # top X% of furthest docs from cluster centroid defined as outliers
        min_cluster_size: int = 5,        # clusters with sizes below this are discarded to -1
        metric: str = "cosine",
    ):
        super().__init__(
            threshold=threshold,
            branching_factor=branching_factor,
            n_clusters=n_clusters,
        )
        self.outlier_percentile = outlier_percentile
        self.min_cluster_size = min_cluster_size
        self.metric = metric
        self.labels_ = None

    def fit(self, X, y=None):
        super().fit(X, y)
        raw_labels = self.labels_.copy()
        unique_labels = np.unique(raw_labels)

        if len(unique_labels) <= 1:
            return self

        final_labels = raw_labels.copy()

        # 1. Compute centroids
        centroids = {}
        for label in unique_labels:
            if label == -1:
                continue
            centroids[label] = X[raw_labels == label].mean(axis=0)

        # 2. Compute distances to centroid
        distances = np.zeros(len(X))
        for i, (emb, label) in enumerate(zip(X, raw_labels)):
            if label == -1:
                continue
            centroid = centroids[label]
            if self.metric == "cosine":
                dot = np.dot(emb, centroid)
                norm_emb = np.linalg.norm(emb)
                norm_cen = np.linalg.norm(centroid)
                distances[i] = 1.0 - (dot / (norm_emb * norm_cen)) if norm_emb > 0 and norm_cen > 0 else 1.0
            else:
                distances[i] = np.linalg.norm(emb - centroid)

        # 3. Percentile-based outlier filter per cluster
        for label in unique_labels:
            if label == -1:
                continue
            cluster_mask = raw_labels == label
            cluster_dists = distances[cluster_mask]

            if len(cluster_dists) > self.min_cluster_size:
                thresh = np.percentile(cluster_dists, self.outlier_percentile)
                outlier_indices = np.where(cluster_mask & (distances > thresh))[0]
                final_labels[outlier_indices] = -1

        # 4. Clean up dwarf clusters
        for label in np.unique(final_labels):
            if label == -1:
                continue
            cluster_size = np.sum(final_labels == label)
            if cluster_size < self.min_cluster_size:
                final_labels[final_labels == label] = -1

        self.labels_ = final_labels
        return self

    def fit_predict(self, X, y=None):
        self.fit(X, y)
        return self.labels_

class BM25Representation:
    def __init__(self, vectorizer=None, k1=1.5, b=0.75):
        from sklearn.feature_extraction.text import CountVectorizer
        self.vectorizer = vectorizer if vectorizer else CountVectorizer(ngram_range=(1, 2))
        self.k1 = k1
        self.b = b
        self.idf_dict = {}
        self.avgdl = 0.0
        self.doc_lengths = None
        self.corpus_matrix = None
        # Compatibility with BERTopic
        self.seed_words = None
        self.seed_multiplier = None
        self._idf_diag = None

    def fit(self, docs, y=None, multiplier=None):
        import scipy.sparse as sp
        # Guard: internal BERTopic call with class-term sparse matrix
        if sp.issparse(docs) or (hasattr(docs, "shape") and len(docs.shape) > 1):
            self._idf_diag = sp.diags(np.ones(docs.shape[1]))
            return self

        # Fit or transform vectorizer
        if hasattr(self.vectorizer, 'vocabulary_'):
            self.corpus_matrix = self.vectorizer.transform(docs)
        else:
            self.corpus_matrix = self.vectorizer.fit_transform(docs)

        self.doc_lengths = self.corpus_matrix.sum(axis=1).A1
        N = self.corpus_matrix.shape[0]
        self.avgdl = self.doc_lengths.mean()

        feature_names = self.vectorizer.get_feature_names_out()
        df = np.bincount(
            self.corpus_matrix.indices,
            minlength=self.corpus_matrix.shape[1]
        )
        # Standard document-level BM25 IDF formula
        idf = np.log((N - df + 0.5) / (df + 0.5))
        self.idf_dict = {word: idf[i] for i, word in enumerate(feature_names)}
        return self

    def transform(self, X):
        return X

    def extract_topics(self, cluster_docs_indices, top_n=10):
        if self.corpus_matrix is None:
            raise RuntimeError("BM25Representation belum di-fit.")
        if not cluster_docs_indices:
            return []

        cluster_matrix = self.corpus_matrix[cluster_docs_indices, :]
        if cluster_matrix.nnz == 0:
            return []

        doc_lengths = self.doc_lengths[cluster_docs_indices]
        n_docs_in_cluster = cluster_matrix.shape[0]

        row_indices = np.repeat(
            np.arange(n_docs_in_cluster),
            np.diff(cluster_matrix.indptr)
        )

        K = self.k1 * (1.0 - self.b + self.b * doc_lengths[row_indices] / self.avgdl)
        tf_data = cluster_matrix.data
        val = tf_data * (self.k1 + 1.0) / (tf_data + K)

        feature_names = self.vectorizer.get_feature_names_out()
        idf_array = np.array([self.idf_dict[word] for word in feature_names])
        col_indices = cluster_matrix.indices
        bm25_data = val * idf_array[col_indices]

        bm25_matrix = csr_matrix(
            (bm25_data, col_indices, cluster_matrix.indptr),
            shape=cluster_matrix.shape
        )

        total_scores = bm25_matrix.sum(axis=0).A1

        scores = [
            (word, float(score))
            for word, score in zip(feature_names, total_scores)
            if score > 0
        ]
        return sorted(scores, key=lambda x: x[1], reverse=True)[:top_n]

SHARED_UMAP_PARAMS = dict(
    n_neighbors=25,
    n_components=5,
    min_dist=0.0,
    metric="cosine",
    random_state=42,
)

# 1. Topic Diversity
def calculate_topic_diversity(topic_model, n_words: int = 10) -> Tuple[float, List[List[str]], set]:
    topics = topic_model.get_topics()
    # Filter out outlier topic (-1)
    topics_to_eval = {tid: tval for tid, tval in topics.items() if tid != -1}

    all_words = set()
    topic_words_list = []
    for topic_id in topics_to_eval:
        words = [word for word, _ in topic_model.get_topic(topic_id)[:n_words]]
        topic_words_list.append(words)
        all_words.update(words)

    K = len(topic_words_list)
    total = K * n_words
    diversity = len(all_words) / total if total > 0 else 0.0
    return diversity, topic_words_list, all_words

# 2. Topic Coherence NPMI
def calculate_npmi(texts: List[str], topic_words_list: List[List[str]], vectorizer_model=None) -> Optional[float]:
    if not topic_words_list:
        return None
    try:
        if vectorizer_model is not None and hasattr(vectorizer_model, 'build_analyzer'):
            analyzer = vectorizer_model.build_analyzer()
            tokenized = [analyzer(text) for text in texts]
        else:
            tokenized = [text.lower().split() for text in texts]

        dictionary = Dictionary(tokenized)
        valid_ids = set(dictionary.token2id.keys())

        filtered = [[w for w in words if w in valid_ids] for words in topic_words_list]
        filtered = [w for w in filtered if len(w) >= 2]

        if not filtered:
            return None

        # Set processes=1 to avoid deadlocks when PyTorch has initialized CUDA.
        model = CoherenceModel(
            topics=filtered,
            texts=tokenized,
            dictionary=dictionary,
            coherence='c_npmi',
            processes=1
        )
        return float(model.get_coherence())
    except Exception as e:
        print(f"Error NPMI: {e}")
        return None

# 3. Embedding Density (Rushkin 2020)
def _bandwidth(embeddings: np.ndarray) -> float:
    N, d = embeddings.shape
    if N < 2:
        return 1.0
    norms = np.linalg.norm(embeddings, axis=1)
    r = np.percentile(norms, 10)
    R = np.percentile(norms, 90)
    if R <= r or R <= 0:
        std_per_dim = np.std(embeddings, axis=0)
        std_per_dim = np.where(std_per_dim < 1e-8, 1.0, std_per_dim)
        h_s = std_per_dim * (4 / (N * (d + 2))) ** (1 / (d + 4))
        return float(np.exp(np.mean(np.log(h_s))))

    log_gc = (d / 2) * np.log(np.pi) - gammaln(1 + d / 2)
    log_v_R = log_gc + d * np.log(R)
    log_v_r = log_gc + d * np.log(r)
    if log_v_r >= log_v_R:
        std_per_dim = np.std(embeddings, axis=0)
        std_per_dim = np.where(std_per_dim < 1e-8, 1.0, std_per_dim)
        h_s = std_per_dim * (4 / (N * (d + 2))) ** (1 / (d + 4))
        return float(np.exp(np.mean(np.log(h_s))))

    log_V = log_v_R + np.log1p(-np.exp(log_v_r - log_v_R))
    h_V = np.exp((log_V - np.log(N)) / d)
    if not np.isfinite(h_V) or h_V <= 0:
        return 1.0
    return float(h_V)

def _topic_density(cluster_emb: np.ndarray, cluster_weights: np.ndarray) -> Optional[float]:
    if len(cluster_emb) < 2:
        return None
    centroid = np.mean(cluster_emb, axis=0)
    h = _bandwidth(cluster_emb)
    h = max(h, 1e-8)
    diff = (centroid - cluster_emb) / h
    log_K = -0.5 * np.sum(diff * diff, axis=1)
    log_K_max = np.max(log_K)
    K = np.exp(log_K - log_K_max)
    denom = np.sum(K)
    if denom == 0:
        return None
    rho = np.sum(K * cluster_weights) / denom
    return float(rho) if np.isfinite(rho) else None

def _compute_semantic_weights(
    embeddings: np.ndarray,
    labels: np.ndarray,
    topic_model,
    docs: List[str],
    vectorizer_model=None
) -> np.ndarray:
    n_docs = len(docs)
    doc_weights = np.ones(n_docs)

    if vectorizer_model is not None and hasattr(vectorizer_model, 'build_analyzer'):
        analyzer = vectorizer_model.build_analyzer()
        tokenized = [set(analyzer(doc)) for doc in docs]
    else:
        tokenized = [set(doc.lower().split()) for doc in docs]

    unique_topics = [t for t in np.unique(labels) if t != -1]

    for tid in unique_topics:
        mask = np.where(labels == tid)[0]
        try:
            topic_words = topic_model.get_topic(tid)
        except Exception:
            continue
        if not topic_words:
            continue

        word_scores = {word: score for word, score in topic_words}

        raw_scores = np.zeros(len(mask))
        for i, doc_idx in enumerate(mask):
            doc_tokens = tokenized[doc_idx]
            raw_scores[i] = sum(word_scores[w] for w in doc_tokens if w in word_scores)

        min_s, max_s = raw_scores.min(), raw_scores.max()
        if max_s > min_s:
            raw_scores = (raw_scores - min_s) / (max_s - min_s)
        else:
            raw_scores = np.ones(len(mask))

        doc_weights[mask] = raw_scores

    return doc_weights

def calculate_embedding_density(
    embeddings: np.ndarray,
    labels: np.ndarray,
    topic_model=None,
    docs: List[str] = None,
    vectorizer_model=None,
    doc_weights: Optional[np.ndarray] = None
) -> Optional[float]:
    if doc_weights is None and topic_model is not None and docs is not None:
        doc_weights = _compute_semantic_weights(
            embeddings, labels, topic_model, docs, vectorizer_model
        )
    if doc_weights is None:
        doc_weights = np.ones(len(embeddings))

    densities = []
    valid_topics = [t for t in np.unique(labels) if t != -1]
    for tid in valid_topics:
        mask = labels == tid
        rho = _topic_density(embeddings[mask], doc_weights[mask])
        if rho is not None:
            densities.append(rho)
    return float(np.mean(densities)) if densities else None

# 4. Intra-topic Similarity
def calculate_intra_topic_similarity(
    embeddings: np.ndarray,
    labels: np.ndarray,
    max_sample: int = 500
) -> Optional[float]:
    its_scores = []
    unique_labels = [l for l in np.unique(labels) if l != -1]
    for label in unique_labels:
        cluster = embeddings[labels == label]
        if len(cluster) < 2:
            continue
        if len(cluster) > max_sample:
            idx = np.random.choice(len(cluster), max_sample, replace=False)
            cluster = cluster[idx]
        sim_matrix = cosine_similarity(cluster)
        n = len(cluster)
        its = (sim_matrix.sum() - n) / (n * (n - 1))
        its_scores.append(its)
    return float(np.mean(its_scores)) if its_scores else None


def run_topic_modeling_pipeline(
    docs: List[str],
    embedding_model_name: str = "indolem/indobertweet-base-uncased",
) -> Tuple[BERTopic, List[int], Dict[str, float]]:
    """Runs the Proposed BERTopic (IndoBERTweet + UMAP + BIRCH) pipeline and returns metrics."""
    if not docs:
        raise ValueError("Cannot run topic modeling on empty document list.")

    # Resolve local model path
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    local_model_path = os.path.join(base_dir, "models", "indobertweet-base-uncased")

    if os.path.exists(local_model_path):
        logger.info(f"Loading SentenceTransformer model from local path: {local_model_path}")
        model_name_to_load = local_model_path
    else:
        logger.info(f"Loading SentenceTransformer model from Hugging Face Hub: {embedding_model_name}")
        model_name_to_load = embedding_model_name

    # 1. Load embedding model and extract embeddings
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()

    embedder = SentenceTransformer(model_name_to_load)
    embeddings = embedder.encode(
        docs,
        batch_size=64,
        show_progress_bar=False,
        convert_to_numpy=True
    )

    # 2. Build UMAP
    umap_model = UMAP(**SHARED_UMAP_PARAMS)

    # 3. Build BIRCH Clustering with outliers and proposed params
    birch_model = BirchWithOutliers(
        threshold=0.25,
        branching_factor=50,
        n_clusters=None,
        outlier_percentile=95.0,
        min_cluster_size=5,
        metric="cosine"
    )

    from sklearn.feature_extraction.text import CountVectorizer

    # 3b. CountVectorizer with ngram_range=(1, 2) and BM25 document-level representation replacement
    vectorizer_model = CountVectorizer(stop_words=list(STOPWORDS), ngram_range=(1, 2))
    bm25_model = BM25Representation(vectorizer=vectorizer_model, k1=1.2, b=0.5)

    # 4. Build BERTopic model
    topic_model = BERTopic(
        embedding_model=embedder,
        umap_model=umap_model,
        hdbscan_model=birch_model,
        vectorizer_model=vectorizer_model,
        ctfidf_model=bm25_model,
    )

    # 5. Fit model
    topics, probs = topic_model.fit_transform(docs, embeddings=embeddings)
    
    # Call reduce topics if there are enough topics to reduce
    unique_non_outliers = set(topic_model.topics_) - {-1}
    if len(unique_non_outliers) > 1:
        topic_model.reduce_topics(docs, nr_topics='auto')
    topics = [int(t) for t in topic_model.topics_]

    # Fit standard document-level BM25
    bm25_model.fit(docs)

    # Monkey-patch get_topic for document-level BM25 extraction
    def bm25_get_topic(topic_id):
        if topic_id == -1:
            return [("Lain-lain", 0.0)]
        indices = np.where(np.array(topic_model.topics_) == topic_id)[0]
        if len(indices) == 0:
            return [("unknown", 0.0)]
        res = bm25_model.extract_topics(indices.tolist(), top_n=10)
        return res if res else [("unknown", 0.0)]

    topic_model.get_topic = bm25_get_topic

    # Update topic_representations_ internal state
    unique_topics = set(topics)
    topic_model.topic_representations_ = {}
    for tid in unique_topics:
        if tid == -1:
            topic_model.topic_representations_[-1] = [("Lain-lain", 0.0)]
            continue
        res = bm25_get_topic(tid)
        topic_model.topic_representations_[tid] = res if res else [("unknown", 0.0)]

    # 6. Calculate Evaluation Metrics
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

    # Clean memory
    del embedder
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    gc.collect()

    metrics = {
        "topic_diversity": float(diversity),
        "c_npmi": float(npmi) if npmi is not None else 0.0,
        "embedding_density": float(ed) if ed is not None else 0.0,
        "intra_topic_similarity": float(its) if its is not None else 0.0,
    }

    return topic_model, topics, metrics
