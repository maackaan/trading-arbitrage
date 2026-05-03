from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Sequence
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from app.domain.models import ProviderPrice
from app.providers.common import StubOrMockProvider
from app.providers.mock import MockMarketEngine
from app.services.csgoskins_price import CSGOSkinsPriceService
from app.services.market_hash_names import market_hash_candidates
from app.storage.db import SkinTable

logger = logging.getLogger(__name__)

_STEAM_PRICE_URL = "https://steamcommunity.com/market/priceoverview/"
_STEAM_MARKET_URL = "https://steamcommunity.com/market/listings/730/"
_STEAM_ORDER_HISTOGRAM_URL = "https://steamcommunity.com/market/itemordershistogram"


class SteamProvider(StubOrMockProvider):
    def __init__(
        self,
        *,
        use_mock: bool,
        mock_engine: MockMarketEngine,
        rate_limit_seconds: float,
        csgoskins_price_service: CSGOSkinsPriceService | None = None,
        country: str = "SE",
        currency_code: int = 3,
        currency: str = "EUR",
    ) -> None:
        super().__init__(
            market_name="steam",
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=rate_limit_seconds,
            csgoskins_price_service=csgoskins_price_service,
        )
        self._item_nameid_cache: dict[str, str] = {}
        self.country = (country or "SE").upper()
        self.currency_code = int(currency_code)
        self.currency = (currency or "EUR").upper()

    async def fetch_prices(self, skins: Sequence[SkinTable]) -> list[ProviderPrice]:
        if self.use_mock:
            return await super().fetch_prices(skins)

        rows: list[ProviderPrice] = []
        for skin in skins:
            payload: dict[str, Any] = {}
            market_hash_name = skin.name
            for candidate in market_hash_candidates(skin.name):
                try:
                    payload = await asyncio.to_thread(self._fetch_lowest_sell_order, candidate)
                except Exception as exc:
                    self.last_price_error = f"{type(exc).__name__}: {exc}"
                    logger.warning("Steam price request failed for %s: %s", candidate, self.last_price_error)
                    continue
                if payload.get("lowest_price"):
                    market_hash_name = candidate
                    break

            price = _parse_steam_price(payload.get("lowest_price"))
            if price is None or price <= 0:
                continue

            rows.append(
                ProviderPrice(
                    market="steam",
                    skin_name=skin.name,
                    price=round(price, 2),
                    currency=self.currency,
                    timestamp=datetime.now(timezone.utc),
                    metadata={
                        "mode": "public_api",
                        "is_simulated": False,
                        "price_source": "steam",
                        "price_source_detail": "steam_order_histogram",
                        "item_url": f"{_STEAM_MARKET_URL}{quote(market_hash_name, safe='')}",
                        "market_hash_name": market_hash_name,
                        "volume": payload.get("volume"),
                    },
                )
            )

        self.last_price_error = None
        return rows

    def _fetch_lowest_sell_order(self, market_hash_name: str) -> dict[str, Any]:
        item_nameid = self._item_nameid_for_market_hash(market_hash_name)
        if item_nameid:
            payload = self._fetch_order_histogram(item_nameid)
            price = _parse_histogram_price(payload)
            if price is not None:
                return {
                    "lowest_price": price,
                    "volume": _parse_volume_from_summary(payload.get("sell_order_summary")),
                }
        return self._fetch_price_overview(market_hash_name)

    def _item_nameid_for_market_hash(self, market_hash_name: str) -> str | None:
        cached = self._item_nameid_cache.get(market_hash_name)
        if cached:
            return cached

        request = Request(
            url=f"{_STEAM_MARKET_URL}{quote(market_hash_name, safe='')}",
            method="GET",
            headers={
                "Accept": "text/html",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urlopen(request, timeout=10) as response:
            html = response.read().decode("utf-8", "ignore")

        match = re.search(r"Market_LoadOrderSpread\(\s*(\d+)\s*\)", html)
        if not match:
            return None
        item_nameid = match.group(1)
        self._item_nameid_cache[market_hash_name] = item_nameid
        return item_nameid

    def _fetch_order_histogram(self, item_nameid: str) -> dict[str, Any]:
        query = urlencode(
            {
                "country": self.country,
                "language": "english",
                "currency": self.currency_code,
                "item_nameid": item_nameid,
                "two_factor": 0,
            }
        )
        request = Request(
            url=f"{_STEAM_ORDER_HISTOGRAM_URL}?{query}",
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) and payload.get("success") else {}

    def _fetch_price_overview(self, market_hash_name: str) -> dict[str, Any]:
        query = f"appid=730&currency={self.currency_code}&market_hash_name={quote(market_hash_name, safe='')}"
        request = Request(
            url=f"{_STEAM_PRICE_URL}?{query}",
            method="GET",
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, dict) and payload.get("success") else {}


def _parse_steam_price(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?)", text.replace(" ", ""))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_histogram_price(payload: dict[str, Any]) -> float | None:
    raw_lowest = payload.get("lowest_sell_order")
    try:
        cents = int(raw_lowest)
    except (TypeError, ValueError):
        cents = 0
    if cents > 0:
        return round(cents / 100.0, 2)

    graph = payload.get("sell_order_graph")
    if isinstance(graph, list) and graph:
        first = graph[0]
        if isinstance(first, list) and first:
            return _parse_steam_price(first[0])
    return None


def _parse_volume_from_summary(value: Any) -> str | None:
    if value is None:
        return None
    match = re.search(r">([0-9,]+)<", str(value))
    return match.group(1) if match else None
