from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from enum import Enum
from typing import Literal

from qwen_agent.agents import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import Message

from src.agent.attachments import inline_uploaded_files, supported_formats_hint
from src.agent.subagent import (
    CitationVerifierSubAgent,
    CommercialLawAnalystSubAgent,
    FundsComplianceAnalystSubAgent,
    RagSubAgent,
    TaxPolicyAnalystSubAgent,
    ValidateSubAgent,
)
from src.agent.tool_call_compat import ToolCallCompatibilityMixin
from src.agent.tool_loop_guard import (
    TerminalToolResult,
    raise_for_terminal_tool_result,
    terminal_finalize_prompt,
    tool_free_finalize_messages,
)
from src.config.llm import load_llm_config
from src.config.logger import attach_run_log
from src.config.runtime import get_run_dir, new_run_id
from src.config.webui import WEBUI_CHATBOT_CONFIG
from src.prompts.prompts import MAIN_AGENT_SYS_PROMPT
from src.tools.common import parse_tool_params
from src.tools.delegate_policy_task import DelegatePolicyTask
from src.tools.read_attachment import AttachmentReadTool  # noqa: F401
from src.tools.read_markdown_files import MarkDownReadTool  # noqa: F401
from src.tools.read_yaml_files import YamlReadTool  # noqa: F401
from src.tools.web_fetch import WebFetchTool  # noqa: F401
from src.tools.web_search import WebSearchTool  # noqa: F401
from src.tools.write_result import WriteResult  # noqa: F401
from src.websearch.provenance import register_user_provided_urls


class AgentMode(Enum):
    """The agent has one adaptive operating mode."""

    NORMAL = 'normal'


class MainAgent(ToolCallCompatibilityMixin, FnCallAgent):
    """One adaptive agent with direct tools and optional specialist delegation."""

    def __init__(
        self,
        llm: dict | BaseChatModel | None = None,
    ):
        subagent_tools = ['MarkDownReadTool', 'YamlReadTool', 'AttachmentReadTool']
        retrieval_tools = subagent_tools + ['WebSearchTool', 'WebFetchTool']
        verification_tools = subagent_tools + ['WebSearchTool', 'WebFetchTool']
        self.specialists = {
            'source_research': RagSubAgent(function_list=retrieval_tools, llm=llm),
            'validity_review': ValidateSubAgent(function_list=verification_tools, llm=llm),
            'tax_analysis': TaxPolicyAnalystSubAgent(function_list=subagent_tools, llm=llm),
            'funds_analysis': FundsComplianceAnalystSubAgent(function_list=subagent_tools, llm=llm),
            'commercial_analysis': CommercialLawAnalystSubAgent(
                function_list=subagent_tools,
                llm=llm,
            ),
            'citation_review': CitationVerifierSubAgent(
                function_list=verification_tools,
                llm=llm,
            ),
        }
        self.delegate_tool = DelegatePolicyTask(self.specialists)
        tools = [
            'MarkDownReadTool',
            'YamlReadTool',
            'AttachmentReadTool',
            'WebSearchTool',
            'WebFetchTool',
            'WriteResult',
            self.delegate_tool,
        ]
        super().__init__(
            llm=llm,
            function_list=tools,
            system_message=MAIN_AGENT_SYS_PROMPT,
            name='3wagent',
            description='跨境政策合规分析助手：资金合规、税务、民商法多领域协同分析。',
        )
        self.mode = AgentMode.NORMAL
        # A transient capability label for the WebUI; this is not a workflow step.
        self.current_step: str | None = None

    def _run(
        self,
        messages: list[Message],
        lang: Literal['en', 'zh'] = 'en',
        **kwargs,
    ) -> Iterator[list[Message]]:
        # Resolve attachments FIRST: an unreadable-only upload blocks the run
        # regardless of mode (and never reaches mode detection or the LLM).
        # Resolve the original message so the main model and any later tool
        # delegation see the same attachment context.
        attachment_resolution = inline_uploaded_files(messages[-1])
        if attachment_resolution.should_block:
            yield [
                Message(
                    role='assistant',
                    content=(
                        '暂时无法读取你上传的附件。'
                        f'当前支持的格式：{supported_formats_hint()}。'
                        '或者在消息中补充具体问题后重试。'
                    ),
                )
            ]
            return

        # Start a new run: all artifacts go under workspace/<run_id>/
        new_run_id()
        register_user_provided_urls(_message_text(messages[-1]))
        attach_run_log(getattr(self.llm, 'model', 'model') or 'model')

        # Every request stays in NORMAL mode. The model decides whether to
        # answer directly, use a foundational tool, or delegate one bounded
        # specialist task based on the evidence gap in the current request.
        self.current_step = '自主处理'
        try:
            yield from self._run_fncall_with_guard(messages, lang=lang, **kwargs)
        finally:
            self.mode = AgentMode.NORMAL
            self.current_step = None

    def _run_fncall_with_guard(
        self,
        messages: list[Message],
        lang: Literal['en', 'zh'] = 'en',
        **kwargs,
    ) -> Iterator[list[Message]]:
        rsp: list[Message] = []
        try:
            for rsp in super()._run(messages=messages, lang=lang, **kwargs):
                yield rsp
        except TerminalToolResult as exc:
            final_messages = tool_free_finalize_messages(
                messages,
                rsp,
                terminal_finalize_prompt(exc),
            )
            for fin in self._call_llm(messages=final_messages, functions=[]):
                yield rsp + fin

    def _call_tool(self, tool_name, tool_args='{}', **kwargs):
        self.current_step = f'按需调用：{tool_name}'
        self._record_capability_use(tool_name, tool_args)
        try:
            result = super()._call_tool(tool_name, tool_args, **kwargs)
            raise_for_terminal_tool_result(tool_name, result)
            return result
        finally:
            self.current_step = None

    def _record_capability_use(self, tool_name: str, tool_args) -> None:
        """Persist a small per-run decision trace for debugging."""
        try:
            parsed = parse_tool_params(tool_args)
        except Exception:  # noqa: BLE001 - tracing must never break a tool call
            parsed = {}
        reason = parsed.get('reason')
        if not reason:
            reason = (
                parsed.get('query')
                or parsed.get('url')
                or parsed.get('file_path')
                or parsed.get('locator')
                or '模型根据当前证据缺口选择该能力'
            )
        event = {
            'timestamp': datetime.now().astimezone().isoformat(),
            'tool': tool_name,
            'capability': parsed.get('capability'),
            'reason': str(reason)[:500],
        }
        try:
            trace_path = get_run_dir() / 'capability_trace.jsonl'
            with trace_path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + '\n')
        except Exception:  # noqa: BLE001 - observability is best-effort
            return


def _message_text(message: Message) -> str:
    content = message.get('content')
    if isinstance(content, list):
        return ''.join(item.get('text') or '' for item in content)
    return str(content or '')


def run_3wagent(model_name=None, provider=None, config_path=None):
    # Imported lazily so headless usage/tests don't require qwen-agent[gui]
    from src.agent.webui import ThemedWebUI

    # Define Agent
    bot = MainAgent(
        llm=load_llm_config(
            model_name=model_name,
            provider=provider,
            config_path=config_path,
        )
    )

    # Run The GUI Agent
    ThemedWebUI(
        bot,
        chatbot_config=WEBUI_CHATBOT_CONFIG
    ).run()

if __name__ == "__main__":
    run_3wagent()
