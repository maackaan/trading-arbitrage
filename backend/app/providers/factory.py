from __future__ import annotations

from app.core.settings import Settings
from app.providers.base import BaseProvider
from app.providers.buff163 import Buff163Provider
from app.providers.buff_market import BuffMarketProvider
from app.providers.csgofloat import CSGOFloatProvider
from app.providers.csmoney import CSMoneyProvider
from app.providers.dmarket import DMarketProvider
from app.providers.mock import MockMarketEngine
from app.providers.skinbaron import SkinBaronProvider
from app.providers.skinport import SkinportProvider
from app.providers.skinsmonkey import SkinsMonkeyProvider
from app.providers.steam import SteamProvider


def _rate(settings: Settings, provider_name: str) -> float:
    return settings.provider_rate_limit_map.get(provider_name, 5.0)


def build_providers(settings: Settings) -> list[BaseProvider]:
    mock_engine = MockMarketEngine(seed=settings.mock_seed)
    use_mock = settings.use_mock_providers

    return [
        SteamProvider(use_mock=use_mock, mock_engine=mock_engine, rate_limit_seconds=_rate(settings, "steam")),
        BuffMarketProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "buff_market"),
        ),
        DMarketProvider(use_mock=use_mock, mock_engine=mock_engine, rate_limit_seconds=_rate(settings, "dmarket")),
        SkinBaronProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "skinbaron"),
        ),
        Buff163Provider(use_mock=use_mock, mock_engine=mock_engine, rate_limit_seconds=_rate(settings, "buff163")),
        CSGOFloatProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "csgofloat"),
        ),
        SkinsMonkeyProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "skinsmonkey"),
        ),
        SkinportProvider(use_mock=use_mock, mock_engine=mock_engine, rate_limit_seconds=_rate(settings, "skinport")),
        CSMoneyProvider(use_mock=use_mock, mock_engine=mock_engine, rate_limit_seconds=_rate(settings, "csmoney")),
    ]
