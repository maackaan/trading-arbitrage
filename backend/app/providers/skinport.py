from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from app.domain.models import ProviderPrice
from app.providers.common import StubOrMockProvider
from app.providers.mock import MockMarketEngine
from app.services.csgoskins_price import CSGOSkinsPriceService
from app.storage.db import SkinTable

logger = logging.getLogger(__name__)


class SkinportProvider(StubOrMockProvider):
    def __init__(
        self,
        *,
        use_mock: bool,
        mock_engine: MockMarketEngine,
        rate_limit_seconds: float,
        csgoskins_price_service: CSGOSkinsPriceService | None = None,
        items_api_url: str = "https://api.skinport.com/v1/items",
        timeout_seconds: int = 20,
        app_id: int = 730,
        currency: str = "USD",
    ) -> None:
        super().__init__(
            market_name="skinport",
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=rate_limit_seconds,
            csgoskins_price_service=csgoskins_price_service,
        )
        self.items_api_url = items_api_url.strip()
        self.timeout_seconds = max(timeout_seconds, 5)
        self.app_id = app_id
        self.currency = currency.upper().strip() or "USD"
        self.last_error: str | None = None
        self._price_cache: dict[str, float] = {}
        self._cache_updated_at: datetime | None = None
        self._cooldown_until: datetime | None = None

    async def fetch_prices(self, skins: Sequence[SkinTable]) -> list[ProviderPrice]:
        if self.use_mock:
            return await super().fetch_prices(skins)

        now = datetime.now(timezone.utc)
        if not self.items_api_url:
            self.last_error = "Skinport items API URL is not configured."
            self.last_price_error = self.last_error
            logger.info(self.last_error)
            return []

        if self._cooldown_until and now < self._cooldown_until:
            if self._price_cache:
                self.last_error = (
                    f"Rate-limited; serving cached Skinport prices until {self._cooldown_until.isoformat()}."
                )
                self.last_price_error = self.last_error
                return self._rows_from_cache(skins, now)
            self.last_error = f"Rate-limited until {self._cooldown_until.isoformat()}."
            self.last_price_error = self.last_error
            return []

        try:
            payload = await asyncio.to_thread(self._fetch_items_payload)
            self._cooldown_until = None
            self.last_error = None
            self.last_price_error = None
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "ignore")
            except Exception:
                body = ""
            retry_after_seconds = _extract_retry_after_seconds(exc, default_seconds=900)
            if exc.code == 429:
                self._cooldown_until = now + timedelta(seconds=retry_after_seconds)
            self.last_error = f"HTTP {exc.code}: {body[:180] or 'request failed'}"
            self.last_price_error = self.last_error
            logger.warning("Skinport price request failed: %s", self.last_error)
            if self._price_cache:
                return self._rows_from_cache(skins, now)
            return []
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.last_price_error = self.last_error
            logger.warning("Skinport price request failed: %s", self.last_error)
            if self._price_cache:
                return self._rows_from_cache(skins, now)
            return []

        price_by_name = _build_price_map(payload)
        if not price_by_name:
            self.last_error = "No Skinport prices returned."
            self.last_price_error = self.last_error
            if self._price_cache:
                return self._rows_from_cache(skins, now)
            return []

        self._price_cache = price_by_name
        self._cache_updated_at = now
        return self._rows_from_map(skins, now, price_by_name, source="skinport_api")

    def _rows_from_cache(self, skins: Sequence[SkinTable], now: datetime) -> list[ProviderPrice]:
        cache_age_seconds = None
        if self._cache_updated_at:
            cache_age_seconds = max(int((now - self._cache_updated_at).total_seconds()), 0)
        source = "skinport_api_cache"
        return self._rows_from_map(
            skins,
            now,
            self._price_cache,
            source=source,
            cache_age_seconds=cache_age_seconds,
        )

    def _rows_from_map(
        self,
        skins: Sequence[SkinTable],
        now: datetime,
        price_by_name: dict[str, float],
        *,
        source: str,
        cache_age_seconds: int | None = None,
    ) -> list[ProviderPrice]:
        rows: list[ProviderPrice] = []
        for skin in skins:
            price = price_by_name.get(skin.name)
            if price is None:
                continue
            metadata: dict[str, Any] = {
                "mode": "official_api",
                "is_simulated": False,
                "price_source": source,
            }
            if cache_age_seconds is not None:
                metadata["cache_age_seconds"] = cache_age_seconds
            rows.append(
                ProviderPrice(
                    market="skinport",
                    skin_name=skin.name,
                    price=price,
                    currency=self.currency,
                    timestamp=now,
                    metadata=metadata,
                )
            )
        return rows

    def _fetch_items_payload(self) -> Any:
        parsed = urlparse(self.items_api_url)
        query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_pairs.setdefault("app_id", str(self.app_id))
        query_pairs.setdefault("currency", self.currency)
        request_url = urlunparse(parsed._replace(query=urlencode(query_pairs)))

        request = Request(
            url=request_url,
            method="GET",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "br",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            raw = response.read()
            content_encoding = (response.headers.get("Content-Encoding") or "").lower()

        if content_encoding == "br":
            try:
                import brotli
            except Exception as exc:
                raise RuntimeError(
                    "Skinport API returned Brotli data but brotli dependency is missing. Install `brotli`."
                ) from exc
            raw = brotli.decompress(raw)

        return json.loads(raw.decode("utf-8"))


def _build_price_map(payload: Any) -> dict[str, float]:
    if not isinstance(payload, list):
        return {}

    prices: dict[str, float] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        market_hash_name = item.get("market_hash_name")
        if not isinstance(market_hash_name, str):
            continue

        min_price = item.get("min_price")
        suggested_price = item.get("suggested_price")
        raw_price = min_price if _is_positive_number(min_price) else suggested_price
        if not _is_positive_number(raw_price):
            continue

        value = float(raw_price) / 100.0
        if value <= 0:
            continue
        prices[market_hash_name] = round(value, 2)
    return prices


def _is_positive_number(value: Any) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _extract_retry_after_seconds(exc: HTTPError, default_seconds: int) -> int:
    header_value = ""
    try:
        header_value = str(exc.headers.get("Retry-After") or "").strip()
    except Exception:
        header_value = ""
    if header_value.isdigit():
        return max(int(header_value), 1)
    return max(default_seconds, 1)
