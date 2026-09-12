"""Tests for strict OpenAI-compatible tool-result serialization."""

from qwen_agent.llm.schema import ASSISTANT, FUNCTION, USER, FunctionCall, Message
from qwen_agent.utils.utils import format_as_text_message
from src.agent.tool_loop_guard import sanitize_response_tail, tool_free_finalize_messages
from src.llm.strict_oai import StrictOpenAICompatibleModel


def test_tool_result_uses_tool_call_id_and_removes_internal_fields():
    messages = [
        Message(USER, "question"),
        Message(
            ASSISTANT,
            "",
            function_call=FunctionCall(name="WebSearchTool", arguments='{"query":"x"}'),
            extra={"function_id": "call_abc"},
        ),
        Message(
            FUNCTION,
            '{"status":"ok"}',
            name="WebSearchTool",
            extra={"function_id": "call_abc"},
        ),
    ]
    dumped = [
        format_as_text_message(message, add_upload_info=False).model_dump()
        for message in messages
    ]

    converted = StrictOpenAICompatibleModel._conv_qwen_agent_messages_to_oai(dumped)

    assert converted[1]["tool_calls"][0]["id"] == "call_abc"
    assert converted[2] == {
        "role": "tool",
        "content": '{"status":"ok"}',
        "tool_call_id": "call_abc",
    }
    assert "id" not in converted[2]
    assert "extra" not in converted[2]


def test_finalization_preserves_reasoning_for_completed_tool_calls():
    completed = [
        Message(USER, "question"),
        Message(ASSISTANT, "", reasoning_content="Search official evidence."),
        Message(
            ASSISTANT,
            "",
            function_call=FunctionCall(name="WebSearchTool", arguments='{"query":"x"}'),
            extra={"function_id": "call_done"},
        ),
        Message(
            FUNCTION,
            "search result",
            name="WebSearchTool",
            extra={"function_id": "call_done"},
        ),
    ]
    interrupted = [
        Message(ASSISTANT, "", reasoning_content="Try another search."),
        Message(
            ASSISTANT,
            "",
            function_call=FunctionCall(name="WebSearchTool", arguments='{"query":"y"}'),
            extra={"function_id": "call_unfinished"},
        ),
    ]

    finalized = tool_free_finalize_messages(completed, interrupted, "Answer now.")
    dumped = [
        format_as_text_message(message, add_upload_info=False).model_dump()
        for message in finalized
    ]
    converted = StrictOpenAICompatibleModel._conv_qwen_agent_messages_to_oai(dumped)

    assert converted[1]["reasoning_content"] == "Search official evidence."
    assert converted[1]["tool_calls"][0]["id"] == "call_done"
    assert converted[2]["tool_call_id"] == "call_done"
    assert "call_unfinished" not in repr(converted)


def test_sanitize_response_tail_drops_unresolved_tool_calls():
    interrupted = [
        Message(ASSISTANT, "", reasoning_content="Try another fetch."),
        Message(
            ASSISTANT,
            "",
            function_call=FunctionCall(name="WebFetchTool", arguments='{"url":"https://x"}'),
            extra={"function_id": "call_unfinished"},
        ),
    ]

    cleaned = sanitize_response_tail(interrupted)

    assert cleaned == []


def test_unresolved_call_before_sibling_responses_is_dropped():
    """The A01 regression: FnCallAgent appends each function response right
    after its call completes, so an interrupted parallel round leaves the
    unresolved call BEFORE its siblings' responses — not at the tail."""
    round_messages = [
        Message(
            ASSISTANT, "",
            function_call=FunctionCall(name="WebSearchTool", arguments='{"query":"a"}'),
            extra={"function_id": "call_a"},
        ),
        Message(
            ASSISTANT, "",
            function_call=FunctionCall(name="WebSearchTool", arguments='{"query":"b"}'),
            extra={"function_id": "call_b"},
        ),
        Message(
            ASSISTANT, "",
            function_call=FunctionCall(name="WebSearchTool", arguments='{"query":"c"}'),
            extra={"function_id": "call_c"},
        ),
        Message(FUNCTION, "result a", name="WebSearchTool", extra={"function_id": "call_a"}),
        Message(FUNCTION, "result b", name="WebSearchTool", extra={"function_id": "call_b"}),
    ]

    cleaned = sanitize_response_tail(round_messages)
    assert [m.extra["function_id"] for m in cleaned] == [
        "call_a", "call_a", "call_b", "call_b",
    ]

    # The same cleanup applies to the finalize-request history.
    finalized = tool_free_finalize_messages(
        [Message(USER, "question")], round_messages, "Answer now."
    )
    dumped = [
        format_as_text_message(message, add_upload_info=False).model_dump()
        for message in finalized
    ]
    converted = StrictOpenAICompatibleModel._conv_qwen_agent_messages_to_oai(dumped)
    assert "call_c" not in repr(converted)
    assert converted[-1] == {"role": "user", "content": "Answer now."}


def test_sanitize_response_tail_keeps_answered_calls_and_final_text():
    response = [
        Message(ASSISTANT, ""),
        Message(
            ASSISTANT,
            "",
            function_call=FunctionCall(name="WebSearchTool", arguments='{"query":"x"}'),
            extra={"function_id": "call_done"},
        ),
        Message(
            FUNCTION,
            "search result",
            name="WebSearchTool",
            extra={"function_id": "call_done"},
        ),
        Message(ASSISTANT, "", reasoning_content="Now fetch it."),
        Message(
            ASSISTANT,
            "",
            function_call=FunctionCall(name="WebFetchTool", arguments='{"url":"https://x"}'),
            extra={"function_id": "call_unfinished"},
        ),
    ]

    cleaned = sanitize_response_tail(response)

    names = [m.function_call.name for m in cleaned if m.function_call]
    assert names == ["WebSearchTool"]
    assert [m.role for m in cleaned] == [ASSISTANT, FUNCTION]
    assert cleaned[1].content == "search result"
