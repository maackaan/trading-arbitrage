from __future__ import annotations

import asyncio
from contextlib import suppress
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import deals, health, listings, skins, ws
from app.core.container import AppContainer
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.providers.factory import build_providers
from app.services.aggregation import AggregationService
from app.services.catalog_search import CatalogSearchService
from app.services.deal_detection import DealDetectionService
from app.services.realtime import RealtimeManager
from app.services.scheduler import RefreshScheduler
from app.storage.db import create_engine, create_session_factory, init_db
from app.storage.repositories import SkinRepository


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    await init_db(engine)
    async with session_factory() as session:
        await SkinRepository(session).seed_skins(settings.seed_skins)

    providers = build_providers(settings)
    catalog_search = None
    if settings.search_catalog_provider.lower() == "csgoskins_gg":
        catalog_search = CatalogSearchService(
            base_url=settings.search_catalog_url,
            api_key=settings.search_catalog_key,
            timeout_seconds=settings.search_catalog_timeout_seconds,
            fetch_wears=settings.search_catalog_fetch_wears,
            image_cache_path=settings.catalog_image_cache_path,
            image_refresh_ttl_seconds=settings.catalog_image_refresh_ttl_seconds,
        )
    realtime = RealtimeManager()
    deal_detection = DealDetectionService()

    aggregation = AggregationService(
        session_factory=session_factory,
        providers=providers,
        realtime=realtime,
        deal_detection=deal_detection,
        listing_refresh_interval_seconds=settings.listing_refresh_interval_seconds,
        listing_since_hours=settings.listing_since_hours,
    )
    scheduler = RefreshScheduler(aggregation, settings.refresh_interval_seconds)

    app.state.container = AppContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        catalog_search=catalog_search,
        providers=providers,
        realtime=realtime,
        aggregation=aggregation,
        scheduler=scheduler,
    )

    await scheduler.start()
    image_prefetch_task: asyncio.Task | None = None
    if catalog_search and settings.catalog_prefetch_images:
        image_prefetch_task = asyncio.create_task(
            catalog_search.prefetch_images_for_names(settings.seed_skins),
            name="catalog-image-prefetch",
        )

    try:
        yield
    finally:
        if image_prefetch_task and not image_prefetch_task.done():
            image_prefetch_task.cancel()
            with suppress(asyncio.CancelledError):
                await image_prefetch_task
        await scheduler.stop()
        await engine.dispose()


app = FastAPI(title="cs2-arbitrage-backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(skins.router)
app.include_router(deals.router)
app.include_router(listings.router)
app.include_router(ws.router)
