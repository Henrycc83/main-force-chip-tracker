from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from chip_tracker.models import Market, SecurityType


class SourceError(RuntimeError):
    """Upstream data is missing, stale, or structurally invalid."""


@dataclass(frozen=True, slots=True)
class RankItem:
    market: Market
    rank: int
    code: str
    name: str
    close: Decimal
    change_amount: Decimal
    net_buy_lots: Decimal
    data_date: date
    source: str


@dataclass(frozen=True, slots=True)
class Quote:
    code: str
    close: Decimal
    change_amount: Decimal
    volume_lots: Decimal
    data_date: date
    source: str


@dataclass(frozen=True, slots=True)
class Denominator:
    code: str
    issued_units: int
    data_date: date
    source: str
    security_type: SecurityType


class MarketDataProvider(Protocol):
    def ranks(self, market: Market, target_date: date) -> list[RankItem]: ...
    def quotes(self, market: Market, target_date: date) -> dict[str, Quote]: ...
    def denominators(
        self, market: Market, codes: set[str], target_date: date
    ) -> dict[str, Denominator]: ...

