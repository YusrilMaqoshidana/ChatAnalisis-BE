import logging
import time
import anyio
import pandas as pd

from app.infrastructure.storage import save_file
from app.utils.preprocessing import preprocess_dataframe
from app.utils.leaderboard import calculate_leaderboard_pandas
from app.utils.daily_graph import calculate_daily_graph_pandas
from app.utils.hourly_graph import calculate_hourly_activity
from app.utils.date_utils import parse_date
from app.services.progress_tracker import PipelineProgressTracker
from app.services.topic_modeling_service import TopicModelingService
from app.services.analysis_result_service import (
    save_analysis_results,
    get_results_summary,
    delete_results,
    get_topic_detail,
    get_message_context
)

# Daftar fungsi yang diekspor agar bisa langsung dipakai oleh controller/route
__all__ = [
    "parse_date",
    "calculate_hourly_activity",
    "run_analysis_pipeline_task",
    "get_results_summary",
    "delete_results",
    "get_topic_detail",
    "get_message_context"
]

logger = logging.getLogger(__name__)

async def run_analysis_pipeline_task(
    session_id: str,
    df_raw: pd.DataFrame,
    original_csv_bytes: bytes,
    mode: str = "fast",
) -> None:
    """
    Fungsi background task untuk menjalankan alur analisis chat secara berurutan:
    Mulai dari preprocessing, ekstraksi embedding, reduksi dimensi, klasterisasi topik,
    hingga perhitungan statistik aktivitas obrolan.
    """
    tracker = PipelineProgressTracker(session_id)

    try:
        # Langkah 1: Simpan salinan file CSV asli ke storage lokal
        orig_object_name = f"{session_id}.csv"
        save_file(orig_object_name, original_csv_bytes)
        await tracker.complete_step(1, time_elapsed="100ms")

        # Langkah 2: Preprocessing teks (pembersihan karakter, slang, stopwords, dan stemming)
        await tracker.start_step(2)
        df_preprocessed = preprocess_dataframe(df_raw)

        if df_preprocessed.empty:
            await tracker.fail_step(2, "Tidak ada pesan setelah preprocessing.")
            return

        await tracker.complete_step(2)

        docs = df_preprocessed["Pesan_Preprocessed"].tolist()
        if len(docs) < 5:
            await tracker.fail_step(3, "Jumlah pesan terlalu sedikit (min 5 pesan) untuk pemodelan topik.")
            return

        # Langkah 3: Ekstraksi representasi vektor teks (embedding) dengan IndoBERTweet
        await tracker.start_step(3)
        embedder, embeddings = await anyio.to_thread.run_sync(
            TopicModelingService.encode_documents, docs
        )
        await tracker.complete_step(3)

        # Langkah 4: Reduksi dimensi vektor embedding menggunakan UMAP
        await tracker.start_step(4)
        umap_model, reduced_embeddings = await anyio.to_thread.run_sync(
            TopicModelingService.reduce_dimensions, embeddings
        )
        await tracker.complete_step(4)

        # Langkah 5: Klasterisasi pesan menjadi topik menggunakan algoritma BIRCH
        await tracker.start_step(5)
        birch_model, topics = await anyio.to_thread.run_sync(
            TopicModelingService.cluster_embeddings, reduced_embeddings
        )
        await tracker.complete_step(5)

        # Langkah 6: Pemodelan topik BERTopic dan ekstraksi kata kunci representasi dengan BM25
        await tracker.start_step(6)
        topic_model, topics_list, topics = await anyio.to_thread.run_sync(
            TopicModelingService.fit_bertopic,
            docs,
            embeddings,
            topics,
            birch_model,
            umap_model,
            embedder
        )
        await tracker.complete_step(6)

        # Langkah 7: Perhitungan metrik evaluasi kualitas topik (Topic Diversity, NPMI, Density)
        await tracker.start_step(7)
        if mode == "fast":
            # Mode cepat: lewati perhitungan matematis berat untuk respon instan
            metrics = TopicModelingService.evaluate_metrics(
                topic_model=None,
                docs=docs,
                topics=topics,
                embeddings=embeddings,
                mode="fast"
            )
            await tracker.complete_step(7, time_elapsed="0ms", skipped=True)
        else:
            # Mode riset: hitung seluruh metrik evaluasi secara lengkap
            metrics = await anyio.to_thread.run_sync(
                TopicModelingService.evaluate_metrics,
                topic_model,
                docs,
                topics,
                embeddings,
                mode
            )
            await tracker.complete_step(7)

        # Langkah 8: Hitung statistik keaktifan obrolan dan simpan hasil analisis
        await tracker.start_step(8)
        df_preprocessed["topic_id"] = topics
        leaderboard_data = calculate_leaderboard_pandas(df_preprocessed, limit=10)
        top_senders = [
            {"name": s["username"], "message_count": s["message_count"]}
            for s in leaderboard_data
        ]
        active_dates = calculate_daily_graph_pandas(df_preprocessed, fill_missing=True)
        active_hours = calculate_hourly_activity(df_preprocessed)

        summary_data = {
            "metrics": metrics,
            "topic_count": len(topics_list),
            "topics": topics_list,
            "top_senders": top_senders,
            "active_dates": active_dates,
            "active_hours": active_hours,
            "analysis_mode": mode
        }

        # Simpan file JSON ringkasan dan CSV pesan berlabel topik ke storage
        save_analysis_results(
            session_id=session_id,
            summary_data=summary_data,
            df_preprocessed=df_preprocessed,
            topics_list=topics_list
        )
        await tracker.complete_step(8, done=True)

    except Exception as exc:
        # Catat pesan error dan kirim notifikasi gagal ke client
        logger.exception("Terjadi kesalahan pada background task analisis")
        await tracker.pipeline_failed(str(exc))
