from app.providers.mock import MockMarketEngine


def test_karambit_has_high_price_floor() -> None:
    engine = MockMarketEngine(seed=42)
    price = engine.next_price("buff163", "Karambit | Doppler (Factory New)")
    assert price >= 250


def test_ak47_stays_in_reasonable_range() -> None:
    engine = MockMarketEngine(seed=42)
    values = [engine.next_price("buff163", "AK-47 | Redline (Field-Tested)") for _ in range(20)]
    assert min(values) >= 5
    assert max(values) <= 200
