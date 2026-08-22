from typing import Dict, Iterator, List, Optional, Union
import copy

from qwen_agent.agents import FnCallAgent
from qwen_agent.tools import BaseTool
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ASSISTANT, Message,USER

from src.prompts.prompts import ROUTING_SUBAGENT_SYSTEM_PROMPT,ROUTING_SUBAGENT_USER_PROMPT, MAIN_AGENT_BACK_PROMPT_TEMPLATE

class RoutingSubAgent(FnCallAgent):
    """Routing SubAgent
    """

    def __init__(
        self,
        function_list:Optional[List[Union[str, Dict,BaseTool]]] = None,
        llm: Optional[Union[Dict, BaseChatModel]] = None
    ):
        super().__init__(function_list=function_list, llm=llm)
    
    def _run(
        self,
        messages: List[Message],
        **kwargs
    ) -> Iterator[List[Message]]:
        new_messages = copy.deepcopy(messages)

        # New System Prompt for subagent
        # The Role is ASSISTANT, duo to that SYSTEM is unique
        new_messages.append(Message(ASSISTANT, ROUTING_SUBAGENT_SYSTEM_PROMPT))

        # User Prompt to Activate Task
        new_messages.append(Message(USER, ROUTING_SUBAGENT_USER_PROMPT))
        yield from super()._run(messages=new_messages)
    
    def GetMainAgentBackPrompt(self):
        with open("workspace/sub_agents/routing_subagent_result.md", "r", encoding="utf-8") as f:
            result_content = f.read()
        return MAIN_AGENT_BACK_PROMPT_TEMPLATE.format(
            sub_agent_name = "routing_agent",
            step_content = "Step 2: Identify the issue profile, domains, jurisdictions",
            result = result_content
        )

