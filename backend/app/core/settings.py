from __future__ import annotations

from functools import lru_cache
from typing import Dict, List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CS2 Arbitrage API"
    environment: str = "dev"
    log_level: str = "INFO"

    database_url: str = "sqlite+aiosqlite:///./app.db"

    use_mock_providers: bool = True
    mock_listings_enabled: bool = False
    mock_seed: int = 42

    refresh_interval_seconds: int = 10
    refresh_skin_batch_size: int = 6
    listing_refresh_interval_seconds: int = 60
    listing_since_hours: int = 6
    default_history_hours: int = 72
    search_catalog_provider: str = "csgoskins_gg"
    search_catalog_url: str = "https://search.csgoskins.gg"
    search_catalog_key: str = "6b86fad2efbfd796e2fdf50271b74a68374d7f750d3c19287ce89c0afa8e753d"
    search_catalog_timeout_seconds: int = 8
    search_catalog_fetch_wears: bool = True
    catalog_image_refresh_ttl_seconds: int = 21600
    csgoskins_price_fallback_enabled: bool = True
    csgoskins_price_ttl_seconds: int = 900
    csgoskins_price_resolve_ttl_seconds: int = 21600
    catalog_image_cache_path: str = "./skin_images_cache.json"
    catalog_prefetch_images: bool = True

    provider_rate_limits: str = "steam:60,buff_market:60,dmarket:60,skinbaron:60,buff163:60,csgofloat:60,skinsmonkey:60,skinport:300,csmoney:60"

    steam_api_key: str = ""
    buff_market_api_key: str = ""
    dmarket_api_key: str = ""
    skinbaron_api_key: str = ""
    buff163_api_key: str = ""
    csgofloat_api_key: str = ""
    csfloat_session_cookie: str = ""
    csfloat_listings_api_url: str = "https://csfloat.com/api/v1/listings"
    csfloat_api_timeout_seconds: int = 10
    csfloat_listings_sort: str = "most_recent"
    csfloat_listings_limit: int = 50
    skinsmonkey_api_key: str = ""
    skinport_api_key: str = ""
    skinport_items_api_url: str = "https://api.skinport.com/v1/items"
    skinport_api_timeout_seconds: int = 20
    skinport_app_id: int = 730
    skinport_currency: str = "USD"
    csmoney_api_key: str = ""
    csmoney_listings_api_url: str = ""
    csmoney_api_timeout_seconds: int = 10
    csmoney_listings_sort: str = "insertDate"
    csmoney_listings_order: str = "desc"
    csmoney_listings_limit: int = 120

    seed_skins: List[str] = Field(
        default_factory=lambda: [
            "AK-47 | Redline (Field-Tested)",
            "AK-47 | Vulcan (Field-Tested)",
            "AK-47 | Asiimov (Field-Tested)",
            "AWP | Asiimov (Battle-Scarred)",
            "AWP | Dragon Lore (Field-Tested)",
            "AWP | Hyper Beast (Minimal Wear)",
            "M4A4 | The Emperor (Minimal Wear)",
            "M4A4 | Howl (Field-Tested)",
            "M4A1-S | Printstream (Field-Tested)",
            "M4A1-S | Hyper Beast (Factory New)",
            "Desert Eagle | Printstream (Field-Tested)",
            "Desert Eagle | Blaze (Factory New)",
            "USP-S | Kill Confirmed (Field-Tested)",
            "USP-S | Cortex (Factory New)",
            "Glock-18 | Water Elemental (Factory New)",
            "Glock-18 | Fade (Factory New)",
            "Karambit | Doppler (Factory New)",
            "Karambit | Tiger Tooth (Factory New)",
            "M9 Bayonet | Crimson Web (Field-Tested)",
            "M9 Bayonet | Fade (Factory New)",
            "Butterfly Knife | Slaughter (Minimal Wear)",
            "Butterfly Knife | Doppler (Factory New)",
            "Bayonet | Marble Fade (Factory New)",
            "Falchion Knife | Damascus Steel (Minimal Wear)",
            "Gut Knife | Lore (Field-Tested)",
            "Stiletto Knife | Damascus Steel (Minimal Wear)",
        ]
    )

    @property
    def provider_rate_limit_map(self) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for chunk in self.provider_rate_limits.split(","):
            chunk = chunk.strip()
            if not chunk or ":" not in chunk:
                continue
            name, value = chunk.split(":", maxsplit=1)
            try:
                result[name.strip().lower()] = max(float(value.strip()), 0.0)
            except ValueError:
                continue
        return result


@lru_cache
def get_settings() -> Settings:
    return Settings()
