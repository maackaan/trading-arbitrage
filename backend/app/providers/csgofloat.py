from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Sequence
from urllib.error import HTTPError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from app.domain.models import ProviderListing
from app.providers.common import StubOrMockProvider
from app.providers.mock import MockMarketEngine
from app.services.csgoskins_price import CSGOSkinsPriceService
from app.storage.db import SkinTable

logger = logging.getLogger(__name__)

_DEFAULT_LISTINGS_URL = "https://csfloat.com/api/v1/listings"


class CSGOFloatProvider(StubOrMockProvider):
    supports_listings = True

    def __init__(
        self,
        *,
        use_mock: bool,
        mock_engine: MockMarketEngine,
        rate_limit_seconds: float,
        csgoskins_price_service: CSGOSkinsPriceService | None = None,
        api_key: str = "",
        session_cookie: str = "",
        listings_api_url: str = _DEFAULT_LISTINGS_URL,
        timeout_seconds: int = 10,
        listings_sort: str = "most_recent",
        listings_limit: int = 50,
    ) -> None:
        super().__init__(
            market_name="csgofloat",
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=rate_limit_seconds,
            csgoskins_price_service=csgoskins_price_service,
        )
        self.api_key = api_key.strip()
        self.session_cookie = session_cookie.strip()
        self.listings_api_url = (listings_api_url or _DEFAULT_LISTINGS_URL).strip()
        self.timeout_seconds = max(timeout_seconds, 3)
        self.listings_sort = (listings_sort or "most_recent").strip()
        self.listings_limit = min(max(int(listings_limit), 1), 50)
        self.last_error: str | None = None

    @property
    def listings_api_configured(self) -> bool:
        return bool(self.listings_api_url)

    @property
    def auth_configured(self) -> bool:
        return bool(self.api_key or self.session_cookie)

    async def fetch_new_listings(
        self,
        skins: Sequence[SkinTable],
        since: datetime | None,
    ) -> list[ProviderListing]:
        if self.use_mock:
            return await super().fetch_new_listings(skins, since)

        if not self.listings_api_configured:
            logger.info("CSFloat listings API is not configured.")
            self.last_error = "CSFloat listings API URL is not configured."
            self.last_listing_error = self.last_error
            return []

        try:
            request_url = self._build_request_url()
            payload = await asyncio.to_thread(self._fetch_json, request_url)
            self.last_error = None
            self.last_listing_error = None
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", "ignore")
            except Exception:
                body = ""
            self.last_error = f"HTTP {exc.code}: {body[:180] or 'request failed'}"
            if exc.code == 403 and not self.auth_configured:
                self.last_error = (
                    "HTTP 403: CSFloat requires login. Set CSGOFLOAT_API_KEY or CSFLOAT_SESSION_COOKIE."
                )
            self.last_listing_error = self.last_error
            logger.warning("CSFloat listings request failed: %s", self.last_error)
            return []
        except Exception:
            self.last_error = "Request failed unexpectedly."
            self.last_listing_error = self.last_error
            logger.warning("CSFloat listings request failed", exc_info=True)
            return []

        now = datetime.now(timezone.utc)
        rows: list[ProviderListing] = []
        for item in _iter_listing_items(payload):
            listing_id = _string_or_none(item, "id")
            if not listing_id:
                continue

            price_cents = _float_or_none(item, "price")
            if price_cents is None or price_cents <= 0:
                continue

            skin_name = _resolve_skin_name(item)
            if not skin_name:
                continue

            listed_at = _parse_datetime(_string_or_none(item, "created_at", "createdAt")) or now
            if since and listed_at < since:
                continue

            item_obj = item.get("item")
            image_url = _build_icon_url(_string_or_none(item_obj if isinstance(item_obj, dict) else {}, "icon_url"))
            float_value = _float_or_none(item_obj if isinstance(item_obj, dict) else {}, "float_value", "floatValue")
            min_offer_price = _float_or_none(item, "min_offer_price", "minOfferPrice")

            rows.append(
                ProviderListing(
                    market="csgofloat",
                    external_id=listing_id,
                    skin_name=skin_name,
                    price=round(price_cents / 100.0, 2),
                    currency="USD",
                    listed_at=listed_at,
                    metadata={
                        "mode": "official_api",
                        "is_simulated": False,
                        "price_source": "csfloat_api",
                        "image_url": image_url,
                        "item_url": f"https://csfloat.com/item/{listing_id}",
                        "float_value": float_value,
                        "min_offer_price": min_offer_price / 100.0 if min_offer_price else None,
                    },
                )
            )

        rows.sort(key=lambda row: row.listed_at, reverse=True)
        return rows[: self.listings_limit]

    def _build_request_url(self) -> str:
        parsed = urlparse(self.listings_api_url)
        query_pairs = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query_pairs.setdefault("sort_by", self.listings_sort)
        query_pairs.setdefault("limit", str(self.listings_limit))
        rebuilt = parsed._replace(query=urlencode(query_pairs))
        return urlunparse(rebuilt)

    def _fetch_json(self, url: str) -> Any:
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        if self.api_key:
            # CSFloat docs expect raw API key value in Authorization header.
            headers["Authorization"] = self.api_key
        if self.session_cookie:
            headers["Cookie"] = self.session_cookie
        request = Request(url=url, method="GET", headers=headers)
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))


def _iter_listing_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("listings", "items", "data", "results"):
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


def _resolve_skin_name(payload: dict[str, Any]) -> str | None:
    item = payload.get("item")
    item_payload = item if isinstance(item, dict) else {}
    market_hash_name = _string_or_none(item_payload, "market_hash_name", "marketHashName")
    if market_hash_name:
        return market_hash_name

    base_name = _string_or_none(item_payload, "item_name", "itemName", "name")
    wear_name = _string_or_none(item_payload, "wear_name", "wearName")
    if not base_name:
        return None
    if wear_name and not base_name.endswith(f"({wear_name})"):
        return f"{base_name} ({wear_name})"
    return base_name


def _build_icon_url(icon_path: str | None) -> str | None:
    if not icon_path:
        return None
    icon = icon_path.strip()
    if not icon:
        return None
    if icon.startswith("http://") or icon.startswith("https://"):
        return icon
    return f"https://community.cloudflare.steamstatic.com/economy/image/{icon}"
