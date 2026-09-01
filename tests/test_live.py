from datetime import date
from decimal import Decimal

from chip_tracker.models import Market
from chip_tracker.sources.base import RankItem
from chip_tracker.sources.live import LiveProvider


def test_tpex_text_change_uses_same_day_fubon_change_after_close_match(monkeypatch):
    target = date(2026, 9, 1)
    rank = RankItem(
        market=Market.OTC,
        rank=14,
        code="8086",
        name="宏捷科",
        close=Decimal("123"),
        change_amount=Decimal("6.5"),
        net_buy_lots=Decimal("1287"),
        data_date=target,
        source="fubon",
    )
    provider = LiveProvider()
    provider._rank_cache[(Market.OTC, target)] = {rank.code: rank}
    monkeypatch.setattr(
        "chip_tracker.sources.live.fetch_json",
        lambda _url: [{
            "Date": "1150901",
            "SecuritiesCompanyCode": "8086",
            "Close": "123.00",
            "Change": "漲停",
            "TradingShares": "10028073",
        }],
    )

    quote = provider._tpex_quotes(target)["8086"]

    assert quote.change_amount == Decimal("6.5")
    assert quote.volume_lots == Decimal("10028.073")
