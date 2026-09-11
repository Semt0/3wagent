"""Provider-neutral capture and persistence of agent results."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import json5
from qwen_agent.llm.schema import ASSISTANT, Message


class AgentResultError(RuntimeError):
    """Raised when an agent completed without a usable result."""


def extract_last_assistant_text(
    messages: list[Message],
    *,
    agent_name: str | None = None,
) -> str:
    """Return the latest non-empty assistant text, independent of tool use."""
    for message in reversed(messages or []):
        if message.role != ASSISTANT:
            continue
        if message.function_call:
            continue
        if agent_name and message.name and message.name != agent_name:
            continue
        content = message.content
        if isinstance(content, str):
            if content.strip():
                return content
            continue
        text = "".join(_content_item_text(item) for item in content or [])
        if text.strip():
            return text
    return ""


def persist_text_result(messages: list[Message], output_path: Path) -> str:
    """Capture direct model text and persist it without requiring a write tool."""
    text = extract_last_assistant_text(messages)
    if not text.strip() and output_path.exists():
        text = output_path.read_text(encoding="utf-8")
    if not text.strip():
        raise AgentResultError(f"agent produced no text result for {output_path}")
    write_text_result(output_path, text)
    return text


def write_text_result(output_path: Path, text: str) -> None:
    """Atomically persist already-captured agent text."""
    _atomic_write_text(output_path, text)


def resolve_structured_result(
    messages: list[Message],
    output_path: Path,
    expected_type: type,
) -> Any:
    """Resolve JSON from direct output or a tool-written compatibility file.

    Direct assistant output is preferred. A file produced by ``WriteResult``
    remains supported for older prompts/providers, but it is never required.
    The validated value is always persisted by the runtime for observability.
    """
    candidates: list[tuple[str, str]] = []
    direct = extract_last_assistant_text(messages)
    if direct.strip():
        candidates.append(("assistant response", direct))
    if output_path.exists():
        file_text = output_path.read_text(encoding="utf-8")
        if file_text.strip() and file_text != direct:
            candidates.append(("result file", file_text))

    errors = []
    for source, text in candidates:
        try:
            result = _parse_json_text(text)
        except (TypeError, ValueError) as exc:
            errors.append(f"{source}: {exc}")
            continue
        if not isinstance(result, expected_type):
            errors.append(
                f"{source}: expected {expected_type.__name__}, got {type(result).__name__}"
            )
            continue
        _atomic_write_text(
            output_path,
            json.dumps(result, ensure_ascii=False, indent=2),
        )
        return result

    detail = "; ".join(errors) if errors else "no direct response or result file"
    raise AgentResultError(f"agent produced no valid structured result: {detail}")


def _parse_json_text(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        first_newline = stripped.find("\n")
        stripped = stripped[first_newline + 1 : -3].strip()

    try:
        return json5.loads(stripped)
    except (TypeError, ValueError):
        pass

    # Tolerate a short explanatory prefix/suffix while still requiring one
    # complete JSON object or array.
    starts = [index for index in (stripped.find("{"), stripped.find("[")) if index >= 0]
    if not starts:
        raise ValueError("response contains no JSON object or array")
    start = min(starts)
    closing = "}" if stripped[start] == "{" else "]"
    end = stripped.rfind(closing)
    if end <= start:
        raise ValueError("response contains incomplete JSON")
    try:
        return json5.loads(stripped[start : end + 1])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc


def _content_item_text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or "")
    return str(getattr(item, "text", "") or "")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
