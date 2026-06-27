"""Minimal backend for the 3wagent dashboard.

This server is intentionally thin: it only serves the static viewer and reads
progress logs produced by Claude Code. All analysis logic remains in the
existing agent workflow.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

import mcp_server.server as mcp_server_module

ROOT = Path(__file__).resolve().parents[1]
REPORTS_ROOT = ROOT / "reports"
VIEWER_ROOT = ROOT / "viewer"
RUNS_ROOT = ROOT / "runs"

app = FastAPI(title="3wagent Dashboard")


def _safe_report_dir(report_id: str) -> Path:
    """Resolve a report id under reports/ and reject path traversal."""
    if not report_id or Path(report_id).name != report_id or report_id in {".", ".."}:
        raise HTTPException(status_code=400, detail=f"Invalid report id: {report_id}")

    report_dir = REPORTS_ROOT / report_id
    reports_root = REPORTS_ROOT.resolve()
    try:
        report_dir.resolve().relative_to(reports_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid report id: {report_id}") from exc
    return report_dir


def _read_report_markdown(report_id: str) -> str:
    report_dir = _safe_report_dir(report_id)
    if not report_dir.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")

    markdown_path = report_dir / "report.md"
    if not markdown_path.exists():
        raise HTTPException(status_code=404, detail=f"No report.md in {report_id}")
    return markdown_path.read_text(encoding="utf-8")


@app.get("/api/runs")
async def api_runs():
    """List all tracked runs under runs/."""
    if not RUNS_ROOT.exists():
        return []
    runs = []
    for run_dir in sorted(RUNS_ROOT.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        status_path = run_dir / "status.json"
        if not status_path.exists():
            continue
        status = json.loads(status_path.read_text(encoding="utf-8"))
        runs.append(
            {
                "run_id": run_dir.name,
                "title": status.get("title", run_dir.name),
                "status": status.get("status", "unknown"),
                "progress_pct": status.get("progress_pct", 0),
                "started_at": status.get("started_at"),
                "completed_at": status.get("completed_at"),
                "current_step": status.get("current_step"),
                "report_id": status.get("report_id"),
            }
        )
    return runs


@app.get("/api/runs/{run_id}/progress")
async def api_run_progress(run_id: str):
    """Return status and progress timeline for a run."""
    run_dir = RUNS_ROOT / run_id
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    status_path = run_dir / "status.json"
    progress_path = run_dir / "progress.jsonl"

    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    events = []
    if progress_path.exists():
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))

    return {"status": status, "events": events}


@app.get("/api/reports")
async def api_reports():
    """List archived reports."""
    reports_json = await mcp_server_module.report_artifact_list()
    return json.loads(reports_json)


@app.get("/api/reports/{report_id}")
async def api_report(report_id: str):
    """Read a report's Markdown content."""
    content = _read_report_markdown(report_id)
    return {"report_id": report_id, "content": content}


@app.get("/api/reports/{report_id}/markdown", response_class=PlainTextResponse)
async def api_report_markdown(report_id: str):
    """Return raw Markdown for browser tabs and direct links."""
    return _read_report_markdown(report_id)


@app.delete("/api/reports/{report_id}")
async def api_delete_report(report_id: str):
    """Delete a report folder and its associated run data.

    This is a hard delete and cannot be undone.
    """
    report_dir = _safe_report_dir(report_id)
    if not report_dir.exists():
        raise HTTPException(status_code=404, detail=f"Report not found: {report_id}")

    shutil.rmtree(report_dir)

    # Also delete associated run if it exists
    run_dir = RUNS_ROOT / report_id
    if run_dir.exists():
        shutil.rmtree(run_dir)

    return {"deleted": report_id}


# Serve the static viewer at root
if VIEWER_ROOT.exists():
    app.mount("/", StaticFiles(directory=VIEWER_ROOT, html=True), name="viewer")
