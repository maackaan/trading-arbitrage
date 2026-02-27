from __future__ import annotations

from datetime import datetime
from typing import Sequence

from app.domain.models import ProviderListing, ProviderPrice
from app.providers.base import BaseProvider
from app.providers.mock import MockMarketEngine
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
    ) -> None:
        super().__init__(use_mock=use_mock, rate_limit_seconds=rate_limit_seconds)
        self.name = market_name
        self.mock_engine = mock_engine

    async def fetch_prices(self, skins: Sequence[SkinTable]) -> list[ProviderPrice]:
        if self.use_mock:
            return self.mock_engine.generate_prices(self.name, skins)
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
            return self.mock_engine.generate_listings(self.name, skins)
        # Placeholder for official API integration. Avoids unsupported scraping.
        return []
