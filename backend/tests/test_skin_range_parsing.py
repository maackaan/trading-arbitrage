from datetime import timedelta

from app.api.skins import _parse_range


def test_parse_range_defaults_when_missing() -> None:
    assert _parse_range(None) == timedelta(hours=72)


def test_parse_range_supports_suffixes() -> None:
    assert _parse_range('7d') == timedelta(days=7)
    assert _parse_range('30m') == timedelta(minutes=30)
    assert _parse_range('12h') == timedelta(hours=12)


def test_parse_range_fallback_on_invalid_input() -> None:
    assert _parse_range('not-a-range') == timedelta(hours=72)
