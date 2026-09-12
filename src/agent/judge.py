"""LLM-as-a-judge relevance review for web search results.

Every deduplicated search candidate is reviewed by a functional sub-agent
that sees the main agent's full conversation context with its task swapped to
relevance judgment; no heuristic pre-filter runs first. When the judge is
unavailable, callers fall back to the heuristic threshold filter
(``websearch/relevance.py``). The judge runs on the same provider config the
current run was started with (recorded by ``config/llm.load_llm_config``).

This module must stay free of ``src.tools`` imports: ``tools/web_search.py``
imports it, and the tool modules are what ``agent/subagent.py`` registers.
"""

from __future__ import annotations

import copy
import uuid
from typing import Any

from qwen_agent.llm.schema import ASSISTANT, USER, Message

from src.agent.functional import FunctionalSubAgent
from src.agent.tool_loop_guard import _message_has_text, drop_unresolved_tool_calls
from src.config.llm import get_active_llm_config
from src.config.runtime import get_run_dir
from src.prompts.prompts import SEARCH_JUDGE_OUTPUT_SPEC, SEARCH_JUDGE_TASK_PROMPT_TEMPLATE


class JudgeUnavailable(RuntimeError):
    """No usable LLM config for the judge (e.g. tests without a provider)."""


class SearchResultJudge(FunctionalSubAgent):
    """One-shot judge: which candidates help answer the current question."""

    OUTPUT_SPEC = SEARCH_JUDGE_OUTPUT_SPEC
    RESULT_TYPE = list

    def __init__(self, **kwargs):
        llm = get_active_llm_config()
        if llm is None:
            raise JudgeUnavailable("no active LLM config; judge is disabled")
        super().__init__(llm=llm, function_list=[], **kwargs)

    def judge(
        self,
        messages: list[Message],
        query: str,
        candidates: list[dict],
    ) -> dict[int, tuple[bool, str]]:
        """Judge candidates against the conversation; return index -> verdict."""
        history = _clean_context(messages)
        history.append(
            Message(
                USER,
                SEARCH_JUDGE_TASK_PROMPT_TEMPLATE.format(
                    query=query,
                    candidates=_format_candidates(candidates),
                    output_spec=self.OUTPUT_SPEC,
                ),
            )
        )
        output_path = get_run_dir() / 'search_judges' / f'{uuid.uuid4().hex}.json'
        verdicts = self.run_with_messages(history, output_path)
        return _validate_verdicts(verdicts, len(candidates))


def judge_search_results(
    messages: list[Message],
    query: str,
    candidates: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split candidates into (kept, discarded). Raises on any judge failure.

    Candidates the judge did not mention are kept: an incomplete verdict list
    must never silently drop evidence.
    """
    verdicts = SearchResultJudge().judge(messages, query, candidates)
    kept: list[dict] = []
    discarded: list[dict] = []
    for index, item in enumerate(candidates, start=1):
        verdict = verdicts.get(index)
        if verdict is None or verdict[0]:
            kept.append(item)
        else:
            discarded.append(
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "reason": verdict[1],
                }
            )
    return kept, discarded


def _clean_context(messages: list[Message]) -> list[Message]:
    """Copy the conversation into a request-valid history for the judge.

    The judge is invoked mid-tool-loop: the tail holds the current round's
    assistant function calls without responses, which strict providers reject.
    """
    history = drop_unresolved_tool_calls(copy.deepcopy(messages))
    while history and history[-1].role == ASSISTANT:
        last = history[-1]
        if last.function_call or not _message_has_text(last):
            history.pop()
            continue
        break
    return history


def _format_candidates(candidates: list[dict]) -> str:
    lines = []
    for index, item in enumerate(candidates, start=1):
        snippet = str(item.get("snippet") or "")[:600]
        lines.append(
            f"{index}. {item.get('title')}\n   URL: {item.get('url')}\n   Snippet: {snippet}"
        )
    return "\n".join(lines)


def _validate_verdicts(verdicts: Any, candidate_count: int) -> dict[int, tuple[bool, str]]:
    if not isinstance(verdicts, list):
        raise ValueError("judge verdicts must be a JSON array")
    validated: dict[int, tuple[bool, str]] = {}
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            continue
        try:
            index = int(verdict.get("index"))
        except (TypeError, ValueError):
            continue
        if not 1 <= index <= candidate_count:
            continue
        validated[index] = (bool(verdict.get("relevant")), str(verdict.get("reason") or ""))
    if not validated:
        raise ValueError("judge returned no valid verdicts")
    return validated
