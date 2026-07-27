"""Apply known coupon codes to a scraped price to get an "effective price"."""
from __future__ import annotations

import dataclasses
from typing import Optional

from .scraper import PriceResult


@dataclasses.dataclass
class PricedDeal:
    retailer: str
    url: str
    list_price: float
    effective_price: float
    applied_coupon: Optional[str]
    in_stock: Optional[bool]


def best_coupon_for(retailer: str, price: float, coupons: list[dict]) -> tuple[float, Optional[str]]:
    """Return (discounted_price, code) for whichever applicable coupon saves the most."""
    best_price = price
    best_code = None

    for coupon in coupons:
        applies_to = coupon.get("retailer", "any")
        if applies_to not in ("any", retailer):
            continue

        discount_type = coupon.get("type")
        value = coupon.get("value", 0)

        if discount_type == "percent":
            candidate = price * (1 - value / 100)
        elif discount_type == "flat":
            candidate = price - value
        else:
            continue

        candidate = max(candidate, 0.0)
        if candidate < best_price:
            best_price = candidate
            best_code = coupon.get("code")

    return best_price, best_code


def price_deals(results: list[PriceResult], coupons: list[dict]) -> list[PricedDeal]:
    deals = []
    for result in results:
        if result.price is None:
            continue
        effective_price, code = best_coupon_for(result.retailer, result.price, coupons)
        deals.append(
            PricedDeal(
                retailer=result.retailer,
                url=result.url,
                list_price=result.price,
                effective_price=effective_price,
                applied_coupon=code,
                in_stock=result.in_stock,
            )
        )
    return sorted(deals, key=lambda d: d.effective_price)
