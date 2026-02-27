from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_container, get_session
from app.core.container import AppContainer
from app.domain.models import MetricBundle, Skin, SkinSearchResponse, SkinSummary, SkinVariantsResponse, WearOption
from app.services.prediction import predict_price_7d5
from app.services.pricing_metrics import rolling_mean, safe_mean, spread_pct
from app.services.wear import WEAR_ORDER, split_wear_suffix
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


def _with_image(
    skin: Skin,
    container: AppContainer | None,
    override_image_url: str | None = None,
) -> Skin:
    image_url = override_image_url
    if image_url is None and container and container.catalog_search:
        image_url = container.catalog_search.image_for_skin_name(skin.name)
    return Skin(
        id=skin.id,
        name=skin.name,
        created_at=skin.created_at,
        image_url=image_url,
    )


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
            image_by_name = {item.title: item.image_url for item in external_items}

            results = [
                _with_image(
                    by_name[name],
                    container,
                    image_by_name.get(name),
                )
                for name in names
                if name in by_name
            ][:25]
            best_match = (
                _with_image(by_name[best_name], container, image_by_name.get(best_name))
                if best_name in by_name
                else None
            )
            wear_options = [
                WearOption(
                    wear=wear,
                    skin=_with_image(by_name[wear_skin_name], container, image_by_name.get(best_name)),
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
        best_match=_with_image(results[0], container) if results else None,
        wear_options=[],
        results=[_with_image(item, container) for item in results],
    )


@router.get("/{skin_id}/prices")
async def skin_prices(
    skin_id: int,
    range: str | None = Query(default="72h"),
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> dict:
    skin_repo = SkinRepository(session)
    price_repo = PriceRepository(session)

    skin = await skin_repo.get(skin_id)
    if skin is None:
        raise HTTPException(status_code=404, detail="Skin not found")

    since = datetime.now(timezone.utc) - _parse_range(range)
    points = await price_repo.get_history(skin_id, since)

    return {
        "skin": _with_image(Skin(id=skin.id, name=skin.name, created_at=skin.created_at), container),
        "range": range,
        "points": [point.model_dump(mode="json") for point in points],
    }


@router.get("/{skin_id}/summary", response_model=SkinSummary)
async def skin_summary(
    skin_id: int,
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> SkinSummary:
    skin_repo = SkinRepository(session)
    price_repo = PriceRepository(session)

    skin = await skin_repo.get(skin_id)
    if skin is None:
        raise HTTPException(status_code=404, detail="Skin not found")

    latest_prices = await price_repo.get_latest_per_market(skin_id)
    latest_metadata = await price_repo.get_latest_metadata(skin_id)
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
        skin=_with_image(Skin(id=skin.id, name=skin.name, created_at=skin.created_at), container),
        baseline_price=baseline,
        image_url=latest_metadata.get("image_url")
        or (container.catalog_search.image_for_skin_name(skin.name) if container.catalog_search else None),
        latest_prices=latest_prices,
        metrics_by_market=metrics,
        prediction_7d5=prediction,
    )


@router.get("/{skin_id}/variants", response_model=SkinVariantsResponse)
async def skin_variants(
    skin_id: int,
    session: AsyncSession = Depends(get_session),
    container: AppContainer = Depends(get_container),
) -> SkinVariantsResponse:
    skin_repo = SkinRepository(session)
    skin = await skin_repo.get(skin_id)
    if skin is None:
        raise HTTPException(status_code=404, detail="Skin not found")

    base_name, _ = split_wear_suffix(skin.name)
    variants = await skin_repo.get_wear_variants(base_name)

    if not variants and container.catalog_search:
        items = await container.catalog_search.search_items(base_name, limit=10)
        best = next((item for item in items if item.title == base_name), items[0] if items else None)
        if best:
            wears = await container.catalog_search.fetch_wears_for_item(best.url)
            names = [f"{best.title} ({wear})" for wear in wears if wear != "Vanilla"]
            if names:
                await skin_repo.ensure_by_names(names)
                variants = await skin_repo.get_wear_variants(best.title)
                base_name = best.title

    wear_options: list[WearOption] = []
    for variant in variants:
        _, wear = split_wear_suffix(variant.name)
        if wear is None:
            continue
        wear_options.append(WearOption(wear=wear, skin=_with_image(variant, container)))

    wear_options.sort(key=lambda item: WEAR_ORDER.get(item.wear, 99))

    return SkinVariantsResponse(
        skin=_with_image(Skin(id=skin.id, name=skin.name, created_at=skin.created_at), container),
        base_name=base_name,
        wear_options=wear_options,
    )
