from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.settings import Settings
from app.providers.base import BaseProvider
from app.services.aggregation import AggregationService
from app.services.catalog_search import CatalogSearchService
from app.services.scheduler import RefreshScheduler
from app.services.realtime import RealtimeManager
from app.storage.db import AsyncSession


@dataclass
class AppContainer:
    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    catalog_search: CatalogSearchService | None
    providers: list[BaseProvider]
    realtime: RealtimeManager
    aggregation: AggregationService
    scheduler: RefreshScheduler
