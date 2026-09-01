from chip_tracker.seed import parse_daily_report


def test_existing_daily_report_can_be_seeded():
    from pathlib import Path
    report = Path(__file__).parents[2] / "reports/main-force-chips/daily/2026-08-31.md"
    if not report.exists():
        return
    snapshot = parse_daily_report(report)
    assert len(snapshot.listed) == 15
    assert len(snapshot.otc) == 15
    assert snapshot.listed[0].code == "6770"
    assert snapshot.otc[0].code == "00937B"

