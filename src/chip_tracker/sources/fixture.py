from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from chip_tracker.models import Market, SecurityType
from chip_tracker.sources.base import Denominator, Quote, RankItem, SourceError


class FixtureProvider:
    def __init__(self, path: Path):
        self.path = path
        self.data = json.loads(path.read_text(encoding="utf-8"))

    def _rows(self, market: Market) -> list[dict]:
        return self.data[market.value]

    def ranks(self, market: Market, target_date: date) -> list[RankItem]:
        fixture_date = date.fromisoformat(self.data["data_date"])
        if fixture_date != target_date:
            raise SourceError(f"fixture date {fixture_date} != target {target_date}")
        return [
            RankItem(
                market=market,
                rank=int(row["rank"]),
                code=row["code"],
                name=row["name"],
                close=Decimal(row["close"]),
                change_amount=Decimal(row["change_amount"]),
                net_buy_lots=Decimal(row["net_buy_lots"]),
                data_date=fixture_date,
                source="fixture:fubon",
            )
            for row in self._rows(market)
        ]

    def quotes(self, market: Market, target_date: date) -> dict[str, Quote]:
        return {
            row["code"]: Quote(
                code=row["code"],
                close=Decimal(row["close"]),
                change_amount=Decimal(row["change_amount"]),
                volume_lots=Decimal(row["volume_lots"]),
                data_date=target_date,
                source="fixture:official-quotes",
            )
            for row in self._rows(market)
        }

    def denominators(
        self, market: Market, codes: set[str], target_date: date
    ) -> dict[str, Denominator]:
        result = {}
        for row in self._rows(market):
            if row["code"] not in codes or row.get("issued_units") is None:
                continue
            result[row["code"]] = Denominator(
                code=row["code"],
                issued_units=int(row["issued_units"]),
                data_date=date.fromisoformat(row.get("denominator_date", self.data["data_date"])),
                source="fixture:official-denominator",
                security_type=SecurityType(row.get("security_type", "ordinary_stock")),
            )
        return result

