from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Market(StrEnum):
    LISTED = "listed"
    OTC = "otc"


class EvidenceStatus(StrEnum):
    CONFIRMED = "confirmed"
    PARTIAL = "partial"
    ONE_SIDED = "one_sided"
    UNAVAILABLE = "unavailable"


class SecurityType(StrEnum):
    ORDINARY = "ordinary_stock"
    ETF = "etf"
    BOND_ETF = "bond_etf"
    LEVERAGED_ETF = "leveraged_etf"
    INVERSE_ETF = "inverse_etf"
    ACTIVE_ETF = "active_etf"
    ETN = "etn"
    DR = "dr"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ChipRow:
    market: Market
    rank: int
    code: str
    name: str
    security_type: SecurityType
    close: Decimal
    change_percent: Decimal
    net_buy_lots: Decimal
    volume_lots: Decimal
    buy_volume_percent: Decimal
    stars: int
    capital_percent: Decimal | None
    evidence_status: EvidenceStatus
    ranking_date: date
    quote_date: date
    denominator_date: date | None
    issued_units: int | None
    ranking_source: str
    quote_source: str
    denominator_source: str | None

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ChipRow":
        decimal_fields = {
            "close", "change_percent", "net_buy_lots", "volume_lots",
            "buy_volume_percent", "capital_percent",
        }
        date_fields = {"ranking_date", "quote_date", "denominator_date"}
        data = dict(value)
        for field in decimal_fields:
            if data.get(field) is not None:
                data[field] = Decimal(str(data[field]))
        for field in date_fields:
            if data.get(field):
                data[field] = date.fromisoformat(data[field])
        data["market"] = Market(data["market"])
        data["security_type"] = SecurityType(data["security_type"])
        data["evidence_status"] = EvidenceStatus(data["evidence_status"])
        return cls(**data)


@dataclass(frozen=True, slots=True)
class DailySnapshot:
    data_date: date
    listed: tuple[ChipRow, ...]
    otc: tuple[ChipRow, ...]
    generated_at: datetime
    source_health: dict[str, str]
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "data_date": self.data_date.isoformat(),
            "generated_at": self.generated_at.isoformat(),
            "source_health": self.source_health,
            "latest": {
                "listed": [row.to_dict() for row in self.listed],
                "otc": [row.to_dict() for row in self.otc],
            },
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DailySnapshot":
        latest = value["latest"]
        return cls(
            data_date=date.fromisoformat(value["data_date"]),
            listed=tuple(ChipRow.from_dict(x) for x in latest["listed"]),
            otc=tuple(ChipRow.from_dict(x) for x in latest["otc"]),
            generated_at=datetime.fromisoformat(value["generated_at"]),
            source_health=dict(value.get("source_health", {})),
            schema_version=int(value.get("schema_version", 1)),
        )


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value

