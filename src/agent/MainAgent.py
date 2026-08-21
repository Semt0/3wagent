from qwen_agent.agents import FnCallAgent
from qwen_agent.gui import WebUI
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ContentItem, Message


from src.prompts.prompts import MAIN_AGENT_SYS_PROMPT
from src.config.webui import WEBUI_CHATBOT_CONFIG
from src.config.llm import load_llm_config

from typing import Optional,List,Union,Dict,Iterator

class MainAgent(FnCallAgent):
    """Customize the main agent to resolve policy problem
    Current Design Plan: Automaton Design???
    Need Further Discussion
    """

    def __init__(
        self,
        llm: Optional[Union[Dict, BaseChatModel]] = None,
    ):
        tools = ['MarkDownReadTool', 'YamlReadTool']
        super().__init__(llm=llm, function_list=tools, system_message=MAIN_AGENT_SYS_PROMPT)

    def _run(
        self,
        messages: List[Message]
    ) -> Iterator[List[Message]]:
        ### Step 1: Resolve the attached files
        # The Last Message 

        # If has attached files
        if isinstance(messages[-1]['content'], list) and any([
            item.file for item in messages[-1]['content']
        ]):
            messages[-1]['content'].append(
                ContentItem(text="\nI have uploaded some files, here are their contents:")
            )
            # TODO: inject the file content into messages

            
        ### SubAgents WorkMode:
        ### SubAgent takes the previous whole messages history as input
        ### Its Last Return Message(Formatted Results) should be injected into MainAgent Messages 
        ### Middle messages can be discarded to save tokens
        
        ### Step 2: Routing SubAgent

        ### Step 3: RAG SubAgent

        ### Step 4: Validate SubAgent 

        ### Step 5: Analysis SubAgent For Specific Domain According to Routing Result

        ### Step 6: Citation-Verifier SubAgent

        ### Step 7: Report Writing SubAgent

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
