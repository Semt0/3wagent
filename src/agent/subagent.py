"""Sub-agents of 3wagent.

All sub-agents share one mechanism (BaseSubAgent): receive messages, work with
tools, write a result file, then report back to the main agent. Concrete
sub-agents only declare identity and prompts as class attributes.
"""

import copy
from datetime import date
from typing import Dict, Iterator, List, Optional, Union

import json5
from qwen_agent.agents import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ASSISTANT, USER, Message
from qwen_agent.tools import BaseTool

from src.agent.tool_loop_guard import (
    TerminalToolResult,
    raise_for_terminal_tool_result,
    terminal_finalize_prompt,
    tool_free_finalize_messages,
)
from src.config.runtime import get_run_dir_relative, get_subagents_dir
from src.prompts.prompts import *
from src.tools.common import PROJECT_ROOT

# Import tools so their @register_tool side effects run (string refs in function_list)
from src.tools.read_attachment import AttachmentReadTool  # noqa: F401
from src.tools.read_markdown_files import MarkDownReadTool  # noqa: F401
from src.tools.read_yaml_files import YamlReadTool  # noqa: F401
from src.tools.web_fetch import WebFetchTool  # noqa: F401
from src.tools.web_search import WebSearchTool  # noqa: F401
from src.tools.write_result import WriteResult  # noqa: F401


class BaseSubAgent(FnCallAgent):
    """Declarative sub-agent: override class attributes only."""

    SUBAGENT_NAME: str = ''
    STEP_CONTENT: str = ''
    SYSTEM_PROMPT: str = ''
    USER_PROMPT: str = 'Now start your working according to the previous messages and information.'
    TOOLS: List[Union[str, Dict, BaseTool]] = []

    # Cap on how much of a result file is injected into the next agent's
    # context. Unbounded injection lets a long retrieval result snowball
    # through every later step until the context window overflows; the full
    # text stays on disk and every workflow agent has MarkDownReadTool.
    BACK_PROMPT_RESULT_MAX_CHARS: int = 8000

    def __init__(
        self,
        function_list: Optional[List[Union[str, Dict, BaseTool]]] = None,
        llm: Optional[Union[Dict, BaseChatModel]] = None,
        **kwargs,
    ):
        assert self.SUBAGENT_NAME, 'SUBAGENT_NAME is required'
        assert self.SYSTEM_PROMPT, 'SYSTEM_PROMPT is required'
        super().__init__(
            function_list=function_list if function_list is not None else self.TOOLS,
            llm=llm,
            # qwen-agent tags every output message with this name; the WebUI
            # uses it to fold sub-agent transcripts into collapsible blocks.
            name=self.SUBAGENT_NAME,
            **kwargs,
        )
        self._last_output_text = ''
        self._truncated = False

    def _run(self, messages: List[Message], **kwargs) -> Iterator[List[Message]]:
        new_messages = copy.deepcopy(messages)

        # New system prompt for the subagent.
        # Role is ASSISTANT because SYSTEM must stay unique at position 0.
        # <RUN_DIR> is filled at runtime so result files land in the current run's directory.
        system_prompt = self.SYSTEM_PROMPT.replace('<RUN_DIR>', str(get_run_dir_relative()))
        new_messages.append(Message(ASSISTANT, system_prompt))

        # User prompt to activate the task (with the real date so the model
        # never has to guess it)
        new_messages.append(Message(USER, f'{self.USER_PROMPT}\n(Current date: {date.today().isoformat()})'))

        rsp: List[Message] = []
        terminal_result: TerminalToolResult | None = None
        try:
            for rsp in super()._run(messages=new_messages, **kwargs):
                yield rsp
        except TerminalToolResult as exc:
            terminal_result = exc

        if terminal_result is not None:
            finalize_messages = tool_free_finalize_messages(
                new_messages,
                rsp,
                terminal_finalize_prompt(terminal_result),
            )
            fin: List[Message] = []
            for fin in self._call_llm(messages=finalize_messages, functions=[]):
                yield rsp + fin
            self._last_output_text = self._extract_last_text(fin)
            self._truncated = False
            self._save_result_file()
            return

        self._last_output_text = self._extract_last_text(rsp)
        self._truncated = self._was_truncated(rsp)
        if self._truncated:
            # The framework LLM-call cap cut the tool loop mid-work. Force one
            # tool-free finalization round so the sub-agent still concludes in
            # writing instead of vanishing without a result.
            finalize_messages = tool_free_finalize_messages(
                new_messages,
                rsp,
                FINALIZE_USER_PROMPT,
            )
            fin: List[Message] = []
            for fin in self._call_llm(messages=finalize_messages, functions=[]):
                yield fin
            final_text = self._extract_last_text(fin)
            if final_text:
                rsp = rsp + fin
                self._last_output_text = final_text
                self._truncated = False  # concluded in writing despite the cut tool loop
        # The result file is written by the framework, not the model: small
        # models cannot reliably nest a multi-thousand-character document
        # into a JSON tool argument, so the model simply ends with a plain
        # Markdown reply and we persist it here.
        self._save_result_file()

    def _call_tool(self, tool_name, tool_args='{}', **kwargs):
        result = super()._call_tool(tool_name, tool_args, **kwargs)
        raise_for_terminal_tool_result(tool_name, result)
        return result

    def _save_result_file(self) -> None:
        if not self._last_output_text.strip():
            return
        result_path = get_subagents_dir() / f'{self.SUBAGENT_NAME}_result.md'
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(self._last_output_text, encoding='utf-8')

    @staticmethod
    def _was_truncated(rsp: List[Message]) -> bool:
        """True when the run ended on an unresolved tool call.

        FnCallAgent silently stops after MAX_LLM_CALL_PER_RUN LLM calls; the
        tell-tale sign is a final assistant message that still asks for a
        tool. Downstream steps should know the result is incomplete.
        """
        if not rsp:
            return False
        last = rsp[-1]
        if last['role'] != ASSISTANT:
            return False
        if last.get('function_call'):
            return True
        content = last.get('content')
        if isinstance(content, str):
            return '<tool_call>' in content
        if isinstance(content, list):
            return any('<tool_call>' in (item.get('text') or '') for item in content)
        return False

    def get_back_prompt(self) -> str:
        """Back prompt for the main agent, read from the sub-agent's result file.

        Falls back to the sub-agent's final reply if the result file is missing.
        """
        result_path = get_subagents_dir() / f'{self.SUBAGENT_NAME}_result.md'
        if result_path.exists():
            result = result_path.read_text(encoding='utf-8')
            if len(result) > self.BACK_PROMPT_RESULT_MAX_CHARS:
                relative_path = get_run_dir_relative() / 'sub_agents' / result_path.name
                result = result[: self.BACK_PROMPT_RESULT_MAX_CHARS] + (
                    f'\n\n...(result truncated at {self.BACK_PROMPT_RESULT_MAX_CHARS} chars; '
                    f'the complete result is saved at {relative_path} — read it with '
                    'MarkDownReadTool if you need the full text)'
                )
        else:
            result = ('(WARNING: sub-agent did not write its result file; '
                      'falling back to its final reply)\n') + (self._last_output_text or '(no output)')
        if getattr(self, '_truncated', False):
            result = ('(NOTE: this sub-agent was cut off by the framework LLM-call limit '
                      'while still working; its result may be incomplete)\n') + result
        return MAIN_AGENT_BACK_PROMPT_TEMPLATE.format(
            sub_agent_name=self.SUBAGENT_NAME,
            step_content=self.STEP_CONTENT,
            result=result,
        )

    @staticmethod
    def _extract_last_text(rsp: List[Message]) -> str:
        for msg in reversed(rsp or []):
            if msg['role'] != ASSISTANT:
                continue
            content = msg.get('content')
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                text = ''.join(item.get('text') or '' for item in content)
                if text.strip():
                    return text
        return ''


class RoutingSubAgent(BaseSubAgent):
    """Routing SubAgent: identify issue profile, domains and jurisdictions."""

    SUBAGENT_NAME = 'routing_subagent'
    STEP_CONTENT = 'Step 2: Identify the issue profile, domains, jurisdictions'
    SYSTEM_PROMPT = ROUTING_SUBAGENT_SYSTEM_PROMPT
    USER_PROMPT = ROUTING_SUBAGENT_USER_PROMPT


class RagSubAgent(BaseSubAgent):
    """RAG SubAgent: retrieve official policy sources per routing result."""

    SUBAGENT_NAME = 'rag_subagent'
    STEP_CONTENT = 'Step 3: Retrieve official policy sources and case-law references'
    SYSTEM_PROMPT = RAG_SUBAGENT_SYSTEM_PROMPT
    USER_PROMPT = RAG_SUBAGENT_USER_PROMPT


class ValidateSubAgent(BaseSubAgent):
    """Validate SubAgent: verify regulatory validity and amendment lineage."""

    SUBAGENT_NAME = 'validate_subagent'
    STEP_CONTENT = 'Step 4: Verify source status, effective dates and amendment lineage'
    SYSTEM_PROMPT = VALIDATE_SUBAGENT_SYSTEM_PROMPT
    USER_PROMPT = VALIDATE_SUBAGENT_USER_PROMPT


class TaxPolicyAnalystSubAgent(BaseSubAgent):
    """Tax policy specialist: withholding, income tax, GST/VAT, treaty relief."""

    SUBAGENT_NAME = 'tax_policy_analyst'
    STEP_CONTENT = 'Step 5: Analyze tax treatment per the routing result'
    SYSTEM_PROMPT = TAX_ANALYST_SYSTEM_PROMPT
    USER_PROMPT = TAX_ANALYST_USER_PROMPT


class FundsComplianceAnalystSubAgent(BaseSubAgent):
    """Funds compliance specialist: FX, AML/KYC, sanctions, payment licensing."""

    SUBAGENT_NAME = 'funds_compliance_analyst'
    STEP_CONTENT = 'Step 5: Analyze funds compliance per the routing result'
    SYSTEM_PROMPT = FUNDS_ANALYST_SYSTEM_PROMPT
    USER_PROMPT = FUNDS_ANALYST_USER_PROMPT


class CommercialLawAnalystSubAgent(BaseSubAgent):
    """Commercial law specialist: formation, share transfer, contracts, licenses."""

    SUBAGENT_NAME = 'commercial_law_analyst'
    STEP_CONTENT = 'Step 5: Analyze corporate and commercial law per the routing result'
    SYSTEM_PROMPT = COMMERCIAL_ANALYST_SYSTEM_PROMPT
    USER_PROMPT = COMMERCIAL_ANALYST_USER_PROMPT


class CitationVerifierSubAgent(BaseSubAgent):
    """Citation verifier: check conclusion support, jurisdiction and reliability."""

    SUBAGENT_NAME = 'citation_verifier'
    STEP_CONTENT = 'Step 6: Verify citations and source support before finalizing'
    SYSTEM_PROMPT = VERIFY_CITATION_SUBAGENT_SYSTEM_PROMPT
    USER_PROMPT = VERIFY_CITATION_SUBAGENT_USER_PROMPT


class ReportWritingSubAgent(BaseSubAgent):
    """Report writer: synthesize the final report per the output contract."""

    SUBAGENT_NAME = 'report_writing'
    STEP_CONTENT = 'Step 7: Write the final report per the output contract'
    SYSTEM_PROMPT = REPORT_WRITING_SUBAGENT_SYSTEM_PROMPT
    USER_PROMPT = REPORT_WRITING_SUBAGENT_USER_PROMPT


class FunctionalSubAgent(FnCallAgent):
    """Generic single-shot functional base subagent.

    Accuracy comes from context cleanliness. Each
    run_task call is one-shot.

    Current usage example: policy-question detection, routing-result analyst selection.
    """
    OUTPUT_SPEC = ""
    RESULT_TYPE = None

    def __init__(
        self,
        function_list: Optional[List[Union[str, Dict, BaseTool]]] = None,
        llm: Optional[Union[Dict, BaseChatModel]] = None,
        **kwargs,
    ):
        super().__init__(
            llm=llm,
            system_message=FUNCTIONAL_SUBAGENT_SYSTEM_PROMPT,
            function_list=function_list,
             **kwargs
        )

    def run_task(self, input_text, output_path):
        """Run once with a clean context; the model writes the formatted output.

        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        user_prompt = FUNCTIONAL_TASK_USER_PROMPT_TEMPLATE.format(
            input_text = input_text,
            output_spec = self.OUTPUT_SPEC,
            # Model-facing paths stay relative to the project root, matching
            # the path convention of all other tools.
            output_path = output_path.relative_to(PROJECT_ROOT)
        )

        # User message run
        for _ in self.run([Message(USER, user_prompt)]):
            pass
        result = json5.loads(output_path.read_text(encoding = "utf-8"))
        
        # Check the result type
        assert(isinstance(result, self.RESULT_TYPE))

        return result

class ModeDetector(FunctionalSubAgent):
    """ Mode Detector:
    """
    OUTPUT_SPEC = MODE_DETECTION_OUTPUT_SPEC
    RESULT_TYPE = Dict

class AnalystsSelector(FunctionalSubAgent):
    """ Analysts Selector: pick domain analysts from the routing result.
    """
    OUTPUT_SPEC = ANALYST_SELECTION_OUTPUT_SPEC
    RESULT_TYPE = Dict
