from datetime import datetime, timedelta, timezone

from app.domain.models import MarketSummary, ProviderPrice
from app.services.price_service import PriceService, canonical_source, is_fresh_live_observation, validate_provider_price


def test_canonical_source_maps_csgofloat_to_csfloat() -> None:
    assert canonical_source("csgofloat") == "csfloat"


def test_invalid_provider_price_is_rejected() -> None:
    row = ProviderPrice(
        market="skinport",
        skin_name="AK-47 | Redline (Field-Tested)",
        price=0,
        currency="USD",
        timestamp=datetime.now(timezone.utc),
    )

    assert validate_provider_price(row) is None


def test_price_comparison_includes_unavailable_sources() -> None:
    observed_at = datetime.now(timezone.utc)
    comparison = PriceService().build_comparison(
        item_name="AK-47 | Redline (Field-Tested)",
        latest_prices=[
            MarketSummary(
                market="skinport",
                price=12.5,
                currency="USD",
                timestamp=observed_at,
                url="https://skinport.com/item/example",
            )
        ],
    )

    assert comparison.cheapest_source is not None
    assert comparison.cheapest_source.source == "skinport"
    by_source = {item.source: item for item in comparison.sources}
    assert by_source["csfloat"].available is False
    assert by_source["csfloat"].error == "No live price available"
    assert by_source["steam"].available is False
    assert by_source["steam"].error == "No live price available"


def test_old_observations_are_not_fresh_live_prices() -> None:
    old_timestamp = datetime.now(timezone.utc) - timedelta(days=2)

    assert is_fresh_live_observation(old_timestamp) is False
