from app.llm.client import get_chat_model
from app.tools.skills.registry import get_skill_template


def run_skill_chain(skill_name: str, variables: dict[str, str]) -> str | None:
    """Run a runtime skill prompt through LangChain.

    Return None when LangChain or a model provider is not configured, so local MVP
    smoke tests can still run without model access.
    """
    model = get_chat_model()
    if model is None:
        return None

    try:
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
    except ImportError:
        return None

    system_prompt = get_skill_template(skill_name)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            (
                "human",
                "Question:\n{question}\n\nIssue profile:\n{issue_profile}\n\nSources:\n{sources}",
            ),
        ]
    )
    chain = prompt | model | StrOutputParser()
    return chain.invoke(variables)
