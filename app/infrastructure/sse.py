import asyncio
from typing import Dict, List

# Global state tracker for progress of sessions
progress_history: Dict[str, List[dict]] = {}

class SSEManager:
    def __init__(self):
        # Maps session_id -> list of asyncio.Queue
        self.queues: Dict[str, List[asyncio.Queue]] = {}

    def get_queue(self, session_id: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        if session_id not in self.queues:
            self.queues[session_id] = []
        self.queues[session_id].append(queue)
        return queue

    def remove_queue(self, session_id: str, queue: asyncio.Queue):
        if session_id in self.queues:
            if queue in self.queues[session_id]:
                self.queues[session_id].remove(queue)
            if not self.queues[session_id]:
                del self.queues[session_id]

    async def broadcast(self, session_id: str, message: dict):
        if session_id in self.queues:
            for queue in self.queues[session_id]:
                await queue.put(message)

sse_manager = SSEManager()
