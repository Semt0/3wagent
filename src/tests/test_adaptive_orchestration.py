"""CAP-01: one normal-mode agent chooses capabilities on demand."""

from __future__ import annotations

import json
from types import SimpleNamespace

from qwen_agent.llm.schema import ASSISTANT, USER, Message
from src.agent.main_agent import AgentMode, MainAgent
from src.tools.delegate_policy_task import DelegatePolicyTask


class StubSpecialist:
    def __init__(self, result: str):
        self.result = result
        self.calls: list[list[Message]] = []

    def run(self, messages):
        self.calls.append(messages)
        yield [Message(ASSISTANT, self.result)]


def test_delegate_runs_only_the_capability_chosen_by_the_model():
    research = StubSpecialist("official source pack")
    tax = StubSpecialist("tax analysis")
    tool = DelegatePolicyTask({"source_research": research, "tax_analysis": tax})

    result = json.loads(
        tool.call(
            {
                "capability": "source_research",
                "task": "Locate the exact rule text",
                "context": "Document number X",
                "reason": "The answer requires primary authority",
            }
        )
    )

    assert result == {
        "status": "ok",
        "capability": "source_research",
        "result": "official source pack",
    }
    assert len(research.calls) == 1
    assert not tax.calls
    assert "Locate the exact rule text" in research.calls[0][0].content
    assert "Document number X" in research.calls[0][0].content


def test_delegate_reports_available_capabilities_without_guessing():
    tool = DelegatePolicyTask({"source_research": StubSpecialist("unused")})

    result = json.loads(
        tool.call(
            {
                "capability": "unknown",
                "task": "Do everything",
                "reason": "test",
            }
        )
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "unknown_capability"
    assert result["available_capabilities"] == ["source_research"]


def test_all_inputs_stay_in_normal_mode_and_use_the_main_agent_loop(monkeypatch):
    from src.agent import main_agent as main_agent_module

    monkeypatch.setattr(
        main_agent_module,
        "inline_uploaded_files",
        lambda message: SimpleNamespace(should_block=False),
    )
    monkeypatch.setattr(main_agent_module, "new_run_id", lambda: "test-run")
    monkeypatch.setattr(main_agent_module, "register_user_provided_urls", lambda text: [])
    monkeypatch.setattr(main_agent_module, "attach_run_log", lambda model: None)

    agent = object.__new__(MainAgent)
    agent.llm = SimpleNamespace(model="test-model")
    agent.mode = AgentMode.NORMAL
    agent.current_step = None
    received = []

    def direct_loop(messages, **kwargs):
        received.extend(messages)
        yield [Message(ASSISTANT, "direct answer")]

    agent._run_fncall_with_guard = direct_loop

    output = list(agent._run([Message(USER, "复杂政策问题")]))

    assert output[-1][-1].content == "direct answer"
    assert received[-1].content == "复杂政策问题"
    assert agent.mode is AgentMode.NORMAL
    assert agent.current_step is None


def test_capability_trace_records_tool_and_selection_reason(monkeypatch, tmp_path):
    from src.agent import main_agent as main_agent_module

    monkeypatch.setattr(main_agent_module, "get_run_dir", lambda: tmp_path)
    agent = object.__new__(MainAgent)

    agent._record_capability_use(
        "DelegatePolicyTask",
        {
            "capability": "validity_review",
            "task": "Check effective date",
            "reason": "The requested date may predate the amendment",
        },
    )

    event = json.loads(
        (tmp_path / "capability_trace.jsonl").read_text(encoding="utf-8")
    )
    assert event["tool"] == "DelegatePolicyTask"
    assert event["capability"] == "validity_review"
    assert event["reason"] == "The requested date may predate the amendment"
