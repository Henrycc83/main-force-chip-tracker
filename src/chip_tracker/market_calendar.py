from __future__ import annotations

from datetime import date
from typing import Callable

from chip_tracker.sources import SourceError
from chip_tracker.sources.http import fetch_json


HOLIDAY_URL = "https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=json"


def official_market_closure(
    target: date, *, fetch: Callable[[str], dict] = fetch_json
) -> str | None:
    """Return the TWSE closure name for a date, or None when it is not a closure."""
    payload = fetch(HOLIDAY_URL)
    if payload.get("stat") != "ok" or payload.get("queryYear") != target.year:
        raise SourceError("TWSE market calendar has an unexpected year or status")
    for row in payload.get("data", []):
        if len(row) < 2 or row[0] != target.isoformat():
            continue
        name = row[1].strip()
        if "開始交易日" in name or "最後交易日" in name:
            return None
        return name
    return None
