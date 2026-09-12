"""Optional specialist delegation for the adaptive main agent.

The main model may call one specialist for one bounded task.  This is not a
workflow engine: no prerequisite, ordering, or follow-up capability is
implied by a call, and the main model remains responsible for deciding when
the returned material is sufficient.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, ClassVar

from qwen_agent.llm.schema import USER, Message
from qwen_agent.tools import BaseTool

from src.agent.results import extract_last_assistant_text
from src.tools.common import parse_tool_params


class DelegatePolicyTask(BaseTool):
    """Run exactly one named specialist on a bounded task."""

    name = "DelegatePolicyTask"
    description = (
        "Optionally delegate one bounded research, validity, domain-analysis, or "
        "citation-review task to a specialist. Use only when independent specialist "
        "work materially improves a complex answer. This tool does not start a fixed "
        "workflow and does not automatically call any other specialist."
    )
    parameters: ClassVar[dict] = {
        "type": "object",
        "properties": {
            "capability": {
                "type": "string",
                "description": (
                    "Specialist capability name. Available names are returned if the "
                    "requested name is unavailable."
                ),
            },
            "task": {
                "type": "string",
                "description": "A precise, self-contained task for the specialist.",
            },
            "context": {
                "type": "string",
                "description": (
                    "Only the facts and evidence the specialist needs. Omit unrelated "
                    "conversation history."
                ),
            },
            "reason": {
                "type": "string",
                "description": (
                    "Short debugging reason why this specialist is useful for the answer."
                ),
            },
        },
        "required": ["capability", "task", "reason"],
    }

    def __init__(self, capabilities: Mapping[str, Any]):
        super().__init__()
        self.capabilities = dict(capabilities)

    def call(self, params: str | dict, **kwargs) -> str:
        try:
            parsed = parse_tool_params(params)
        except Exception as exc:  # noqa: BLE001 - tool boundary returns structured errors
            return self._error("invalid_arguments", str(exc))

        capability = str(parsed.get("capability") or "").strip()
        task = str(parsed.get("task") or "").strip()
        context = str(parsed.get("context") or "").strip()
        reason = str(parsed.get("reason") or "").strip()
        if not capability or not task or not reason:
            return self._error(
                "missing_required_field",
                "capability, task and reason must all be non-empty",
            )

        specialist = self.capabilities.get(capability)
        if specialist is None:
            return self._error(
                "unknown_capability",
                f"unknown capability: {capability}",
            )

        prompt = f"专项任务：\n{task}"
        if context:
            prompt += f"\n\n必要上下文：\n{context}"
        prompt += (
            "\n\n只完成上述专项任务；不要自行启动其他研究步骤，也不要扩展用户范围。"
        )

        final_frame: list[Message] = []
        try:
            for frame in specialist.run([Message(USER, prompt)]):
                final_frame = frame
        except Exception as exc:  # noqa: BLE001 - isolate optional specialist failure
            return self._error("specialist_failed", str(exc), capability=capability)

        result = extract_last_assistant_text(
            final_frame,
            agent_name=getattr(specialist, "name", None),
        )
        if not result.strip():
            result = str(getattr(specialist, "_last_output_text", "") or "")
        if not result.strip():
            return self._error(
                "empty_specialist_result",
                "specialist returned no usable text",
                capability=capability,
            )

        return json.dumps(
            {
                "status": "ok",
                "capability": capability,
                "result": result,
            },
            ensure_ascii=False,
        )

    def _error(self, code: str, message: str, **extra: str) -> str:
        return json.dumps(
            {
                "status": "error",
                "error": {"code": code, "message": message},
                "available_capabilities": sorted(self.capabilities),
                **extra,
            },
            ensure_ascii=False,
        )
