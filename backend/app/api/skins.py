from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_container, get_session
from app.core.container import AppContainer
from app.domain.models import MetricBundle, Skin, SkinSearchResponse, SkinSummary, WearOption
from app.services.catalog_search import WEAR_ORDER
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


@router.get("/search", response_model=SkinSearchResponse)
async def search_skins(
    q: str = Query(min_length=1, max_length=100),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> SkinSearchResponse:
    skin_repo = SkinRepository(session)
    catalog = container.catalog_search

    if catalog:
        external_items = await catalog.search_items(q, limit=30)
        if external_items:
            names = [item.title for item in external_items]
            best_name = external_items[0].title
            wear_names = await catalog.fetch_wears_for_item(external_items[0].url)
            wear_skin_names = [
                f"{best_name} ({wear})"
                for wear in wear_names
                if wear != "Vanilla"
            ]

            all_names = list(dict.fromkeys([*names, *wear_skin_names]))
            skin_records = await skin_repo.ensure_by_names(all_names)
            by_name = {skin.name: skin for skin in skin_records}

            results = [by_name[name] for name in names if name in by_name][:25]
            best_match = by_name.get(best_name)
            wear_options = [
                WearOption(
                    wear=wear,
                    skin=by_name[wear_skin_name],
                )
                for wear, wear_skin_name in (
                    (wear, f"{best_name} ({wear})")
                    for wear in sorted(wear_names, key=lambda value: WEAR_ORDER.get(value, 99))
                    if wear != "Vanilla"
                )
                if wear_skin_name in by_name
            ]

            corrected_query = None
            if best_match and best_match.name.strip().lower() != q.strip().lower():
                corrected_query = best_match.name

            return SkinSearchResponse(
                query=q,
                corrected_query=corrected_query,
                suggestions=[item.title for item in external_items[:5]],
                best_match=best_match,
                wear_options=wear_options,
                results=results,
            )

    results, suggestions, corrected_query = await skin_repo.search(q)
    return SkinSearchResponse(
        query=q,
        corrected_query=corrected_query,
        suggestions=suggestions,
        best_match=results[0] if results else None,
        wear_options=[],
        results=results,
    )


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
