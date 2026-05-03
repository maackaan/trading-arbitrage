from datetime import datetime, timezone

from app.providers.skinport import SkinportProvider, _build_price_map
from app.providers.mock import MockMarketEngine


class SkinRow:
    def __init__(self, name: str) -> None:
        self.name = name


def test_skinport_min_price_uses_decimal_api_value() -> None:
    rows = _build_price_map(
        [
            {
                "market_hash_name": "AK-47 | Redline (Field-Tested)",
                "currency": "EUR",
                "min_price": 11.33,
                "suggested_price": 13.18,
                "item_page": "https://skinport.com/item/example",
                "market_page": "https://skinport.com/market/example",
                "updated_at": 1568073728,
            }
        ]
    )

    item = rows["AK-47 | Redline (Field-Tested)"]
    assert item.price == 11.33
    assert item.currency == "EUR"
    assert item.item_url == "https://skinport.com/item/example"


def test_skinport_does_not_use_suggested_price_without_live_min_price() -> None:
    rows = _build_price_map(
        [
            {
                "market_hash_name": "AK-47 | Redline (Field-Tested)",
                "currency": "EUR",
                "min_price": None,
                "suggested_price": 13.18,
                "quantity": 0,
            }
        ]
    )

    assert rows == {}


def test_skinport_rows_use_fetch_time_as_snapshot_timestamp() -> None:
    provider = SkinportProvider(
        use_mock=False,
        mock_engine=MockMarketEngine(),
        rate_limit_seconds=0,
    )
    now = datetime.now(timezone.utc)
    rows = provider._rows_from_map(
        [SkinRow("AK-47 | Redline (Field-Tested)")],  # type: ignore[list-item]
        now,
        _build_price_map(
            [
                {
                    "market_hash_name": "AK-47 | Redline (Field-Tested)",
                    "currency": "USD",
                    "min_price": 38.75,
                    "updated_at": 1710000000,
                }
            ]
        ),
        source="skinport_api",
    )

    assert rows[0].timestamp == now
    assert rows[0].metadata["provider_updated_at"] == "2024-03-09T16:00:00+00:00"
