"""Service that orchestrates BERTopic model lifecycle operations."""

from __future__ import annotations

import asyncio
from typing import Any

from bertopic import BERTopic

from app.ml.topic_model import load_model_from_minio, save_model_to_minio, update_model


class TopicModelService:
    """Coordinate model load, update, and persistence."""

    async def load(self) -> BERTopic | None:
        """Load existing BERTopic model from MinIO if available."""
        return await load_model_from_minio()

    async def update_loaded_model(
        self,
        loaded_model: BERTopic | None,
        documents: list[str],
        timeframe: str,
    ) -> tuple[BERTopic, dict[str, Any], str]:
        """Run fit_transform/partial_fit and prepare response payload."""
        model, topics, probabilities, action = await update_model(loaded_model, documents)

        topic_info_df = await asyncio.to_thread(model.get_topic_info)
        topic_info: list[dict[str, Any]] = []
        if hasattr(topic_info_df, "to_dict"):
            topic_info = topic_info_df.to_dict(orient="records")

        payload = {
            "topics": [int(topic) for topic in topics],
            "probabilities": self.normalize_probabilities(probabilities),
            "topic_info": topic_info,
            "timeframe": timeframe,
        }
        return model, payload, action

    async def train_or_update(self, documents: list[str], timeframe: str) -> tuple[BERTopic, dict[str, Any], str]:
        """Load model and run training/update without persisting to storage yet."""
        loaded_model = await self.load()
        return await self.update_loaded_model(loaded_model, documents, timeframe)

    async def save(self, model: BERTopic) -> None:
        """Persist updated BERTopic model to MinIO."""
        await save_model_to_minio(model)

    @staticmethod
    def normalize_probabilities(probabilities: Any) -> list[Any]:
        """Normalize BERTopic probabilities object to JSON-friendly list."""
        if probabilities is None:
            return []

        if hasattr(probabilities, "tolist"):
            return probabilities.tolist()

        if isinstance(probabilities, list):
            return probabilities

        try:
            return list(probabilities)
        except TypeError:
            return []
