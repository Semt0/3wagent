"""Generic single-shot functional sub-agent (clean context, structured output).

Kept separate from ``subagent.py`` so that tool-layer modules (e.g.
``tools/web_search.py``) can use functional sub-agents without an import
cycle: this module must never import from ``src.tools``.
"""

from typing import Any, Dict, List, Optional, Union

from qwen_agent.agents import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import USER, Message
from qwen_agent.tools import BaseTool

from src.agent.results import resolve_structured_result
from src.agent.tool_call_compat import ToolCallCompatibilityMixin
from src.prompts.prompts import (
    FUNCTIONAL_SUBAGENT_SYSTEM_PROMPT,
    FUNCTIONAL_TASK_USER_PROMPT_TEMPLATE,
)


class FunctionalSubAgent(ToolCallCompatibilityMixin, FnCallAgent):
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
        """Run once, validate direct structured output, and persist it."""

        user_prompt = FUNCTIONAL_TASK_USER_PROMPT_TEMPLATE.format(
            input_text=input_text,
            output_spec=self.OUTPUT_SPEC,
        )

        rsp: List[Message] = []
        for rsp in self.run([Message(USER, user_prompt)]):
            pass
        return resolve_structured_result(rsp, output_path, self.RESULT_TYPE)

    def run_with_messages(self, messages: List[Message], output_path) -> Any:
        """One-shot structured task over an existing conversation context."""
        rsp: List[Message] = []
        for rsp in self.run(messages):
            pass
        return resolve_structured_result(rsp, output_path, self.RESULT_TYPE)
