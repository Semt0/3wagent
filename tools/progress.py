#!/usr/bin/env python3
"""Progress tracking for 3wagent runs.

Claude Code calls this CLI at each workflow step to write status and events
under runs/YYYYMMDD-topic/. The dashboard frontend reads these files.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = ROOT / "runs"

DEFAULT_STEPS = [
    "frame",
    "parse",
    "retrieve",
    "validate",
    "analyze-funds",
    "analyze-tax",
    "analyze-commercial",
    "verify",
    "synthesize",
    "archive",
]


@dataclass
class ProgressEvent:
    timestamp: str
    step: str
    status: str
    agent: str | None = None
    message: str | None = None


@dataclass
class RunStatus:
    run_id: str
    title: str
    status: str
    started_at: str
    current_step: str
    progress_pct: int
    completed_at: str | None = None
    report_id: str | None = None
    error: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_dir(run_id: str) -> Path:
    return RUNS_ROOT / run_id


def _ensure_run_dir(run_id: str) -> Path:
    run_dir = _run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _status_path(run_id: str) -> Path:
    return _ensure_run_dir(run_id) / "status.json"


def _progress_path(run_id: str) -> Path:
    return _ensure_run_dir(run_id) / "progress.jsonl"


def _load_status(run_id: str) -> dict[str, Any]:
    path = _status_path(run_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _compute_progress(step: str, status: str) -> int:
    """Rough progress percentage based on step position and status."""
    try:
        idx = DEFAULT_STEPS.index(step)
    except ValueError:
        idx = len(DEFAULT_STEPS) - 1
    base = int((idx / len(DEFAULT_STEPS)) * 100)
    if status == "completed":
        return min(base + 10, 100)
    return base


def start_run(run_id: str, title: str) -> None:
    """Initialize a new run directory and status file."""
    _ensure_run_dir(run_id)
    status = RunStatus(
        run_id=run_id,
        title=title,
        status="running",
        started_at=_now(),
        current_step="frame",
        progress_pct=0,
    )
    _status_path(run_id).write_text(
        json.dumps(asdict(status), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _progress_path(run_id).write_text("", encoding="utf-8")
    log_step(run_id, step="frame", status="running", agent="lead-policy-agent", message="Framing issue")


def log_step(
    run_id: str,
    step: str,
    status: str,
    agent: str | None = None,
    message: str | None = None,
) -> None:
    """Append a progress event and update status.json."""
    event = ProgressEvent(
        timestamp=_now(),
        step=step,
        status=status,
        agent=agent,
        message=message,
    )
    progress_path = _progress_path(run_id)
    with progress_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    current = _load_status(run_id)
    if not current:
        return

    current["current_step"] = step
    current["progress_pct"] = _compute_progress(step, status)
    _status_path(run_id).write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def complete_run(run_id: str, report_id: str) -> None:
    """Mark a run as completed and link to the generated report."""
    log_step(run_id, step="archive", status="completed", agent="lead-policy-agent", message="Report archived")
    current = _load_status(run_id)
    current["status"] = "completed"
    current["completed_at"] = _now()
    current["report_id"] = report_id
    current["progress_pct"] = 100
    current["current_step"] = "archive"
    _status_path(run_id).write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fail_run(run_id: str, error: str) -> None:
    """Mark a run as failed."""
    log_step(run_id, step=(_load_status(run_id).get("current_step") or "unknown"), status="failed", message=error)
    current = _load_status(run_id)
    current["status"] = "failed"
    current["completed_at"] = _now()
    current["error"] = error
    _status_path(run_id).write_text(
        json.dumps(current, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track 3wagent run progress.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Start a new run")
    start.add_argument("--run-id", required=True)
    start.add_argument("--title", required=True)
    start.add_argument("--open-dashboard", action="store_true", default=False, help="Open the dashboard in the browser after starting the run.")

    step = subparsers.add_parser("step", help="Log a step event")
    step.add_argument("--run-id", required=True)
    step.add_argument("--step", required=True)
    step.add_argument("--status", required=True, choices=["pending", "running", "completed", "failed"])
    step.add_argument("--agent", default=None)
    step.add_argument("--message", default=None)

    complete = subparsers.add_parser("complete", help="Mark run as completed")
    complete.add_argument("--run-id", required=True)
    complete.add_argument("--report-id", required=True)

    fail = subparsers.add_parser("fail", help="Mark run as failed")
    fail.add_argument("--run-id", required=True)
    fail.add_argument("--error", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv or sys.argv[1:])

    if args.command == "start":
        start_run(args.run_id, args.title)
        if args.open_dashboard:
            # Import lazily to avoid circular deps
            sys.path.insert(0, str(ROOT / "tools"))
            import open_dashboard
            open_dashboard.open_dashboard(verbose=False)
    elif args.command == "step":
        log_step(args.run_id, args.step, args.status, args.agent, args.message)
    elif args.command == "complete":
        complete_run(args.run_id, args.report_id)
    elif args.command == "fail":
        fail_run(args.run_id, args.error)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
