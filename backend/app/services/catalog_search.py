from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import unquote

from app.services.search_matching import score_skin_name
from app.services.wear import WEAR_ORDER, split_wear_suffix

logger = logging.getLogger(__name__)

WEAR_FROM_SLUG = {
    "factory-new": "Factory New",
    "minimal-wear": "Minimal Wear",
    "field-tested": "Field-Tested",
    "well-worn": "Well-Worn",
    "battle-scarred": "Battle-Scarred",
    "vanilla": "Vanilla",
}
DEFAULT_WEAR_OPTIONS = [
    "Factory New",
    "Minimal Wear",
    "Field-Tested",
    "Well-Worn",
    "Battle-Scarred",
]
WEAR_TO_SLUG = {
    "Factory New": "factory-new",
    "Minimal Wear": "minimal-wear",
    "Field-Tested": "field-tested",
    "Well-Worn": "well-worn",
    "Battle-Scarred": "battle-scarred",
}


@dataclass
class CatalogItem:
    title: str
    url: str
    category: str | None
    image_url: str | None


class CatalogSearchService:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: int = 8,
        fetch_wears: bool = True,
        image_cache_path: str | None = None,
        image_refresh_ttl_seconds: int = 6 * 3600,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.fetch_wears_enabled = fetch_wears
        self.image_cache_path = image_cache_path
        self.image_refresh_ttl_seconds = max(image_refresh_ttl_seconds, 60)
        self._wear_cache: dict[str, tuple[float, list[str]]] = {}
        self._image_cache: dict[str, str] = {}
        self._image_refresh_cache: dict[str, tuple[float, str | None]] = {}
        self._load_image_cache()

    async def search_items(self, query: str, limit: int = 30) -> list[CatalogItem]:
        if not query.strip() or not self.base_url or not self.api_key:
            return []

        payload = {
            "q": query,
            "limit": max(limit * 3, 50),
            "attributesToRetrieve": ["category", "title", "url", "image_url_primary", "image_url_fallback"],
        }
        response = await asyncio.to_thread(self._post_json, f"{self.base_url}/indexes/pages/search", payload)
        hits = response.get("hits", [])

        items: list[CatalogItem] = []
        for hit in hits:
            url = str(hit.get("url") or "")
            raw_title = str(hit.get("title") or "").strip()
            category = str(hit.get("category") or "").strip() or None
            if not url.startswith("https://csgoskins.gg/items/"):
                continue
            if not raw_title:
                continue
            title = build_display_name(raw_title, category)
            image_url = str(hit.get("image_url_primary") or hit.get("image_url_fallback") or "").strip() or None
            image_url = _upgrade_catalog_image_url(image_url)
            items.append(CatalogItem(title=title, url=url, category=category, image_url=image_url))
            if image_url:
                self._put_image_cache(title, image_url)

        deduped: dict[str, CatalogItem] = {}
        for item in items:
            deduped.setdefault(item.url, item)

        ranked = sorted(
            deduped.values(),
            key=lambda item: score_skin_name(query, item.title),
            reverse=True,
        )
        return ranked[:limit]

    async def prefetch_images_for_names(self, names: list[str]) -> None:
        unique_base_names = []
        seen: set[str] = set()
        for name in names:
            base_name = _base_name_from_skin_name(name)
            if not base_name:
                continue
            key = _normalize_name(base_name)
            if key in seen:
                continue
            seen.add(key)
            if self._image_cache.get(key):
                continue
            unique_base_names.append(base_name)

        for base_name in unique_base_names:
            if not self.base_url or not self.api_key:
                break
            try:
                items = await self.search_items(base_name, limit=3)
                for item in items:
                    if item.image_url:
                        self._put_image_cache(item.title, item.image_url)
                        break
            except Exception:
                logger.debug("Image prefetch failed for %s", base_name)
            await asyncio.sleep(0.05)

        self._save_image_cache()

    def image_for_skin_name(self, skin_name: str) -> str | None:
        base_name = _base_name_from_skin_name(skin_name)
        key = _normalize_name(base_name)
        return self._image_cache.get(key)

    async def refresh_image_for_skin_name(self, skin_name: str) -> str | None:
        base_name, wear = split_wear_suffix(skin_name.strip())
        if not base_name:
            return None
        if not self.base_url or not self.api_key:
            return self.image_for_skin_name(skin_name)

        cache_key = f"{_normalize_name(base_name)}::{wear or 'base'}"
        if cache_key in self._image_refresh_cache:
            cached_at, cached_value = self._image_refresh_cache[cache_key]
            if (time.time() - cached_at) < self.image_refresh_ttl_seconds:
                return cached_value or self.image_for_skin_name(skin_name)

        refreshed: str | None = None
        try:
            items = await self.search_items(base_name, limit=8)
            if items:
                exact = next((item for item in items if item.title == base_name), None)
                target = exact or items[0]
                target_url = _build_variant_url(target.url, wear)
                html = await asyncio.to_thread(self._get_text, target_url)
                refreshed = _extract_product_image_from_html(html) or target.image_url
        except Exception:
            logger.debug("Failed refreshing high-res image for %s", skin_name)

        refreshed = _upgrade_catalog_image_url(refreshed)
        if refreshed:
            self._put_image_cache(base_name, refreshed)
            self._save_image_cache()

        self._image_refresh_cache[cache_key] = (time.time(), refreshed)
        return refreshed or self.image_for_skin_name(skin_name)

    async def fetch_wears_for_item(self, item_url: str) -> list[str]:
        if not self.fetch_wears_enabled:
            return []
        if item_url in self._wear_cache:
            cached_at, value = self._wear_cache[item_url]
            if (time.time() - cached_at) < 1800:
                return value

        try:
            html = await asyncio.to_thread(self._get_text, item_url)
            wears = extract_wears_from_html(html)
            if not wears:
                wears = infer_default_wears(item_url)
            self._wear_cache[item_url] = (time.time(), wears)
            return wears
        except Exception:
            wears = infer_default_wears(item_url)
            self._wear_cache[item_url] = (time.time(), wears)
            logger.warning("Falling back to inferred wear options for %s", item_url)
            return wears

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url=url,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=self.timeout_seconds) as response:
            return response.read().decode("utf-8", "ignore")

    def _put_image_cache(self, skin_name: str, image_url: str) -> None:
        base_name = _base_name_from_skin_name(skin_name)
        key = _normalize_name(base_name)
        upgraded = _upgrade_catalog_image_url(image_url)
        if not key or not upgraded:
            return
        self._image_cache[key] = upgraded

    def _load_image_cache(self) -> None:
        if not self.image_cache_path:
            return
        try:
            if not os.path.exists(self.image_cache_path):
                return
            with open(self.image_cache_path, "r", encoding="utf-8") as file:
                payload = json.load(file)
            if isinstance(payload, dict):
                for key, value in payload.items():
                    if not isinstance(key, str) or not isinstance(value, str):
                        continue
                    normalized = _upgrade_catalog_image_url(value)
                    if key and normalized:
                        self._image_cache[key] = normalized
        except Exception:
            logger.debug("Failed loading image cache from %s", self.image_cache_path)

    def _save_image_cache(self) -> None:
        if not self.image_cache_path:
            return
        try:
            directory = os.path.dirname(self.image_cache_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(self.image_cache_path, "w", encoding="utf-8") as file:
                json.dump(self._image_cache, file, ensure_ascii=True)
        except Exception:
            logger.debug("Failed saving image cache to %s", self.image_cache_path)


def extract_wears_from_html(html: str) -> list[str]:
    hrefs = re.findall(r'href="https://csgoskins\.gg/items/[^"#?]+/([^"#?]+)"', html)
    found: set[str] = set()

    for suffix in hrefs:
        slug = suffix.lower()
        for prefix in ("stattrak-", "souvenir-"):
            if slug.startswith(prefix):
                slug = slug[len(prefix) :]
        wear = WEAR_FROM_SLUG.get(slug)
        if wear:
            found.add(wear)

    if not found and "Vanilla" in html:
        found.add("Vanilla")

    return sorted(found, key=lambda wear: WEAR_ORDER.get(wear, 99))


def infer_default_wears(item_url: str) -> list[str]:
    lowered = item_url.lower()
    if lowered.endswith("-vanilla") or "/vanilla" in lowered:
        return ["Vanilla"]
    return list(DEFAULT_WEAR_OPTIONS)


def build_display_name(title: str, category: str | None) -> str:
    normalized_title = title.strip()
    if not category:
        return normalized_title

    normalized_category = category.strip()
    if not normalized_category or normalized_title.lower().startswith(normalized_category.lower()):
        return normalized_title
    if "|" in normalized_title:
        return normalized_title

    return f"{normalized_category} | {normalized_title}"


def _base_name_from_skin_name(name: str) -> str:
    value = (name or "").strip()
    if value.endswith(")") and " (" in value:
        return value[: value.rfind(" (")].strip()
    return value


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def _build_variant_url(item_url: str, wear: str | None) -> str:
    if not wear or wear == "Vanilla":
        return item_url
    slug = WEAR_TO_SLUG.get(wear)
    if not slug:
        return item_url
    return f"{item_url}/{slug}"


def _extract_product_image_from_html(html: str) -> str | None:
    scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    for script in scripts:
        text = script.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("@type") != "Product":
            continue
        image = payload.get("image")
        if isinstance(image, str):
            value = image.strip()
            if value:
                return _upgrade_catalog_image_url(value)
        if isinstance(image, list):
            for item in image:
                value = str(item).strip()
                if value:
                    return _upgrade_catalog_image_url(value)
    return None


def _upgrade_catalog_image_url(image_url: str | None) -> str | None:
    if not image_url:
        return None
    decoded = _decode_csgoskins_proxy_image_url(image_url)
    return _sanitize_image_url(decoded or image_url)


def _decode_csgoskins_proxy_image_url(image_url: str) -> str | None:
    match = re.search(r"/public/uih/items/([^/]+)/", image_url)
    if not match:
        return None

    token = unquote(match.group(1)).strip()
    if not token:
        return None
    padded = token + ("=" * ((4 - (len(token) % 4)) % 4))

    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            raw = decoder(padded.encode("ascii"))
            decoded = raw.decode("utf-8", "ignore").strip()
        except Exception:
            continue
        if decoded.startswith("https://") or decoded.startswith("http://"):
            return _sanitize_image_url(decoded)
    return None


def _sanitize_image_url(value: str) -> str:
    return value.strip().strip("\"'<>")
