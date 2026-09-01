from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from chip_tracker.models import (
    ChipRow, DailySnapshot, EvidenceStatus, Market, SecurityType,
)
from chip_tracker.storage import write_json_atomic
from chip_tracker.publisher import observation_path
from chip_tracker.validator import validate_snapshot


TYPE_MAP = {
    "普通股": SecurityType.ORDINARY,
    "ETF": SecurityType.ETF,
    "債券 ETF": SecurityType.BOND_ETF,
    "槓桿 ETF": SecurityType.LEVERAGED_ETF,
    "反向 ETF": SecurityType.INVERSE_ETF,
    "主動式 ETF": SecurityType.ACTIVE_ETF,
    "ETN": SecurityType.ETN,
    "DR": SecurityType.DR,
}


def _decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", "").replace("%", "").replace("+", "").strip())


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_daily_report(path: Path) -> DailySnapshot:
    text = path.read_text(encoding="utf-8-sig")
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", path.stem)
    if not match:
        raise ValueError(f"date missing from {path}")
    data_date = date.fromisoformat(match.group(1))
    denominators: dict[tuple[str, str], tuple[int, date, str, EvidenceStatus]] = {}
    for line in text.splitlines():
        cells = _cells(line) if line.startswith("|") else []
        if len(cells) == 8 and cells[0] in {"上市", "上櫃"} and cells[3].replace(",", "").isdigit():
            status = EvidenceStatus.CONFIRMED if "已確認（計算值）" in cells[7] else EvidenceStatus.PARTIAL
            denominators[(cells[0], cells[1])] = (
                int(cells[3].replace(",", "")), date.fromisoformat(cells[4]), cells[5], status
            )
    grouped: dict[Market, list[ChipRow]] = {Market.LISTED: [], Market.OTC: []}
    current_market: Market | None = None
    for line in text.splitlines():
        if line.startswith("## 上市主力"):
            current_market = Market.LISTED
            continue
        if line.startswith("## 上櫃主力"):
            current_market = Market.OTC
            continue
        if not line.startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) == 12 and cells[0] in {"上市", "上櫃"} and cells[1].isdigit():
            market_name = cells[0]
            values = cells[1:]
        elif len(cells) == 11 and current_market is not None and cells[0].isdigit():
            market_name = "上市" if current_market is Market.LISTED else "上櫃"
            values = cells
        else:
            continue
        market = Market.LISTED if market_name == "上市" else Market.OTC
        denominator = denominators.get((market_name, values[1]))
        issued_units, denominator_date, denominator_source, evidence = (
            denominator if denominator else (None, None, None, EvidenceStatus.PARTIAL)
        )
        cap = None if not denominator or values[10] == "不可用" else _decimal(values[10])
        grouped[market].append(ChipRow(
            market=market,
            rank=int(values[0]),
            code=values[1],
            name=values[2],
            security_type=TYPE_MAP.get(values[3], SecurityType.OTHER),
            close=_decimal(values[4]),
            change_percent=_decimal(values[5]),
            net_buy_lots=_decimal(values[6]),
            volume_lots=_decimal(values[7]),
            buy_volume_percent=_decimal(values[8]),
            stars=values[9].count("★"),
            capital_percent=cap,
            evidence_status=evidence,
            ranking_date=data_date,
            quote_date=data_date,
            denominator_date=denominator_date,
            issued_units=issued_units,
            ranking_source=f"seed:{path.name}",
            quote_source=f"seed:{path.name}",
            denominator_source=denominator_source,
        ))
    snapshot = DailySnapshot(
        data_date=data_date,
        listed=tuple(grouped[Market.LISTED]),
        otc=tuple(grouped[Market.OTC]),
        generated_at=datetime.combine(data_date, time(18, 30), ZoneInfo("Asia/Taipei")),
        source_health={"seed_report": "confirmed"},
    )
    result = validate_snapshot(snapshot)
    if not result.passed:
        raise ValueError(f"invalid seed {path.name}: {'; '.join(result.errors)}")
    return snapshot


def import_reports(project_root: Path, reports_root: Path) -> list[Path]:
    imported = []
    for source in sorted((reports_root / "daily").glob("20??-??-??.md")):
        snapshot = parse_daily_report(source)
        destination = observation_path(project_root, snapshot)
        write_json_atomic(destination, snapshot.to_dict())
        imported.append(destination)
    return imported
