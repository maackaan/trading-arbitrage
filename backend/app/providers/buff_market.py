from app.providers.common import StubOrMockProvider
from app.providers.mock import MockMarketEngine
from app.services.csgoskins_price import CSGOSkinsPriceService


class BuffMarketProvider(StubOrMockProvider):
    def __init__(
        self,
        *,
        use_mock: bool,
        mock_engine: MockMarketEngine,
        rate_limit_seconds: float,
        csgoskins_price_service: CSGOSkinsPriceService | None = None,
    ) -> None:
        super().__init__(
            market_name="buff_market",
            use_mock=use_mock,
            mock_engine=mock_engine,
            rate_limit_seconds=rate_limit_seconds,
            csgoskins_price_service=csgoskins_price_service,
        )
