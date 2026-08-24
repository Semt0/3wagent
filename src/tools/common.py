"""Shared path helper for the file tools.

All tools take paths relative to the project root; resolution and
confinement live here so every tool enforces the same boundary.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_project_path(file_path: str) -> Path:
    """Resolve a project-root-relative path and confine it to the project root.

    Raises ValueError if the resolved path escapes the project root.
    """
    path = (PROJECT_ROOT / file_path.strip()).resolve()
    path.relative_to(PROJECT_ROOT)
    return path
