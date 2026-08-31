"""Terminate qwen-agent tool loops on explicitly terminal tool results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

TERMINAL_TOOL_CODES = {
    "already_fetched",
    "fetch_budget_exhausted",
    "previous_fetch_failed",
    "search_budget_exhausted",
}


@dataclass
class TerminalToolResult(RuntimeError):
    tool_name: str
    result: str
    code: str


def raise_for_terminal_tool_result(tool_name: str, result: Any) -> None:
    if not isinstance(result, str):
        return
    try:
        payload = json.loads(result)
    except (TypeError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return
    error = payload.get("error")
    code = str(error.get("code") or "") if isinstance(error, dict) else ""
    if code in TERMINAL_TOOL_CODES:
        raise TerminalToolResult(tool_name=tool_name, result=result, code=code)


def terminal_finalize_prompt(exc: TerminalToolResult) -> str:
    return (
        f'Tool "{exc.tool_name}" returned terminal status "{exc.code}":\n'
        f"{exc.result}\n\n"
        "The tool loop has been stopped. Do not call any tool again. Use the evidence already "
        "in the conversation and produce the complete final response now."
    )
