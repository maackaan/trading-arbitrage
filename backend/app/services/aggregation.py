from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.providers.base import BaseProvider
from app.services.deal_detection import DealDetectionService
from app.services.price_service import validate_provider_listing, validate_provider_price
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
        refresh_skin_batch_size: int,
        listing_refresh_interval_seconds: int,
        listing_since_hours: int,
    ) -> None:
        self.session_factory = session_factory
        self.providers = providers
        self.realtime = realtime
        self.deal_detection = deal_detection
        self.refresh_skin_batch_size = max(refresh_skin_batch_size, 1)
        self.listing_refresh_interval_seconds = listing_refresh_interval_seconds
        self.listing_since_hours = max(listing_since_hours, 1)
        self._skin_batch_offset = 0

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

            all_skins = await skin_repo.list_all()
            if not all_skins:
                return
            if len(all_skins) <= self.refresh_skin_batch_size:
                skins = all_skins
            else:
                start = self._skin_batch_offset % len(all_skins)
                end = start + self.refresh_skin_batch_size
                if end <= len(all_skins):
                    skins = all_skins[start:end]
                else:
                    skins = [*all_skins[start:], *all_skins[: end % len(all_skins)]]
                self._skin_batch_offset = (start + self.refresh_skin_batch_size) % len(all_skins)
            skin_by_name = {skin.name: skin for skin in skins}
            all_skin_by_name = {skin.name: skin for skin in all_skins}
            snapshot_rows: list[dict] = []

            for provider in self.providers:
                if not provider.background_price_refresh_enabled:
                    continue
                if provider.can_refresh_prices(now):
                    try:
                        prices = await provider.fetch_prices(skins)
                        provider.mark_price_refresh(now)
                    except Exception as exc:
                        provider.last_price_error = f"{type(exc).__name__}: {exc}"
                        logger.warning("Price refresh failed for provider=%s: %s", provider.name, provider.last_price_error)
                        continue

                    for raw_item in prices:
                        item = validate_provider_price(raw_item)
                        if item is None:
                            logger.warning(
                                "Skipping invalid price from provider=%s skin=%s",
                                provider.name,
                                getattr(raw_item, "skin_name", "unknown"),
                            )
                            continue
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

                try:
                    listings = await provider.fetch_new_listings(
                        all_skins,
                        since=now - timedelta(hours=self.listing_since_hours),
                    )
                    provider.mark_listing_refresh(now)
                except Exception as exc:
                    provider.last_listing_error = f"{type(exc).__name__}: {exc}"
                    logger.warning(
                        "Listing refresh failed for provider=%s: %s",
                        provider.name,
                        provider.last_listing_error,
                    )
                    continue

                baseline_cache: dict[int, tuple[float | None, str | None]] = {}
                rolling_cache: dict[tuple[int, str], float | None] = {}

                for raw_listing in listings:
                    listing = validate_provider_listing(raw_listing)
                    if listing is None:
                        logger.warning(
                            "Skipping invalid listing from provider=%s skin=%s",
                            provider.name,
                            getattr(raw_listing, "skin_name", "unknown"),
                        )
                        continue
                    skin = self._resolve_listing_skin(all_skin_by_name, listing.skin_name)
                    if skin is None:
                        continue

                    baseline_price: float | None
                    baseline_market: str | None
                    if skin.id in baseline_cache:
                        baseline_price, baseline_market = baseline_cache[skin.id]
                    else:
                        buff_latest = await price_repo.get_market_prices(
                            skin_id=skin.id,
                            market="buff163",
                            since=now - timedelta(days=14),
                            limit=10,
                        )
                        if buff_latest:
                            baseline_price = buff_latest[-1]
                            baseline_market = "buff163"
                        else:
                            skinport_latest = await price_repo.get_market_prices(
                                skin_id=skin.id,
                                market="skinport",
                                since=now - timedelta(days=14),
                                limit=10,
                            )
                            baseline_price = skinport_latest[-1] if skinport_latest else None
                            baseline_market = "skinport" if skinport_latest else None
                        baseline_cache[skin.id] = (baseline_price, baseline_market)

                    rolling_key = (skin.id, listing.market)
                    if rolling_key in rolling_cache:
                        market_rolling = rolling_cache[rolling_key]
                    else:
                        market_recent = await price_repo.get_market_prices(
                            skin_id=skin.id,
                            market=listing.market,
                            since=now - timedelta(days=14),
                            limit=30,
                        )
                        market_rolling = rolling_mean(market_recent, window=12) if market_recent else None
                        rolling_cache[rolling_key] = market_rolling

                    eval_result = self.deal_detection.evaluate(
                        listing_price=listing.price,
                        buff_baseline=baseline_price,
                        rolling_mean_price=market_rolling,
                    )

                    metadata = dict(listing.metadata)
                    metadata.setdefault("is_simulated", False)
                    metadata.setdefault("mode", "official_api")
                    if baseline_price is not None:
                        metadata["reference_market_price"] = round(baseline_price, 4)
                        if baseline_market:
                            metadata["reference_market"] = baseline_market
                    if market_rolling is not None:
                        metadata["rolling_mean_price"] = round(market_rolling, 4)

                    row = await listing_repo.upsert_listing(
                        external_id=listing.external_id,
                        market=listing.market,
                        skin_id=skin.id,
                        skin_name=skin.name,
                        price=listing.price,
                        currency=listing.currency,
                        listed_at=listing.listed_at,
                        detected_at=now,
                        metadata=metadata,
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
