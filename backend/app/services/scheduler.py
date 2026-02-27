from __future__ import annotations

import asyncio
import logging

from app.services.aggregation import AggregationService

logger = logging.getLogger(__name__)


class RefreshScheduler:
    def __init__(self, aggregation: AggregationService, refresh_interval_seconds: int) -> None:
        self.aggregation = aggregation
        self.refresh_interval_seconds = max(refresh_interval_seconds, 1)
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        self._task = asyncio.create_task(self._run(), name="price-refresh-scheduler")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        logger.info("Starting refresh scheduler with interval=%ss", self.refresh_interval_seconds)
        while not self._stopping.is_set():
            try:
                await self.aggregation.refresh_once()
            except Exception:
                logger.exception("Background refresh failed")
            await asyncio.sleep(self.refresh_interval_seconds)
        logger.info("Refresh scheduler stopped")
