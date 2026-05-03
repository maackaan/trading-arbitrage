from __future__ import annotations

from app.core.settings import Settings
from app.providers.base import BaseProvider
from app.providers.buff163 import Buff163Provider
from app.providers.buff_market import BuffMarketProvider
from app.providers.csfloat_provider import CSFloatProvider
from app.providers.csmoney import CSMoneyProvider
from app.providers.dmarket import DMarketProvider
from app.providers.common import StubOrMockProvider
from app.providers.mock import MockMarketEngine
from app.providers.skinbaron import SkinBaronProvider
from app.providers.skinport_provider import SkinportProvider
from app.providers.skinsmonkey import SkinsMonkeyProvider
from app.providers.steam import SteamProvider
from app.services.csgoskins_price import CSGOSkinsPriceService


SAFE_REAL_RATE_LIMIT_SECONDS = {
    "steam": 60.0,
    "buff_market": 60.0,
    "dmarket": 60.0,
    "skinbaron": 60.0,
    "buff163": 60.0,
    "csgofloat": 60.0,
    "skinsmonkey": 60.0,
    "skinport": 300.0,
    "csmoney": 60.0,
}


def _rate(settings: Settings, provider_name: str, *, use_mock: bool) -> float:
    configured = settings.provider_rate_limit_map.get(provider_name, 5.0)
    if use_mock:
        return configured
    safe_floor = SAFE_REAL_RATE_LIMIT_SECONDS.get(provider_name, 60.0)
    return max(configured, safe_floor)


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
            rate_limit_seconds=_rate(settings, "steam", use_mock=use_mock),
            csgoskins_price_service=csgoskins_price_service,
            country=settings.steam_country,
            currency_code=settings.steam_currency_code,
            currency=settings.steam_currency,
        ),
        BuffMarketProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "buff_market", use_mock=use_mock),
            csgoskins_price_service=csgoskins_price_service,
        ),
        DMarketProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "dmarket", use_mock=use_mock),
            csgoskins_price_service=csgoskins_price_service,
        ),
        SkinBaronProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "skinbaron", use_mock=use_mock),
            csgoskins_price_service=csgoskins_price_service,
        ),
        Buff163Provider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "buff163", use_mock=use_mock),
            csgoskins_price_service=csgoskins_price_service,
        ),
        CSFloatProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "csgofloat", use_mock=use_mock),
            csgoskins_price_service=csgoskins_price_service,
            api_key=settings.csgofloat_api_key,
            session_cookie=settings.csfloat_session_cookie,
            listings_api_url=settings.csfloat_listings_api_url,
            timeout_seconds=settings.csfloat_api_timeout_seconds,
            listings_sort=settings.csfloat_listings_sort,
            listings_limit=settings.csfloat_listings_limit,
        ),
        SkinsMonkeyProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "skinsmonkey", use_mock=use_mock),
            csgoskins_price_service=csgoskins_price_service,
        ),
        SkinportProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "skinport", use_mock=use_mock),
            csgoskins_price_service=csgoskins_price_service,
            items_api_url=settings.skinport_items_api_url,
            timeout_seconds=settings.skinport_api_timeout_seconds,
            app_id=settings.skinport_app_id,
            currency=settings.skinport_currency,
        ),
        CSMoneyProvider(
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=_rate(settings, "csmoney", use_mock=use_mock),
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
