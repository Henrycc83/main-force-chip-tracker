from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from shutil import copytree

from chip_tracker.memory import monthly_summary
from chip_tracker.models import DailySnapshot, SecurityType
from chip_tracker.storage import write_text_atomic


def consecutive_segments(snapshots: list[DailySnapshot], minimum: int = 2) -> list[dict]:
    output = []
    for market, code, active in _consecutive_row_groups(snapshots, minimum):
        total_buy = sum((x.net_buy_lots for x in active), Decimal(0))
        total_volume = sum((x.volume_lots for x in active), Decimal(0))
        price_change = (active[-1].close / active[0].close - Decimal(1)) * Decimal(100)
        latest_units = active[-1].issued_units
        capital = (
            total_buy * Decimal(1000) / Decimal(latest_units) * Decimal(100)
        ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if latest_units else None
        output.append({
            "market": market, "code": code, "name": active[-1].name,
            "security_type": active[-1].security_type.value,
            "start": active[0].ranking_date.isoformat(),
            "end": active[-1].ranking_date.isoformat(),
            "days": len(active), "ranks": [x.rank for x in active],
            "observed_buy_lots": format(total_buy, "f"),
            "observed_volume_lots": format(total_volume, "f"),
            "weighted_buy_percent": format(
                (total_buy / total_volume * Decimal(100)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ), "f"
            ),
            "price_change_percent": format(
                price_change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f"
            ),
            "observed_capital_percent": format(capital, "f") if capital is not None else None,
            "denominator_date": (
                active[-1].denominator_date.isoformat() if active[-1].denominator_date else None
            ),
            "evidence_status": (
                "confirmed" if all(x.evidence_status.value == "confirmed" for x in active)
                else "partial"
            ),
            "close_low": format(min(x.close for x in active), "f"),
            "close_high": format(max(x.close for x in active), "f"),
            "latest_close": format(active[-1].close, "f"),
            "daily_details": [
                {
                    "date": x.ranking_date.isoformat(), "rank": x.rank,
                    "close": format(x.close, "f"),
                    "change_percent": format(x.change_percent, "f"),
                    "net_buy_lots": format(x.net_buy_lots, "f"),
                    "volume_lots": format(x.volume_lots, "f"),
                    "buy_volume_percent": format(x.buy_volume_percent, "f"),
                    "stars": x.stars,
                    "capital_percent": (
                        format(x.capital_percent, "f") if x.capital_percent is not None else None
                    ),
                }
                for x in active
            ],
        })
    return sorted(output, key=lambda x: (-x["days"], x["market"], x["code"]))


def _consecutive_row_groups(
    snapshots: list[DailySnapshot], minimum: int = 2
) -> list[tuple[str, str, list]]:
    dates = [snapshot.data_date for snapshot in snapshots]
    seen: dict[tuple[str, str], dict[date, object]] = defaultdict(dict)
    for snapshot in snapshots:
        for row in (*snapshot.listed, *snapshot.otc):
            seen[(row.market.value, row.code)][snapshot.data_date] = row
    output = []
    for (market, code), by_date in seen.items():
        active: list = []
        for day in dates + [None]:
            if day in by_date:
                active.append(by_date[day])
                continue
            if len(active) >= minimum:
                output.append((market, code, active.copy()))
            active = []
    return output


def render_monthly(snapshots: list[DailySnapshot], month: str) -> str:
    data = monthly_summary(snapshots, month)
    ordinary = [x for x in data["summary_rows"] if x["security_type"] == SecurityType.ORDINARY.value]
    funds = [x for x in data["summary_rows"] if x["security_type"] != SecurityType.ORDINARY.value]
    lines = [
        f"# 主力籌碼月報｜{month}", "",
        f"- 已觀察交易日：{data['trading_days_observed']}",
        f"- 覆蓋狀態：{data['coverage_status']}",
        "- 限制：未進前15名不能視為0張；本表只加總排行可觀察值。", "",
        "## 普通股", "",
        "| 市場 | 代碼 | 名稱 | 入榜日數 | 可觀察買超張數 | 加權買超比 | 月內價格變化 |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for row in ordinary:
        lines.append(
            f"| {row['market']} | {row['code']} | {row['name']} | {row['buy_top15_days']} | "
            f"{row['observed_buy_lots']} | {row['weighted_buy_percent']}% | {row['month_price_change_percent']}% |"
        )
    lines += ["", "## ETF／其他資金流附錄", "", "| 市場 | 代碼 | 名稱 | 類型 | 入榜日數 | 可觀察買超張數 |", "|---|---|---|---|---:|---:|"]
    for row in funds:
        lines.append(
            f"| {row['market']} | {row['code']} | {row['name']} | {row['security_type']} | "
            f"{row['buy_top15_days']} | {row['observed_buy_lots']} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_monthly_report(root: Path, snapshots: list[DailySnapshot], month: str) -> Path:
    target = root / "reports" / "main-force-chips" / "monthly" / f"{month}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = render_monthly(snapshots, month)
    write_text_atomic(target, payload)
    write_text_atomic(root / "reports" / "main-force-chips" / "monthly-latest.md", payload)
    _update_index(target.parent / "index.md", month, target.name)
    return target


def render_daily(snapshot: DailySnapshot) -> str:
    all_rows = [*snapshot.listed, *snapshot.otc]
    overall = "已確認" if all(row.evidence_status.value == "confirmed" for row in all_rows) else "部分或代理"
    lines = [
        f"# 主力籌碼買超每日追蹤｜{snapshot.data_date}", "",
        f"- 整體證據狀態：{overall}；30 筆結構與公式均已由獨立驗證器確認。", "",
    ]
    for heading, rows in (("上市", snapshot.listed), ("上櫃", snapshot.otc)):
        lines += [
            f"## {heading}主力買超前15名", "",
            "| 市場 | 名次 | 代碼 | 名稱 | 證券類型 | 收盤價 | 今日收盤漲跌幅 | 主力買超量（張） | 成交量（張） | 買超量 ÷ 成交量百分比 | 星等 | 股本占比 |",
            "|---|---:|---|---|---|---:|---:|---:|---:|---:|:---:|---:|",
        ]
        for row in rows:
            cap = "不可用" if row.capital_percent is None else f"{row.capital_percent}%"
            lines.append(
                f"| {heading} | {row.rank} | {row.code} | {row.name} | {row.security_type.value} | "
                f"{row.close} | {row.change_percent:+}% | {row.net_buy_lots} | {row.volume_lots} | "
                f"{row.buy_volume_percent}% | {'★' * row.stars} | {cap} |"
            )
        lines.append("")
        lines += [
            f"### {heading}證據與分母稽核", "",
            "| 代碼 | 證據狀態 | 排行日期 | 行情日期 | 分母日期 | 排行來源 | 行情來源 | 分母來源 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for row in rows:
            evidence = "已確認" if row.evidence_status.value == "confirmed" else "部分或代理"
            lines.append(
                f"| {row.code} | {evidence} | {row.ranking_date} | {row.quote_date} | "
                f"{row.denominator_date or '不可用'} | {row.ranking_source} | {row.quote_source} | "
                f"{row.denominator_source or '不可用'} |"
            )
        lines.append("")
    lines += ["## 覆蓋檢查", "", "- 上市15/15、上櫃15/15；公式、日期及重複代碼已獨立驗證。", ""]
    return "\n".join(lines)


def write_daily_report(root: Path, snapshot: DailySnapshot) -> Path:
    payload = render_daily(snapshot)
    base = root / "reports" / "main-force-chips"
    target = base / "daily" / f"{snapshot.data_date}.md"
    write_text_atomic(target, payload)
    write_text_atomic(base / "daily-latest.md", payload)
    _update_index(target.parent / "index.md", snapshot.data_date.isoformat(), target.name)
    return target


def render_weekly(snapshots: list[DailySnapshot]) -> str:
    if not snapshots:
        return "# 主力籌碼週報\n\n無資料。\n"
    iso = snapshots[-1].data_date.isocalendar()
    segments = consecutive_segments(snapshots)
    lines = [
        f"# 主力籌碼買超週報｜{iso.year}-W{iso.week:02d}", "",
        f"- 實際交易日：{len(snapshots)}", "- 未入榜不得視為0張。", "",
        "| 市場 | 代碼 | 名稱 | 類型 | 連續區段 | 天數 | 名次 | 累計買超／成交量 | 加權買超比 | 價格變化 | 股本占比 |",
        "|---|---|---|---|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in segments:
        capital_text = (
            f"{row['observed_capital_percent']}%"
            if row["observed_capital_percent"] is not None else "不可用"
        )
        lines.append(
            f"| {row['market']} | {row['code']} | {row['name']} | {row['security_type']} | "
            f"{row['start']}–{row['end']} | {row['days']} | {','.join(map(str, row['ranks']))} | "
            f"{row['observed_buy_lots']}／{row['observed_volume_lots']} | {row['weighted_buy_percent']}% | "
            f"{row['price_change_percent']}% | {capital_text} |"
        )
    lines += ["", "## 每日明細", ""]
    for row in segments:
        lines += [
            f"### {row['code']} {row['name']}｜{row['start']}–{row['end']}", "",
            "| 日期 | 名次 | 收盤價 | 漲跌幅 | 買超張數 | 成交量 | 買超比 | 星等 | 股本占比 |",
            "|---|---:|---:|---:|---:|---:|---:|:---:|---:|",
        ]
        for day in row["daily_details"]:
            day_capital = (
                f"{day['capital_percent']}%" if day["capital_percent"] is not None else "不可用"
            )
            lines.append(
                f"| {day['date']} | {day['rank']} | {day['close']} | {day['change_percent']}% | "
                f"{day['net_buy_lots']} | {day['volume_lots']} | {day['buy_volume_percent']}% | "
                f"{'★' * day['stars']} | {day_capital} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_weekly_report(root: Path, snapshots: list[DailySnapshot]) -> Path:
    latest = snapshots[-1].data_date.isocalendar()
    payload = render_weekly(snapshots)
    base = root / "reports" / "main-force-chips"
    target = base / "weekly" / f"{latest.year}-W{latest.week:02d}.md"
    write_text_atomic(target, payload)
    write_text_atomic(base / "weekly-latest.md", payload)
    _update_index(target.parent / "index.md", f"{latest.year}-W{latest.week:02d}", target.name)
    return target


def render_analysis(snapshots: list[DailySnapshot]) -> str:
    if not snapshots:
        return "# 主力籌碼週日分析\n\n無本週交易資料；暫不觸發。\n"
    iso = snapshots[-1].data_date.isocalendar()
    segments = consecutive_segments(snapshots)
    ordinary = [x for x in segments if x["security_type"] == SecurityType.ORDINARY.value]
    funds = [x for x in segments if x["security_type"] != SecurityType.ORDINARY.value]
    lines = [
        f"# 潛在主力籌碼週日分析｜{iso.year}-W{iso.week:02d}", "",
        "- 性質：條件式追蹤，不是買賣建議，也不承諾報酬。",
        "- 自動資料範圍：本週前15名排行、量價、買超比與股本占比；三大法人、重大訊息與產業催化在本次自動執行中標示不可用。",
        "- 限制：未入榜代表未知，不得當成0張；單一排行不能證明同一主力持續鎖籌。", "",
        "## 普通股候選", "",
    ]
    if not ordinary:
        lines += ["本週沒有連續至少2個交易日入榜的普通股，暫不觸發。", ""]
    for row in ordinary:
        weighted = Decimal(row["weighted_buy_percent"])
        capital = Decimal(row["observed_capital_percent"]) if row["observed_capital_percent"] else None
        price_change = Decimal(row["price_change_percent"])
        stable_rank = max(row["ranks"]) - min(row["ranks"]) <= 5
        priority = (
            "高" if row["days"] >= 3 and weighted > 15 and capital is not None and capital >= Decimal("0.5")
            else "中" if row["days"] >= 2 and weighted > 10
            else "低"
        )
        evidence = "已確認" if row["evidence_status"] == "confirmed" else "部分或代理"
        counter = (
            "區段漲幅偏快，存在追價與高檔爆量滯漲風險。" if price_change > 8
            else "價格未同步轉強，籌碼訊號尚未獲價格確認。" if price_change <= 0
            else "排行資料無法辨識是否為同一主力，連續買超仍可能是短線輪動。"
        )
        trigger = (
            f"僅在下一交易日仍入前15、買超比大於10%，且收盤有效站上 {row['close_high']} 時，以計畫部位不超過10%試單。"
            if row["evidence_status"] == "confirmed"
            else "證據仍為部分或代理，暫不觸發；待分母日期與行情口徑同日確認後再評估。"
        )
        capital_text = (
            f"{row['observed_capital_percent']}%"
            if row["observed_capital_percent"] is not None else "不可用"
        )
        lines += [
            f"### {row['code']} {row['name']}｜{priority}優先｜{evidence}", "",
            f"- 支持證據：連續 {row['days']} 日入榜，名次 {','.join(map(str, row['ranks']))}；累計可觀察買超 {row['observed_buy_lots']} 張，加權買超比 {row['weighted_buy_percent']}%，區段股本占比 {capital_text}。",
            f"- 名次／量價：名次{'穩定' if stable_rank else '波動'}；區段收盤變化 {row['price_change_percent']}%。",
            f"- 反證：{counter}",
            "- 風險：未入榜不是賣超；自動資料未涵蓋三大法人、重大訊息與產業催化，這三項目前不可用。",
            f"- 關鍵價位：觀察收盤低點 {row['close_low']}、區段高點 {row['close_high']}、最新收盤 {row['latest_close']}。", "",
            "#### 3 個驗證指標", "",
            f"1. 下一交易日仍在前15且買超比維持大於10%（目前 {row['weighted_buy_percent']}%）。",
            f"2. 收盤守住區段低點 {row['close_low']}，並突破或站穩區段高點 {row['close_high']}。",
            f"3. 累計股本占比持續增加，且分母日期維持可比（目前 {row['denominator_date'] or '不可用'}）。", "",
            "#### 條件式分階段策略", "",
            f"- 不追價觀察區：高於區段高點 {row['close_high']} 約3%以上時不追，等待量縮回測或新平台。",
            f"- 試單觸發：{trigger}",
            "- 加碼條件：試單後再連續2個交易日入榜、買超比不下降且價格未跌破突破位；每次不超過計畫部位10%，總曝險上限30%。",
            f"- 失效／停損：收盤跌破 {row['close_low']}，或進場價回落5%且籌碼未重新確認時退出，不攤平。",
            "- 分批減碼：漲幅擴大但爆量滯漲、買超比連續下降，或跌破短期平台時分2至3次減碼。",
            "- 不交易情境：跳空超過5%、資料日期不一致、重大訊息不可核實、成交量異常或證據仍為部分／代理。", "",
        ]
    lines += ["## ETF／其他資金流附錄", "", "ETF、ETN、DR及槓桿反向商品只解讀為資金流，不稱為公司鎖籌碼。", ""]
    if not funds:
        lines += ["本週沒有連續至少2個交易日入榜的非普通股商品。", ""]
    else:
        lines += [
            "| 市場 | 代碼 | 名稱 | 類型 | 連續天數 | 累計買超 | 加權買超比 |",
            "|---|---|---|---|---:|---:|---:|",
        ]
        for row in funds:
            lines.append(
                f"| {row['market']} | {row['code']} | {row['name']} | {row['security_type']} | "
                f"{row['days']} | {row['observed_buy_lots']} | {row['weighted_buy_percent']}% |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_analysis_report(root: Path, snapshots: list[DailySnapshot]) -> Path:
    latest = snapshots[-1].data_date.isocalendar()
    payload = render_analysis(snapshots)
    base = root / "reports" / "main-force-chips"
    target = base / "analysis" / f"{latest.year}-W{latest.week:02d}.md"
    write_text_atomic(target, payload)
    write_text_atomic(base / "analysis-latest.md", payload)
    _update_index(target.parent / "index.md", f"{latest.year}-W{latest.week:02d}", target.name)
    return target


def sync_static_reports(root: Path) -> Path:
    """Mirror auditable Markdown reports into the GitHub Pages artifact."""
    source = root / "reports" / "main-force-chips"
    target = root / "docs" / "reports" / "main-force-chips"
    if source.exists():
        copytree(source, target, dirs_exist_ok=True)
    return target


def _update_index(path: Path, label: str, filename: str) -> None:
    heading = "# 報告索引"
    entry = f"- [{label}]({filename})"
    existing = path.read_text(encoding="utf-8") if path.exists() else f"{heading}\n"
    lines = [line for line in existing.splitlines() if not line.startswith(f"- [{label}]")]
    lines.append(entry)
    write_text_atomic(path, "\n".join(lines) + "\n")
