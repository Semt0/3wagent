"""Tests for tools/open_dashboard.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import open_dashboard


def test_start_server_uses_configured_host_and_port(tmp_path, monkeypatch):
    captured = {}

    class DummyProcess:
        pid = 12345

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return DummyProcess()

    monkeypatch.setattr(open_dashboard, "_find_python", lambda: Path("/tmp/python"))
    monkeypatch.setattr(open_dashboard.subprocess, "Popen", fake_popen)

    pid = open_dashboard._start_server(tmp_path / "server.log")

    assert pid == 12345
    assert captured["args"] == [
        "/tmp/python",
        "-m",
        "uvicorn",
        "server.app:app",
        "--host",
        open_dashboard.HOST,
        "--port",
        str(open_dashboard.PORT),
    ]
    assert captured["kwargs"]["start_new_session"] is True
