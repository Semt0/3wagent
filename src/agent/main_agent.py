from typing import Dict, Iterator, List, Literal, Optional, Union

from qwen_agent.agents import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import Message

from src.agent.attachments import inline_uploaded_files
from src.config.llm import load_llm_config
from src.config.webui import WEBUI_CHATBOT_CONFIG
from src.prompts.prompts import MAIN_AGENT_SYS_PROMPT
from src.tools.read_markdown_files import MarkDownReadTool  # noqa: F401
from src.tools.read_yaml_files import YamlReadTool  # noqa: F401


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
        super().__init__(
            llm=llm,
            function_list=tools,
            system_message=MAIN_AGENT_SYS_PROMPT,
            name='3wagent',
            description='跨境政策合规分析助手：资金合规、税务、民商法多领域协同分析。',
        )

    def _run(
        self,
        messages: List[Message],
        lang: Literal['en', 'zh'] = 'en',
        **kwargs,
    ) -> Iterator[List[Message]]:
        ### Step 1: Resolve the attached files
        attachment_resolution = inline_uploaded_files(messages[-1])
        if attachment_resolution.should_block:
            yield [
                Message(
                    role='assistant',
                    content=(
                        '暂时无法读取你上传的附件。请上传 Markdown、TXT 或 YAML 文件，'
                        '或者在消息中补充具体问题后重试。'
                    ),
                )
            ]
            return

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

        yield from super()._run(messages=messages, lang=lang, **kwargs)

def run_3wagent(model_name):
    # Imported lazily so headless usage/tests don't require qwen-agent[gui]
    from src.agent.webui import ThemedWebUI

    # Define Agent
    bot = MainAgent(llm = load_llm_config(model_name=model_name))

    # Run The GUI Agent
    ThemedWebUI(
        bot,
        chatbot_config=WEBUI_CHATBOT_CONFIG
    ).run()

if __name__ == "__main__":
    run_3wagent()
