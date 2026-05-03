from app.providers.steam import _parse_histogram_price, _parse_steam_price, _parse_volume_from_summary
from app.providers.steam import SteamProvider
from app.providers.mock import MockMarketEngine


def test_parse_steam_usd_price() -> None:
    assert _parse_steam_price("$38.75") == 38.75


def test_parse_steam_price_with_group_separator() -> None:
    assert _parse_steam_price("$1,238.40") == 1238.4


def test_parse_steam_price_returns_none_for_missing_value() -> None:
    assert _parse_steam_price(None) is None


def test_parse_histogram_price_prefers_lowest_sell_order_cents() -> None:
    assert _parse_histogram_price({"lowest_sell_order": "4548"}) == 45.48


def test_parse_volume_from_summary_extracts_order_count() -> None:
    assert (
        _parse_volume_from_summary(
            '<span class="market_commodity_orders_header_promote">1008</span> for sale'
        )
        == "1008"
    )


def test_steam_provider_uses_configured_currency() -> None:
    provider = SteamProvider(
        use_mock=False,
        mock_engine=MockMarketEngine(),
        rate_limit_seconds=0,
        country="SE",
        currency_code=3,
        currency="EUR",
    )

    assert provider.country == "SE"
    assert provider.currency_code == 3
    assert provider.currency == "EUR"
