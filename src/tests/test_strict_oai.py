"""Tests for strict OpenAI-compatible tool-result serialization."""

from qwen_agent.llm.schema import ASSISTANT, FUNCTION, USER, FunctionCall, Message
from qwen_agent.utils.utils import format_as_text_message
from src.agent.main_agent import MainAgent
from src.agent.tool_loop_guard import tool_free_finalize_messages
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


def test_workflow_injects_subagent_results_as_user_context():
    class StubSubAgent:
        STEP_CONTENT = "stub step"

        def __init__(self, label):
            self.label = label

        def run(self, messages):
            yield [Message(ASSISTANT, f"{self.label} output")]

        def get_back_prompt(self):
            return f"context from {self.label}"

    agent = object.__new__(MainAgent)
    agent.routing_agent = StubSubAgent("routing")
    agent.rag_agent = StubSubAgent("rag")
    agent.validate_agent = StubSubAgent("validate")
    agent.citation_verifier = StubSubAgent("citations")
    agent.report_writer = StubSubAgent("report")
    agent._select_analysts = lambda: [StubSubAgent("analyst")]
    captured = []

    def final_run(messages, **kwargs):
        captured.extend(messages)
        yield [Message(ASSISTANT, "final answer")]

    agent._run_fncall_with_guard = final_run

    list(agent._run_workflow([Message(USER, "question")]))

    injected = [message for message in captured if str(message.content).startswith("context from")]
    assert len(injected) == 6
    assert all(message.role == USER for message in injected)
    assert captured[-1].role == USER
