from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from chip_tracker.calculations import capital_percent, change_percent, star_count
from chip_tracker.models import ChipRow, DailySnapshot, EvidenceStatus, Market
from chip_tracker.sources import MarketDataProvider, SourceError


TAIPEI = ZoneInfo("Asia/Taipei")


def build_snapshot(provider: MarketDataProvider, target_date: date) -> DailySnapshot:
    built: dict[Market, tuple[ChipRow, ...]] = {}
    health: dict[str, str] = {}
    for market in (Market.LISTED, Market.OTC):
        ranks = provider.ranks(market, target_date)
        if len(ranks) != 15:
            raise SourceError(f"{market.value}: expected 15 ranks, got {len(ranks)}")
        quotes = provider.quotes(market, target_date)
        denominators = provider.denominators(
            market, {rank.code for rank in ranks}, target_date
        )
        rows = []
        for rank in ranks:
            quote = quotes.get(rank.code)
            if quote is None:
                raise SourceError(f"missing official quote: {market.value} {rank.code}")
            if quote.data_date != target_date or rank.data_date != target_date:
                raise SourceError(f"date mismatch: {market.value} {rank.code}")
            if quote.close != rank.close or quote.change_amount != rank.change_amount:
                raise SourceError(f"quote mismatch: {market.value} {rank.code}")
            denominator = denominators.get(rank.code)
            status = (
                EvidenceStatus.PARTIAL
                if _is_proxy(rank.source) or _is_proxy(quote.source)
                else EvidenceStatus.CONFIRMED
            )
            cap = None
            if denominator is None:
                status = EvidenceStatus.PARTIAL
            elif denominator.data_date > target_date:
                raise SourceError(f"future denominator: {rank.code}")
            else:
                cap = capital_percent(rank.net_buy_lots, denominator.issued_units)
                if denominator.data_date != target_date:
                    status = EvidenceStatus.PARTIAL
            raw_ratio = rank.net_buy_lots / quote.volume_lots * Decimal(100)
            rows.append(ChipRow(
                market=market,
                rank=rank.rank,
                code=rank.code,
                name=rank.name,
                security_type=(denominator.security_type if denominator else _infer_type(rank.code, rank.name)),
                close=rank.close,
                change_percent=change_percent(rank.close, rank.change_amount),
                net_buy_lots=rank.net_buy_lots,
                volume_lots=quote.volume_lots,
                buy_volume_percent=raw_ratio.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                stars=star_count(raw_ratio),
                capital_percent=cap,
                evidence_status=status,
                ranking_date=rank.data_date,
                quote_date=quote.data_date,
                denominator_date=denominator.data_date if denominator else None,
                issued_units=denominator.issued_units if denominator else None,
                ranking_source=rank.source,
                quote_source=quote.source,
                denominator_source=denominator.source if denominator else None,
            ))
        built[market] = tuple(rows)
        health[f"{market.value}_ranking"] = (
            "partial" if any(_is_proxy(row.ranking_source) for row in rows) else "confirmed"
        )
        health[f"{market.value}_quotes"] = (
            "partial" if any(_is_proxy(row.quote_source) for row in rows) else "confirmed"
        )
        health[f"{market.value}_denominators"] = (
            "confirmed" if all(
                x.issued_units is not None and x.denominator_date == target_date
                for x in rows
            )
            else "partial"
        )
    return DailySnapshot(
        data_date=target_date,
        listed=built[Market.LISTED],
        otc=built[Market.OTC],
        generated_at=datetime.now(TAIPEI),
        source_health=health,
    )


def _infer_type(code: str, name: str):
    from chip_tracker.sources.live import _security_type
    return _security_type(code, name)


def _is_proxy(source: str | None) -> bool:
    return bool(source and "r.jina.ai/" in source.lower())
