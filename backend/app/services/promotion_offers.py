"""Server-owned one-off paid promotion tariffs (EUR minor units).

A homepage featured listing costs five times the corresponding TOP tariff.
Historical payment orders are never repriced.
"""

from typing import Literal

PromotionHours = Literal[12, 24, 72]
TOP_PRICES_CENTS: dict[int, int] = {12: 99, 24: 170, 72: 450}
HOMEPAGE_MULTIPLIER = 5


def amount_cents(kind: Literal["listing_top", "homepage_hero"], hours: PromotionHours) -> int:
    top = TOP_PRICES_CENTS[hours]
    return top * (HOMEPAGE_MULTIPLIER if kind == "homepage_hero" else 1)


def offers(kind: Literal["listing_top", "homepage_hero"]) -> list[dict[str, int]]:
    return [{"durationHours": hours, "amountCents": amount_cents(kind, hours)}
            for hours in TOP_PRICES_CENTS]
