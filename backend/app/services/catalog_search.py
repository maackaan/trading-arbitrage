from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.request import Request, urlopen

from app.services.search_matching import score_skin_name

logger = logging.getLogger(__name__)

WEAR_ORDER = {
    "Factory New": 0,
    "Minimal Wear": 1,
    "Field-Tested": 2,
    "Well-Worn": 3,
    "Battle-Scarred": 4,
    "Vanilla": 5,
}

WEAR_FROM_SLUG = {
    "factory-new": "Factory New",
    "minimal-wear": "Minimal Wear",
    "field-tested": "Field-Tested",
    "well-worn": "Well-Worn",
    "battle-scarred": "Battle-Scarred",
    "vanilla": "Vanilla",
}


@dataclass
class CatalogItem:
    title: str
    url: str
    category: str | None


class CatalogSearchService:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: int = 8,
        fetch_wears: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.fetch_wears_enabled = fetch_wears
        self._wear_cache: dict[str, tuple[float, list[str]]] = {}

    async def search_items(self, query: str, limit: int = 30) -> list[CatalogItem]:
        if not query.strip() or not self.base_url or not self.api_key:
            return []

        payload = {
            "q": query,
            "limit": max(limit * 3, 50),
            "attributesToRetrieve": ["category", "title", "url"],
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
            items.append(CatalogItem(title=title, url=url, category=category))

        deduped: dict[str, CatalogItem] = {}
        for item in items:
            deduped.setdefault(item.url, item)

        ranked = sorted(
            deduped.values(),
            key=lambda item: score_skin_name(query, item.title),
            reverse=True,
        )
        return ranked[:limit]

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
            self._wear_cache[item_url] = (time.time(), wears)
            return wears
        except Exception:
            logger.exception("Failed loading wear options from %s", item_url)
            return []

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
