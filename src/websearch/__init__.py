"""Provider-independent web-search integration used by Qwen tools."""

from src.websearch.client import OpenWebSearchClient, OpenWebSearchError

__all__ = ["OpenWebSearchClient", "OpenWebSearchError"]
