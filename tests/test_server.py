"""Tests for server/app.py endpoints."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import server.app as server_app


@pytest.fixture
def client(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        monkeypatch.setattr(server_app, "RUNS_ROOT", tmp_path / "runs")
        monkeypatch.setattr(server_app, "REPORTS_ROOT", tmp_path / "reports")
        monkeypatch.setattr(server_app, "VIEWER_ROOT", tmp_path / "viewer")
        yield TestClient(server_app.app)


def test_api_runs_empty(client):
    res = client.get("/api/runs")
    assert res.status_code == 200
    assert res.json() == []


def test_api_delete_report_and_run(client):
    report_dir = server_app.REPORTS_ROOT / "20260601-test"
    report_dir.mkdir(parents=True)
    (report_dir / "report.md").write_text("# Test", encoding="utf-8")

    run_dir = server_app.RUNS_ROOT / "20260601-test"
    run_dir.mkdir(parents=True)
    (run_dir / "status.json").write_text('{"status":"completed"}', encoding="utf-8")

    res = client.delete("/api/reports/20260601-test")
    assert res.status_code == 200
    assert res.json()["deleted"] == "20260601-test"

    assert not report_dir.exists()
    assert not run_dir.exists()


def test_api_report_returns_json_content(client):
    report_dir = server_app.REPORTS_ROOT / "20260601-test"
    report_dir.mkdir(parents=True)
    (report_dir / "report.md").write_text("# Test\n\nHello", encoding="utf-8")

    res = client.get("/api/reports/20260601-test")
    assert res.status_code == 200
    assert res.json() == {"report_id": "20260601-test", "content": "# Test\n\nHello"}


def test_api_report_markdown_returns_plain_text(client):
    report_dir = server_app.REPORTS_ROOT / "20260601-test"
    report_dir.mkdir(parents=True)
    (report_dir / "report.md").write_text("# Test\n\nHello", encoding="utf-8")

    res = client.get("/api/reports/20260601-test/markdown")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert res.text == "# Test\n\nHello"


def test_api_rejects_invalid_report_id(client):
    with pytest.raises(HTTPException) as exc_info:
        server_app._safe_report_dir("..")

    assert exc_info.value.status_code == 400


def test_api_delete_report_not_found(client):
    res = client.delete("/api/reports/missing")
    assert res.status_code == 404
