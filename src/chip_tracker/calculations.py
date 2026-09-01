from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


PERCENT_2 = Decimal("0.01")
PERCENT_4 = Decimal("0.0001")


def buy_volume_percent(net_buy_lots: Decimal, volume_lots: Decimal) -> Decimal:
    if volume_lots <= 0:
        raise ValueError("volume_lots must be positive")
    value = net_buy_lots / volume_lots * Decimal(100)
    return value.quantize(PERCENT_2, rounding=ROUND_HALF_UP)


def capital_percent(net_buy_lots: Decimal, issued_units: int) -> Decimal:
    if issued_units <= 0:
        raise ValueError("issued_units must be positive")
    value = net_buy_lots * Decimal(1000) / Decimal(issued_units) * Decimal(100)
    return value.quantize(PERCENT_4, rounding=ROUND_HALF_UP)


def change_percent(close: Decimal, change_amount: Decimal) -> Decimal:
    previous = close - change_amount
    if previous <= 0:
        raise ValueError("previous close must be positive")
    return (change_amount / previous * Decimal(100)).quantize(
        PERCENT_2, rounding=ROUND_HALF_UP
    )


def star_count(unrounded_percent: Decimal) -> int:
    if unrounded_percent < 0:
        raise ValueError("negative buy ratio is invalid for buy ranking")
    if unrounded_percent <= Decimal("5"):
        return 1
    if unrounded_percent <= Decimal("10"):
        return 2
    if unrounded_percent <= Decimal("15"):
        return 3
    if unrounded_percent <= Decimal("20"):
        return 4
    return 5


def weighted_buy_percent(rows: list[tuple[Decimal, Decimal]]) -> Decimal | None:
    total_volume = sum((volume for _, volume in rows), Decimal(0))
    if total_volume <= 0:
        return None
    total_buy = sum((buy for buy, _ in rows), Decimal(0))
    return (total_buy / total_volume * Decimal(100)).quantize(
        PERCENT_2, rounding=ROUND_HALF_UP
    )
