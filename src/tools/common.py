"""Shared path and parameter helpers for the file tools.

All tools take paths relative to the project root; resolution and
confinement live here so every tool enforces the same boundary.
"""

from pathlib import Path

import json5

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def parse_tool_params(params) -> dict:
    """Parse tool-call params, tolerating double-encoded JSON from the model.

    Small models sometimes emit `arguments` as a JSON-encoded string instead
    of a JSON object; unwrap one extra layer in that case.
    """
    if isinstance(params, dict):
        return params
    parsed = json5.loads(params)
    if isinstance(parsed, str):
        parsed = json5.loads(parsed)
    if not isinstance(parsed, dict):
        raise ValueError("arguments must be a JSON object")
    return parsed


def resolve_project_path(file_path: str) -> Path:
    """Resolve a project-root-relative path and confine it to the project root.

    Raises ValueError if the resolved path escapes the project root.
    """
    path = (PROJECT_ROOT / file_path.strip()).resolve()
    path.relative_to(PROJECT_ROOT)
    return path


def get_file_path_param(params: dict) -> str:
    """Extract the file path from tool params, tolerating common alias keys.

    Small models often guess 'path' or 'file' instead of the declared 'file_path'.
    """
    for key in ("file_path", "path", "file", "absolute_address"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raise KeyError("file_path")
