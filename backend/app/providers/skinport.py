from app.providers.common import StubOrMockProvider
from app.providers.mock import MockMarketEngine


class SkinportProvider(StubOrMockProvider):
    def __init__(self, *, use_mock: bool, mock_engine: MockMarketEngine, rate_limit_seconds: float) -> None:
        super().__init__(
            market_name="skinport",
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=rate_limit_seconds,
        )
