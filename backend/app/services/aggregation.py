from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.providers.base import BaseProvider
from app.services.deal_detection import DealDetectionService
from app.services.pricing_metrics import rolling_mean
from app.services.realtime import RealtimeManager
from app.services.wear import PREFERRED_LISTING_WEAR, has_wear_suffix, split_wear_suffix
from app.storage.db import AsyncSession, SkinTable
from app.storage.repositories import ListingRepository, PriceRepository, SkinRepository

logger = logging.getLogger(__name__)


class AggregationService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        providers: list[BaseProvider],
        realtime: RealtimeManager,
        deal_detection: DealDetectionService,
        listing_refresh_interval_seconds: int,
        listing_since_hours: int,
    ) -> None:
        self.session_factory = session_factory
        self.providers = providers
        self.realtime = realtime
        self.deal_detection = deal_detection
        self.listing_refresh_interval_seconds = listing_refresh_interval_seconds
        self.listing_since_hours = max(listing_since_hours, 1)

    @staticmethod
    def _resolve_listing_skin(skin_by_name: dict[str, SkinTable], source_skin_name: str):
        skin = skin_by_name.get(source_skin_name)
        if skin is None:
            return None
        if has_wear_suffix(skin.name):
            return skin

        base_name, _ = split_wear_suffix(skin.name)
        variants = []
        for wear in PREFERRED_LISTING_WEAR:
            candidate = skin_by_name.get(f"{base_name} ({wear})")
            if candidate is not None:
                variants.append(candidate)
        return variants[0] if variants else skin

    async def refresh_once(self) -> None:
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            skin_repo = SkinRepository(session)
            price_repo = PriceRepository(session)
            listing_repo = ListingRepository(session)

            skins = await skin_repo.list_all()
            skin_by_name = {skin.name: skin for skin in skins}
            snapshot_rows: list[dict] = []

            for provider in self.providers:
                if provider.can_refresh_prices(now):
                    prices = await provider.fetch_prices(skins)
                    provider.mark_price_refresh(now)
                    for item in prices:
                        skin = skin_by_name.get(item.skin_name)
                        if skin is None:
                            continue
                        snapshot_rows.append(
                            {
                                "skin_id": skin.id,
                                "market": item.market,
                                "price": item.price,
                                "currency": item.currency,
                                "observed_at": item.timestamp,
                                "metadata": item.metadata,
                            }
                        )

            if snapshot_rows:
                await price_repo.add_snapshots(snapshot_rows)
                for snapshot in snapshot_rows:
                    await self.realtime.broadcast(
                        "price_update",
                        {
                            "skin_id": snapshot["skin_id"],
                            "market": snapshot["market"],
                            "price": snapshot["price"],
                            "currency": snapshot["currency"],
                            "timestamp": snapshot["observed_at"].isoformat(),
                        },
                    )

            for provider in self.providers:
                if not provider.supports_listings:
                    continue
                if not provider.can_refresh_listings(now, self.listing_refresh_interval_seconds):
                    continue

                listings = await provider.fetch_new_listings(
                    skins,
                    since=now - timedelta(hours=self.listing_since_hours),
                )
                provider.mark_listing_refresh(now)
                for listing in listings:
                    skin = self._resolve_listing_skin(skin_by_name, listing.skin_name)
                    if skin is None:
                        continue

                    buff_latest = await price_repo.get_market_prices(
                        skin_id=skin.id,
                        market="buff163",
                        since=now - timedelta(days=14),
                        limit=10,
                    )
                    market_recent = await price_repo.get_market_prices(
                        skin_id=skin.id,
                        market=listing.market,
                        since=now - timedelta(days=14),
                        limit=30,
                    )
                    eval_result = self.deal_detection.evaluate(
                        listing_price=listing.price,
                        buff_baseline=buff_latest[-1] if buff_latest else None,
                        rolling_mean_price=rolling_mean(market_recent, window=12) if market_recent else None,
                    )

                    row = await listing_repo.upsert_listing(
                        external_id=listing.external_id,
                        market=listing.market,
                        skin_id=skin.id,
                        skin_name=skin.name,
                        price=listing.price,
                        currency=listing.currency,
                        listed_at=listing.listed_at,
                        detected_at=now,
                        metadata=listing.metadata,
                        is_deal=eval_result.is_deal,
                        discount_vs_buff_pct=eval_result.discount_vs_buff_pct,
                        discount_vs_rolling_pct=eval_result.discount_vs_rolling_pct,
                        extreme_underpricing=eval_result.extreme_underpricing,
                    )

                    await self.realtime.broadcast(
                        "new_listing",
                        {
                            "listing_id": row.id,
                            "market": row.market,
                            "skin_id": row.skin_id,
                            "skin_name": row.skin_name,
                            "price": row.price,
                            "currency": row.currency,
                            "listed_at": row.listed_at.isoformat(),
                            "detected_at": row.detected_at.isoformat(),
                            "is_deal": row.is_deal,
                            "extreme_underpricing": row.extreme_underpricing,
                        },
                    )

                    if row.is_deal:
                        await self.realtime.broadcast(
                            "deal_alert",
                            {
                                "listing_id": row.id,
                                "market": row.market,
                                "skin_id": row.skin_id,
                                "skin_name": row.skin_name,
                                "price": row.price,
                                "discount_vs_buff_pct": row.discount_vs_buff_pct,
                                "discount_vs_rolling_pct": row.discount_vs_rolling_pct,
                                "extreme_underpricing": row.extreme_underpricing,
                            },
                        )

            logger.debug("Aggregation refresh completed")
