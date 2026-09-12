"""Tests for provider-neutral agent result capture."""

import json

import pytest
from qwen_agent.llm.schema import ASSISTANT, FUNCTION, Message
from src.agent.results import (
    AgentResultError,
    extract_last_assistant_text,
    resolve_structured_result,
)
from src.agent.subagent import ModeDetector


def test_extract_last_assistant_text_ignores_tools_and_other_agents():
    messages = [
        Message(ASSISTANT, "子代理内容", name="rag_subagent"),
        Message(FUNCTION, "工具结果", name="WebFetchTool"),
        Message(ASSISTANT, "最终回答", name="3wagent"),
    ]

    assert extract_last_assistant_text(messages, agent_name="3wagent") == "最终回答"


def test_resolve_structured_result_parses_direct_json_and_persists_it(tmp_path):
    output_path = tmp_path / "mode_detection.json"
    messages = [
        Message(
            ASSISTANT,
            '```json\n{"is_policy_question": false, "reason": "casual chat"}\n```',
        )
    ]

    result = resolve_structured_result(messages, output_path, dict)

    assert result == {"is_policy_question": False, "reason": "casual chat"}
    assert json.loads(output_path.read_text(encoding="utf-8")) == result


def test_resolve_structured_result_keeps_tool_written_file_as_fallback(tmp_path):
    output_path = tmp_path / "legacy.json"
    output_path.write_text('{"analysts": ["tax"]}', encoding="utf-8")

    result = resolve_structured_result([], output_path, dict)

    assert result == {"analysts": ["tax"]}


def test_resolve_structured_result_uses_valid_file_after_invalid_direct_output(tmp_path):
    output_path = tmp_path / "legacy.json"
    output_path.write_text('{"analysts": ["funds"]}', encoding="utf-8")

    result = resolve_structured_result(
        [Message(ASSISTANT, "not valid JSON")],
        output_path,
        dict,
    )

    assert result == {"analysts": ["funds"]}


def test_resolve_structured_result_reports_invalid_output_instead_of_missing_file(tmp_path):
    with pytest.raises(AgentResultError, match="no valid structured result"):
        resolve_structured_result(
            [Message(ASSISTANT, "I cannot decide")],
            tmp_path / "missing.json",
            dict,
        )


def test_functional_subagent_accepts_direct_provider_response(monkeypatch, tmp_path):
    def fake_run(self, messages):
        yield [
            Message(
                ASSISTANT,
                '{"is_policy_question": false, "reason": "greeting"}',
            )
        ]

    monkeypatch.setattr(ModeDetector, "run", fake_run)
    detector = object.__new__(ModeDetector)
    output_path = tmp_path / "mode_detection.json"

    result = detector.run_task("hi", output_path)

    assert result["is_policy_question"] is False
    assert output_path.exists()
