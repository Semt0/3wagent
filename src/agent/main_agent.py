from typing import Dict, Iterator, List, Literal, Optional, Union
import copy

from qwen_agent.agents import FnCallAgent
from qwen_agent.gui import WebUI
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ContentItem, Message, USER, ASSISTANT

from src.config.llm import load_llm_config
from src.config.webui import WEBUI_CHATBOT_CONFIG
from src.prompts.prompts import MAIN_AGENT_SYS_PROMPT
from src.tools.read_markdown_files import MarkDownReadTool  # noqa: F401
from src.tools.read_yaml_files import YamlReadTool  # noqa: F401
from src.tools.write_result import WriteResult
from src.tools.searxng_search import SearxngSearchTool  # noqa: F401
from src.agent.subagent import RagSubAgent, RoutingSubAgent


class MainAgent(FnCallAgent):
    """Customize the main agent to resolve policy problem
    Current Design Plan: Automaton Design???
    Need Further Discussion
    """

    def __init__(
        self,
        llm: Optional[Union[Dict, BaseChatModel]] = None,
    ):
        tools = ['MarkDownReadTool', 'YamlReadTool', "WriteResult"]
        rag_tools = tools + ['SearxngSearchTool']
        super().__init__(llm=llm, function_list=tools, system_message=MAIN_AGENT_SYS_PROMPT)
        self.routing_agent = RoutingSubAgent(function_list=tools, llm=llm)
        self.rag_agent = RagSubAgent(function_list=rag_tools, llm=llm)

    def _run(
        self,
        messages: List[Message],
        lang: Literal['en', 'zh'] = 'en',
        **kwargs,
    ) -> Iterator[List[Message]]:
        # DeepCopy, Empty Previous Response
        new_messages = copy.deepcopy(messages)
        response = []

        ### Step 1: Resolve the attached files

        # The Last Message Must Be From User
        assert(new_messages[-1]['role'] == USER)

        # If has attached files
        if isinstance(new_messages[-1]['content'], list) and any([
            item.file for item in new_messages[-1]['content']
        ]):
            new_messages[-1]['content'].append(
                ContentItem(text="\nI have uploaded some files, here are their contents:")
            )
            # TODO: inject the file content into messages

            
        ### SubAgents WorkMode:
        ### SubAgent takes the previous whole messages history as input, as well as its own system prompt and user instruction
        ### Its Last Result(Formatted Results Stored in files) should be injected into MainAgent Messages 
        ### Middle messages can be discarded to save tokens
        
        ### Step 2: Routing SubAgent
        # subagent run
        for rsp in self.routing_agent.run(new_messages):
            yield response + rsp
        
        # add to previous response
        response.extend(rsp)

        # add the result into MainAgent messages
        new_messages.append(Message(ASSISTANT,self.routing_agent.get_back_prompt()))


        ### Step 3: RAG SubAgent
        # subagent run
        for rsp in self.rag_agent.run(new_messages):
            yield response + rsp

        # add to previous response
        response.extend(rsp)

        # add the result into MainAgent messages
        new_messages.append(Message(ASSISTANT,self.rag_agent.get_back_prompt()))

        ### Step 4: Validate SubAgent 

        ### Step 5: Analysis SubAgent For Specific Domain According to Routing Result

        ### Step 6: Citation-Verifier SubAgent

        ### Step 7: Report Writing SubAgent

        yield from super()._run(messages=new_messages, lang=lang, **kwargs)

def run_3wagent(model_name):
    # Define Agent
    bot = MainAgent(llm = load_llm_config(model_name=model_name))

    # Run The GUI Agent
    WebUI(
        bot,
        chatbot_config=WEBUI_CHATBOT_CONFIG
    ).run()

if __name__ == "__main__":
    run_3wagent()
