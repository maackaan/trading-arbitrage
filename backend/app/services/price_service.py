from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Iterable

from app.domain.models import (
    MAX_REASONABLE_SKIN_PRICE,
    MarketSummary,
    NormalizedProviderPrice,
    PriceComparison,
    ProviderListing,
    ProviderPrice,
)

NO_LIVE_PRICE_ERROR = "No live price available"
LIVE_PRICE_MAX_AGE = timedelta(hours=24)
LIVE_COMPARISON_SOURCES = ("steam", "skinport", "csfloat")
KNOWN_PRICE_SOURCES = {
    "steam",
    "buff_market",
    "dmarket",
    "skinbaron",
    "buff163",
    "csfloat",
    "skinsmonkey",
    "skinport",
    "csmoney",
}
SOURCE_ALIASES = {
    "csgofloat": "csfloat",
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def canonical_source(source: str) -> str:
    key = (source or "").strip().lower()
    return SOURCE_ALIASES.get(key, key)


def is_known_source(source: str) -> bool:
    return canonical_source(source) in KNOWN_PRICE_SOURCES


def is_valid_price_value(price: object) -> bool:
    try:
        value = float(price)
    except (TypeError, ValueError):
        return False
    return isfinite(value) and 0 < value <= MAX_REASONABLE_SKIN_PRICE


def is_fresh_live_observation(timestamp: datetime | None, *, now: datetime | None = None) -> bool:
    if timestamp is None:
        return False
    current = now or now_utc()
    observed_at = timestamp
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    return current - observed_at <= LIVE_PRICE_MAX_AGE


def validate_provider_price(price: ProviderPrice) -> ProviderPrice | None:
    source = canonical_source(price.market)
    if not is_known_source(source):
        return None
    if not is_valid_price_value(price.price):
        return None
    if price.timestamp is None:
        return None

    return ProviderPrice(
        market=source,
        skin_name=price.skin_name,
        price=round(float(price.price), 2),
        currency=price.currency,
        timestamp=price.timestamp,
        metadata=price.metadata,
    )


def validate_provider_listing(listing: ProviderListing) -> ProviderListing | None:
    source = canonical_source(listing.market)
    if not is_known_source(source):
        return None
    if not is_valid_price_value(listing.price):
        return None
    if listing.listed_at is None:
        return None

    return ProviderListing(
        market=source,
        external_id=listing.external_id,
        skin_name=listing.skin_name,
        price=round(float(listing.price), 2),
        currency=listing.currency,
        listed_at=listing.listed_at,
        metadata=listing.metadata,
    )


class PriceService:
    def __init__(self, sources: Iterable[str] = LIVE_COMPARISON_SOURCES) -> None:
        self.sources = tuple(canonical_source(source) for source in sources if is_known_source(source))

    def build_comparison(
        self,
        *,
        item_name: str,
        latest_prices: Iterable[MarketSummary],
    ) -> PriceComparison:
        latest_by_source = {
            canonical_source(price.market): price
            for price in latest_prices
            if is_known_source(price.market) and is_valid_price_value(price.price) and price.timestamp is not None
        }

        rows: list[NormalizedProviderPrice] = []
        for source in self.sources:
            latest = latest_by_source.get(source)
            if latest is None:
                rows.append(unavailable_price(item_name=item_name, source=source))
                continue

            rows.append(
                NormalizedProviderPrice(
                    item_name=item_name,
                    source=source,  # type: ignore[arg-type]
                    price=round(float(latest.price), 2),
                    currency=latest.currency,
                    url=latest.url,
                    last_updated=latest.timestamp,
                    available=True,
                )
            )

        available = sorted((row for row in rows if row.available and row.price is not None), key=lambda row: row.price or 0)
        cheapest = available[0] if available else None
        percentage_difference = None
        if len(available) >= 2 and available[0].price:
            highest = max(row.price or 0 for row in available)
            percentage_difference = round(((highest - available[0].price) / available[0].price) * 100, 2)

        return PriceComparison(
            item_name=item_name,
            sources=rows,
            cheapest_source=cheapest,
            percentage_difference=percentage_difference,
        )


def unavailable_price(*, item_name: str, source: str, error: str = NO_LIVE_PRICE_ERROR) -> NormalizedProviderPrice:
    return NormalizedProviderPrice(
        item_name=item_name,
        source=canonical_source(source),  # type: ignore[arg-type]
        price=None,
        currency=None,
        url=None,
        last_updated=now_utc(),
        available=False,
        error=error,
    )
