from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from chip_tracker.models import DailySnapshot, SecurityType
from chip_tracker.storage import read_json


def load_snapshots(observation_root: Path) -> list[DailySnapshot]:
    snapshots = []
    for path in sorted(observation_root.glob("*/*/*.json")):
        try:
            snapshots.append(DailySnapshot.from_dict(read_json(path)))
        except (KeyError, ValueError, TypeError):
            continue
    unique = {item.data_date: item for item in snapshots}
    return [unique[key] for key in sorted(unique)]


def rolling_20d(snapshots: list[DailySnapshot]) -> list[dict]:
    window = snapshots[-20:]
    appearances: dict[tuple[str, str], list[tuple[date, object]]] = defaultdict(list)
    trading_dates = [snapshot.data_date for snapshot in window]
    for snapshot in window:
        for row in (*snapshot.listed, *snapshot.otc):
            if row.security_type is SecurityType.ORDINARY:
                appearances[(row.market.value, row.code)].append((snapshot.data_date, row))
    output = []
    for (market, code), values in appearances.items():
        dates = {item[0] for item in values}
        longest = current = 0
        for trading_date in trading_dates:
            if trading_date in dates:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        current_streak = 0
        for trading_date in reversed(trading_dates):
            if trading_date in dates:
                current_streak += 1
            else:
                break
        rows = [item[1] for item in values]
        total_buy = sum((row.net_buy_lots for row in rows), Decimal(0))
        total_volume = sum((row.volume_lots for row in rows), Decimal(0))
        weighted = (
            total_buy / total_volume * Decimal(100)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if total_volume else None
        latest = rows[-1]
        output.append({
            "market": market,
            "code": code,
            "name": latest.name,
            "appearance_count": len(values),
            "longest_streak": longest,
            "current_streak": current_streak,
            "observed_buy_lots": format(total_buy, "f"),
            "observed_sell_lots": None,
            "weighted_buy_percent": format(weighted, "f") if weighted is not None else None,
            "latest_rank": latest.rank,
            "latest_date": values[-1][0].isoformat(),
            "buy_sell_state": "buy_top15" if values[-1][0] == trading_dates[-1] else "unranked_unknown",
            "evidence_status": (
                "confirmed" if len(window) == 20 else "partial"
            ),
            "coverage_trading_days": len(window),
        })
    return sorted(output, key=lambda x: (-x["appearance_count"], x["market"], x["code"]))


def monthly_summary(snapshots: list[DailySnapshot], month: str) -> dict:
    selected = [s for s in snapshots if s.data_date.strftime("%Y-%m") == month]
    grouped: dict[tuple[str, str], list] = defaultdict(list)
    trading_dates = [snapshot.data_date for snapshot in selected]
    for snapshot in selected:
        for row in (*snapshot.listed, *snapshot.otc):
            grouped[(row.market.value, row.code)].append(row)
    summary = []
    for (market, code), rows in grouped.items():
        total_buy = sum((row.net_buy_lots for row in rows), Decimal(0))
        total_volume = sum((row.volume_lots for row in rows), Decimal(0))
        weighted = (total_buy / total_volume * Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ) if total_volume else None
        ranked_dates = {row.ranking_date for row in rows}
        longest = current = 0
        for trading_date in trading_dates:
            if trading_date in ranked_dates:
                current += 1
                longest = max(longest, current)
            else:
                current = 0
        latest_units = rows[-1].issued_units
        capital = (
            total_buy * Decimal(1000) / Decimal(latest_units) * Decimal(100)
        ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if latest_units else None
        classification = (
            "高優先追蹤" if len(rows) >= 3 and weighted is not None and weighted > 20 and capital is not None and capital >= 1
            else "中優先追蹤" if len(rows) >= 2 and weighted is not None and weighted > 10
            else "觀察"
        )
        summary.append({
            "market": market,
            "code": code,
            "name": rows[-1].name,
            "security_type": rows[-1].security_type.value,
            "buy_top15_days": len(rows),
            "longest_streak": longest,
            "observed_buy_lots": format(total_buy, "f"),
            "weighted_buy_percent": format(weighted, "f") if weighted is not None else None,
            "month_price_change_percent": format(
                ((rows[-1].close / rows[0].close - Decimal(1)) * Decimal(100)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ), "f"
            ),
            "monthly_capital_percent": format(capital, "f") if capital is not None else None,
            "denominator_date": rows[-1].denominator_date.isoformat() if rows[-1].denominator_date else None,
            "classification": classification,
            "evidence_status": (
                "confirmed" if all(row.evidence_status.value == "confirmed" for row in rows)
                else "partial"
            ),
        })
    coverage = "unavailable" if not selected else ("confirmed" if len(selected) >= 18 else "partial")
    return {
        "month": month,
        "trading_days_observed": len(selected),
        "coverage_status": coverage,
        "summary_rows": sorted(summary, key=lambda x: (-x["buy_top15_days"], x["code"])),
        "limitations": (
            "Only observed top-15 ranks are aggregated; unranked is not zero. "
            "Coverage remains partial unless a conservative full-month threshold is met."
        ),
    }


def previous_month(today: date) -> str:
    year, month = today.year, today.month - 1
    if month == 0:
        year, month = year - 1, 12
    return f"{year:04d}-{month:02d}"
