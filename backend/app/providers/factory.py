from __future__ import annotations

from app.core.settings import Settings
from app.providers.base import BaseProvider
from app.providers.buff163 import Buff163Provider
from app.providers.buff_market import BuffMarketProvider
from app.providers.csgofloat import CSGOFloatProvider
from app.providers.csmoney import CSMoneyProvider
from app.providers.dmarket import DMarketProvider
from app.providers.common import StubOrMockProvider
from app.providers.mock import MockMarketEngine
from app.providers.skinbaron import SkinBaronProvider
from app.providers.skinport import SkinportProvider
from app.providers.skinsmonkey import SkinsMonkeyProvider
from app.providers.steam import SteamProvider
from app.services.csgoskins_price import CSGOSkinsPriceService


def _rate(settings: Settings, provider_name: str) -> float:
    return settings.provider_rate_limit_map.get(provider_name, 5.0)


def build_providers(settings: Settings) -> list[BaseProvider]:
    mock_engine = MockMarketEngine(seed=settings.mock_seed)
    use_mock = settings.use_mock_providers
    csgoskins_price_service = CSGOSkinsPriceService(
        enabled=settings.csgoskins_price_fallback_enabled,
        search_base_url=settings.search_catalog_url,
        search_api_key=settings.search_catalog_key,
        timeout_seconds=settings.search_catalog_timeout_seconds,
        resolve_ttl_seconds=settings.csgoskins_price_resolve_ttl_seconds,
        snapshot_ttl_seconds=settings.csgoskins_price_ttl_seconds,
    )

    providers = [
        SteamProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "steam"),
            csgoskins_price_service=csgoskins_price_service,
        ),
        BuffMarketProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "buff_market"),
            csgoskins_price_service=csgoskins_price_service,
        ),
        DMarketProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "dmarket"),
            csgoskins_price_service=csgoskins_price_service,
        ),
        SkinBaronProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "skinbaron"),
            csgoskins_price_service=csgoskins_price_service,
        ),
        Buff163Provider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "buff163"),
            csgoskins_price_service=csgoskins_price_service,
        ),
        CSGOFloatProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "csgofloat"),
            csgoskins_price_service=csgoskins_price_service,
            api_key=settings.csgofloat_api_key,
            listings_api_url=settings.csfloat_listings_api_url,
            timeout_seconds=settings.csfloat_api_timeout_seconds,
            listings_sort=settings.csfloat_listings_sort,
            listings_limit=settings.csfloat_listings_limit,
        ),
        SkinsMonkeyProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "skinsmonkey"),
            csgoskins_price_service=csgoskins_price_service,
        ),
        SkinportProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "skinport"),
            csgoskins_price_service=csgoskins_price_service,
        ),
        CSMoneyProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "csmoney"),
            csgoskins_price_service=csgoskins_price_service,
            api_key=settings.csmoney_api_key,
            listings_api_url=settings.csmoney_listings_api_url,
            timeout_seconds=settings.csmoney_api_timeout_seconds,
            listings_sort=settings.csmoney_listings_sort,
            listings_order=settings.csmoney_listings_order,
            listings_limit=settings.csmoney_listings_limit,
        ),
    ]

    for provider in providers:
        if isinstance(provider, StubOrMockProvider):
            provider.mock_listings_enabled = settings.mock_listings_enabled

    return providers
