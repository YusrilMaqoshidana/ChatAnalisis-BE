import time
from typing import Dict, Any, Optional

from app.infrastructure.sse import progress_history, sse_manager

class PipelineProgressTracker:
    """
    Mengelola dan mengirimkan status progres analisis secara real-time
    ke frontend melalui Server-Sent Events (SSE).
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._step_start_times: Dict[int, float] = {}

    async def emit_event(self, event: Dict[str, Any]) -> None:
        """Menyimpan data riwayat progres dan menyiarkannya ke client."""
        progress_history.setdefault(self.session_id, []).append(event)
        await sse_manager.broadcast(self.session_id, event)

    async def start_step(self, step_id: int) -> None:
        """Menandai bahwa suatu langkah sedang mulai dikerjakan."""
        self._step_start_times[step_id] = time.time()
        event = {"step_id": step_id, "status": "running"}
        await self.emit_event(event)

    async def complete_step(
        self,
        step_id: int,
        time_elapsed: Optional[str] = None,
        skipped: bool = False,
        done: bool = False
    ) -> None:
        """Menandai bahwa suatu langkah telah selesai beserta durasi pengerjaannya."""
        if time_elapsed is None:
            start_t = self._step_start_times.get(step_id, time.time())
            time_elapsed = "0ms" if skipped else f"{int((time.time() - start_t) * 1000)}ms"

        event: Dict[str, Any] = {
            "step_id": step_id,
            "status": "completed",
            "time_elapsed": time_elapsed
        }
        if skipped:
            event["skipped"] = True
        if done:
            event["done"] = True

        await self.emit_event(event)

    async def fail_step(self, step_id: int, error: str) -> None:
        """Menandai kegagalan pada langkah tertentu."""
        event = {"step_id": step_id, "status": "failed", "error": error}
        await self.emit_event(event)

    async def fail_pipeline(self, error: str) -> None:
        """Menandai kegagalan sistem secara keseluruhan selama proses analisis."""
        event = {"status": "failed", "error": error}
        await self.emit_event(event)
