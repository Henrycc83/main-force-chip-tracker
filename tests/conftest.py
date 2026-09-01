from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from chip_tracker.models import Market


@pytest.fixture
def fixture_file(tmp_path):
    def rows(market: str):
        prefix = "1" if market == "listed" else "3"
        output = []
        for rank in range(1, 16):
            code = f"{prefix}{rank:03d}"
            output.append({
                "rank": rank,
                "code": code,
                "name": f"測試{market}{rank}",
                "security_type": "ordinary_stock",
                "close": str(Decimal("50") + rank),
                "change_amount": "1",
                "net_buy_lots": str(rank * 100),
                "volume_lots": str(rank * 1000),
                "issued_units": 100_000_000,
                "denominator_date": "2026-09-01",
            })
        return output
    path = tmp_path / "market.json"
    path.write_text(json.dumps({
        "data_date": "2026-09-01", "listed": rows("listed"), "otc": rows("otc")
    }, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def target_date():
    return date(2026, 9, 1)

