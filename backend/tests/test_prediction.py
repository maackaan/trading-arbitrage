from datetime import datetime, timedelta, timezone

from app.services.prediction import predict_price_7d5


def test_prediction_returns_result() -> None:
    now = datetime(2026, 2, 27, tzinfo=timezone.utc)
    points = [(now - timedelta(days=5 - i), 100 + i) for i in range(6)]

    prediction = predict_price_7d5(
        buff_points=points,
        other_market_latest=[103.0, 101.5, 102.5],
        now=now,
    )

    assert prediction is not None
    assert prediction.predicted_price > 0
    assert prediction.lower_band <= prediction.predicted_price <= prediction.upper_band
    assert prediction.target_timestamp > now


def test_prediction_none_without_buff_history() -> None:
    assert predict_price_7d5(buff_points=[], other_market_latest=[]) is None
