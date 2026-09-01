from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from html import unescape

from chip_tracker.models import Market, SecurityType
from chip_tracker.sources.base import Denominator, Quote, RankItem, SourceError
from chip_tracker.sources.http import fetch_bytes, fetch_json


FUBON_URL = {
    Market.LISTED: "https://fubon-ebrokerdj.fbs.com.tw/z/zg/zgk.djhtm?A=F&B=0&C=1",
    Market.OTC: "https://fubon-ebrokerdj.fbs.com.tw/z/zg/zgk.djhtm?A=F&B=1&C=1",
}


def _number(value: str) -> Decimal:
    cleaned = value.replace(",", "").replace("＋", "+").strip()
    return Decimal(cleaned)


def _roc_date(value: str) -> date:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 7:
        raise SourceError(f"invalid ROC date: {value}")
    return date(int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:]))


def _security_type(code: str, name: str) -> SecurityType:
    upper = name.upper()
    if code.endswith("L") or "正2" in name:
        return SecurityType.LEVERAGED_ETF
    if code.endswith("R") or "反1" in name:
        return SecurityType.INVERSE_ETF
    if code.endswith("B") or "債" in name:
        return SecurityType.BOND_ETF
    if code.endswith("A") or "主動" in name:
        return SecurityType.ACTIVE_ETF
    if code.startswith("00") or "ETF" in upper:
        return SecurityType.ETF
    if "DR" in upper:
        return SecurityType.DR
    return SecurityType.ORDINARY


class LiveProvider:
    """Official quote/denominator adapters plus the requested Fubon rank source.

    The Fubon parser deliberately fails closed when the expected row schema changes.
    """

    def __init__(self) -> None:
        self._rank_cache: dict[tuple[Market, date], dict[str, RankItem]] = {}

    def ranks(self, market: Market, target_date: date) -> list[RankItem]:
        source_url = FUBON_URL[market]
        try:
            raw = fetch_bytes(source_url)
            text = raw.decode("cp950", errors="replace")
            rows = self._parse_fubon_html(text, market, target_date, source_url)
        except SourceError:
            proxy_url = f"https://r.jina.ai/{source_url}"
            text = fetch_bytes(proxy_url).decode("utf-8-sig")
            rows = self._parse_fubon_markdown(text, market, target_date, proxy_url)
        if len(rows) != 15:
            raise SourceError(f"Fubon parser expected 15 rows, got {len(rows)}")
        self._rank_cache[(market, target_date)] = {row.code: row for row in rows}
        return rows

    def _page_date(self, text: str, target_date: date) -> date:
        visible = unescape(re.sub(r"<[^>]+>", " ", text))
        visible = re.sub(r"\s+", " ", visible)
        mmdd = re.search(r"(?<!\d)(\d{2})/(\d{2})(?!\d)", visible)
        if not mmdd:
            raise SourceError("Fubon page date not found")
        page_date = date(target_date.year, int(mmdd.group(1)), int(mmdd.group(2)))
        if page_date != target_date:
            raise SourceError(f"Fubon page date {page_date} != target {target_date}")
        return page_date

    def _parse_fubon_html(
        self, text: str, market: Market, target_date: date, source_url: str
    ) -> list[RankItem]:
        page_date = self._page_date(text, target_date)

        # Every row has five buy-side cells followed by five sell-side cells.
        # Parse the complete first five cells so a layout shift fails closed.
        rows = []
        pattern = re.compile(
            r"<tr>\s*<td[^>]*>\s*(?P<rank>\d+)\s*</td>\s*"
            r"<td[^>]*>\s*<a[^>]*Link2Stk\('(?P<code>[0-9A-Z]{4,7})'\)[^>]*>"
            r"(?P<label>[^<]+)</a>\s*</td>\s*"
            r"<td[^>]*>\s*(?P<buy>[0-9][0-9,]*)\s*</td>\s*"
            r"<td[^>]*>\s*(?P<close>[0-9][0-9,.]*)\s*</td>\s*"
            r"<td[^>]*>\s*(?P<change>[+-]?[0-9][0-9,.]*)\s*</td>",
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(text):
            code = match.group("code")
            label = unescape(match.group("label")).strip()
            rows.append(RankItem(
                market=market,
                rank=int(match.group("rank")),
                code=code,
                name=label[len(code):].strip() if label.startswith(code) else label,
                close=_number(match.group("close")),
                change_amount=_number(match.group("change")),
                net_buy_lots=_number(match.group("buy")),
                data_date=page_date,
                source=source_url,
            ))
            if len(rows) == 15:
                break
        return rows

    def _parse_fubon_markdown(
        self, text: str, market: Market, target_date: date, source_url: str
    ) -> list[RankItem]:
        page_date = self._page_date(text, target_date)
        rows = []
        pattern = re.compile(
            r"^(?P<rank>\d+)\t(?P<label>[0-9A-Z]{4,7}[^\t]+)\t"
            r"(?P<buy>[0-9][0-9,]*)\t(?P<close>[0-9][0-9,.]*)\t"
            r"(?P<change>[+-]?[0-9][0-9,.]*)\t",
            re.MULTILINE,
        )
        for match in pattern.finditer(text):
            rank = int(match.group("rank"))
            if rank > 15:
                break
            label = match.group("label")
            code_match = re.match(r"([0-9A-Z]{4,7})", label)
            if not code_match:
                continue
            code = code_match.group(1)
            rows.append(RankItem(
                market=market, rank=rank, code=code,
                name=label[len(code):].strip(), close=_number(match.group("close")),
                change_amount=_number(match.group("change")),
                net_buy_lots=_number(match.group("buy")), data_date=page_date,
                source=source_url,
            ))
        return rows

    def quotes(self, market: Market, target_date: date) -> dict[str, Quote]:
        if market is Market.LISTED:
            return self._twse_quotes(target_date)
        return self._tpex_quotes(target_date)

    def _twse_quotes(self, target_date: date) -> dict[str, Quote]:
        stamp = target_date.strftime("%Y%m%d")
        url = ("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
               f"?date={stamp}&type=ALLBUT0999&response=json")
        payload = fetch_json(url)
        if payload.get("date") != stamp:
            raise SourceError("TWSE quote date mismatch")
        tables = payload.get("tables", [])
        table = next((x for x in tables if "證券代號" in x.get("fields", [])), None)
        if not table:
            raise SourceError("TWSE quote table missing")
        fields = table["fields"]
        pos = {name: fields.index(name) for name in fields}
        result = {}
        for row in table["data"]:
            try:
                sign = -1 if "-" in row[pos.get("漲跌(+/-)", 9)] else 1
                code = row[pos["證券代號"]].strip()
                result[code] = Quote(
                    code=code,
                    close=_number(row[pos["收盤價"]]),
                    change_amount=_number(row[pos["漲跌價差"]]) * sign,
                    volume_lots=_number(row[pos["成交股數"]]) / Decimal(1000),
                    data_date=target_date,
                    source=url,
                )
            except (KeyError, ValueError, ArithmeticError):
                continue
        return result

    def _tpex_quotes(self, target_date: date) -> dict[str, Quote]:
        url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
        payload = fetch_json(url)
        result = {}
        for row in payload:
            try:
                if _roc_date(row["Date"]) != target_date:
                    continue
                code = row["SecuritiesCompanyCode"].strip()
                close = _number(row["Close"])
                try:
                    change = _number(row["Change"])
                except ArithmeticError:
                    # TPEx uses text markers such as 漲停/跌停 instead of a
                    # numeric change for some rows.  The requested same-day
                    # Fubon rank still provides the change amount; use it only
                    # when code/date/close have already matched.
                    rank = self._rank_cache.get((Market.OTC, target_date), {}).get(code)
                    if rank is None or rank.close != close:
                        continue
                    change = rank.change_amount
                result[code] = Quote(
                    code=code,
                    close=close,
                    change_amount=change,
                    volume_lots=_number(row["TradingShares"]) / Decimal(1000),
                    data_date=target_date,
                    source=url,
                )
            except (KeyError, ValueError, ArithmeticError):
                continue
        if not result:
            raise SourceError("TPEx has no rows for target date")
        return result

    def denominators(
        self, market: Market, codes: set[str], target_date: date
    ) -> dict[str, Denominator]:
        if market is Market.OTC:
            rows = fetch_json("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes")
            result = {}
            for row in rows:
                code = row.get("SecuritiesCompanyCode", "").strip()
                if code not in codes or not row.get("Capitals"):
                    continue
                name = row.get("CompanyName", "")
                result[code] = Denominator(
                    code, int(_number(row["Capitals"])), _roc_date(row["Date"]),
                    "TPEx Capitals", _security_type(code, name),
                )
            return result

        company_url = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        fund_url = "https://openapi.twse.com.tw/v1/opendata/t187ap47_L"
        result: dict[str, Denominator] = {}
        for row in fetch_json(company_url):
            code = str(row.get("公司代號", "")).strip()
            if code not in codes:
                continue
            raw_units = row.get("已發行普通股數或TDR原股發行股數", "")
            raw_date = row.get("出表日期", "")
            if raw_units and raw_date:
                result[code] = Denominator(
                    code, int(_number(raw_units)), _roc_date(raw_date), company_url,
                    SecurityType.ORDINARY,
                )
        for row in fetch_json(fund_url):
            code = str(row.get("基金代號", row.get("證券代號", ""))).strip()
            if code not in codes:
                continue
            unit_key = next((key for key in row if "發行單位" in key), None)
            raw_date = row.get("出表日期", "")
            if unit_key and row[unit_key] and raw_date:
                result[code] = Denominator(
                    code, int(_number(row[unit_key])), _roc_date(raw_date), fund_url,
                    _security_type(code, row.get("基金名稱", "")),
                )
        return result
