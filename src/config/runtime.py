"""Runtime state for the current run.

Each run (one user question) gets its own directory under workspace/:
    workspace/<run_id>/logs/         - debug logs
    workspace/<run_id>/sub_agents/   - sub-agent result files
run_id is a timestamp for now, e.g. 20260826-143052.
"""

from datetime import datetime
from pathlib import Path

from src.tools.common import PROJECT_ROOT

WORKSPACE_DIR = PROJECT_ROOT / 'workspace'

_run_id: str | None = None


def new_run_id() -> str:
    """Start a new run: generate a timestamp run_id and create its directories."""
    global _run_id
    _run_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    run_dir = get_run_dir()
    (run_dir / 'logs').mkdir(parents=True, exist_ok=True)
    (run_dir / 'sub_agents').mkdir(parents=True, exist_ok=True)
    return _run_id


def get_run_id() -> str:
    """Current run_id; starts a new run lazily if none is active."""
    if _run_id is None:
        return new_run_id()
    return _run_id


def get_run_dir() -> Path:
    return WORKSPACE_DIR / get_run_id()


def get_subagents_dir() -> Path:
    return get_run_dir() / 'sub_agents'


def get_logs_dir() -> Path:
    return get_run_dir() / 'logs'


def get_run_dir_relative() -> Path:
    """Run directory relative to the project root (for model-facing prompts)."""
    return Path('workspace') / get_run_id()
