import io
import json
import logging
from typing import Dict, Any, List
import pandas as pd
from fastapi import HTTPException, status

from app.infrastructure.storage import save_file, read_file, delete_file
from app.infrastructure.sse import progress_history
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

def save_analysis_results(
    session_id: str,
    summary_data: Dict[str, Any],
    df_preprocessed: pd.DataFrame,
    topics_list: List[Dict[str, Any]]
) -> None:
    """Tujuan: Menyimpan data ringkasan (JSON) dan file CSV berlabel topik ke dalam storage lokal."""
    # 1. Simpan ringkasan hasil analisis dalam format JSON
    result_json = json.dumps(summary_data, ensure_ascii=False)
    result_bytes = result_json.encode("utf-8")
    result_object_name = f"{session_id}_result.json"
    save_file(result_object_name, result_bytes)

    # 2. Petakan ID topik ke labelnya, lalu simpan file CSV pesan berlabel
    label_map = {t["topic_id"]: t["label"] for t in topics_list}
    label_map[-1] = "Lain-lain"
    df_preprocessed["topic_label"] = df_preprocessed["topic_id"].map(label_map)

    labeled_csv_str = df_preprocessed.to_csv(index=False)
    labeled_csv_bytes = labeled_csv_str.encode("utf-8")
    labeled_object_name = f"{session_id}_labeled.csv"
    save_file(labeled_object_name, labeled_csv_bytes)

def get_results_summary(job_id: str) -> ResultsSummaryDTO:
    """Tujuan: Mengambil data ringkasan analisis dari storage dan menyusunnya ke dalam objek DTO untuk API."""
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
            active_hours=active_hours,
            analysis_mode=data.get("analysis_mode", "fast")
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal membaca format JSON hasil analisis: {str(exc)}"
        )

def delete_results(job_id: str) -> dict:
    """Tujuan: Menghapus seluruh file hasil analisis dan riwayat progres sesi yang bersangkutan dari storage."""
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
    """
    Tujuan: Mengambil daftar pesan yang masuk ke dalam klaster topik tertentu,
    lalu mengurutkan pesan berdasarkan jumlah kecocokan kata kunci representatif.
    """
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

        # Urutkan pesan: pesan yang paling banyak memuat kata kunci topik diletakkan paling atas
        if keywords and not df_topic.empty:
            kw_set = [kw.lower() for kw in keywords]
            def calculate_row_score(row):
                msg_content = str(row.get("pesan", "")).lower()
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
    """
    Tujuan: Mengambil konteks linimasa percakapan (5 pesan sebelum dan 5 pesan sesudah)
    di sekitar pesan yang dipilih oleh pengguna.
    """
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

        # Ambil 5 pesan sebelum dan 5 pesan sesudah pesan target
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
