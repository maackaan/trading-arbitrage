from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class SkinTable(Base):
    __tablename__ = "skins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    snapshots = relationship("PriceSnapshotTable", back_populates="skin", cascade="all, delete-orphan")


class PriceSnapshotTable(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skin_id: Mapped[int] = mapped_column(ForeignKey("skins.id"), index=True)
    market: Mapped[str] = mapped_column(String(64), index=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    skin = relationship("SkinTable", back_populates="snapshots")


class ListingTable(Base):
    __tablename__ = "listings"
    __table_args__ = (UniqueConstraint("market", "external_id", name="uq_listing_market_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(128))
    market: Mapped[str] = mapped_column(String(64), index=True)
    skin_id: Mapped[int | None] = mapped_column(ForeignKey("skins.id"), nullable=True, index=True)
    skin_name: Mapped[str] = mapped_column(String(255), index=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    listed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")

    is_deal: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    discount_vs_buff_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_vs_rolling_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    extreme_underpricing: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url, future=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
