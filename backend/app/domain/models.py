from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class Skin(BaseModel):
    id: int
    name: str
    created_at: datetime


class WearOption(BaseModel):
    wear: str
    skin: Skin


class SkinSearchResponse(BaseModel):
    query: str
    corrected_query: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)
    best_match: Optional[Skin] = None
    wear_options: List[WearOption] = Field(default_factory=list)
    results: List[Skin] = Field(default_factory=list)


class SkinVariantsResponse(BaseModel):
    skin: Skin
    base_name: str
    wear_options: List[WearOption] = Field(default_factory=list)


class ProviderPrice(BaseModel):
    market: str
    skin_name: str
    price: float
    currency: str = "USD"
    timestamp: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProviderListing(BaseModel):
    market: str
    external_id: str
    skin_name: str
    price: float
    currency: str = "USD"
    listed_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PricePoint(BaseModel):
    market: str
    price: float
    currency: str
    timestamp: datetime


class MarketSummary(BaseModel):
    market: str
    price: float
    currency: str
    timestamp: datetime
    spread_vs_buff163_pct: Optional[float] = None


class MetricBundle(BaseModel):
    mean_price: float
    rolling_mean_price: float
    spread_vs_buff163_pct: Optional[float] = None


class PredictionResult(BaseModel):
    target_timestamp: datetime
    predicted_price: float
    lower_band: float
    upper_band: float
    model: Literal["v1_weighted_trend_mean_reversion"] = "v1_weighted_trend_mean_reversion"


class SkinSummary(BaseModel):
    skin: Skin
    reference_market: str = "buff163"
    baseline_price: Optional[float] = None
    image_url: Optional[str] = None
    latest_prices: List[MarketSummary]
    metrics_by_market: Dict[str, MetricBundle]
    prediction_7d5: Optional[PredictionResult] = None


class DealItem(BaseModel):
    listing_id: int
    market: str
    skin_id: Optional[int]
    skin_name: str
    price: float
    currency: str
    listed_at: datetime
    detected_at: datetime
    discount_vs_buff_pct: Optional[float] = None
    discount_vs_rolling_pct: Optional[float] = None
    reference_price: Optional[float] = None
    image_url: Optional[str] = None
    price_source: Optional[str] = None
    is_simulated: bool = False
    extreme_underpricing: bool = False


class ListingItem(BaseModel):
    listing_id: int
    market: str
    skin_id: Optional[int]
    skin_name: str
    price: float
    currency: str
    listed_at: datetime
    detected_at: datetime
    is_deal: bool
    reference_price: Optional[float] = None
    image_url: Optional[str] = None
    price_source: Optional[str] = None
    is_simulated: bool = False
    extreme_underpricing: bool


class RealtimeEvent(BaseModel):
    event: Literal["price_update", "deal_alert", "new_listing"]
    payload: Dict[str, Any]
    timestamp: datetime
