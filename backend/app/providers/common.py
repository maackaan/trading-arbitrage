from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Sequence

from app.domain.models import ProviderListing, ProviderPrice
from app.providers.base import BaseProvider
from app.providers.mock import MockMarketEngine
from app.services.csgoskins_price import CSGOSkinsPriceService
from app.storage.db import SkinTable


class StubOrMockProvider(BaseProvider):
    supports_listings: bool = False

    def __init__(
        self,
        *,
        market_name: str,
        use_mock: bool,
        mock_engine: MockMarketEngine,
        rate_limit_seconds: float,
        csgoskins_price_service: CSGOSkinsPriceService | None = None,
        mock_listings_enabled: bool = False,
    ) -> None:
        super().__init__(use_mock=use_mock, rate_limit_seconds=rate_limit_seconds)
        self.name = market_name
        self.mock_engine = mock_engine
        self.csgoskins_price_service = csgoskins_price_service
        self.mock_listings_enabled = mock_listings_enabled

    async def fetch_prices(self, skins: Sequence[SkinTable]) -> list[ProviderPrice]:
        if self.use_mock:
            prices = self.mock_engine.generate_prices(self.name, skins)
            await self._override_price_rows(prices)
            for price in prices:
                price.metadata = {
                    **price.metadata,
                    "is_simulated": True,
                    "simulation_reason": "mock_provider_no_official_price_api",
                }
            return prices
        # In real mode, use csgoskins aggregated snapshot fallback when available.
        return await self._fetch_prices_via_csgoskins(skins)

    async def fetch_new_listings(
        self,
        skins: Sequence[SkinTable],
        since: datetime | None,
    ) -> list[ProviderListing]:
        if not self.supports_listings:
            return []
        if self.use_mock:
            if not self.mock_listings_enabled:
                return []
            listings = self.mock_engine.generate_listings(self.name, skins)
            await self._override_listing_rows(listings)
            for listing in listings:
                listing.metadata = {
                    **listing.metadata,
                    "is_simulated": True,
                    "simulation_reason": "mock_provider_no_official_listing_api",
                }
            return listings
        # Placeholder for official API integration. Avoids unsupported scraping.
        return []

    async def _fetch_prices_via_csgoskins(self, skins: Sequence[SkinTable]) -> list[ProviderPrice]:
        if not self.csgoskins_price_service or not self.csgoskins_price_service.supports_market(self.name):
            return []

        now = datetime.now(timezone.utc)
        rows: list[ProviderPrice] = []
        for skin in skins:
            lookup = await self.csgoskins_price_service.get_market_price(skin.name, self.name)
            if lookup is None or lookup.price <= 0:
                continue
            rows.append(
                ProviderPrice(
                    market=self.name,
                    skin_name=skin.name,
                    price=round(lookup.price, 2),
                    currency="USD",
                    timestamp=now,
                    metadata={
                        "mode": "aggregated_api",
                        "is_simulated": False,
                        "price_source": "csgoskins_aggregate",
                        "item_url": lookup.item_url,
                        "image_url": lookup.image_url,
                        "aggregate_low_price": lookup.aggregate_low_price,
                        "aggregate_high_price": lookup.aggregate_high_price,
                    },
                )
            )
        return rows

    async def _override_price_rows(self, rows: list[ProviderPrice]) -> None:
        if not self.csgoskins_price_service or not self.csgoskins_price_service.supports_market(self.name):
            return

        for row in rows:
            lookup = await self.csgoskins_price_service.get_market_price(row.skin_name, self.name)
            if lookup is None:
                continue

            row.price = round(lookup.price, 2)
            row.currency = "USD"
            row.metadata = {
                **row.metadata,
                "mode": "aggregated_api",
                "is_simulated": False,
                "item_url": lookup.item_url,
                "image_url": lookup.image_url,
                "aggregate_low_price": lookup.aggregate_low_price,
                "aggregate_high_price": lookup.aggregate_high_price,
                "price_source": "csgoskins_aggregate",
            }

    async def _override_listing_rows(self, rows: list[ProviderListing]) -> None:
        if not self.csgoskins_price_service or not self.csgoskins_price_service.supports_market(self.name):
            return

        now = datetime.now(timezone.utc)
        for row in rows:
            lookup = await self.csgoskins_price_service.get_market_price(row.skin_name, self.name)
            if lookup is None or lookup.price <= 0:
                continue

            discount_factor = float(row.metadata.get("discount_factor", 1.0))
            discount_factor = min(max(discount_factor, 0.72), 1.12)

            row.price = round(max(0.2, lookup.price * discount_factor), 2)
            row.currency = "USD"
            row.listed_at = now - timedelta(seconds=self.mock_engine.random.randint(0, 90))
            row.metadata = {
                **row.metadata,
                "mode": "aggregated_api",
                "is_simulated": False,
                "price_source": "csgoskins_aggregate",
                "reference_market_price": lookup.price,
                "item_url": lookup.item_url,
                "image_url": lookup.image_url,
                "aggregate_low_price": lookup.aggregate_low_price,
                "aggregate_high_price": lookup.aggregate_high_price,
            }
