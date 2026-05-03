from app.providers.csgofloat import _build_icon_url, _iter_listing_items, _resolve_skin_name
from app.providers.csgofloat import CSGOFloatProvider
from app.providers.mock import MockMarketEngine


def test_resolve_skin_name_prefers_market_hash_name() -> None:
    payload = {
        "item": {
            "market_hash_name": "AK-47 | Redline (Field-Tested)",
            "item_name": "AK-47 | Redline",
            "wear_name": "Factory New",
        }
    }
    assert _resolve_skin_name(payload) == "AK-47 | Redline (Field-Tested)"


def test_resolve_skin_name_builds_from_item_and_wear() -> None:
    payload = {"item": {"item_name": "AWP | Asiimov", "wear_name": "Battle-Scarred"}}
    assert _resolve_skin_name(payload) == "AWP | Asiimov (Battle-Scarred)"


def test_build_icon_url_normalizes_relative_path() -> None:
    assert _build_icon_url("abc123") == "https://community.cloudflare.steamstatic.com/economy/image/abc123"
    assert _build_icon_url("https://example.com/a.png") == "https://example.com/a.png"


def test_iter_listing_items_supports_data_key() -> None:
    payload = {"data": [{"id": "x"}]}
    rows = _iter_listing_items(payload)
    assert len(rows) == 1
    assert rows[0]["id"] == "x"


def test_build_price_lookup_url_uses_market_hash_name_filter() -> None:
    provider = CSGOFloatProvider(
        use_mock=False,
        mock_engine=MockMarketEngine(),
        rate_limit_seconds=0,
    )

    url = provider._build_price_lookup_url("AK-47 | Redline (Field-Tested)")

    assert "sort_by=lowest_price" in url
    assert "limit=1" in url
    assert "type=buy_now" in url
    assert "market_hash_name=AK-47+%7C+Redline+%28Field-Tested%29" in url
