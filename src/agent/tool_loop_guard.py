"""Terminate qwen-agent tool loops on explicitly terminal tool results."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from qwen_agent.llm.schema import ASSISTANT, FUNCTION, USER, Message

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


def drop_unresolved_tool_calls(messages: list[Message]) -> list[Message]:
    """Pair assistant function-call groups with their function responses.

    ``FnCallAgent`` appends a function response right after each completed
    tool call, so when a terminal result interrupts a round of parallel calls,
    the unresolved calls sit *before* the responses of their completed
    siblings (fc1, fc2, fc3, func1, func2). They are not at the tail, and at
    the OAI boundary the group merges into one assistant message whose
    ``tool_calls`` outnumber the following tool messages — strict providers
    then reject the whole request with HTTP 400.

    Pair each call group with responses in order and drop unpaired calls and
    orphan responses.
    """
    cleaned: list[Message] = []
    i = 0
    n = len(messages)
    while i < n:
        message = messages[i]
        if message.role == ASSISTANT and message.function_call:
            group: list[Message] = []
            while i < n and messages[i].role == ASSISTANT and messages[i].function_call:
                group.append(messages[i])
                i += 1
            responses: list[Message] = []
            while i < n and messages[i].role == FUNCTION:
                responses.append(messages[i])
                i += 1
            for call, response in zip(group, responses):
                if call.function_call.name != response.name:
                    break
                cleaned.append(call)
                cleaned.append(response)
            # Unpaired calls and orphan responses are dropped.
        else:
            cleaned.append(message)
            i += 1
    return cleaned


def tool_free_finalize_messages(
    messages: list[Message],
    response: list[Message],
    prompt: str,
) -> list[Message]:
    """Build valid history for a final LLM call with functions disabled.

    A terminal tool result interrupts ``FnCallAgent`` mid-round, leaving
    assistant function calls without matching responses anywhere in the round
    tail. Sending those to an OpenAI-compatible endpoint produces HTTP 400.

    Drop unresolved calls (see ``drop_unresolved_tool_calls``), then strip the
    now-dangling assistant tail. Preserve reasoning attached to completed
    tool-call/response pairs: thinking-mode APIs require that exact
    ``reasoning_content`` to be passed back with the tool call.
    """
    history = drop_unresolved_tool_calls(copy.deepcopy(messages + response))

    # Remove the dangling assistant tail (empty fragments and any call whose
    # response was dropped above).
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
            and not message.reasoning_content
        )
    ]
    history.append(Message(USER, prompt))
    return history


def sanitize_response_tail(response: list[Message]) -> list[Message]:
    """Drop unresolved tool calls from a response before it is persisted.

    Frontends persist the yielded frames as conversation history, and strict
    OpenAI-compatible APIs reject the next request when an assistant
    ``tool_calls`` message has no following tool message (HTTP 400). Apply the
    same cleanup as ``tool_free_finalize_messages`` to the response itself so
    saved history stays valid.
    """
    cleaned = drop_unresolved_tool_calls(response)

    while cleaned and cleaned[-1].role == ASSISTANT:
        last = cleaned[-1]
        if last.function_call or not _message_has_text(last):
            cleaned.pop()
            continue
        break

    return [
        message
        for message in cleaned
        if not (
            message.role == ASSISTANT
            and not _message_has_text(message)
            and not message.function_call
            and not message.reasoning_content
        )
    ]


def _message_has_text(message: Message) -> bool:
    content = message.content
    if isinstance(content, str):
        return bool(content.strip())
    return any((item.text or '').strip() for item in content or [])
