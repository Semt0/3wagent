from app.core.config import settings


def get_chat_model():
    """Return the configured LangChain chat model, or None when LLM is not configured."""
    provider = settings.llm_provider.lower().replace("-", "_")

    if provider in {"openai", "openai_compatible"}:
        return _openai_chat_model()
    if provider == "anthropic":
        return _anthropic_chat_model()
    if provider == "ollama":
        return _ollama_chat_model()

    return None


def _openai_chat_model():
    if not settings.llm_api_key:
        return None

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    kwargs = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
        "api_key": settings.llm_api_key,
    }
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url

    return ChatOpenAI(**kwargs)


def _anthropic_chat_model():
    if not settings.llm_api_key:
        return None

    try:
        from langchain_anthropic import ChatAnthropic
    except ImportError:
        return None

    return ChatAnthropic(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=settings.llm_api_key,
    )


def _ollama_chat_model():
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        return None

    kwargs = {
        "model": settings.llm_model,
        "temperature": settings.llm_temperature,
    }
    if settings.llm_base_url:
        kwargs["base_url"] = settings.llm_base_url

    return ChatOllama(**kwargs)
