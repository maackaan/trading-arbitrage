from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Sequence

from app.domain.models import ProviderListing, ProviderPrice
from app.storage.db import SkinTable


class BaseProvider(ABC):
    name: str
    supports_listings: bool = False

    def __init__(self, *, use_mock: bool, rate_limit_seconds: float = 5.0) -> None:
        self.use_mock = use_mock
        self.rate_limit_seconds = max(rate_limit_seconds, 0.0)
        self._last_price_run: datetime | None = None
        self._last_listing_run: datetime | None = None
        self.last_price_error: str | None = None
        self.last_listing_error: str | None = None

    def can_refresh_prices(self, now: datetime | None = None) -> bool:
        if self._last_price_run is None:
            return True
        current = now or datetime.now(timezone.utc)
        elapsed = (current - self._last_price_run).total_seconds()
        return elapsed >= self.rate_limit_seconds

    def can_refresh_listings(self, now: datetime | None = None, listing_interval_seconds: float = 5.0) -> bool:
        if self._last_listing_run is None:
            return True
        current = now or datetime.now(timezone.utc)
        elapsed = (current - self._last_listing_run).total_seconds()
        return elapsed >= max(listing_interval_seconds, self.rate_limit_seconds)

    def mark_price_refresh(self, now: datetime | None = None) -> None:
        self._last_price_run = now or datetime.now(timezone.utc)

    def mark_listing_refresh(self, now: datetime | None = None) -> None:
        self._last_listing_run = now or datetime.now(timezone.utc)

    @abstractmethod
    async def fetch_prices(self, skins: Sequence[SkinTable]) -> list[ProviderPrice]:
        raise NotImplementedError

    async def fetch_new_listings(
        self,
        skins: Sequence[SkinTable],
        since: datetime | None,
    ) -> list[ProviderListing]:
        return []
