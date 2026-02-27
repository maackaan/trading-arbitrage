from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.domain.models import MetricBundle, Skin, SkinSummary
from app.services.prediction import predict_price_7d5
from app.services.pricing_metrics import rolling_mean, safe_mean, spread_pct
from app.storage.repositories import PriceRepository, SkinRepository

router = APIRouter(prefix="/api/skins", tags=["skins"])


def _parse_range(value: str | None, default_hours: int = 72) -> timedelta:
    if not value:
        return timedelta(hours=default_hours)

    value = value.strip().lower()
    try:
        if value.endswith("m"):
            return timedelta(minutes=int(value[:-1]))
        if value.endswith("h"):
            return timedelta(hours=int(value[:-1]))
        if value.endswith("d"):
            return timedelta(days=int(value[:-1]))
        return timedelta(hours=int(value))
    except ValueError:
        return timedelta(hours=default_hours)


@router.get("/search", response_model=list[Skin])
async def search_skins(
    q: str = Query(min_length=1, max_length=100),
    session: AsyncSession = Depends(get_session),
) -> list[Skin]:
    skin_repo = SkinRepository(session)
    return await skin_repo.search(q)


@router.get("/{skin_id}/prices")
async def skin_prices(
    skin_id: int,
    range: str | None = Query(default="72h"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    skin_repo = SkinRepository(session)
    price_repo = PriceRepository(session)

    skin = await skin_repo.get(skin_id)
    if skin is None:
        raise HTTPException(status_code=404, detail="Skin not found")

    since = datetime.now(timezone.utc) - _parse_range(range)
    points = await price_repo.get_history(skin_id, since)

    return {
        "skin": Skin(id=skin.id, name=skin.name, created_at=skin.created_at),
        "range": range,
        "points": [point.model_dump(mode="json") for point in points],
    }


@router.get("/{skin_id}/summary", response_model=SkinSummary)
async def skin_summary(
    skin_id: int,
    session: AsyncSession = Depends(get_session),
) -> SkinSummary:
    skin_repo = SkinRepository(session)
    price_repo = PriceRepository(session)

    skin = await skin_repo.get(skin_id)
    if skin is None:
        raise HTTPException(status_code=404, detail="Skin not found")

    latest_prices = await price_repo.get_latest_per_market(skin_id)
    baseline = next((item.price for item in latest_prices if item.market == "buff163"), None)

    metrics: dict[str, MetricBundle] = {}
    since = datetime.now(timezone.utc) - timedelta(days=14)

    for item in latest_prices:
        market_prices = await price_repo.get_market_prices(
            skin_id=skin_id,
            market=item.market,
            since=since,
            limit=400,
        )
        metrics[item.market] = MetricBundle(
            mean_price=round(safe_mean(market_prices), 4),
            rolling_mean_price=round(rolling_mean(market_prices, window=10), 4),
            spread_vs_buff163_pct=spread_pct(item.price, baseline),
        )

    for item in latest_prices:
        item.spread_vs_buff163_pct = spread_pct(item.price, baseline)

    buff_points = await price_repo.get_market_points(
        skin_id=skin_id,
        market="buff163",
        since=since,
        limit=500,
    )
    other_latest = [item.price for item in latest_prices if item.market != "buff163"]
    prediction = predict_price_7d5(buff_points=buff_points, other_market_latest=other_latest)

    return SkinSummary(
        skin=Skin(id=skin.id, name=skin.name, created_at=skin.created_at),
        baseline_price=baseline,
        latest_prices=latest_prices,
        metrics_by_market=metrics,
        prediction_7d5=prediction,
    )
