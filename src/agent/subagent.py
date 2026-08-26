"""Sub-agents of 3wagent.

All sub-agents share one mechanism (BaseSubAgent): receive messages, work with
tools, write a result file, then report back to the main agent. Concrete
sub-agents only declare identity and prompts as class attributes.
"""

import copy
from datetime import date
from typing import Dict, Iterator, List, Optional, Union

from qwen_agent.agents import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ASSISTANT, USER, Message
from qwen_agent.tools import BaseTool

from src.prompts.prompts import (
    MAIN_AGENT_BACK_PROMPT_TEMPLATE,
    RAG_SUBAGENT_SYSTEM_PROMPT,
    RAG_SUBAGENT_USER_PROMPT,
    ROUTING_SUBAGENT_SYSTEM_PROMPT,
    ROUTING_SUBAGENT_USER_PROMPT,
    COMMERCIAL_ANALYST_SYSTEM_PROMPT,
    COMMERCIAL_ANALYST_USER_PROMPT,
    FUNDS_ANALYST_SYSTEM_PROMPT,
    FUNDS_ANALYST_USER_PROMPT,
    TAX_ANALYST_SYSTEM_PROMPT,
    TAX_ANALYST_USER_PROMPT,
    VALIDATE_SUBAGENT_SYSTEM_PROMPT,
    VALIDATE_SUBAGENT_USER_PROMPT,
    VERIFY_CITATION_SUBAGENT_SYSTEM_PROMPT,
    VERIFY_CITATION_SUBAGENT_USER_PROMPT,
    REPORT_WRITING_SUBAGENT_SYSTEM_PROMPT,
    REPORT_WRITING_SUBAGENT_USER_PROMPT,
)
from src.config.runtime import get_run_dir_relative, get_subagents_dir
from src.tools.common import PROJECT_ROOT

# Import tools so their @register_tool side effects run (string refs in function_list)
from src.tools.read_markdown_files import MarkDownReadTool  # noqa: F401
from src.tools.read_yaml_files import YamlReadTool  # noqa: F401
from src.tools.write_result import WriteResult  # noqa: F401
from src.tools.searxng_search import SearxngSearchTool  # noqa: F401


class BaseSubAgent(FnCallAgent):
    """Declarative sub-agent: override class attributes only."""

    SUBAGENT_NAME: str = ''
    STEP_CONTENT: str = ''
    SYSTEM_PROMPT: str = ''
    USER_PROMPT: str = 'Now start your working according to the previous messages and information.'
    TOOLS: List[Union[str, Dict, BaseTool]] = []

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
            **kwargs,
        )
        self._last_output_text = ''

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
        for rsp in super()._run(messages=new_messages, **kwargs):
            yield rsp
        self._last_output_text = self._extract_last_text(rsp)

    def get_back_prompt(self) -> str:
        """Back prompt for the main agent, read from the sub-agent's result file.

        Falls back to the sub-agent's final reply if the result file is missing.
        """
        result_path = get_subagents_dir() / f'{self.SUBAGENT_NAME}_result.md'
        if result_path.exists():
            result = result_path.read_text(encoding='utf-8')
        else:
            result = ('(WARNING: sub-agent did not write its result file; '
                      'falling back to its final reply)\n') + (self._last_output_text or '(no output)')
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
    """Generic single-shot functional subagent with a clean context.

    Unlike BaseSubAgent (workflow stages sharing conversation history), this
    agent receives ONLY its role prompt, the input and the output spec — no
    history, no tools. Accuracy comes from context cleanliness. The formatted
    output is written to a file so consumers read results via the same
    file-based protocol as the workflow subagents.

    Current uses: policy-question detection, routing-result analyst selection.
    """

    def __init__(
        self,
        role_prompt: str,
        llm: Optional[Union[Dict, BaseChatModel]] = None,
        **kwargs,
    ):
        super().__init__(function_list=[], llm=llm, system_message=role_prompt, **kwargs)

    def run_task(self, input_text: str, output_spec: str, output_path) -> str:
        """Run once with a clean context and write the formatted output to a file.

        Args:
            input_text: the input to judge/transform.
            output_spec: the formatted output requirements for the model.
            output_path: file to write the formatted output into; consumers
                should read the result from this file (file-based protocol).
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        user_msg = f"{input_text}\n\nOutput requirements:\n{output_spec}"
        messages = [Message(USER, user_msg)]
        rsp: List[Message] = []
        for rsp in self.run(messages):
            pass
        result = self._extract_last_text(rsp)
        output_path.write_text(result, encoding='utf-8')
        return result

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
