"""Terminate qwen-agent tool loops on explicitly terminal tool results."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from qwen_agent.llm.schema import ASSISTANT, USER, Message

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


def tool_free_finalize_messages(
    messages: list[Message],
    response: list[Message],
    prompt: str,
) -> list[Message]:
    """Build valid history for a final LLM call with functions disabled.

    A terminal tool result interrupts ``FnCallAgent`` after it has emitted the
    assistant's function call but before it can append the matching function
    response. Sending that unresolved tail to an OpenAI-compatible endpoint
    can produce HTTP 400 because it becomes an empty assistant message. Pure
    reasoning stream fragments have the same problem on stricter servers.

    Drop only the unresolved assistant tail and empty reasoning-only assistant
    messages. Completed tool-call/response pairs and their evidence remain in
    the history.
    """
    history = copy.deepcopy(messages + response)

    # The interrupted call has no FUNCTION response, so it is safe to remove.
    # A reasoning-only fragment may immediately precede it in streamed output.
    while history and history[-1].role == ASSISTANT:
        last = history[-1]
        if last.function_call or not _message_has_text(last):
            history.pop()
            continue
        break

    history = [
        message
        for message in history
        if not (
            message.role == ASSISTANT
            and not _message_has_text(message)
            and not message.function_call
        )
    ]
    history.append(Message(USER, prompt))
    return history


def _message_has_text(message: Message) -> bool:
    content = message.content
    if isinstance(content, str):
        return bool(content.strip())
    return any((item.text or '').strip() for item in content or [])
