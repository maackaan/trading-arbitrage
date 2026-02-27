from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_container, get_session
from app.core.container import AppContainer
from app.domain.models import ListingItem
from app.storage.repositories import ListingRepository

router = APIRouter(prefix="/api", tags=["listings"])


@router.get("/listings/new", response_model=list[ListingItem])
async def get_new_listings(
    market: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    since_hours: int = Query(default=6, ge=1, le=168),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> list[ListingItem]:
    repo = ListingRepository(session)
    items = await repo.get_new_listings(
        market=market,
        limit=limit,
        since_hours=since_hours,
    )
    if not container.catalog_search:
        return items
    return [
        item
        if item.image_url
        else ListingItem(
            listing_id=item.listing_id,
            market=item.market,
            skin_id=item.skin_id,
            skin_name=item.skin_name,
            price=item.price,
            currency=item.currency,
            listed_at=item.listed_at,
            detected_at=item.detected_at,
            is_deal=item.is_deal,
            reference_price=item.reference_price,
            image_url=container.catalog_search.image_for_skin_name(item.skin_name),
            price_source=item.price_source,
            extreme_underpricing=item.extreme_underpricing,
        )
        for item in items
    ]
