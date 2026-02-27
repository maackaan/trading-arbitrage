from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.domain.models import ListingItem
from app.storage.repositories import ListingRepository

router = APIRouter(prefix="/api", tags=["listings"])


@router.get("/listings/new", response_model=list[ListingItem])
async def get_new_listings(
    market: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    since_hours: int = Query(default=6, ge=1, le=168),
    include_simulated: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> list[ListingItem]:
    repo = ListingRepository(session)
    return await repo.get_new_listings(
        market=market,
        limit=limit,
        since_hours=since_hours,
        include_simulated=include_simulated,
    )
