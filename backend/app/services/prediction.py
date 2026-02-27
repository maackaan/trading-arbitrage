from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

from app.domain.models import PredictionResult

TRADE_LOCK_DAYS = 7.5


def _weighted_moving_average(values: list[float]) -> float:
    if not values:
        return 0.0
    weights = [idx + 1 for idx in range(len(values))]
    numerator = sum(v * w for v, w in zip(values, weights))
    denominator = sum(weights)
    return numerator / denominator


def _linear_trend(points: list[tuple[datetime, float]]) -> float:
    if len(points) < 2:
        return 0.0

    start_ts = points[0][0].timestamp()
    xs = [(p[0].timestamp() - start_ts) / 86400.0 for p in points]
    ys = [p[1] for p in points]

    span_days = max(xs) - min(xs)
    if span_days < 0.75:
        return 0.0

    x_mean = mean(xs)
    y_mean = mean(ys)
    denom = sum((x - x_mean) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    slope_per_day = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denom
    return slope_per_day


def predict_price_7d5(
    *,
    buff_points: list[tuple[datetime, float]],
    other_market_latest: list[float],
    now: datetime | None = None,
) -> PredictionResult | None:
    if not buff_points:
        return None

    current_time = now or datetime.now(timezone.utc)
    ordered = sorted(buff_points, key=lambda point: point[0])
    buff_values = [max(price, 0.01) for _, price in ordered]
    buff_last = buff_values[-1]

    wma = _weighted_moving_average(buff_values[-12:])
    trend_slope = _linear_trend(ordered[-48:])
    max_daily_move = max(buff_last * 0.08, 0.8)
    trend_slope = max(min(trend_slope, max_daily_move), -max_daily_move)
    trend_projection = buff_last + trend_slope * TRADE_LOCK_DAYS

    external_values = [value for value in other_market_latest if value > 0]
    external_anchor_raw = mean(external_values) if external_values else buff_last
    external_anchor = min(max(external_anchor_raw, buff_last * 0.6), buff_last * 1.4)
    mean_reversion_target = 0.7 * trend_projection + 0.3 * external_anchor

    predicted = (0.75 * wma) + (0.25 * mean_reversion_target)
    recent = buff_values[-30:]
    recent_min = min(recent)
    recent_max = max(recent)
    lower_guard = max(recent_min * 0.65, 0.5)
    upper_guard = max(recent_max * 1.6, lower_guard * 1.15)
    predicted = min(max(predicted, lower_guard), upper_guard)

    residuals = [value - wma for value in buff_values[-20:]]
    residual_std = pstdev(residuals) if len(residuals) >= 2 else max(buff_last * 0.02, 0.03)
    horizon_scale = math.sqrt(TRADE_LOCK_DAYS / 2.0)
    band = max(residual_std * horizon_scale, predicted * 0.03)
    band = min(band, predicted * 0.35)

    return PredictionResult(
        target_timestamp=current_time + timedelta(days=TRADE_LOCK_DAYS),
        predicted_price=round(predicted, 4),
        lower_band=round(max(predicted - band, 0.01), 4),
        upper_band=round(predicted + band, 4),
    )
