"""Interactive terminal frontend for 3wagent."""

from __future__ import annotations

import sys
from typing import TextIO

from qwen_agent.llm.schema import USER, Message

from src.agent.main_agent import AgentMode, MainAgent
from src.agent.results import extract_last_assistant_text
from src.config.llm import load_llm_config

EXIT_COMMANDS = {"/exit", "/quit"}


def build_cli_agent(model_name=None, provider=None, config_path=None) -> MainAgent:
    """Create the same agent used by the WebUI without importing Gradio."""
    return MainAgent(
        llm=load_llm_config(
            model_name=model_name,
            provider=provider,
            config_path=config_path,
        )
    )


def run_cli(
    agent: MainAgent,
    *,
    input_stream: TextIO = sys.stdin,
    output_stream: TextIO = sys.stdout,
    error_stream: TextIO = sys.stderr,
) -> None:
    """Run a multi-turn terminal conversation until EOF or ``/exit``."""
    history: list[Message] = []
    _write(
        output_stream,
        "3wagent CLI\n命令：/clear 清空对话，/exit 或 /quit 退出。\n",
    )

    while True:
        _write(output_stream, "\n你> ")
        line = input_stream.readline()
        if line == "":
            _write(output_stream, "\n")
            return

        question = line.strip()
        if not question:
            continue
        if question.lower() in EXIT_COMMANDS:
            return
        if question.lower() == "/clear":
            history.clear()
            _reset_agent_state(agent)
            _write(output_stream, "对话已清空。\n")
            continue

        history.append(Message(USER, question))
        responses: list[Message] = []
        printed = ""
        answer_started = False
        last_step = None

        try:
            for responses in agent.run(history):
                step = getattr(agent, "current_step", None)
                if step and step != last_step:
                    _write(error_stream, f"\n[{step}]\n")
                    last_step = step

                answer = _latest_agent_answer(responses, getattr(agent, "name", "3wagent"))
                if not answer or answer == printed:
                    continue
                if not answer_started:
                    _write(output_stream, "3wagent> ")
                    answer_started = True
                if answer.startswith(printed):
                    _write(output_stream, answer[len(printed):])
                else:
                    # Providers normally stream cumulative text. If one emits
                    # a replacement frame, redraw it on a fresh line instead
                    # of silently concatenating incompatible snapshots.
                    _write(output_stream, f"\n{answer}")
                printed = answer
        except KeyboardInterrupt:
            _reset_agent_state(agent)
            history.pop()
            _write(error_stream, "\n本轮已取消。\n")
            continue
        except Exception as exc:  # noqa: BLE001 - keep the REPL usable after one failed turn
            _reset_agent_state(agent)
            history.pop()
            _write(error_stream, f"\nError: {type(exc).__name__}: {exc}\n")
            continue

        if responses:
            history.extend(responses)
        if not answer_started:
            _write(output_stream, "3wagent> （本轮没有生成文本回答）")
        _write(output_stream, "\n")


def run_cli_3wagent(model_name=None, provider=None, config_path=None) -> None:
    run_cli(build_cli_agent(model_name, provider, config_path))


def _latest_agent_answer(messages: list[Message], agent_name: str) -> str:
    return extract_last_assistant_text(messages, agent_name=agent_name)


def _reset_agent_state(agent: MainAgent) -> None:
    agent.mode = AgentMode.NORMAL
    agent.current_step = None


def _write(stream: TextIO, text: str) -> None:
    stream.write(text)
    stream.flush()
