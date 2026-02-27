from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Sequence

from app.domain.models import ProviderListing, ProviderPrice
from app.services.wear import has_wear_suffix, split_wear_suffix
from app.storage.db import SkinTable


class MockMarketEngine:
    def __init__(self, seed: int = 42) -> None:
        self.random = random.Random(seed)
        self._state: dict[tuple[str, str], float] = {}
        self._base_cache: dict[str, float] = {}
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

    @staticmethod
    def _stable_unit(name: str) -> float:
        digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
        return int(digest, 16) / 0xFFFFFFFF

    def _infer_base_price(self, skin_name: str) -> float:
        if skin_name in self.base_prices:
            return self.base_prices[skin_name]

        base_name, wear = split_wear_suffix(skin_name)
        lowered = base_name.lower()
        unit = self._stable_unit(base_name)

        knife_terms = [
            "knife",
            "karambit",
            "bayonet",
            "talon",
            "butterfly",
            "stiletto",
            "falchion",
            "huntsman",
            "bowie",
            "navaja",
            "ursus",
            "nomad",
            "skeleton",
            "paracord",
            "survival",
            "gut knife",
        ]
        glove_terms = [
            "gloves",
            "wraps",
            "hand wraps",
            "driver gloves",
            "sport gloves",
            "specialist gloves",
            "moto gloves",
            "bloodhound gloves",
            "hydra gloves",
            "broken fang gloves",
        ]
        high_tier_terms = [
            "dragon lore",
            "gungnir",
            "medusa",
            "howl",
            "wild lotus",
            "fade",
            "doppler ruby",
            "doppler sapphire",
            "emerald",
            "black pearl",
        ]

        if any(term in lowered for term in high_tier_terms):
            base = 900.0 + (unit * 4200.0)
        elif any(term in lowered for term in knife_terms):
            base = 280.0 + (unit * 2200.0)
        elif any(term in lowered for term in glove_terms):
            base = 180.0 + (unit * 1800.0)
        elif "sticker" in lowered:
            base = 1.0 + (unit * 250.0)
        elif "case" in lowered or "capsule" in lowered:
            base = 0.3 + (unit * 45.0)
        else:
            base = 6.0 + (unit * 220.0)

        wear_multiplier = {
            "Factory New": 1.18,
            "Minimal Wear": 1.08,
            "Field-Tested": 1.0,
            "Well-Worn": 0.86,
            "Battle-Scarred": 0.74,
            "Vanilla": 1.06,
        }.get(wear, 1.0)
        return round(max(base * wear_multiplier, 0.3), 2)

    def _get_skin_base(self, skin_name: str) -> float:
        if skin_name not in self._base_cache:
            self._base_cache[skin_name] = self._infer_base_price(skin_name)
        return self._base_cache[skin_name]

    def next_price(self, market: str, skin_name: str) -> float:
        key = (market, skin_name)
        base = self._get_skin_base(skin_name)
        center = base * self.market_bias.get(market, 1.0)

        if key not in self._state:
            self._state[key] = center * self.random.uniform(0.95, 1.05)

        current = self._state[key]
        drift = (center - current) * 0.18
        noise_scale = 0.004 if center > 500 else 0.008
        noise = self.random.gauss(0.0, center * noise_scale)
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
        candidate_skins = [skin for skin in skins if has_wear_suffix(skin.name)]
        if not candidate_skins:
            candidate_skins = list(skins)

        for skin in candidate_skins:
            if self.random.random() > 0.12:
                continue

            self._listing_counter += 1
            baseline = self.next_price("buff163", skin.name)
            discount_factor = self.random.uniform(0.94, 1.08)
            if self.random.random() < 0.20:
                discount_factor = self.random.uniform(0.78, 0.92)
            if self.random.random() < 0.04:
                discount_factor = self.random.uniform(0.55, 0.72)

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
