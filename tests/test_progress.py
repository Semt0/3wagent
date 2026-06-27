"""Tests for tools/progress.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from progress import complete_run, fail_run, log_step, start_run


def test_start_run_writes_status_and_progress(tmp_path, monkeypatch):
    import progress as progress_module

    monkeypatch.setattr(progress_module, "RUNS_ROOT", tmp_path)
    start_run("20260601-test", "Test Run")

    status = json.loads((tmp_path / "20260601-test" / "status.json").read_text(encoding="utf-8"))
    assert status["run_id"] == "20260601-test"
    assert status["title"] == "Test Run"
    assert status["status"] == "running"
    assert status["current_step"] == "frame"

    events = (tmp_path / "20260601-test" / "progress.jsonl").read_text(encoding="utf-8").strip()
    assert "frame" in events
    assert "running" in events


def test_log_step_updates_status(tmp_path, monkeypatch):
    import progress as progress_module

    monkeypatch.setattr(progress_module, "RUNS_ROOT", tmp_path)
    start_run("20260601-test", "Test Run")
    log_step("20260601-test", "retrieve", "running", "rag-retriever", "Searching sources")

    status = json.loads((tmp_path / "20260601-test" / "status.json").read_text(encoding="utf-8"))
    assert status["current_step"] == "retrieve"
    assert status["progress_pct"] > 0


def test_complete_run(tmp_path, monkeypatch):
    import progress as progress_module

    monkeypatch.setattr(progress_module, "RUNS_ROOT", tmp_path)
    start_run("20260601-test", "Test Run")
    complete_run("20260601-test", "20260601-test-report")

    status = json.loads((tmp_path / "20260601-test" / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "completed"
    assert status["report_id"] == "20260601-test-report"
    assert status["progress_pct"] == 100


def test_fail_run(tmp_path, monkeypatch):
    import progress as progress_module

    monkeypatch.setattr(progress_module, "RUNS_ROOT", tmp_path)
    start_run("20260601-test", "Test Run")
    fail_run("20260601-test", "Source unavailable")

    status = json.loads((tmp_path / "20260601-test" / "status.json").read_text(encoding="utf-8"))
    assert status["status"] == "failed"
    assert status["error"] == "Source unavailable"
