from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DealEvaluation:
    is_deal: bool
    discount_vs_buff_pct: float | None
    discount_vs_rolling_pct: float | None
    extreme_underpricing: bool


class DealDetectionService:
    def __init__(
        self,
        min_discount_vs_buff_pct: float = 10.0,
        min_discount_vs_rolling_pct: float = 8.0,
        extreme_discount_pct: float = 25.0,
    ) -> None:
        self.min_discount_vs_buff_pct = min_discount_vs_buff_pct
        self.min_discount_vs_rolling_pct = min_discount_vs_rolling_pct
        self.extreme_discount_pct = extreme_discount_pct

    def evaluate(
        self,
        *,
        listing_price: float,
        buff_baseline: float | None,
        rolling_mean_price: float | None,
    ) -> DealEvaluation:
        discount_vs_buff = self._discount_pct(listing_price, buff_baseline)
        discount_vs_rolling = self._discount_pct(listing_price, rolling_mean_price)

        is_deal = (
            (discount_vs_buff is not None and discount_vs_buff >= self.min_discount_vs_buff_pct)
            or (
                discount_vs_rolling is not None
                and discount_vs_rolling >= self.min_discount_vs_rolling_pct
            )
        )

        extreme = (
            (discount_vs_buff is not None and discount_vs_buff >= self.extreme_discount_pct)
            or (
                discount_vs_rolling is not None
                and discount_vs_rolling >= self.extreme_discount_pct
            )
        )

        return DealEvaluation(
            is_deal=is_deal,
            discount_vs_buff_pct=discount_vs_buff,
            discount_vs_rolling_pct=discount_vs_rolling,
            extreme_underpricing=extreme,
        )

    @staticmethod
    def _discount_pct(price: float, baseline: float | None) -> float | None:
        if baseline is None or baseline <= 0:
            return None
        return ((baseline - price) / baseline) * 100.0
