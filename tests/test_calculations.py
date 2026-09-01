from decimal import Decimal

import pytest

from chip_tracker.calculations import (
    buy_volume_percent, capital_percent, change_percent, star_count,
)


@pytest.mark.parametrize(("value", "expected"), [
    ("0", 1), ("5.0000", 1), ("5.0001", 2), ("10", 2),
    ("10.0001", 3), ("15", 3), ("15.0001", 4), ("20", 4),
    ("20.0001", 5),
])
def test_star_boundaries(value, expected):
    assert star_count(Decimal(value)) == expected


def test_percent_formulas_use_required_precision():
    assert buy_volume_percent(Decimal("1"), Decimal("6")) == Decimal("16.67")
    assert capital_percent(Decimal("123"), 1_000_000) == Decimal("12.3000")
    assert change_percent(Decimal("110"), Decimal("10")) == Decimal("10.00")


@pytest.mark.parametrize("volume", [Decimal("0"), Decimal("-1")])
def test_zero_or_negative_volume_is_rejected(volume):
    with pytest.raises(ValueError):
        buy_volume_percent(Decimal("1"), volume)

