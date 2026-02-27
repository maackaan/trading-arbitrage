from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Sequence
from urllib.request import Request, urlopen

from app.domain.models import ProviderListing
from app.providers.common import StubOrMockProvider
from app.providers.mock import MockMarketEngine
from app.services.csgoskins_price import CSGOSkinsPriceService
from app.storage.db import SkinTable

logger = logging.getLogger(__name__)


class CSMoneyProvider(StubOrMockProvider):
    supports_listings = True

    def __init__(
        self,
        *,
        use_mock: bool,
        mock_engine: MockMarketEngine,
        rate_limit_seconds: float,
        csgoskins_price_service: CSGOSkinsPriceService | None = None,
        api_key: str = "",
        listings_api_url: str = "",
        timeout_seconds: int = 10,
    ) -> None:
        super().__init__(
            market_name="csmoney",
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=rate_limit_seconds,
            csgoskins_price_service=csgoskins_price_service,
        )
        self.api_key = api_key.strip()
        self.listings_api_url = listings_api_url.strip()
        self.timeout_seconds = max(timeout_seconds, 3)
        self._logged_missing_config = False

    @property
    def listings_api_configured(self) -> bool:
        return bool(self.listings_api_url)

    async def fetch_new_listings(
        self,
        skins: Sequence[SkinTable],
        since: datetime | None,
    ) -> list[ProviderListing]:
        if self.use_mock:
            return await super().fetch_new_listings(skins, since)

        if not self.listings_api_configured:
            if not self._logged_missing_config:
                logger.info(
                    "CSMoney listings API is not configured. Set CSMONEY_LISTINGS_API_URL (and CSMONEY_API_KEY if required)."
                )
                self._logged_missing_config = True
            return []

        try:
            payload = await asyncio.to_thread(self._fetch_json, self.listings_api_url)
        except Exception:
            logger.warning("CSMoney listings request failed", exc_info=True)
            return []

        now = datetime.now(timezone.utc)
        rows: list[ProviderListing] = []
        for item in _iter_listing_items(payload):
            external_id = _string_or_none(item, "id", "listing_id", "asset_id", "offer_id")
            skin_name = _string_or_none(item, "skin_name", "market_hash_name", "name", "full_name")
            price = _float_or_none(item, "price", "price_usd", "usd_price", "amount")
            if not external_id or not skin_name or price is None or price <= 0:
                continue

            listed_at_raw = _string_or_none(item, "listed_at", "created_at", "insert_date", "insertDate")
            listed_at = _parse_datetime(listed_at_raw) or now
            image_url = _string_or_none(item, "image_url", "image", "preview_image")
            item_url = _string_or_none(item, "item_url", "url", "listing_url")
            currency = _string_or_none(item, "currency") or "USD"

            rows.append(
                ProviderListing(
                    market="csmoney",
                    external_id=external_id,
                    skin_name=skin_name,
                    price=round(price, 2),
                    currency=currency,
                    listed_at=listed_at,
                    metadata={
                        "mode": "official_api",
                        "is_simulated": False,
                        "price_source": "csmoney_api",
                        "image_url": image_url,
                        "item_url": item_url,
                    },
                )
            )

        rows.sort(key=lambda row: row.listed_at, reverse=True)
        return rows

    def _fetch_json(self, url: str) -> Any:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request = Request(url=url, method="GET", headers=headers)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


def _iter_listing_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "listings", "data", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _string_or_none(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _float_or_none(payload: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
