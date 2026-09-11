"""Strict OpenAI-compatible transport fixes for Qwen-Agent messages."""

from __future__ import annotations

from typing import Any

from qwen_agent.llm.base import register_llm
from qwen_agent.llm.oai import TextChatAtOAI


@register_llm("strict_oai")
class StrictOpenAICompatibleModel(TextChatAtOAI):
    """Serialize tool results using the standard ``tool_call_id`` field.

    Qwen-Agent currently emits ``id`` plus internal ``extra`` metadata for a
    tool-result message. Lenient servers accept that shape, but strict
    OpenAI-compatible APIs reject it because ``tool_call_id`` is required.
    """

    @staticmethod
    def _conv_qwen_agent_messages_to_oai(messages: list[dict[str, Any]]) -> list[dict]:
        converted = TextChatAtOAI._conv_qwen_agent_messages_to_oai(messages)
        normalized: list[dict] = []
        for message in converted:
            if message.get("role") != "tool":
                normalized.append(message)
                continue
            function_id = message.get("id") or (message.get("extra") or {}).get(
                "function_id"
            )
            normalized.append(
                {
                    "role": "tool",
                    "content": message.get("content", ""),
                    "tool_call_id": function_id or "1",
                }
            )
        return normalized
