from app.services.pricing_metrics import rolling_mean, safe_mean, spread_pct


def test_safe_mean_handles_empty() -> None:
    assert safe_mean([]) == 0.0


def test_rolling_mean_uses_window() -> None:
    assert rolling_mean([1, 2, 3, 4, 5], window=2) == 4.5


def test_spread_pct() -> None:
    assert round(spread_pct(110, 100) or 0, 2) == 10.0
    assert spread_pct(10, None) is None
