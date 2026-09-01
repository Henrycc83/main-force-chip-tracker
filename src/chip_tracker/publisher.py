from __future__ import annotations

from pathlib import Path

from chip_tracker.dashboard import dashboard_payload
from chip_tracker.memory import load_snapshots
from chip_tracker.models import DailySnapshot
from chip_tracker.storage import write_json_atomic
from chip_tracker.validator import validate_snapshot


class PublicationRejected(RuntimeError):
    pass


def observation_path(root: Path, snapshot: DailySnapshot) -> Path:
    day = snapshot.data_date
    return root / "data" / "observations" / f"{day:%Y}" / f"{day:%m}" / f"{day}.json"


def publish(root: Path, snapshot: DailySnapshot, *, dashboard_path: Path | None = None) -> dict:
    qa = validate_snapshot(snapshot)
    if not qa.passed:
        raise PublicationRejected("; ".join(qa.errors))
    obs_path = observation_path(root, snapshot)
    write_json_atomic(obs_path, snapshot.to_dict())
    history = load_snapshots(root / "data" / "observations")
    payload = dashboard_payload(snapshot, history, qa)
    target = dashboard_path or root / "docs" / "data" / "dashboard.json"
    write_json_atomic(target, payload)
    write_json_atomic(root / "data" / "state" / "rolling-20d.json", payload["rolling_20d"])
    write_json_atomic(root / "data" / "run-status" / f"{snapshot.data_date}.json", {
        "data_date": snapshot.data_date.isoformat(), "published": True, "qa": qa.to_dict()
    })
    return payload

