import io
import json
import logging
import time
import os
from datetime import datetime
from typing import Dict, List

import anyio
import pandas as pd
import numpy as np
from fastapi import HTTPException, status

from app.config import settings
from app.infrastructure.storage import save_file, read_file, delete_file
from app.infrastructure.sse import progress_history, sse_manager
from app.utils.preprocessing import preprocess_dataframe
from app.utils.leaderboard import calculate_leaderboard_pandas
from app.utils.daily_graph import calculate_daily_graph_pandas
from app.schemas import (
    ResultsSummaryDTO,
    MetricsDTO,
    TopicDTO,
    SenderDTO,
    DateActivityDTO,
    HourActivityDTO,
    TopicDetailDTO,
    MessageDTO,
    MessageContextDTO,
    ContextMessageDTO
)

logger = logging.getLogger(__name__)

def parse_date(date_str: str) -> datetime | None:
    """Parse date string into datetime object with multiple format support."""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S", 
        "%Y-%m-%d %H:%M", 
        "%Y-%m-%d", 
        "%d/%m/%Y %H:%M:%S", 
        "%d/%m/%Y %H:%M", 
        "%d/%m/%Y",
        "%d/%m/%y %I.%M %p",
        "%d/%m/%y %H.%M",
        "%d/%m/%y %H:%M"
    ):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None

def calculate_hourly_activity(df: pd.DataFrame) -> list[dict]:
    """Calculate hourly message frequency count."""
    if df.empty or "timestamp" not in df.columns:
        return []
    df = df.copy()
    df["parsed_time"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df_clean = df.dropna(subset=["parsed_time"])
    if df_clean.empty:
        return []
    hourly_counts = df_clean.groupby(df_clean["parsed_time"].dt.hour).size()
    hourly_data = []
    for h in range(24):
        count = int(hourly_counts.get(h, 0))
        hourly_data.append({"hour": h, "count": count})
    return hourly_data

async def run_analysis_pipeline_task(
    session_id: str,
    df_raw: pd.DataFrame,
    original_csv_bytes: bytes,
):
    """Background task to run the complete data processing, BERTopic, and metrics calculation."""
    try:
        # Save original context file
        orig_object_name = f"{session_id}.csv"
        save_file(orig_object_name, original_csv_bytes)
        
        # 1. Update Step 1 Status
        event = {"step_id": 1, "status": "completed", "time_elapsed": "100ms"}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        # 2. Step 2: Preprocessing
        event = {"step_id": 2, "status": "running"}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        start_t = time.time()
        df_preprocessed = preprocess_dataframe(df_raw)
        
        if df_preprocessed.empty:
            err_event = {"step_id": 2, "status": "failed", "error": "Tidak ada pesan setelah preprocessing."}
            progress_history[session_id].append(err_event)
            await sse_manager.broadcast(session_id, err_event)
            return
            
        elapsed_2 = f"{int((time.time() - start_t) * 1000)}ms"
        
        event = {"step_id": 2, "status": "completed", "time_elapsed": elapsed_2}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        docs = df_preprocessed["Pesan_Preprocessed"].tolist()
        if len(docs) < 5:
            err_event = {"step_id": 3, "status": "failed", "error": "Jumlah pesan terlalu sedikit (min 5 pesan) untuk pemodelan topik."}
            progress_history[session_id].append(err_event)
            await sse_manager.broadcast(session_id, err_event)
            return
            
        # 3. Step 3: IndoBERTweet Embedding
        event = {"step_id": 3, "status": "running"}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        start_t = time.time()
        
        def encode_docs():
            from sentence_transformers import SentenceTransformer
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            local_model_path = os.path.join(base_dir, "models", "indobertweet-base-uncased")
            model_to_load = local_model_path if os.path.exists(local_model_path) else "indolem/indobertweet-base-uncased"
            embedder = SentenceTransformer(model_to_load)
            emb = embedder.encode(docs, batch_size=64, show_progress_bar=False, convert_to_numpy=True)
            return embedder, emb
            
        embedder, embeddings = await anyio.to_thread.run_sync(encode_docs)
        elapsed_3 = f"{int((time.time() - start_t) * 1000)}ms"
        
        event = {"step_id": 3, "status": "completed", "time_elapsed": elapsed_3}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        # 4. Step 4: UMAP Dimension Reduction
        event = {"step_id": 4, "status": "running"}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        start_t = time.time()
        
        def run_umap(emb):
            from umap import UMAP
            from app.utils.topic_modeling import SHARED_UMAP_PARAMS
            umap_model = UMAP(**SHARED_UMAP_PARAMS)
            reduced = umap_model.fit_transform(emb)
            return umap_model, reduced
            
        umap_model, reduced_embeddings = await anyio.to_thread.run_sync(run_umap, embeddings)
        elapsed_4 = f"{int((time.time() - start_t) * 1000)}ms"
        
        event = {"step_id": 4, "status": "completed", "time_elapsed": elapsed_4}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        # 5. Step 5: BIRCH Clustering
        event = {"step_id": 5, "status": "running"}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        start_t = time.time()
        
        def run_birch(reduced):
            from app.utils.topic_modeling import BirchWithOutliers
            birch_model = BirchWithOutliers(
                threshold=0.25,
                branching_factor=50,
                n_clusters=None,
                outlier_percentile=95.0,
                min_cluster_size=5,
                metric="cosine"
            )
            topics = birch_model.fit_predict(reduced)
            return birch_model, topics
            
        birch_model, topics = await anyio.to_thread.run_sync(run_birch, reduced_embeddings)
        elapsed_5 = f"{int((time.time() - start_t) * 1000)}ms"
        
        event = {"step_id": 5, "status": "completed", "time_elapsed": elapsed_5}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        # 6. Step 6: c-TF-IDF keyword extraction & evaluations
        event = {"step_id": 6, "status": "running"}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        start_t = time.time()
        
        def run_bertopic_fit(embedder, umap_model, birch_model, topics, embeddings):
            from bertopic import BERTopic
            from sklearn.feature_extraction.text import CountVectorizer
            from app.utils.topic_modeling import BM25Representation, STOPWORDS
            
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
            
            # Reduce topics using 'auto' only if there are enough topics to reduce
            unique_non_outliers = set(topic_model.topics_) - {-1}
            if len(unique_non_outliers) > 1:
                topic_model.reduce_topics(docs, nr_topics='auto')
            
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
            unique_topics = set(topic_model.topics_)
            topic_model.topic_representations_ = {}
            for tid in unique_topics:
                if tid == -1:
                    topic_model.topic_representations_[-1] = [("Lain-lain", 0.0)]
                    continue
                res = bm25_get_topic(tid)
                topic_model.topic_representations_[tid] = res if res else [("unknown", 0.0)]
            
            topics_info = topic_model.get_topic_info()
            topics_list = []
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
            
        topic_model, topics_list, topics = await anyio.to_thread.run_sync(
            run_bertopic_fit, embedder, umap_model, birch_model, topics, embeddings
        )
        elapsed_6 = f"{int((time.time() - start_t) * 1000)}ms"
        
        event = {"step_id": 6, "status": "completed", "time_elapsed": elapsed_6}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        # 7. Step 7: Hitung metrik evaluasi
        event = {"step_id": 7, "status": "running"}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        start_t = time.time()
        
        def run_bertopic_eval_only(topic_model, topics, embeddings):
            from app.utils.topic_modeling import (
                calculate_topic_diversity,
                calculate_npmi,
                calculate_embedding_density,
                calculate_intra_topic_similarity
            )
            
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
            
            metrics = {
                "topic_diversity": round(float(diversity), 4),
                "c_npmi": round(float(npmi), 4) if npmi is not None else 0.0,
                "embedding_density": round(float(ed), 4) if ed is not None else 0.0,
                "intra_topic_similarity": round(float(its), 4) if its is not None else 0.0,
            }
            return metrics
            
        metrics = await anyio.to_thread.run_sync(
            run_bertopic_eval_only, topic_model, topics, embeddings
        )
        elapsed_7 = f"{int((time.time() - start_t) * 1000)}ms"
        
        event = {"step_id": 7, "status": "completed", "time_elapsed": elapsed_7}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        # 8. Step 8: Simpan hasil analisis di database dengan kunci session_id / jobId
        event = {"step_id": 8, "status": "running"}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
        start_t = time.time()
        
        df_preprocessed["topic_id"] = topics
        leaderboard_data = calculate_leaderboard_pandas(df_preprocessed, limit=10)
        top_senders = [{"name": s["username"], "message_count": s["message_count"]} for s in leaderboard_data]
        active_dates = calculate_daily_graph_pandas(df_preprocessed, fill_missing=True)
        active_hours = calculate_hourly_activity(df_preprocessed)
        
        summary_data = {
            "metrics": metrics,
            "topic_count": len(topics_list),
            "topics": topics_list,
            "top_senders": top_senders,
            "active_dates": active_dates,
            "active_hours": active_hours
        }
        
        # Save summary result JSON
        result_json = json.dumps(summary_data, ensure_ascii=False)
        result_bytes = result_json.encode("utf-8")
        result_object_name = f"{session_id}_result.json"
        save_file(result_object_name, result_bytes)
        
        # Save labeled CSV
        label_map = {t["topic_id"]: t["label"] for t in topics_list}
        label_map[-1] = "Lain-lain"
        df_preprocessed["topic_label"] = df_preprocessed["topic_id"].map(label_map)
        
        labeled_csv_str = df_preprocessed.to_csv(index=False)
        labeled_csv_bytes = labeled_csv_str.encode("utf-8")
        labeled_object_name = f"{session_id}_labeled.csv"
        save_file(labeled_object_name, labeled_csv_bytes)
        
        elapsed_8 = f"{int((time.time() - start_t) * 1000)}ms"
        
        event = {"step_id": 8, "status": "completed", "time_elapsed": elapsed_8, "done": True}
        progress_history[session_id].append(event)
        await sse_manager.broadcast(session_id, event)
        
    except Exception as exc:
        logger.exception("Error inside background analysis task")
        err_event = {"status": "failed", "error": str(exc)}
        progress_history[session_id].append(err_event)
        await sse_manager.broadcast(session_id, err_event)

def get_results_summary(job_id: str) -> ResultsSummaryDTO:
    """Retrieve and parse results summary from storage."""
    object_name = f"{job_id}_result.json"
    try:
        content_bytes = read_file(object_name)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data untuk session_id tersebut tidak ditemukan di storage."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membaca storage: {e}"
        )
        
    try:
        data = json.loads(content_bytes.decode("utf-8"))
        
        metrics = MetricsDTO(**data["metrics"])
        topics = [TopicDTO(**t) for t in data["topics"]]
        top_senders = [SenderDTO(**s) for s in data["top_senders"]]
        active_dates = [DateActivityDTO(**d) for d in data["active_dates"]]
        active_hours = [HourActivityDTO(**h) for h in data["active_hours"]]
        
        return ResultsSummaryDTO(
            metrics=metrics,
            topic_count=data["topic_count"],
            topics=topics,
            top_senders=top_senders,
            active_dates=active_dates,
            active_hours=active_hours
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membaca format JSON hasil analisis: {str(exc)}"
        )

def delete_results(job_id: str) -> dict:
    """Delete all files and session history associated with job_id."""
    objects_to_delete = [
        f"{job_id}.csv",
        f"post_processing_{job_id}.csv",
        f"post_preprocessing_{job_id}.csv",
        f"{job_id}_result.json",
        f"{job_id}_labeled.csv"
    ]
    
    for obj_name in objects_to_delete:
        try:
            delete_file(obj_name)
        except Exception as exc:
            logger.warning(f"Gagal menghapus objek {obj_name}: {exc}")
            
    if job_id in progress_history:
        try:
            del progress_history[job_id]
        except Exception:
            pass
            
    return {"session_id": job_id}

def get_topic_detail(job_id: str, topic_id: int) -> TopicDetailDTO:
    """Retrieve detailed messages belonging to a specific topic cluster."""
    labeled_object_name = f"{job_id}_labeled.csv"
    result_object_name = f"{job_id}_result.json"
    
    try:
        csv_bytes = read_file(labeled_object_name)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data untuk session_id tersebut tidak ditemukan di storage."
        )
        
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes), dtype=str)
        if df.empty:
            return TopicDetailDTO(topic_id=topic_id, label=f"Topic {topic_id}", messages=[])
            
        df["topic_id"] = df["topic_id"].astype(int)
        df_topic = df[df["topic_id"] == topic_id]
        
        label = f"Topik {topic_id}"
        keywords = []
        try:
            result_bytes = read_file(result_object_name)
            result_data = json.loads(result_bytes.decode("utf-8"))
            for t in result_data.get("topics", []):
                if t.get("topic_id") == topic_id:
                    label = t.get("label", label)
                    keywords = t.get("keywords", [])
                    break
            if topic_id == -1:
                label = "Lain-lain"
        except Exception:
            pass
            
        # Urutkan pesan berdasarkan kecocokan kata kunci (keywords) representasi topik
        if keywords and not df_topic.empty:
            kw_set = [kw.lower() for kw in keywords]
            def calculate_row_score(row):
                msg_content = str(row.get("pesan", "")).lower()
                # Hitung berapa banyak kata kunci representasi yang muncul di pesan asli
                return sum(1 for kw in kw_set if kw in msg_content)
            
            df_topic = df_topic.copy()
            df_topic["match_score"] = df_topic.apply(calculate_row_score, axis=1)
            df_topic["index"] = pd.to_numeric(df_topic["index"], errors="coerce").fillna(0).astype(int)
            df_topic = df_topic.sort_values(by=["match_score", "index"], ascending=[False, True])

        messages = []
        for _, row in df_topic.iterrows():
            idx_val = row.get("index", "")
            sender_val = row.get("pengirim", "")
            content_val = row.get("pesan", "")
            timestamp_val = row.get("timestamp", "")
            
            messages.append(
                MessageDTO(
                    message_id=f"msg_{idx_val}",
                    sender=str(sender_val) if pd.notna(sender_val) else "",
                    content=str(content_val) if pd.notna(content_val) else "",
                    timestamp=str(timestamp_val) if pd.notna(timestamp_val) else ""
                )
            )
            
        return TopicDetailDTO(
            topic_id=topic_id,
            label=label,
            messages=messages
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membaca data detail klaster topik: {str(exc)}"
        )

def get_message_context(job_id: str, message_id: str) -> MessageContextDTO:
    """Retrieve chronological context (timeline) around a specific message."""
    original_object_name = f"{job_id}.csv"
    
    try:
        if message_id.startswith("msg_"):
            parts = message_id.split("_")
            target_index = int(parts[1])
        else:
            target_index = int(message_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Format ID pesan tidak valid: {message_id}"
        )
        
    try:
        csv_bytes = read_file(original_object_name)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data untuk session_id tersebut tidak ditemukan di storage."
        )
        
    try:
        df = pd.read_csv(io.BytesIO(csv_bytes), dtype=str)
        if df.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File riwayat chat kosong."
            )
            
        if "index" not in df.columns:
            df["index"] = df.index
        df["index"] = df["index"].astype(int)
        
        df_target = df[df["index"] == target_index]
        if df_target.empty:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pesan dengan ID {message_id} tidak ditemukan."
            )
            
        target_row = df_target.iloc[0]
        focused_msg = MessageDTO(
            message_id=message_id,
            sender=str(target_row.get("pengirim", "")) if pd.notna(target_row.get("pengirim")) else "",
            content=str(target_row.get("pesan", "")) if pd.notna(target_row.get("pesan")) else "",
            timestamp=str(target_row.get("timestamp", "")) if pd.notna(target_row.get("timestamp")) else ""
        )
        
        df_slice = df[df["index"].between(target_index - 5, target_index + 5)].sort_values("index")
        
        context_messages = []
        for _, row in df_slice.iterrows():
            row_idx = int(row.get("index"))
            sender_val = row.get("pengirim", "")
            content_val = row.get("pesan", "")
            timestamp_val = row.get("timestamp", "")
            
            context_messages.append(
                ContextMessageDTO(
                    message_id=f"msg_{row_idx}",
                    sender=str(sender_val) if pd.notna(sender_val) else "",
                    content=str(content_val) if pd.notna(content_val) else "",
                    timestamp=str(timestamp_val) if pd.notna(timestamp_val) else "",
                    is_focused=(row_idx == target_index)
                )
            )
            
        return MessageContextDTO(
            focused_message=focused_msg,
            context_messages=context_messages
        )
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memproses konteks timeline pesan: {str(exc)}"
        )
