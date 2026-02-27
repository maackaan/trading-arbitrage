from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
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
        listings_sort: str = "insertDate",
        listings_order: str = "desc",
        listings_limit: int = 120,
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
        self.listings_sort = (listings_sort or "insertDate").strip()
        self.listings_order = (listings_order or "desc").strip().lower()
        self.listings_limit = max(int(listings_limit), 1)
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
            request_url = self._build_request_url(since)
            payload = await asyncio.to_thread(self._fetch_json, request_url)
        except Exception:
            logger.warning("CSMoney listings request failed", exc_info=True)
            return []

        now = datetime.now(timezone.utc)
        rows: list[ProviderListing] = []
        for item in _iter_listing_items(payload):
            external_id = _string_or_none(item, "id", "listing_id", "asset_id", "offer_id")
            skin_name = _string_or_none(
                item,
                "skin_name",
                "market_hash_name",
                "marketHashName",
                "name",
                "full_name",
                "fullName",
            )
            price = _extract_price(item)
            if not external_id or not skin_name or price is None or price <= 0:
                continue

            listed_at_raw = _string_or_none(
                item,
                "listed_at",
                "created_at",
                "insert_date",
                "insertDate",
            )
            listed_at = _parse_datetime(listed_at_raw) or now
            image_url = _string_or_none(
                item,
                "image_url",
                "imageUrl",
                "image",
                "preview_image",
                "previewImage",
            )
            item_url = _string_or_none(item, "item_url", "itemUrl", "url", "listing_url", "listingUrl")
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

    def _build_request_url(self, since: datetime | None) -> str:
        parsed = urlparse(self.listings_api_url)
        query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_pairs.setdefault("order", self.listings_order)
        query_pairs.setdefault("sort", self.listings_sort)
        query_pairs.setdefault("limit", str(self.listings_limit))
        if since:
            since_iso = since.astimezone(timezone.utc).isoformat()
            query_pairs.setdefault("since", since_iso)
            query_pairs.setdefault("sinceIso", since_iso)
        rebuilt = parsed._replace(query=urlencode(query_pairs))
        return urlunparse(rebuilt)

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
        if isinstance(value, dict):
            for nested in ("items", "listings", "results"):
                rows = value.get(nested)
                if isinstance(rows, list):
                    return [item for item in rows if isinstance(item, dict)]
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


def _extract_price(payload: dict[str, Any]) -> float | None:
    direct = _float_or_none(
        payload,
        "price",
        "price_usd",
        "priceUsd",
        "usd_price",
        "usdPrice",
        "amount",
    )
    if direct is not None:
        return direct

    cents = _float_or_none(
        payload,
        "price_cents",
        "priceCents",
        "price_cent",
        "priceCent",
        "amount_cents",
        "amountCents",
    )
    if cents is not None:
        return cents / 100.0

    pricing = payload.get("pricing")
    if isinstance(pricing, dict):
        nested = _extract_price(pricing)
        if nested is not None:
            return nested
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
