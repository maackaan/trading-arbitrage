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
    mock_seed: int = 42

    refresh_interval_seconds: int = 10
    listing_refresh_interval_seconds: int = 8
    default_history_hours: int = 72

    provider_rate_limits: str = "steam:5,buff_market:5,dmarket:5,skinbaron:5,buff163:5,csgofloat:5,skinsmonkey:5,skinport:5,csmoney:5"

    steam_api_key: str = ""
    buff_market_api_key: str = ""
    dmarket_api_key: str = ""
    skinbaron_api_key: str = ""
    buff163_api_key: str = ""
    csgofloat_api_key: str = ""
    skinsmonkey_api_key: str = ""
    skinport_api_key: str = ""
    csmoney_api_key: str = ""

    seed_skins: List[str] = Field(
        default_factory=lambda: [
            "AK-47 | Redline (Field-Tested)",
            "AWP | Asiimov (Battle-Scarred)",
            "M4A4 | The Emperor (Minimal Wear)",
            "Desert Eagle | Printstream (Field-Tested)",
            "USP-S | Kill Confirmed (Field-Tested)",
            "Glock-18 | Water Elemental (Factory New)",
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
