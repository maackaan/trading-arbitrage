from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.container import AppContainer
from app.providers.csgofloat import CSGOFloatProvider
from app.providers.csmoney import CSMoneyProvider

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health(container: AppContainer = Depends(get_container)) -> dict:
    csfloat_provider = next((p for p in container.providers if isinstance(p, CSGOFloatProvider)), None)
    csmoney_provider = next((p for p in container.providers if isinstance(p, CSMoneyProvider)), None)
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "use_mock_providers": container.settings.use_mock_providers,
        "mock_listings_enabled": container.settings.mock_listings_enabled,
        "csfloat_listings_api_configured": bool(
            csfloat_provider and csfloat_provider.listings_api_configured
        ),
        "csmoney_listings_api_configured": bool(
            csmoney_provider and csmoney_provider.listings_api_configured
        ),
    }
