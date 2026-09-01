from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from chip_tracker.memory import load_snapshots
from chip_tracker.pipeline import run_calendar_reports, run_pipeline
from chip_tracker.reports import write_monthly_report
from chip_tracker.seed import import_reports
from chip_tracker.sources import FixtureProvider, LiveProvider, SourceError
from chip_tracker.storage import write_json_atomic


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="chip-tracker")
    result.add_argument("--root", type=Path, default=Path.cwd())
    commands = result.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--date", dest="target_date")
    run.add_argument("--fixture", type=Path)
    run.add_argument("--dashboard-path", type=Path)
    seed = commands.add_parser("seed")
    seed.add_argument("--reports-root", type=Path, required=True)
    monthly = commands.add_parser("rebuild-month")
    monthly.add_argument("month")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = args.root.resolve()
    if args.command == "seed":
        imported = import_reports(root, args.reports_root.resolve())
        print(json.dumps({"imported": len(imported)}, ensure_ascii=False))
        return 0
    if args.command == "rebuild-month":
        history = load_snapshots(root / "data" / "observations")
        target = write_monthly_report(root, history, args.month)
        print(target)
        return 0
    target = (
        datetime.strptime(args.target_date, "%Y-%m-%d").date()
        if args.target_date else datetime.now(ZoneInfo("Asia/Taipei")).date()
    )
    provider = FixtureProvider(args.fixture) if args.fixture else LiveProvider()
    scheduled_outputs = run_calendar_reports(root, target)
    if target.weekday() >= 5:
        print(json.dumps({
            "status": "no_new_data",
            "data_date": None,
            "scheduled_reports": [str(path) for path in scheduled_outputs],
        }, ensure_ascii=False))
        return 0
    try:
        payload = run_pipeline(root, provider, target, dashboard_path=args.dashboard_path)
    except SourceError as exc:
        write_json_atomic(root / "data" / "run-status" / f"{target}.json", {
            "data_date": target.isoformat(), "published": False,
            "status": "no_new_data", "error": str(exc),
        })
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"status": payload["status"], "data_date": payload["data_date"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
