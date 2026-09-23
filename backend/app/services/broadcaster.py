"""In-memory per-user live channel broadcaster using asyncio.Queue.

Supports Server-Sent Events (SSE) streaming where each connected client
for a user receives pushed events (e.g. new_mail).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class Broadcaster:
    """Manages SSE subscribers per user."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: str) -> asyncio.Queue[dict[str, Any]]:
        """Register a new connection for user_id and return its event queue."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        async with self._lock:
            if user_id not in self._subscribers:
                self._subscribers[user_id] = set()
            self._subscribers[user_id].add(queue)
        logger.debug("User %s connected to live stream. Total connections: %d", user_id, len(self._subscribers[user_id]))
        return queue

    async def disconnect(self, user_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        """Unregister a connection queue for user_id."""
        async with self._lock:
            if user_id in self._subscribers:
                self._subscribers[user_id].discard(queue)
                if not self._subscribers[user_id]:
                    del self._subscribers[user_id]
        logger.debug("User %s disconnected from live stream.", user_id)

    async def publish(self, user_id: str, event: str, data: Any) -> int:
        """Publish an event to all active connections for user_id.

        Returns the number of subscribers the event was delivered to.
        """
        payload = {"event": event, "data": data}
        async with self._lock:
            queues = list(self._subscribers.get(user_id, set()))

        if not queues:
            logger.debug("No active subscribers for user %s to receive event '%s'", user_id, event)
            return 0

        for q in queues:
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("Queue full for subscriber of user %s, event dropped.", user_id)

        logger.info("Published event '%s' to %d connection(s) for user %s", event, len(queues), user_id)
        return len(queues)


# Global broadcaster singleton
broadcaster = Broadcaster()
