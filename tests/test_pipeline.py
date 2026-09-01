from datetime import date, timedelta
from dataclasses import replace
from decimal import Decimal

import pytest

from chip_tracker.builder import build_snapshot
from chip_tracker.memory import monthly_summary, rolling_20d
from chip_tracker.models import DailySnapshot
from chip_tracker.pipeline import run_calendar_reports, run_pipeline
from chip_tracker.publisher import PublicationRejected, publish
from chip_tracker.sources import FixtureProvider
from chip_tracker.storage import read_json
from chip_tracker.validator import validate_snapshot


def test_fixture_build_validates_30_rows(fixture_file, target_date):
    snapshot = build_snapshot(FixtureProvider(fixture_file), target_date)
    result = validate_snapshot(snapshot)
    assert result.passed
    assert result.checked_rows == 30
    assert len(snapshot.listed) == len(snapshot.otc) == 15
    assert snapshot.listed[0].buy_volume_percent == Decimal("10.00")
    assert snapshot.listed[0].stars == 2


def test_pipeline_publishes_observation_and_dashboard(tmp_path, fixture_file, target_date):
    dashboard = tmp_path / "published" / "dashboard.json"
    payload = run_pipeline(
        tmp_path, FixtureProvider(fixture_file), target_date, dashboard_path=dashboard
    )
    assert payload["status"] == "confirmed"
    assert payload["market_summary"]["TWSE"]["rows"] == 15
    assert read_json(dashboard)["data_date"] == "2026-09-01"
    assert (tmp_path / "data/observations/2026/09/2026-09-01.json").exists()
    assert (tmp_path / "reports/main-force-chips/daily/2026-09-01.md").exists()


def test_proxy_rank_is_published_as_partial(tmp_path, fixture_file, target_date):
    class ProxyFixture(FixtureProvider):
        def ranks(self, market, target):
            return [replace(row, source="https://r.jina.ai/https://example.test") for row in super().ranks(market, target)]

    payload = run_pipeline(tmp_path, ProxyFixture(fixture_file), target_date)

    assert payload["status"] == "partial"
    assert payload["quality"]["source_health"]["listed_ranking"] == "partial"
    assert all(row["evidence_status"] == "partial" for row in payload["latest"]["listed"])


def test_invalid_candidate_never_overwrites_dashboard(tmp_path, fixture_file, target_date):
    dashboard = tmp_path / "dashboard.json"
    dashboard.write_text('{"sentinel": true}', encoding="utf-8")
    snapshot = build_snapshot(FixtureProvider(fixture_file), target_date)
    invalid = DailySnapshot(
        snapshot.data_date, snapshot.listed[:-1], snapshot.otc,
        snapshot.generated_at, snapshot.source_health,
    )
    with pytest.raises(PublicationRejected):
        publish(tmp_path, invalid, dashboard_path=dashboard)
    assert read_json(dashboard) == {"sentinel": True}


def test_rolling_memory_counts_trading_days_not_calendar_days(fixture_file, target_date):
    base = build_snapshot(FixtureProvider(fixture_file), target_date)
    history = []
    for offset in (0, 1, 4):
        day = target_date + timedelta(days=offset)
        history.append(DailySnapshot(
            day,
            tuple(_dated(row, day) for row in base.listed),
            tuple(_dated(row, day) for row in base.otc),
            base.generated_at, base.source_health,
        ))
    memory = rolling_20d(history)
    assert memory[0]["longest_streak"] == 3
    assert memory[0]["appearance_count"] == 3
    assert memory[0]["evidence_status"] == "partial"


def test_monthly_never_treats_missing_rank_as_zero(fixture_file, target_date):
    snapshot = build_snapshot(FixtureProvider(fixture_file), target_date)
    result = monthly_summary([snapshot], "2026-09")
    row = next(x for x in result["summary_rows"] if x["code"] == "1001")
    assert row["buy_top15_days"] == 1
    assert "unranked is not zero" in result["limitations"]
    assert result["coverage_status"] == "partial"
    assert row["longest_streak"] == 1
    assert "monthly_capital_percent" in row
    assert "classification" in row


def test_month_first_report_does_not_require_same_day_market_data(tmp_path, fixture_file, target_date):
    snapshot = build_snapshot(FixtureProvider(fixture_file), target_date)
    publish(tmp_path, snapshot, dashboard_path=tmp_path / "dashboard.json")
    outputs = run_calendar_reports(tmp_path, date(2026, 10, 1))
    assert outputs[0].name == "2026-09.md"
    assert "partial" in outputs[0].read_text(encoding="utf-8")


def test_sunday_analysis_has_evidence_countercase_and_conditional_strategy(
    tmp_path, fixture_file, target_date
):
    base = build_snapshot(FixtureProvider(fixture_file), target_date)
    for offset in (0, 1, 2):
        day = target_date + timedelta(days=offset)
        publish(tmp_path, DailySnapshot(
            day,
            tuple(_dated(row, day) for row in base.listed),
            tuple(_dated(row, day) for row in base.otc),
            base.generated_at, base.source_health,
        ))
    outputs = run_calendar_reports(tmp_path, date(2026, 9, 6))
    report = next(path for path in outputs if path.parent.name == "analysis")
    text = report.read_text(encoding="utf-8")
    for required in ("反證", "3 個驗證指標", "試單觸發", "失效／停損", "不交易情境", "ETF／其他資金流附錄"):
        assert required in text
    assert (tmp_path / "reports/main-force-chips/analysis-latest.md").read_text(encoding="utf-8") == text


def _dated(row, day):
    values = row.to_dict()
    values["ranking_date"] = values["quote_date"] = day.isoformat()
    if values["denominator_date"]:
        values["denominator_date"] = day.isoformat()
    return type(row).from_dict(values)
