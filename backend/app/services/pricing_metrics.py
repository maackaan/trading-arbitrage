from __future__ import annotations

from statistics import mean


def safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(mean(values))


def rolling_mean(values: list[float], window: int = 10) -> float:
    if not values:
        return 0.0
    window_values = values[-window:]
    return float(mean(window_values))


def spread_pct(price: float, baseline: float | None) -> float | None:
    if baseline is None or baseline <= 0:
        return None
    return ((price - baseline) / baseline) * 100.0
