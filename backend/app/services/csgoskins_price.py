from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from app.services.catalog_search import build_display_name
from app.services.search_matching import normalize_text, score_skin_name
from app.services.wear import split_wear_suffix

logger = logging.getLogger(__name__)

WEAR_TO_SLUG = {
    "Factory New": "factory-new",
    "Minimal Wear": "minimal-wear",
    "Field-Tested": "field-tested",
    "Well-Worn": "well-worn",
    "Battle-Scarred": "battle-scarred",
}

MARKET_LABEL_MAP = {
    "csmoney": "csmoney",
    "csfloat": "csgofloat",
    "buff163": "buff163",
    "buffmarket": "buff_market",
    "dmarket": "dmarket",
    "skinport": "skinport",
    "skinbaron": "skinbaron",
    "skinsmonkey": "skinsmonkey",
    "steam": "steam",
    "steamcommunitymarket": "steam",
}

_CACHE_MISS = object()


@dataclass
class ResolvedItem:
    title: str
    item_url: str
    image_url: str | None


@dataclass
class SkinMarketSnapshot:
    skin_name: str
    item_url: str
    image_url: str | None
    aggregate_low_price: float | None
    aggregate_high_price: float | None
    prices_by_market: dict[str, float]


@dataclass
class MarketPriceLookup:
    market: str
    price: float
    item_url: str
    image_url: str | None
    aggregate_low_price: float | None
    aggregate_high_price: float | None


class CSGOSkinsPriceService:
    def __init__(
        self,
        *,
        enabled: bool,
        search_base_url: str,
        search_api_key: str,
        timeout_seconds: int = 10,
        resolve_ttl_seconds: int = 6 * 3600,
        snapshot_ttl_seconds: int = 180,
        missing_ttl_seconds: int = 90,
    ) -> None:
        self.enabled = enabled
        self.search_base_url = search_base_url.rstrip("/")
        self.search_api_key = search_api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.resolve_ttl_seconds = max(resolve_ttl_seconds, 60)
        self.snapshot_ttl_seconds = max(snapshot_ttl_seconds, 30)
        self.missing_ttl_seconds = max(missing_ttl_seconds, 30)

        self._resolve_cache: dict[str, tuple[float, ResolvedItem | None]] = {}
        self._snapshot_cache: dict[str, tuple[float, SkinMarketSnapshot | None]] = {}
        self._skin_locks: dict[str, asyncio.Lock] = {}

    @property
    def supported_markets(self) -> set[str]:
        return set(MARKET_LABEL_MAP.values())

    def supports_market(self, market: str) -> bool:
        return market.lower().strip() in self.supported_markets

    async def get_market_price(self, skin_name: str, market: str) -> MarketPriceLookup | None:
        market_key = market.lower().strip()
        if not self.enabled or not self.supports_market(market_key):
            return None

        snapshot = await self.get_skin_snapshot(skin_name)
        if snapshot is None:
            return None

        price = snapshot.prices_by_market.get(market_key)
        if price is None:
            return None

        return MarketPriceLookup(
            market=market_key,
            price=price,
            item_url=snapshot.item_url,
            image_url=snapshot.image_url,
            aggregate_low_price=snapshot.aggregate_low_price,
            aggregate_high_price=snapshot.aggregate_high_price,
        )

    async def get_skin_snapshot(self, skin_name: str) -> SkinMarketSnapshot | None:
        if not self.enabled or not skin_name.strip():
            return None

        cache_key = skin_name.strip().lower()
        cached = self._cache_get(self._snapshot_cache, cache_key)
        if cached is not _CACHE_MISS:
            return cached

        lock = self._skin_locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            cached = self._cache_get(self._snapshot_cache, cache_key)
            if cached is not _CACHE_MISS:
                return cached

            snapshot = await self._load_skin_snapshot_uncached(skin_name)
            self._cache_set(
                self._snapshot_cache,
                cache_key,
                snapshot,
                self.snapshot_ttl_seconds if snapshot else self.missing_ttl_seconds,
            )
            return snapshot

    async def _load_skin_snapshot_uncached(self, skin_name: str) -> SkinMarketSnapshot | None:
        base_name, wear = split_wear_suffix(skin_name)
        resolved = await self._resolve_item(base_name)
        if resolved is None:
            return None

        page_url = self._build_item_variant_url(resolved.item_url, wear)
        html = await asyncio.to_thread(self._get_text, page_url)

        aggregate_low, aggregate_high, page_image = extract_product_metadata(html)
        prices_by_market = extract_active_offer_prices(html)

        if not prices_by_market:
            return None

        return SkinMarketSnapshot(
            skin_name=skin_name,
            item_url=page_url,
            image_url=page_image or resolved.image_url,
            aggregate_low_price=aggregate_low,
            aggregate_high_price=aggregate_high,
            prices_by_market=prices_by_market,
        )

    async def _resolve_item(self, base_name: str) -> ResolvedItem | None:
        cache_key = base_name.strip().lower()
        cached = self._cache_get(self._resolve_cache, cache_key)
        if cached is not _CACHE_MISS:
            return cached

        if not self.search_base_url or not self.search_api_key:
            self._cache_set(self._resolve_cache, cache_key, None, self.missing_ttl_seconds)
            return None

        payload = {
            "q": base_name,
            "limit": 12,
            "attributesToRetrieve": ["title", "category", "url", "image_url_primary", "image_url_fallback"],
        }

        try:
            response = await asyncio.to_thread(
                self._post_json,
                f"{self.search_base_url}/indexes/pages/search",
                payload,
            )
        except Exception:
            logger.exception("Failed to resolve item via csgoskins for %s", base_name)
            self._cache_set(self._resolve_cache, cache_key, None, self.missing_ttl_seconds)
            return None

        hits = response.get("hits", [])
        candidates: list[tuple[float, ResolvedItem]] = []
        target_norm = normalize_text(base_name)

        for hit in hits:
            url = str(hit.get("url") or "")
            if not url.startswith("https://csgoskins.gg/items/"):
                continue

            raw_title = str(hit.get("title") or "").strip()
            category = str(hit.get("category") or "").strip() or None
            if not raw_title:
                continue

            display_name = build_display_name(raw_title, category)
            score = score_skin_name(base_name, display_name)
            candidate_norm = normalize_text(display_name)
            if candidate_norm == target_norm:
                score += 90
            elif target_norm and target_norm in candidate_norm:
                score += 40

            image_url = str(hit.get("image_url_primary") or hit.get("image_url_fallback") or "").strip() or None
            candidates.append((score, ResolvedItem(title=display_name, item_url=url, image_url=image_url)))

        if not candidates:
            self._cache_set(self._resolve_cache, cache_key, None, self.missing_ttl_seconds)
            return None

        candidates.sort(key=lambda item: item[0], reverse=True)
        best = candidates[0][1]
        self._cache_set(self._resolve_cache, cache_key, best, self.resolve_ttl_seconds)
        return best

    @staticmethod
    def _build_item_variant_url(item_url: str, wear: str | None) -> str:
        if wear is None or wear == "Vanilla":
            return item_url
        slug = WEAR_TO_SLUG.get(wear)
        if not slug:
            return item_url
        return f"{item_url}/{slug}"

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.search_api_key}",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read().decode("utf-8", "ignore")

    @staticmethod
    def _cache_get(cache: dict[str, tuple[float, Any]], key: str):
        entry = cache.get(key)
        if not entry:
            return _CACHE_MISS
        expires_at, value = entry
        if expires_at <= time.time():
            cache.pop(key, None)
            return _CACHE_MISS
        return value

    @staticmethod
    def _cache_set(cache: dict[str, tuple[float, Any]], key: str, value: Any, ttl_seconds: int) -> None:
        cache[key] = (time.time() + max(ttl_seconds, 1), value)


def extract_product_metadata(html: str) -> tuple[float | None, float | None, str | None]:
    scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)

    for script in scripts:
        text = script.strip()
        if not text:
            continue

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue

        if not isinstance(data, dict) or data.get("@type") != "Product":
            continue

        offers = data.get("offers") if isinstance(data.get("offers"), dict) else {}
        low = _parse_price(offers.get("lowPrice"))
        high = _parse_price(offers.get("highPrice"))

        image = data.get("image")
        if isinstance(image, list):
            image_url = next((str(item).strip() for item in image if str(item).strip()), None)
        elif isinstance(image, str):
            image_url = image.strip() or None
        else:
            image_url = None

        return low, high, image_url

    return None, None, None


def extract_active_offer_prices(html: str) -> dict[str, float]:
    prices_by_market: dict[str, float] = {}
    blocks = html.split('<div class="active-offer ')

    for block in blocks[1:]:
        market_match = re.search(
            r'href="https://csgoskins\.gg/markets/[^"]+"[^>]*>.*?>\s*([^<]+?)\s*</a>',
            block,
            re.S,
        )
        if not market_match:
            continue

        market_label = _normalize_market_label(market_match.group(1))
        market = MARKET_LABEL_MAP.get(market_label)
        if market is None:
            continue

        price_match = re.search(
            r'>\s*from\s*</div>\s*<div[^>]*>\s*\$([0-9,]+(?:\.[0-9]{2})?)\s*</div>',
            block,
            re.S | re.IGNORECASE,
        )
        if not price_match:
            continue

        price = _parse_price(price_match.group(1))
        if price is None or price <= 0:
            continue

        existing = prices_by_market.get(market)
        if existing is None or price < existing:
            prices_by_market[market] = price

    return prices_by_market


def _normalize_market_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _parse_price(value: Any) -> float | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    cleaned = raw.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None
