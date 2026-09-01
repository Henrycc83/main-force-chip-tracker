from __future__ import annotations

from datetime import date
from pathlib import Path

from chip_tracker.builder import build_snapshot
from chip_tracker.memory import load_snapshots, previous_month
from chip_tracker.publisher import publish
from chip_tracker.reports import (
    sync_static_reports,
    write_daily_report,
    write_monthly_report,
    write_weekly_report,
)
from chip_tracker.sources import MarketDataProvider


def run_pipeline(
    root: Path,
    provider: MarketDataProvider,
    target_date: date,
    *,
    dashboard_path: Path | None = None,
) -> dict:
    run_calendar_reports(root, target_date)
    snapshot = build_snapshot(provider, target_date)
    payload = publish(root, snapshot, dashboard_path=dashboard_path)
    write_daily_report(root, snapshot)
    sync_static_reports(root)
    history = load_snapshots(root / "data" / "observations")
    same_week = [
        item for item in history
        if item.data_date.isocalendar()[:2] == target_date.isocalendar()[:2]
    ]
    return payload


def run_calendar_reports(root: Path, target_date: date) -> list[Path]:
    """Build reports that do not require a new same-day market snapshot."""
    history = load_snapshots(root / "data" / "observations")
    outputs: list[Path] = []
    if target_date.day == 1:
        outputs.append(write_monthly_report(root, history, previous_month(target_date)))
    if target_date.weekday() == 5:
        same_week = [
            item for item in history
            if item.data_date.isocalendar()[:2] == target_date.isocalendar()[:2]
        ]
        if same_week:
            outputs.append(write_weekly_report(root, same_week))
    sync_static_reports(root)
    return outputs
