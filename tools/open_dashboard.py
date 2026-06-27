#!/usr/bin/env python3
"""Open the 3wagent dashboard in the browser.

Cross-platform launcher that starts the FastAPI backend (if not already running)
and opens the default browser. Works on macOS, Linux, and Windows.

Usage:
    uv run python tools/open_dashboard.py
    python tools/open_dashboard.py        # if .venv is already activated
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8080
URL = f"http://{HOST}:{PORT}"


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _find_python() -> Path:
    """Return the venv Python interpreter or fall back to sys.executable."""
    root = _root()
    # macOS / Linux
    candidate = root / ".venv" / "bin" / "python"
    if candidate.exists():
        return candidate
    # Windows
    candidate = root / ".venv" / "Scripts" / "python.exe"
    if candidate.exists():
        return candidate
    return Path(sys.executable)


def _is_server_running(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def _start_server(log_path: Path | None = None) -> int:
    """Start uvicorn in the background and return the PID."""
    python = _find_python()
    root = _root()
    if log_path is None:
        log_path = root / "runs" / ".dashboard-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with log_path.open("a") as f:
        proc = subprocess.Popen(
            [str(python), "-m", "uvicorn", "server.app:app", "--host", HOST, "--port", str(PORT)],
            cwd=root,
            stdout=f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return proc.pid


def _wait_for_server(timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _is_server_running(HOST, PORT):
            return True
        time.sleep(0.25)
    return False


def open_dashboard(launch: bool = True, verbose: bool = True) -> int:
    """Start the backend if needed and open the browser."""
    if verbose:
        print(f"3wagent dashboard: {URL}")

    if _is_server_running(HOST, PORT):
        if verbose:
            print("Server is already running.")
    elif launch:
        if verbose:
            print("Starting server...")
        pid = _start_server()
        if verbose:
            print(f"Server started (PID: {pid})")
        if not _wait_for_server():
            print("ERROR: Server did not start within timeout.", file=sys.stderr)
            return 1
    else:
        if verbose:
            print("Server not running and --no-launch specified.")
            print("You can start it manually with:")
            print(f"  uv run python -m uvicorn server.app:app --host {HOST} --port {PORT}")
        return 0

    if verbose:
        print("Opening browser...")
    webbrowser.open(URL)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-launch",
        dest="launch",
        action="store_false",
        default=True,
        help="Do not start the server if it is not already running.",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress output.")
    args = parser.parse_args(argv or sys.argv[1:])
    return open_dashboard(launch=args.launch, verbose=not args.quiet)


if __name__ == "__main__":
    raise SystemExit(main())
