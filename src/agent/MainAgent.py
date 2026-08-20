from qwen_agent.agents import Assistant
from qwen_agent.gui import WebUI
from src.prompts.prompts import MAIN_AGENT_SYS_PROMPT
from typing import Optional
from src.tools.read_markdown_files import MarkDownReadTool

from src.config.llm import load_llm_config

def init_agent_service(model_name : Optional[str] = "finance-27b"):

    llm_config = load_llm_config(model_name=model_name)
    system_prompt = MAIN_AGENT_SYS_PROMPT
    tools = ['MarkDownReadTool']

    bot = Assistant(
        llm = llm_config,
        name = "3wagent",
        description = "3wagent: a policy research agent", 
        function_list=tools,
        system_message = system_prompt
    )

    return bot

def run_3wagent():
    # Define Agent
    bot = init_agent_service()
    chatbot_config = {
        "prompt.suggestions" : [
            "hello",
            "hi"
        ]
    }

    # Run The GUI Agent
    WebUI(
        bot,
        chatbot_config=chatbot_config
    ).run()

if __name__ == "__main__":
    run_3wagent()
