from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.domain.models import DealItem
from app.storage.repositories import ListingRepository

router = APIRouter(prefix="/api", tags=["deals"])


def _parse_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


@router.get("/deals", response_model=list[DealItem])
async def get_deals(
    market: str | None = Query(default=None),
    min_discount: float = Query(default=12.0, ge=0.0),
    since_hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[DealItem]:
    repo = ListingRepository(session)
    rows = await repo.get_deals(
        market=market,
        min_discount_pct=min_discount,
        since_hours=since_hours,
        limit=limit,
    )

    payload: list[DealItem] = []
    for row in rows:
        metadata = _parse_metadata(row.metadata_json)
        payload.append(
            DealItem(
                listing_id=row.id,
                market=row.market,
                skin_id=row.skin_id,
                skin_name=row.skin_name,
                price=row.price,
                currency=row.currency,
                listed_at=row.listed_at,
                detected_at=row.detected_at,
                discount_vs_buff_pct=row.discount_vs_buff_pct,
                discount_vs_rolling_pct=row.discount_vs_rolling_pct,
                reference_price=metadata.get("reference_market_price"),
                image_url=metadata.get("image_url"),
                price_source=metadata.get("price_source"),
                extreme_underpricing=row.extreme_underpricing,
            )
        )
    return payload
