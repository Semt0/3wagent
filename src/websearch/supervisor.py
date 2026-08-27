"""Lifecycle management for the bundled open-websearch daemon."""

from __future__ import annotations

import atexit
import logging
import os
import subprocess
import time
from dataclasses import replace
from typing import Self
from urllib.parse import urlparse

from src.config.websearch import WebSearchSettings
from src.tools.common import PROJECT_ROOT
from src.websearch.client import OpenWebSearchClient, OpenWebSearchError

LOGGER = logging.getLogger(__name__)


class OpenWebSearchSupervisor:
    """Start a bundled daemon when needed and stop only the owned process."""

    def __init__(self, settings: WebSearchSettings | None = None) -> None:
        self.settings = settings or WebSearchSettings.from_env()
        self.process: subprocess.Popen | None = None
        self._log_file = None
        self._atexit_registered = False

    @property
    def owns_process(self) -> bool:
        return self.process is not None

    def start(self) -> bool:
        """Ensure the configured daemon is ready; return whether it was started here."""
        if not self.settings.auto_start:
            LOGGER.info("open-websearch autostart is disabled")
            return False

        parsed = urlparse(self.settings.base_url)
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            LOGGER.info("open-websearch uses a remote service; skipping local autostart")
            return False

        if self._daemon_ready():
            LOGGER.info("reusing open-websearch daemon at %s", self.settings.base_url)
            return False

        runtime_dir = PROJECT_ROOT / "infra" / "open-websearch"
        executable = runtime_dir / "node_modules" / ".bin" / "open-websearch"
        if not executable.is_file():
            raise RuntimeError(
                "open-websearch is not installed; run "
                "`npm ci --prefix src/infra/open-websearch` first"
            )

        log_dir = PROJECT_ROOT / "workspace" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = (log_dir / "open-websearch.log").open("a", encoding="utf-8")
        env = os.environ.copy()
        env.setdefault("DEFAULT_SEARCH_ENGINE", "bing")
        env.setdefault("ALLOWED_SEARCH_ENGINES", "bing,duckduckgo,startpage,baidu,sogou")
        env.setdefault("SEARCH_MODE", "request")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        host = parsed.hostname or "127.0.0.1"
        self.process = subprocess.Popen(
            [str(executable), "serve", "--host", host, "--port", str(port)],
            cwd=runtime_dir,
            env=env,
            stdout=self._log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        atexit.register(self.stop)
        self._atexit_registered = True

        deadline = time.monotonic() + self.settings.startup_timeout_seconds
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.stop()
                raise RuntimeError(
                    "open-websearch exited during startup; see "
                    "src/workspace/logs/open-websearch.log"
                )
            if self._daemon_ready():
                LOGGER.info("started open-websearch daemon at %s", self.settings.base_url)
                return True
            time.sleep(0.1)

        self.stop()
        raise RuntimeError(
            "open-websearch did not become ready within "
            f"{self.settings.startup_timeout_seconds}s; see "
            "src/workspace/logs/open-websearch.log"
        )

    def stop(self) -> None:
        """Stop the daemon only when this supervisor started it."""
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None
        if self._atexit_registered:
            atexit.unregister(self.stop)
            self._atexit_registered = False

    def _daemon_ready(self) -> bool:
        probe_settings = replace(self.settings, timeout_seconds=min(self.settings.timeout_seconds, 1))
        try:
            OpenWebSearchClient(probe_settings).status()
        except OpenWebSearchError:
            return False
        return True

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()
