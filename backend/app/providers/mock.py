from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Sequence

from app.domain.models import ProviderListing, ProviderPrice
from app.storage.db import SkinTable


class MockMarketEngine:
    def __init__(self, seed: int = 42) -> None:
        self.random = random.Random(seed)
        self._state: dict[tuple[str, str], float] = {}
        self._listing_counter = 0

        self.base_prices: dict[str, float] = {
            "AK-47 | Redline (Field-Tested)": 22.5,
            "AWP | Asiimov (Battle-Scarred)": 85.0,
            "M4A4 | The Emperor (Minimal Wear)": 37.0,
            "Desert Eagle | Printstream (Field-Tested)": 49.0,
            "USP-S | Kill Confirmed (Field-Tested)": 56.0,
            "Glock-18 | Water Elemental (Factory New)": 18.0,
        }

        self.market_bias: dict[str, float] = {
            "steam": 1.06,
            "buff_market": 1.01,
            "dmarket": 0.99,
            "skinbaron": 1.03,
            "buff163": 1.0,
            "csgofloat": 1.02,
            "skinsmonkey": 1.05,
            "skinport": 1.01,
            "csmoney": 1.04,
        }

    def next_price(self, market: str, skin_name: str) -> float:
        key = (market, skin_name)
        base = self.base_prices.get(skin_name, self.random.uniform(8.0, 120.0))
        center = base * self.market_bias.get(market, 1.0)

        if key not in self._state:
            self._state[key] = center * self.random.uniform(0.95, 1.05)

        current = self._state[key]
        drift = (center - current) * 0.18
        noise = self.random.gauss(0.0, center * 0.01)
        next_value = max(0.5, current + drift + noise)
        self._state[key] = next_value
        return round(next_value, 2)

    def generate_prices(self, market: str, skins: Sequence[SkinTable]) -> list[ProviderPrice]:
        now = datetime.now(timezone.utc)
        return [
            ProviderPrice(
                market=market,
                skin_name=skin.name,
                price=self.next_price(market, skin.name),
                currency="USD",
                timestamp=now,
                metadata={"mode": "mock"},
            )
            for skin in skins
        ]

    def generate_listings(self, market: str, skins: Sequence[SkinTable]) -> list[ProviderListing]:
        now = datetime.now(timezone.utc)
        listings: list[ProviderListing] = []
        for skin in skins:
            if self.random.random() > 0.20:
                continue

            self._listing_counter += 1
            baseline = self.next_price("buff163", skin.name)
            discount_factor = self.random.uniform(0.7, 1.05)
            if self.random.random() < 0.08:
                discount_factor = self.random.uniform(0.5, 0.68)

            listing_price = round(max(0.5, baseline * discount_factor), 2)
            listings.append(
                ProviderListing(
                    market=market,
                    external_id=f"{market}-{self._listing_counter}",
                    skin_name=skin.name,
                    price=listing_price,
                    currency="USD",
                    listed_at=now - timedelta(minutes=self.random.randint(0, 90)),
                    metadata={"mode": "mock", "discount_factor": discount_factor},
                )
            )

        return listings
