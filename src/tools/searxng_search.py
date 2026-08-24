from qwen_agent.tools.base import BaseTool, register_tool
import json5
import json
import os
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888").rstrip("/")

# Local service: never route through proxy env vars
_opener = build_opener(ProxyHandler({}))


@register_tool('SearxngSearchTool')
class SearxngSearchTool(BaseTool):
    name = "SearxngSearchTool"
    description = ("Search the public web via the local SearXNG instance, return titles, urls and snippets. "
                   "Use SHORT queries (1-3 key terms) for best results, e.g. '增值税法 境外服务'. "
                   "Use this as a fallback after reading the local sources/ registry.")
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "description": "Short search query, 1-3 key terms, Chinese or English",
                "type": "string"
            },
            "limit": {
                "description": "Max number of results, default 10",
                "type": "integer"
            }
        },
        "required": ["query"]
    }

    MAX_EMPTY_RETRIES = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._consecutive_empty = 0

    def call(self, params: str, **kwargs) -> str:
        par = json5.loads(params)
        query = par["query"].strip()
        if not query:
            return "error: query is required"

        if self._consecutive_empty >= self.MAX_EMPTY_RETRIES:
            return ("error: web search is unavailable right now (engines rate-limited). "
                    "STOP searching and proceed with the local sources/ registry only.")

        limit = max(1, min(int(par.get("limit", 10)), 20))
        url = f"{SEARXNG_URL}/search?{urlencode({'q': query, 'format': 'json'})}"
        try:
            with _opener.open(url, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return f"error: searxng request failed: {exc}. Ensure the local SearXNG container is running (docker start searxng)."
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
            for item in payload.get("results", [])[:limit]
        ]
        if not results:
            self._consecutive_empty += 1
            remaining = self.MAX_EMPTY_RETRIES - self._consecutive_empty
            return f"error: no results. Retries left: {remaining}. Try ONE shorter query (1-2 key terms); if that fails, proceed without web search."
        self._consecutive_empty = 0
        return json.dumps(results, ensure_ascii=False, indent=2)
