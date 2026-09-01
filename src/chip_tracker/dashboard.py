from __future__ import annotations

from chip_tracker.memory import monthly_summary, previous_month, rolling_20d
from chip_tracker.models import DailySnapshot
from chip_tracker.validator import ValidationResult


def _public_row(row) -> dict:
    data = row.to_dict()
    # Stable public-schema alias used by the static UI contract.  Keep the
    # more specific ranking_date/quote_date fields for audit detail.
    data["source_date"] = data["ranking_date"]
    return data


def dashboard_payload(
    latest: DailySnapshot,
    history: list[DailySnapshot],
    qa: ValidationResult,
) -> dict:
    latest_rows = [*latest.listed, *latest.otc]
    denominator_dates = sorted({
        row.denominator_date.isoformat()
        for row in latest_rows if row.denominator_date is not None
    })
    overall_status = (
        "unavailable" if not qa.passed
        else "confirmed" if all(row.evidence_status.value == "confirmed" for row in latest_rows)
        else "partial"
    )
    return {
        "generated_at": latest.generated_at.isoformat(),
        "data_date": latest.data_date.isoformat(),
        "status": overall_status,
        "market_summary": {
            "TWSE": {"rows": len(latest.listed), "validated": qa.passed},
            "TPEx": {"rows": len(latest.otc), "validated": qa.passed},
        },
        "latest": {
            "listed": [_public_row(row) for row in latest.listed],
            "otc": [_public_row(row) for row in latest.otc],
        },
        "rolling_20d": rolling_20d(history),
        "monthly": monthly_summary(history, previous_month(latest.data_date)),
        "report_links": {
            "daily": f"reports/main-force-chips/daily/{latest.data_date.isoformat()}.md",
            "weekly": "reports/main-force-chips/weekly-latest.md",
            "analysis": "reports/main-force-chips/analysis-latest.md",
            "monthly": "reports/main-force-chips/monthly-latest.md",
        },
        "quality": {
            "listed_rows": len(latest.listed),
            "otc_rows": len(latest.otc),
            "formula_errors": len(qa.errors),
            "date_coverage": [item.data_date.isoformat() for item in history[-20:]],
            "denominator_dates": denominator_dates,
            "source_health": latest.source_health,
            "latest_qa_result": qa.to_dict(),
        },
    }
