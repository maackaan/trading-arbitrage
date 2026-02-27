from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence

from sqlalchemy import Select, and_, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import ListingItem, MarketSummary, PricePoint, Skin
from app.services.search_matching import score_skin_name, suggest_skin_names
from app.services.wear import WEAR_ORDER, split_wear_suffix
from app.storage.db import ListingTable, PriceSnapshotTable, SkinTable


def _score_row(query: str, skin_name: str) -> float:
    return score_skin_name(query, skin_name)


def _parse_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _is_simulated(metadata: dict) -> bool:
    if bool(metadata.get("is_simulated")):
        return True
    mode = str(metadata.get("mode") or "").strip().lower()
    if mode in {"mock", "csgoskins_fallback"}:
        return True
    return False


class SkinRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def seed_skins(self, names: Sequence[str]) -> None:
        existing = {
            name
            for name in (
                await self.session.scalars(select(SkinTable.name).where(SkinTable.name.in_(names)))
            ).all()
        }
        for name in names:
            if name not in existing:
                self.session.add(SkinTable(name=name))
        await self.session.commit()

    async def list_all(self) -> list[SkinTable]:
        result = await self.session.scalars(select(SkinTable).order_by(SkinTable.name.asc()))
        return list(result.all())

    async def get_by_name(self, name: str) -> SkinTable | None:
        stmt = select(SkinTable).where(SkinTable.name == name)
        return (await self.session.scalars(stmt)).first()

    async def get_by_names(self, names: Sequence[str]) -> list[Skin]:
        if not names:
            return []
        stmt = select(SkinTable).where(SkinTable.name.in_(names)).order_by(SkinTable.name.asc())
        rows = (await self.session.scalars(stmt)).all()
        return [Skin(id=row.id, name=row.name, created_at=row.created_at) for row in rows]

    async def ensure_by_names(self, names: Sequence[str]) -> list[Skin]:
        unique_names = [name.strip() for name in names if name.strip()]
        if not unique_names:
            return []
        await self.seed_skins(unique_names)
        return await self.get_by_names(unique_names)

    async def get_wear_variants(self, base_name: str) -> list[Skin]:
        stmt = (
            select(SkinTable)
            .where(SkinTable.name.ilike(f"{base_name} (%)"))
            .order_by(SkinTable.name.asc())
        )
        rows = (await self.session.scalars(stmt)).all()
        parsed: list[tuple[int, Skin]] = []
        for row in rows:
            _, wear = split_wear_suffix(row.name)
            if wear is None:
                continue
            parsed.append(
                (
                    WEAR_ORDER.get(wear, 99),
                    Skin(id=row.id, name=row.name, created_at=row.created_at),
                )
            )
        parsed.sort(key=lambda pair: pair[0])
        return [skin for _, skin in parsed]

    async def search(
        self, query: str, limit: int = 25
    ) -> tuple[list[Skin], list[str], str | None]:
        rows = (await self.session.scalars(select(SkinTable).order_by(SkinTable.name.asc()))).all()
        scored = sorted(
            ((score, row) for row in rows if (score := _score_row(query, row.name)) > 0),
            key=lambda pair: pair[0],
            reverse=True,
        )
        results = [
            Skin(id=row.id, name=row.name, created_at=row.created_at)
            for score, row in scored[:limit]
            if score >= 45.0
        ]

        suggestions = suggest_skin_names(query, (row.name for row in rows), limit=5)
        corrected_query = None
        if suggestions and query.strip().lower() != suggestions[0].strip().lower():
            corrected_query = suggestions[0]

        return results, suggestions, corrected_query

    async def get(self, skin_id: int) -> SkinTable | None:
        return await self.session.get(SkinTable, skin_id)


class PriceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_snapshot(
        self,
        *,
        skin_id: int,
        market: str,
        price: float,
        currency: str,
        observed_at: datetime,
        metadata: dict,
    ) -> None:
        self.session.add(
            PriceSnapshotTable(
                skin_id=skin_id,
                market=market,
                price=price,
                currency=currency,
                observed_at=observed_at,
                metadata_json=json.dumps(metadata),
            )
        )

    async def add_snapshots(self, snapshots: Iterable[dict]) -> None:
        for snapshot in snapshots:
            await self.add_snapshot(**snapshot)
        await self.session.commit()

    async def get_history(self, skin_id: int, since: datetime) -> list[PricePoint]:
        stmt = (
            select(PriceSnapshotTable)
            .where(
                and_(
                    PriceSnapshotTable.skin_id == skin_id,
                    PriceSnapshotTable.observed_at >= since,
                )
            )
            .order_by(PriceSnapshotTable.observed_at.asc())
        )
        rows = (await self.session.scalars(stmt)).all()
        return [
            PricePoint(
                market=row.market,
                price=row.price,
                currency=row.currency,
                timestamp=row.observed_at,
            )
            for row in rows
        ]

    async def get_latest_per_market(self, skin_id: int) -> list[MarketSummary]:
        latest_subquery = (
            select(
                PriceSnapshotTable.market.label("market"),
                func.max(PriceSnapshotTable.observed_at).label("max_observed"),
            )
            .where(PriceSnapshotTable.skin_id == skin_id)
            .group_by(PriceSnapshotTable.market)
            .subquery()
        )

        stmt = (
            select(PriceSnapshotTable)
            .join(
                latest_subquery,
                and_(
                    PriceSnapshotTable.market == latest_subquery.c.market,
                    PriceSnapshotTable.observed_at == latest_subquery.c.max_observed,
                ),
            )
            .where(PriceSnapshotTable.skin_id == skin_id)
            .order_by(PriceSnapshotTable.market.asc())
        )
        rows = (await self.session.scalars(stmt)).all()
        return [
            MarketSummary(
                market=row.market,
                price=row.price,
                currency=row.currency,
                timestamp=row.observed_at,
            )
            for row in rows
        ]

    async def get_market_prices(
        self,
        *,
        skin_id: int,
        market: str,
        since: datetime,
        limit: int = 500,
    ) -> list[float]:
        stmt = (
            select(PriceSnapshotTable.price)
            .where(
                and_(
                    PriceSnapshotTable.skin_id == skin_id,
                    PriceSnapshotTable.market == market,
                    PriceSnapshotTable.observed_at >= since,
                )
            )
            .order_by(PriceSnapshotTable.observed_at.asc())
            .limit(limit)
        )
        values = await self.session.scalars(stmt)
        return [float(v) for v in values.all()]

    async def get_market_points(
        self,
        *,
        skin_id: int,
        market: str,
        since: datetime,
        limit: int = 500,
    ) -> list[tuple[datetime, float]]:
        stmt = (
            select(PriceSnapshotTable.observed_at, PriceSnapshotTable.price)
            .where(
                and_(
                    PriceSnapshotTable.skin_id == skin_id,
                    PriceSnapshotTable.market == market,
                    PriceSnapshotTable.observed_at >= since,
                )
            )
            .order_by(PriceSnapshotTable.observed_at.asc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [(ts, float(price)) for ts, price in rows]

    async def get_latest_metadata(self, skin_id: int) -> dict:
        stmt = (
            select(PriceSnapshotTable.metadata_json)
            .where(PriceSnapshotTable.skin_id == skin_id)
            .order_by(desc(PriceSnapshotTable.observed_at))
            .limit(1)
        )
        raw = (await self.session.scalars(stmt)).first()
        return _parse_metadata(raw)


class ListingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_listing(
        self,
        *,
        external_id: str,
        market: str,
        skin_id: int | None,
        skin_name: str,
        price: float,
        currency: str,
        listed_at: datetime,
        detected_at: datetime,
        metadata: dict,
        is_deal: bool,
        discount_vs_buff_pct: float | None,
        discount_vs_rolling_pct: float | None,
        extreme_underpricing: bool,
    ) -> ListingTable:
        stmt = select(ListingTable).where(
            and_(ListingTable.market == market, ListingTable.external_id == external_id)
        )
        existing = (await self.session.scalars(stmt)).first()

        if existing is None:
            existing = ListingTable(
                external_id=external_id,
                market=market,
                skin_id=skin_id,
                skin_name=skin_name,
                price=price,
                currency=currency,
                listed_at=listed_at,
                detected_at=detected_at,
                metadata_json=json.dumps(metadata),
                is_deal=is_deal,
                discount_vs_buff_pct=discount_vs_buff_pct,
                discount_vs_rolling_pct=discount_vs_rolling_pct,
                extreme_underpricing=extreme_underpricing,
            )
            self.session.add(existing)
        else:
            existing.skin_id = skin_id
            existing.skin_name = skin_name
            existing.price = price
            existing.currency = currency
            existing.listed_at = listed_at
            existing.detected_at = detected_at
            existing.metadata_json = json.dumps(metadata)
            existing.is_deal = is_deal
            existing.discount_vs_buff_pct = discount_vs_buff_pct
            existing.discount_vs_rolling_pct = discount_vs_rolling_pct
            existing.extreme_underpricing = extreme_underpricing

        await self.session.commit()
        await self.session.refresh(existing)
        return existing

    async def get_new_listings(
        self,
        *,
        market: str | None = None,
        limit: int = 100,
        since_hours: int = 24,
    ) -> list[ListingItem]:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        conditions = [ListingTable.listed_at >= since]
        if market:
            conditions.append(ListingTable.market == market)

        stmt = (
            select(ListingTable)
            .where(and_(*conditions))
            .order_by(desc(ListingTable.listed_at), desc(ListingTable.detected_at))
            .limit(max(limit * 6, limit))
        )

        rows = list((await self.session.scalars(stmt)).all())
        items: list[ListingItem] = []
        for row in rows:
            metadata = _parse_metadata(row.metadata_json)
            if _is_simulated(metadata):
                continue
            items.append(
                ListingItem(
                    listing_id=row.id,
                    market=row.market,
                    skin_id=row.skin_id,
                    skin_name=row.skin_name,
                    price=row.price,
                    currency=row.currency,
                    listed_at=row.listed_at,
                    detected_at=row.detected_at,
                    is_deal=row.is_deal,
                    reference_price=metadata.get("reference_market_price"),
                    image_url=metadata.get("image_url"),
                    price_source=metadata.get("price_source"),
                    extreme_underpricing=row.extreme_underpricing,
                )
            )
            if len(items) >= limit:
                break
        return items

    async def get_deals(
        self,
        *,
        market: str | None = None,
        min_discount_pct: float = 0.0,
        since_hours: int = 24,
        limit: int = 100,
    ) -> list[ListingTable]:
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        conditions = [ListingTable.is_deal.is_(True), ListingTable.listed_at >= since]
        if market:
            conditions.append(ListingTable.market == market)

        if min_discount_pct > 0:
            conditions.append(
                func.coalesce(ListingTable.discount_vs_buff_pct, ListingTable.discount_vs_rolling_pct, 0.0)
                >= min_discount_pct
            )

        stmt = (
            select(ListingTable)
            .where(and_(*conditions))
            .order_by(
                desc(
                    func.coalesce(
                        ListingTable.discount_vs_buff_pct,
                        ListingTable.discount_vs_rolling_pct,
                        0.0,
                    )
                ),
                desc(ListingTable.listed_at),
            )
            .limit(max(limit * 6, limit))
        )
        rows = list((await self.session.scalars(stmt)).all())
        filtered: list[ListingTable] = []
        for row in rows:
            metadata = _parse_metadata(row.metadata_json)
            if _is_simulated(metadata):
                continue
            filtered.append(row)
            if len(filtered) >= limit:
                break
        return filtered

    async def list_available_markets(self) -> list[str]:
        stmt = select(ListingTable.market).distinct().order_by(ListingTable.market.asc())
        values = await self.session.scalars(stmt)
        return [value for value in values.all() if value]


async def clear_all(session: AsyncSession) -> None:
    for table in [ListingTable, PriceSnapshotTable, SkinTable]:
        await session.execute(delete(table))
    await session.commit()
