from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import WebSocket

from app.domain.models import RealtimeEvent

logger = logging.getLogger(__name__)


class RealtimeManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, event: str, payload: dict) -> None:
        message = RealtimeEvent(
            event=event,
            payload=payload,
            timestamp=datetime.now(timezone.utc),
        ).model_dump(mode="json")

        async with self._lock:
            connections = list(self._connections)

        stale: list[WebSocket] = []
        for connection in connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)

        if stale:
            async with self._lock:
                for connection in stale:
                    self._connections.discard(connection)

        if stale:
            logger.info("Removed %d stale websocket connection(s)", len(stale))
