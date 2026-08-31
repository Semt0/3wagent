from __future__ import annotations

import copy
from collections.abc import Iterator
from enum import Enum
from typing import Literal

from qwen_agent.agents import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ASSISTANT, USER, Message

from src.agent.attachments import inline_uploaded_files, supported_formats_hint
from src.agent.subagent import *
from src.agent.tool_loop_guard import (
    TerminalToolResult,
    raise_for_terminal_tool_result,
    terminal_finalize_prompt,
)
from src.config.llm import load_llm_config
from src.config.logger import attach_run_log
from src.config.runtime import get_run_dir, get_subagents_dir, new_run_id
from src.config.webui import WEBUI_CHATBOT_CONFIG
from src.prompts.prompts import FINALIZE_USER_PROMPT, MAIN_AGENT_SYS_PROMPT
from src.tools.read_attachment import AttachmentReadTool  # noqa: F401
from src.tools.read_markdown_files import MarkDownReadTool  # noqa: F401
from src.tools.read_yaml_files import YamlReadTool  # noqa: F401
from src.tools.web_fetch import WebFetchTool  # noqa: F401
from src.tools.web_search import WebSearchTool  # noqa: F401
from src.tools.write_result import WriteResult  # noqa: F401
from src.websearch.provenance import register_user_provided_urls


class AgentMode(Enum):
    """Top-level modes of the main agent.

    NORMAL: casual Q&A, answer directly.
    WORKING: a policy question is being processed by the workflow.

    Future extensions: per-subagent states, failure rollback to NORMAL,
    redo requests back to an earlier subagent.
    """
    NORMAL = 'normal'
    WORKING = 'working'


class MainAgent(FnCallAgent):
    """Customize the main agent to resolve policy problem

    Two modes (AgentMode): NORMAL for casual Q&A, WORKING for the policy
    research workflow. Mode detection is delegated to a FunctionalSubAgent.
    """

    def __init__(
        self,
        llm: dict | BaseChatModel | None = None,
    ):
        tools = [
            'MarkDownReadTool',
            'YamlReadTool',
            'AttachmentReadTool',
            'WebFetchTool',
            'WriteResult',
        ]
        functional_tools = ['WriteResult']
        # Workflow sub-agents report via their final reply (the framework
        # persists it to the result file), so they no longer need WriteResult.
        # The main agent and functional sub-agents keep it.
        subagent_tools = ['MarkDownReadTool', 'YamlReadTool', 'AttachmentReadTool']
        retrieval_tools = subagent_tools + ['WebSearchTool', 'WebFetchTool']
        verification_tools = subagent_tools + ['WebSearchTool', 'WebFetchTool']
        super().__init__(
            llm=llm,
            function_list=tools,
            system_message=MAIN_AGENT_SYS_PROMPT,
            name='3wagent',
            description='跨境政策合规分析助手：资金合规、税务、民商法多领域协同分析。',
        )
        self.routing_agent = RoutingSubAgent(function_list=subagent_tools, llm=llm)
        self.rag_agent = RagSubAgent(function_list=retrieval_tools, llm=llm)
        self.validate_agent = ValidateSubAgent(function_list=verification_tools, llm=llm)
        self.citation_verifier = CitationVerifierSubAgent(
            function_list=verification_tools, llm=llm
        )
        self.report_writer = ReportWritingSubAgent(function_list=subagent_tools, llm=llm)
        # Domain analysts, selected per routing result (see _select_analysts)
        self.analysts = {
            'tax': TaxPolicyAnalystSubAgent(function_list=subagent_tools, llm=llm),
            'funds': FundsComplianceAnalystSubAgent(function_list=subagent_tools, llm=llm),
            'commercial': CommercialLawAnalystSubAgent(function_list=subagent_tools, llm=llm),
        }
        # Functional subagent for policy-question detection (clean context)
        self.mode_detector = ModeDetector(llm=llm, function_list=functional_tools)
        # Functional subagent for analyst selection from the routing result
        self.analysts_selector = AnalystsSelector(llm=llm, function_list=functional_tools)
        self.mode = AgentMode.NORMAL
        # Current workflow step label for the WebUI status panel; None in NORMAL mode.
        self.current_step: str | None = None

    def _run(
        self,
        messages: list[Message],
        lang: Literal['en', 'zh'] = 'en',
        **kwargs,
    ) -> Iterator[list[Message]]:
        # Resolve attachments FIRST: an unreadable-only upload blocks the run
        # regardless of mode (and never reaches mode detection or the LLM).
        # Resolving the original messages[-1] (not a copy) is safe here: the
        # workflow below deep-copies messages AFTER inlining, so sub-agents
        # receive the resolved content.
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

        # Mode transition: NORMAL -> WORKING when a policy question is detected.
        # (Detection is skipped while WORKING; the workflow finishes within one
        # _run call, and failures also fall back to NORMAL via the finally below.)
        if self.mode == AgentMode.NORMAL:
            self.current_step = '模式检测'
            try:
                is_policy = self._is_policy_question(messages[-1])
            finally:
                self.current_step = None
            if is_policy:
                self.mode = AgentMode.WORKING

        if self.mode == AgentMode.WORKING:
            try:
                yield from self._run_workflow(messages, lang=lang, **kwargs)
            finally:
                self.mode = AgentMode.NORMAL
                self.current_step = None
        else:
            yield from self._run_fncall_with_guard(messages, lang=lang, **kwargs)

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
            final_messages = messages + rsp + [Message(USER, terminal_finalize_prompt(exc))]
            for fin in self._call_llm(messages=final_messages, functions=[]):
                yield rsp + fin

    def _call_tool(self, tool_name, tool_args='{}', **kwargs):
        result = super()._call_tool(tool_name, tool_args, **kwargs)
        raise_for_terminal_tool_result(tool_name, result)
        return result

    # Check if the user last question is a policy question
    def _is_policy_question(self, last_message: Message) -> bool:
        """Ask the functional subagent whether this input is a policy question."""
        question = _message_text(last_message)
        if not question.strip():
            return False
        result_path = get_run_dir() / 'mode_detection.json'
        result = self.mode_detector.run_task(input_text = question , output_path = result_path)

        # type check
        assert "is_policy_question" in result
        assert isinstance(result["is_policy_question"], bool)

        return result["is_policy_question"]

    def _run_workflow(
        self,
        messages: list[Message],
        lang: Literal['en', 'zh'] = 'en',
        **kwargs,
    ) -> Iterator[list[Message]]:
        # DeepCopy, Empty Previous Response
        # (attachments were already resolved and inlined in _run above)
        new_messages = copy.deepcopy(messages)
        response = []

        ### SubAgents WorkMode:
        ### SubAgent takes the previous whole messages history as input, as well as its own system prompt and user instruction
        ### Its Last Result(Formatted Results Stored in files) should be injected into MainAgent Messages 
        ### Middle messages can be discarded to save tokens
        
        ### Step 2: Routing SubAgent
        # subagent run
        self.current_step = self.routing_agent.STEP_CONTENT
        for rsp in self.routing_agent.run(new_messages):
            yield response + rsp
        
        # add to previous response
        response.extend(rsp)

        # add the result into MainAgent messages
        new_messages.append(Message(ASSISTANT,self.routing_agent.get_back_prompt()))


        ### Step 3: RAG SubAgent
        # subagent run
        self.current_step = self.rag_agent.STEP_CONTENT
        for rsp in self.rag_agent.run(new_messages):
            yield response + rsp

        # add to previous response
        response.extend(rsp)

        # add the result into MainAgent messages
        new_messages.append(Message(ASSISTANT,self.rag_agent.get_back_prompt()))

        ### Step 4: Validate SubAgent
        # subagent run
        self.current_step = self.validate_agent.STEP_CONTENT
        for rsp in self.validate_agent.run(new_messages):
            yield response + rsp

        # add to previous response
        response.extend(rsp)

        # add the result into MainAgent messages
        new_messages.append(Message(ASSISTANT,self.validate_agent.get_back_prompt()))

        ### Step 5: Domain Analysts selected by the routing result
        self.current_step = 'Step 5: 选择领域分析师'
        for analyst in self._select_analysts():
            self.current_step = analyst.STEP_CONTENT
            for rsp in analyst.run(new_messages):
                yield response + rsp
            response.extend(rsp)
            new_messages.append(Message(ASSISTANT, analyst.get_back_prompt()))

        ### Step 6: Citation-Verifier SubAgent
        self.current_step = self.citation_verifier.STEP_CONTENT
        for rsp in self.citation_verifier.run(new_messages):
            yield response + rsp
        response.extend(rsp)
        new_messages.append(Message(ASSISTANT, self.citation_verifier.get_back_prompt()))

        ### Step 7: Report Writing SubAgent
        self.current_step = self.report_writer.STEP_CONTENT
        for rsp in self.report_writer.run(new_messages):
            yield response + rsp
        response.extend(rsp)
        new_messages.append(Message(ASSISTANT, self.report_writer.get_back_prompt()))

        # Final main loop: keep the accumulated subagent transcript in every frame
        self.current_step = '主代理综合'
        final_rsp: list[Message] = []
        for rsp in self._run_fncall_with_guard(new_messages, lang=lang, **kwargs):
            final_rsp = rsp
            yield response + rsp
        if BaseSubAgent._was_truncated(final_rsp):
            # Same recovery as BaseSubAgent: the framework LLM-call cap cut the
            # tool loop mid-work, so force one tool-free finalization round to
            # still deliver a written answer instead of vanishing.
            finalize_messages = new_messages + final_rsp + [Message(USER, FINALIZE_USER_PROMPT)]
            for fin in self._call_llm(messages=finalize_messages, functions=[]):
                yield response + final_rsp + fin

    def _select_analysts(self):
        """Pick domain analysts by asking the analysts_selector functional
        subagent to judge the routing result.

        Falls back to the tax analyst on any failure or empty selection
        (tax is the most common primary domain for the covered issue types).
        """
        routing_result_path = get_subagents_dir() / 'routing_subagent_result.md'
        routing_result = routing_result_path.read_text(encoding='utf-8') if routing_result_path.exists() else ''
        if not routing_result.strip():
            # Routing produced nothing (typically its tool loop hit the
            # framework call cap). Asking the selector with empty input
            # invites a guess, so skip it and fall back to the two domains
            # that cover most cross-border payment issues.
            return [self.analysts['tax'], self.analysts['funds']]
        selection_path = get_run_dir() / 'analyst_selection.json'
        try:
            result = self.analysts_selector.run_task(input_text=routing_result, output_path=selection_path)
            selected = [self.analysts[name] for name in result.get('analysts', []) if name in self.analysts]
        except Exception:  # noqa: BLE001 - selection failure has a safe fallback
            selected = []
        return selected or [self.analysts['tax']]


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
