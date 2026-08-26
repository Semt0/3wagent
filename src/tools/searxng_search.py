from qwen_agent.tools.base import BaseTool, register_tool
import json
import os
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler

from src.tools.common import parse_tool_params

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://127.0.0.1:8888").rstrip("/")

# Local service: never route through proxy env vars
_opener = build_opener(ProxyHandler({}))


@register_tool('SearxngSearchTool')
class SearxngSearchTool(BaseTool):
    name = "SearxngSearchTool"
    description = ("Search the public web via the local SearXNG instance, return titles, urls and snippets. "
                   "Call format: <tool_call>\n"
                   "{\"name\": \"SearxngSearchTool\", \"arguments\": {\"query\": \"增值税法 境外服务\"}}\n"
                   "</tool_call>\n"
                   "Short queries (1-3 key terms) work best; longer queries are automatically split into "
                   "shorter sub-queries. Use this as a fallback after reading the local sources/ registry.")
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "description": "Search query, 1-3 key terms, Chinese or English",
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
    MAX_QUERY_TERMS = 3
    MAX_SPLIT_QUERIES = 4

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._consecutive_empty = 0

    def call(self, params: str, **kwargs) -> str:
        try:
            par = parse_tool_params(params)
        except Exception:
            return ('error: invalid arguments. Use a JSON object like '
                    '{"query": "增值税法"} (arguments itself must NOT be a quoted string).')
        query = str(par.get("query", "")).strip()
        if not query:
            return 'error: missing required parameter "query"'

        if self._consecutive_empty >= self.MAX_EMPTY_RETRIES:
            return ("error: web search is unavailable right now (engines rate-limited). "
                    "STOP searching and proceed with the local sources/ registry only.")

        limit = max(1, min(int(par.get("limit", 10)), 20))
        queries = self._split_queries(query)

        merged, seen = [], set()
        last_error = None
        for q in queries:
            try:
                items = self._search(q)
            except Exception as exc:
                last_error = exc
                continue
            for item in items:
                url = item.get("url", "")
                if url and url not in seen:
                    seen.add(url)
                    merged.append(item)
                if len(merged) >= limit:
                    break

        if not merged:
            if last_error is not None:
                return (f"error: searxng request failed: {last_error}. "
                        "Ensure the local SearXNG container is running (docker start searxng).")
            self._consecutive_empty += 1
            remaining = self.MAX_EMPTY_RETRIES - self._consecutive_empty
            return f"error: no results. Retries left: {remaining}. If this persists, proceed without web search."

        self._consecutive_empty = 0
        return json.dumps(merged[:limit], ensure_ascii=False, indent=2)

    def _split_queries(self, query: str) -> list:
        """Split long queries into single-term sub-queries; engines treat
        space-separated terms as strict AND, which returns nothing for long queries."""
        terms = query.split()
        if len(terms) <= self.MAX_QUERY_TERMS:
            return [query]
        return terms[: self.MAX_SPLIT_QUERIES]

    def _search(self, query: str) -> list:
        url = f"{SEARXNG_URL}/search?{urlencode({'q': query, 'format': 'json'})}"
        with _opener.open(url, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
            }
            for item in payload.get("results", [])
        ]
