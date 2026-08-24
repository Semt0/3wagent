from typing import Dict, Iterator, List, Optional, Union
import copy

from qwen_agent.agents import FnCallAgent
from qwen_agent.tools import BaseTool
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ASSISTANT, Message, USER

from src.prompts.prompts import RAG_SUBAGENT_SYSTEM_PROMPT, RAG_SUBAGENT_USER_PROMPT, MAIN_AGENT_BACK_PROMPT_TEMPLATE
from src.tools.common import PROJECT_ROOT
# Import tools so their @register_tool side effects run (string refs in function_list)
from src.tools.read_markdown_files import MarkDownReadTool  # noqa: F401
from src.tools.read_yaml_files import YamlReadTool  # noqa: F401
from src.tools.write_result import WriteResult  # noqa: F401
from src.tools.searxng_search import SearxngSearchTool  # noqa: F401


class RagSubAgent(FnCallAgent):
    """RAG SubAgent: retrieve official policy sources per routing result.
    """

    def __init__(
        self,
        function_list: Optional[List[Union[str, Dict, BaseTool]]] = None,
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
        new_messages.append(Message(ASSISTANT, RAG_SUBAGENT_SYSTEM_PROMPT))

        # User Prompt to Activate Task
        new_messages.append(Message(USER, RAG_SUBAGENT_USER_PROMPT))
        yield from super()._run(messages=new_messages)

    def GetMainAgentBackPrompt(self):
        result_path = PROJECT_ROOT / "workspace/sub_agents/rag_subagent_result.md"
        result_content = result_path.read_text(encoding="utf-8")
        return MAIN_AGENT_BACK_PROMPT_TEMPLATE.format(
            sub_agent_name="rag_subagent",
            step_content="Step 3: Retrieve official policy sources and case-law references",
            result=result_content
        )
