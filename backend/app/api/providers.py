from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.container import AppContainer

router = APIRouter(prefix="/api", tags=["providers"])


@router.get("/providers/status")
async def provider_status(container: AppContainer = Depends(get_container)) -> dict:
    items: list[dict] = []
    for provider in container.providers:
        items.append(
            {
                "name": provider.name,
                "use_mock": provider.use_mock,
                "supports_listings": provider.supports_listings,
                "rate_limit_seconds": provider.rate_limit_seconds,
                "last_price_error": provider.last_price_error,
                "last_listing_error": provider.last_listing_error,
            }
        )
    return {"providers": items}
