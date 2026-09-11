"""Normalize provider-specific textual tool calls at the model boundary."""

from __future__ import annotations

import copy
import html
import json
import re
from collections.abc import Iterator

import json5
from qwen_agent.llm.schema import ASSISTANT, ContentItem, FunctionCall, Message

_DSML_MARKER = r"[|｜]{1,2}DSML[|｜]{1,2}"
_DSML_INVOKE = re.compile(
    rf'<{_DSML_MARKER}\s+invoke\s+name=(?P<quote>["\'])(?P<name>.+?)(?P=quote)\s*>'
    rf"(?P<body>.*?)\\?</{_DSML_MARKER}\s+invoke\s*>",
    re.DOTALL,
)
_DSML_ARGUMENTS = re.compile(
    rf'<{_DSML_MARKER}\s+parameter\s+name=(?P<quote>["\'])arguments(?P=quote)'
    rf"(?:\s+string=(?:[\"\'])?(?:false|true)(?:[\"\'])?)?\s*>"
    rf"(?P<arguments>.*?)\\?</{_DSML_MARKER}\s+parameter\s*>",
    re.DOTALL,
)
_DSML_CALLS_TAG = re.compile(rf"\\?</?{_DSML_MARKER}\s+calls\s*>", re.DOTALL)
_TOOL_CALL = re.compile(r"<tool_call>\s*(?P<call>.*?)\s*</tool_call>", re.DOTALL)


class ToolCallCompatibilityMixin:
    """Convert known textual protocols before ``FnCallAgent`` sees output."""

    def _call_llm(
        self,
        messages: list[Message],
        functions: list[dict] | None = None,
        stream: bool = True,
        extra_generate_cfg: dict | None = None,
    ) -> Iterator[list[Message]]:
        output = super()._call_llm(
            messages=messages,
            functions=functions,
            stream=stream,
            extra_generate_cfg=extra_generate_cfg,
        )
        for frame in output:
            if functions:
                yield normalize_textual_tool_calls(frame)
            else:
                yield frame


def normalize_textual_tool_calls(messages: list[Message]) -> list[Message]:
    """Convert complete DeepSeek DSML invocations to Qwen ``FunctionCall`` messages.

    Native function-call messages and ordinary assistant text pass through
    unchanged. Incomplete or unrecognized DSML also remains text so this layer
    never invents an executable call from ambiguous output.
    """
    normalized: list[Message] = []
    for message in messages:
        if message.role != ASSISTANT or message.function_call:
            normalized.append(message)
            continue
        text = _message_text(message)
        matches, parsed_calls = _parse_dsml_calls(text)
        if not parsed_calls:
            matches, parsed_calls = _parse_tool_call_tags(text)

        if not parsed_calls:
            normalized.append(message)
            continue

        prefix = _DSML_CALLS_TAG.sub("", text[: matches[0].start()]).strip()
        if prefix:
            normalized.append(
                Message(
                    role=ASSISTANT,
                    content=prefix,
                    reasoning_content=message.reasoning_content,
                    name=message.name,
                    extra=copy.deepcopy(message.extra),
                )
            )
        for index, (name, arguments) in enumerate(parsed_calls, start=1):
            extra = copy.deepcopy(message.extra) or {}
            extra["function_id"] = str(index)
            normalized.append(
                Message(
                    role=ASSISTANT,
                    content="",
                    reasoning_content=(
                        message.reasoning_content if index == 1 and not prefix else None
                    ),
                    function_call=FunctionCall(name=name, arguments=arguments),
                    name=message.name,
                    extra=extra,
                )
            )
    return normalized


def _parse_dsml_calls(text: str) -> tuple[list[re.Match], list[tuple[str, str]]]:
    matches = list(_DSML_INVOKE.finditer(text))
    parsed_calls: list[tuple[str, str]] = []
    for match in matches:
        arguments_match = _DSML_ARGUMENTS.search(match.group("body"))
        if arguments_match is None:
            return matches, []
        name = html.unescape(match.group("name")).strip()
        arguments = html.unescape(arguments_match.group("arguments")).strip()
        # Some rendered transcripts escape underscores for Markdown.
        arguments = arguments.replace(r"\_", "_")
        if not name or not arguments:
            return matches, []
        parsed_calls.append((name, arguments))
    return matches, parsed_calls


def _parse_tool_call_tags(text: str) -> tuple[list[re.Match], list[tuple[str, str]]]:
    matches = list(_TOOL_CALL.finditer(text))
    parsed_calls: list[tuple[str, str]] = []
    for match in matches:
        try:
            call = json5.loads(match.group("call"))
        except (TypeError, ValueError):
            return matches, []
        if not isinstance(call, dict) or not isinstance(call.get("name"), str):
            return matches, []
        arguments = call.get("arguments", {})
        if isinstance(arguments, str):
            serialized_arguments = arguments
        elif isinstance(arguments, dict):
            serialized_arguments = json.dumps(arguments, ensure_ascii=False)
        else:
            return matches, []
        parsed_calls.append((call["name"].strip(), serialized_arguments))
    return matches, parsed_calls


def _message_text(message: Message) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(_content_item_text(item) for item in content or [])


def _content_item_text(item: ContentItem | dict) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or "")
    return str(item.text or "")
