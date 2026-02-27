from app.providers.common import StubOrMockProvider
from app.providers.mock import MockMarketEngine


class CSMoneyProvider(StubOrMockProvider):
    supports_listings = True

    def __init__(self, *, use_mock: bool, mock_engine: MockMarketEngine, rate_limit_seconds: float) -> None:
        super().__init__(
            market_name="csmoney",
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=rate_limit_seconds,
        )
