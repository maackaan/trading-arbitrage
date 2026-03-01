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


def test_prediction_none_when_history_is_too_short() -> None:
    now = datetime(2026, 2, 27, tzinfo=timezone.utc)
    points = [(now - timedelta(days=4 - i), 100 + i) for i in range(5)]
    assert predict_price_7d5(buff_points=points, other_market_latest=[101.0], now=now) is None


def test_prediction_stays_reasonable_for_short_span_history() -> None:
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    # Many points within a short window should not create a huge trend spike.
    points = [(now - timedelta(minutes=50 - i), 20.0 + (i * 0.03)) for i in range(51)]

    prediction = predict_price_7d5(
        buff_points=points,
        other_market_latest=[19.8, 20.2, 20.5],
        now=now,
    )

    assert prediction is not None
    assert 10.0 <= prediction.predicted_price <= 40.0
