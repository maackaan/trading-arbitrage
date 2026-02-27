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
    ) -> None:
        super().__init__(use_mock=use_mock, rate_limit_seconds=rate_limit_seconds)
        self.name = market_name
        self.mock_engine = mock_engine
        self.csgoskins_price_service = csgoskins_price_service

    async def fetch_prices(self, skins: Sequence[SkinTable]) -> list[ProviderPrice]:
        if self.use_mock:
            prices = self.mock_engine.generate_prices(self.name, skins)
            await self._override_price_rows(prices)
            return prices
        # Placeholder for official API integration. Avoids unsupported scraping.
        return []

    async def fetch_new_listings(
        self,
        skins: Sequence[SkinTable],
        since: datetime | None,
    ) -> list[ProviderListing]:
        if not self.supports_listings:
            return []
        if self.use_mock:
            listings = self.mock_engine.generate_listings(self.name, skins)
            await self._override_listing_rows(listings)
            return listings
        # Placeholder for official API integration. Avoids unsupported scraping.
        return []

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
                "mode": "csgoskins_fallback",
                "item_url": lookup.item_url,
                "image_url": lookup.image_url,
                "aggregate_low_price": lookup.aggregate_low_price,
                "aggregate_high_price": lookup.aggregate_high_price,
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
                "mode": "csgoskins_fallback",
                "price_source": "csgoskins.gg",
                "reference_market_price": lookup.price,
                "item_url": lookup.item_url,
                "image_url": lookup.image_url,
                "aggregate_low_price": lookup.aggregate_low_price,
                "aggregate_high_price": lookup.aggregate_high_price,
            }
