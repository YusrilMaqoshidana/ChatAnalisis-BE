"""Background topic training orchestration service."""

from __future__ import annotations

import asyncio

from app.services.preprocessing_service import extract_messages, prepare_messages
from app.services.progress_service import ProgressService
from app.services.topic_model_service import TopicModelService


class TopicTrainingService:
    """Coordinate async topic training pipeline and progress updates."""

    _MODEL_UPDATE_LOCK = asyncio.Lock()

    def __init__(self, progress_service: ProgressService, topic_model_service: TopicModelService) -> None:
        self.progress_service = progress_service
        self.topic_model_service = topic_model_service

    async def process_training_job(
        self,
        job_id: str,
        filename: str,
        timeframe: str,
        content: bytes,
    ) -> None:
        """Execute parsing, preprocessing, training/update, and model persistence stages."""
        model = None

        try:
            await self.progress_service.set_progress(job_id, "processing", 10, "Parsing file")
            messages = extract_messages(filename, content)

            await self.progress_service.set_progress(job_id, "processing", 20, "Preprocessing chat")
            prepared_rows = prepare_messages(messages, timeframe)
            documents = [str(row.get("pesan_preprocessed") or "").strip() for row in prepared_rows]
            documents = [doc for doc in documents if doc]

            if not documents:
                raise ValueError("Tidak ada pesan valid setelah preprocessing.")

            async with self._MODEL_UPDATE_LOCK:
                await self.progress_service.set_progress(job_id, "processing", 30, "Loading model from MinIO")
                loaded_model = await self.topic_model_service.load()

                await self.progress_service.set_progress(job_id, "processing", 50, "Training BERTopic")
                model, _payload, action = await self.topic_model_service.update_loaded_model(
                    loaded_model,
                    documents,
                    timeframe,
                )

                stage_message = "Updating BERTopic model" if action == "updated" else "Finalizing BERTopic training"
                await self.progress_service.set_progress(job_id, "processing", 70, stage_message)

                await self.progress_service.set_progress(job_id, "processing", 85, "Saving model to MinIO")
                await self.topic_model_service.save(model)

            await self.progress_service.set_done(job_id, "Training selesai")
        except Exception as exc:
            await self.progress_service.set_error(job_id, str(exc))
        finally:
            if model is not None:
                del model
