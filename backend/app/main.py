from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import deals, health, listings, skins, ws
from app.core.container import AppContainer
from app.core.logging import configure_logging
from app.core.settings import get_settings
from app.providers.factory import build_providers
from app.services.aggregation import AggregationService
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
    realtime = RealtimeManager()
    deal_detection = DealDetectionService()

    aggregation = AggregationService(
        session_factory=session_factory,
        providers=providers,
        realtime=realtime,
        deal_detection=deal_detection,
        listing_refresh_interval_seconds=settings.listing_refresh_interval_seconds,
    )
    scheduler = RefreshScheduler(aggregation, settings.refresh_interval_seconds)

    app.state.container = AppContainer(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        providers=providers,
        realtime=realtime,
        aggregation=aggregation,
        scheduler=scheduler,
    )

    await aggregation.refresh_once()
    await scheduler.start()

    try:
        yield
    finally:
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
