from typing import Dict, Iterator, List, Literal, Optional, Union
import copy

from qwen_agent.agents import FnCallAgent
from qwen_agent.llm import BaseChatModel
from qwen_agent.llm.schema import ContentItem, Message, USER, ASSISTANT

from src.agent.attachments import inline_uploaded_files
from src.config.llm import load_llm_config
from src.config.webui import WEBUI_CHATBOT_CONFIG
from src.prompts.prompts import MAIN_AGENT_SYS_PROMPT
from src.tools.read_markdown_files import MarkDownReadTool  # noqa: F401
from src.tools.read_yaml_files import YamlReadTool  # noqa: F401
from src.tools.write_result import WriteResult
from src.tools.searxng_search import SearxngSearchTool  # noqa: F401
from src.agent.subagent import (
    CommercialLawAnalystSubAgent,
    FundsComplianceAnalystSubAgent,
    RagSubAgent,
    RoutingSubAgent,
    TaxPolicyAnalystSubAgent,
    ValidateSubAgent,
)
from src.tools.common import PROJECT_ROOT


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
        super().__init__(
            llm=llm,
            function_list=tools,
            system_message=MAIN_AGENT_SYS_PROMPT,
            name='3wagent',
            description='跨境政策合规分析助手：资金合规、税务、民商法多领域协同分析。',
        )
        self.routing_agent = RoutingSubAgent(function_list=tools, llm=llm)
        self.rag_agent = RagSubAgent(function_list=rag_tools, llm=llm)
        self.validate_agent = ValidateSubAgent(function_list=rag_tools, llm=llm)
        # Domain analysts, selected per routing result (see _select_analysts)
        self.analysts = {
            'tax': TaxPolicyAnalystSubAgent(function_list=rag_tools, llm=llm),
            'funds': FundsComplianceAnalystSubAgent(function_list=rag_tools, llm=llm),
            'commercial': CommercialLawAnalystSubAgent(function_list=rag_tools, llm=llm),
        }

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
        # subagent run
        for rsp in self.validate_agent.run(new_messages):
            yield response + rsp

        # add to previous response
        response.extend(rsp)

        # add the result into MainAgent messages
        new_messages.append(Message(ASSISTANT,self.validate_agent.get_back_prompt()))

        ### Step 5: Domain Analysts selected by the routing result
        for analyst in self._select_analysts():
            for rsp in analyst.run(new_messages):
                yield response + rsp
            response.extend(rsp)
            new_messages.append(Message(ASSISTANT, analyst.get_back_prompt()))

        ### Step 6: Citation-Verifier SubAgent

        ### Step 7: Report Writing SubAgent

        yield from super()._run(messages=new_messages, lang=lang, **kwargs)

    def _select_analysts(self):
        """Pick domain analysts by keyword-matching the routing result.

        Falls back to the tax analyst when nothing matches (tax is the most
        common primary domain for the covered issue types).
        """
        result_path = PROJECT_ROOT / 'workspace' / 'sub_agents' / 'routing_subagent_result.md'
        text = result_path.read_text(encoding='utf-8').lower() if result_path.exists() else ''
        selected = []
        if any(k in text for k in ('funds', '外汇', '资金合规', 'aml', '制裁')):
            selected.append(self.analysts['funds'])
        if any(k in text for k in ('tax', '税务', '预提', '增值税', '所得税')):
            selected.append(self.analysts['tax'])
        if any(k in text for k in ('commercial', '民商', '公司设立', '股权')):
            selected.append(self.analysts['commercial'])
        return selected or [self.analysts['tax']]

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
