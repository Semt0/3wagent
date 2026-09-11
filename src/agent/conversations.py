"""Durable storage for WebUI conversations.

Conversation history is intentionally separate from ``workspace/<run_id>``:
run directories describe one agent execution, while a conversation can span
many executions.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.config.runtime import WORKSPACE_DIR

SCHEMA_VERSION = 1
UNTITLED = "新对话"


def _jsonable(value: Any) -> Any:
    """Convert qwen-agent/pydantic values into plain JSON values."""
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(exclude_none=True))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def conversation_title(messages: Iterable[dict], limit: int = 36) -> str:
    """Build a compact title from the first textual user message."""
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content", "")
        if isinstance(content, list):
            text = " ".join(
                str(item.get("text", ""))
                for item in content
                if isinstance(item, dict) and item.get("text")
            )
        else:
            text = str(content)
        text = " ".join(text.split())
        if text:
            return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
    return UNTITLED


class ConversationStore:
    """JSON-file conversation repository with atomic writes."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root is not None else WORKSPACE_DIR / "conversations"
        self._lock = threading.RLock()

    def create(self, messages: Iterable[dict] = ()) -> str:
        conversation_id = uuid.uuid4().hex
        self.save(conversation_id, messages, create=True)
        return conversation_id

    def save(
        self,
        conversation_id: str,
        messages: Iterable[dict],
        *,
        create: bool = False,
    ) -> dict:
        self._validate_id(conversation_id)
        plain_messages = _jsonable(list(messages))
        now = datetime.now(UTC).isoformat()
        with self._lock:
            existing = None if create else self._read(conversation_id)
            record = {
                "version": SCHEMA_VERSION,
                "id": conversation_id,
                "title": conversation_title(plain_messages),
                "created_at": (existing or {}).get("created_at", now),
                "updated_at": now,
                "messages": plain_messages,
            }
            self.root.mkdir(parents=True, exist_ok=True)
            target = self.root / f"{conversation_id}.json"
            temporary = target.with_suffix(f".{uuid.uuid4().hex}.tmp")
            temporary.write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(temporary, target)
        return record

    def load(self, conversation_id: str) -> dict:
        self._validate_id(conversation_id)
        with self._lock:
            record = self._read(conversation_id)
        if record is None:
            raise FileNotFoundError(f"Conversation not found: {conversation_id}")
        return record

    def list(self) -> list[dict]:
        """Return valid conversations newest first, without message bodies."""
        if not self.root.exists():
            return []
        summaries = []
        with self._lock:
            for path in self.root.glob("*.json"):
                try:
                    record = json.loads(path.read_text(encoding="utf-8"))
                    self._validate_record(record)
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
                summaries.append({key: record[key] for key in (
                    "id", "title", "created_at", "updated_at"
                )})
        return sorted(summaries, key=lambda item: item["updated_at"], reverse=True)

    def _read(self, conversation_id: str) -> dict | None:
        path = self.root / f"{conversation_id}.json"
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        self._validate_record(record)
        return record

    @staticmethod
    def _validate_id(conversation_id: str) -> None:
        if not isinstance(conversation_id, str) or not conversation_id:
            raise ValueError("conversation_id must be a non-empty string")
        if any(char not in "0123456789abcdef" for char in conversation_id):
            raise ValueError("Invalid conversation_id")

    @staticmethod
    def _validate_record(record: dict) -> None:
        required = {"version", "id", "title", "created_at", "updated_at", "messages"}
        if not isinstance(record, dict) or not required.issubset(record):
            raise ValueError("Invalid conversation record")
        if record["version"] != SCHEMA_VERSION or not isinstance(record["messages"], list):
            raise ValueError("Unsupported conversation record")
