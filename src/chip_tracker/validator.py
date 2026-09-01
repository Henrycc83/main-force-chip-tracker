from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from chip_tracker.models import DailySnapshot, Market


@dataclass(frozen=True, slots=True)
class ValidationResult:
    passed: bool
    errors: tuple[str, ...]
    checked_rows: int

    def to_dict(self) -> dict:
        return {"passed": self.passed, "errors": list(self.errors), "checked_rows": self.checked_rows}


def validate_snapshot(snapshot: DailySnapshot) -> ValidationResult:
    """Independent reference validation; intentionally does not import calculations."""
    errors: list[str] = []
    checked = 0
    for market, rows in ((Market.LISTED, snapshot.listed), (Market.OTC, snapshot.otc)):
        if len(rows) != 15:
            errors.append(f"{market.value}: row count {len(rows)} != 15")
        ranks = [row.rank for row in rows]
        if ranks != list(range(1, 16)):
            errors.append(f"{market.value}: ranks are not exactly 1..15")
        codes = [row.code for row in rows]
        if len(codes) != len(set(codes)):
            errors.append(f"{market.value}: duplicate codes")
        for row in rows:
            checked += 1
            if row.market is not market:
                errors.append(f"{row.code}: market mismatch")
            if row.ranking_date != snapshot.data_date or row.quote_date != snapshot.data_date:
                errors.append(f"{row.code}: stale date")
            if row.volume_lots <= 0:
                errors.append(f"{row.code}: non-positive volume")
                continue
            raw = row.net_buy_lots / row.volume_lots * Decimal(100)
            expected_ratio = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if row.buy_volume_percent != expected_ratio:
                errors.append(f"{row.code}: buy ratio")
            expected_stars = 1 + sum(raw > boundary for boundary in map(Decimal, ("5", "10", "15", "20")))
            if row.stars != expected_stars:
                errors.append(f"{row.code}: stars")
            if row.issued_units is not None:
                expected_cap = (
                    row.net_buy_lots * Decimal(1000) / Decimal(row.issued_units) * Decimal(100)
                ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
                if row.capital_percent != expected_cap:
                    errors.append(f"{row.code}: capital ratio")
            elif row.capital_percent is not None:
                errors.append(f"{row.code}: capital ratio lacks denominator")
    return ValidationResult(not errors, tuple(errors), checked)

