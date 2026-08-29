"""Offline tests for the open-websearch client, policy, and Qwen tools."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

import pytest
from src.config.websearch import WebSearchSettings
from src.websearch.client import OpenWebSearchClient, OpenWebSearchError
from src.websearch.policy import is_official_url, load_jurisdiction_search_policy
from src.websearch.protocol import FetchResponse, SearchResponse, SearchResult


def test_src_is_the_self_contained_runtime_root():
    from src.tools.common import PROJECT_ROOT, resolve_project_path

    expected_root = Path(__file__).resolve().parents[1]
    assert PROJECT_ROOT == expected_root
    for relative_path in (
        "config/jurisdictions.yaml",
        "config/routing.yaml",
        "config/source-levels.yaml",
        "config/output-contract.yaml",
        "sources/cn.yaml",
        "templates/report.md",
        "infra/open-websearch/package.json",
    ):
        assert resolve_project_path(relative_path).is_file()

    with pytest.raises(ValueError):
        resolve_project_path("../config/jurisdictions.yaml")


def _json_transport(payload: dict, status: int = 200):
    def transport(request, timeout):
        return status, json.dumps(payload).encode("utf-8")

    return transport


def test_settings_are_injectable_and_clamped():
    settings = WebSearchSettings.from_env(
        {
            "OPEN_WEBSEARCH_URL": "http://localhost:4321/",
            "WEBSEARCH_TIMEOUT_SECONDS": "999",
            "WEBSEARCH_MAX_RESULTS": "0",
            "WEBFETCH_MAX_CHARS": "500",
            "WEBSEARCH_FALLBACK_TO_SEARXNG": "true",
            "OPEN_WEBSEARCH_AUTOSTART": "false",
            "OPEN_WEBSEARCH_STARTUP_TIMEOUT_SECONDS": "999",
        }
    )

    assert settings.base_url == "http://localhost:4321"
    assert settings.timeout_seconds == 120
    assert settings.max_results == 1
    assert settings.max_fetch_chars == 1_000
    assert settings.fallback_to_searxng is True
    assert settings.auto_start is False
    assert settings.startup_timeout_seconds == 120


def test_settings_reject_remote_service_by_default():
    with pytest.raises(ValueError, match="localhost"):
        WebSearchSettings.from_env({"OPEN_WEBSEARCH_URL": "https://search.example.com"})


def test_search_normalizes_daemon_response_and_preserves_partial_failures():
    envelope = {
        "status": "ok",
        "data": {
            "query": "withholding tax",
            "engines": ["bing", "duckduckgo"],
            "totalResults": 1,
            "results": [
                {
                    "title": "Official guidance",
                    "url": "https://www.irs.gov/example",
                    "description": "Guidance text",
                    "source": "web",
                    "engine": "bing",
                }
            ],
            "partialFailures": [
                {"engine": "duckduckgo", "code": "engine_error", "message": "blocked"}
            ],
        },
        "error": None,
        "hint": None,
    }
    client = OpenWebSearchClient(
        WebSearchSettings(max_results=5), transport=_json_transport(envelope)
    )

    response = client.search(" withholding tax ", limit=50, engines=["bing", "duckduckgo", "bing"])

    assert response.query == "withholding tax"
    assert response.results[0].snippet == "Guidance text"
    assert response.results[0].engine == "bing"
    assert response.partial_failures[0]["engine"] == "duckduckgo"


def test_search_sends_capped_limit_and_unique_engines():
    captured = {}

    def transport(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return 200, json.dumps(
            {
                "status": "ok",
                "data": {"query": "tax", "engines": ["bing"], "results": []},
            }
        ).encode("utf-8")

    client = OpenWebSearchClient(WebSearchSettings(max_results=4), transport=transport)
    client.search("tax", limit=20, engines=["bing", "bing"])

    assert captured["body"]["limit"] == 4
    assert captured["body"]["engines"] == ["bing"]


def test_error_envelope_becomes_structured_exception():
    envelope = {
        "status": "error",
        "data": None,
        "error": {"code": "engine_error", "message": "upstream blocked"},
        "hint": "try another engine",
    }
    client = OpenWebSearchClient(
        WebSearchSettings(), transport=_json_transport(envelope, status=500)
    )

    with pytest.raises(OpenWebSearchError) as caught:
        client.search("tax")

    assert caught.value.code == "engine_error"
    assert caught.value.retryable is True
    assert caught.value.hint == "try another engine"


def test_transport_failure_becomes_service_unavailable():
    def transport(request, timeout):
        raise URLError("offline")

    client = OpenWebSearchClient(WebSearchSettings(), transport=transport)

    with pytest.raises(OpenWebSearchError) as caught:
        client.status()

    assert caught.value.code == "service_unavailable"
    assert caught.value.retryable is True


def test_fetch_normalizes_content_and_rejects_local_targets():
    envelope = {
        "status": "ok",
        "data": {
            "url": "https://example.com/law",
            "finalUrl": "https://example.com/current-law",
            "contentType": "text/html",
            "title": "Current law",
            "retrievalMethod": "request",
            "truncated": False,
            "content": "Article 1 ...",
            "links": [{"text": "Next", "href": "https://example.com/next"}],
        },
    }
    client = OpenWebSearchClient(WebSearchSettings(), transport=_json_transport(envelope))

    response = client.fetch("https://example.com/law")

    assert response.final_url == "https://example.com/current-law"
    assert response.content == "Article 1 ..."
    with pytest.raises(OpenWebSearchError, match="local URLs"):
        client.fetch("http://localhost/admin")
    with pytest.raises(OpenWebSearchError, match="private or local"):
        client.fetch("http://127.0.0.1/admin")


def test_jurisdiction_policy_and_official_domain_matching():
    policy = load_jurisdiction_search_policy("CN")

    assert policy is not None
    assert policy.engines == ["bing", "baidu", "sogou"]
    assert is_official_url("https://sub.safe.gov.cn/policy", policy.official_domains)
    assert not is_official_url("https://safe.gov.cn.example.com/fake", policy.official_domains)


def test_every_jurisdiction_has_web_search_policy():
    for jurisdiction in ("CN", "US", "HK", "SG"):
        policy = load_jurisdiction_search_policy(jurisdiction)
        assert policy is not None
        assert policy.engines
        assert policy.official_domains


def test_supervisor_reuses_an_existing_daemon(monkeypatch):
    from src.websearch.supervisor import OpenWebSearchSupervisor

    supervisor = OpenWebSearchSupervisor(WebSearchSettings())
    monkeypatch.setattr(supervisor, "_daemon_ready", lambda: True)

    assert supervisor.start() is False
    assert supervisor.owns_process is False


def test_supervisor_starts_and_stops_its_owned_daemon(monkeypatch, tmp_path):
    import src.websearch.supervisor as supervisor_module
    from src.websearch.supervisor import OpenWebSearchSupervisor

    executable = tmp_path / "infra" / "open-websearch" / "node_modules" / ".bin"
    executable.mkdir(parents=True)
    (executable / "open-websearch").touch()

    class FakeProcess:
        def __init__(self):
            self.returncode = None
            self.terminated = False

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = 0

        def wait(self, timeout):
            return self.returncode

        def kill(self):
            self.returncode = -9

    process = FakeProcess()
    invocation = {}

    def fake_popen(args, **kwargs):
        invocation["args"] = args
        invocation["kwargs"] = kwargs
        return process

    readiness = iter((False, True))
    monkeypatch.setattr(supervisor_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(supervisor_module.subprocess, "Popen", fake_popen)
    supervisor = OpenWebSearchSupervisor(WebSearchSettings(startup_timeout_seconds=1))
    monkeypatch.setattr(supervisor, "_daemon_ready", lambda: next(readiness))

    assert supervisor.start() is True
    assert invocation["args"][-4:] == ["--host", "127.0.0.1", "--port", "3210"]
    assert supervisor.owns_process is True

    supervisor.stop()
    assert process.terminated is True
    assert supervisor.owns_process is False


def test_qwen_search_tool_marks_and_prioritizes_official_results(monkeypatch):
    from src.tools.web_search import WebSearchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    tool = WebSearchTool()

    class FakeClient:
        def search(self, query, **kwargs):
            return SearchResponse(
                query=query,
                engines=kwargs["engines"],
                results=[
                    SearchResult("Commentary", "https://example.com/post", "", "bing", "web"),
                    SearchResult("IRS", "https://www.irs.gov/payments", "", "bing", "web"),
                ],
            )

    tool.client = FakeClient()
    payload = json.loads(tool.call({"query": "withholding", "jurisdiction": "US"}))

    assert payload["status"] == "ok"
    assert payload["results"][0]["title"] == "IRS"
    assert payload["results"][0]["is_official"] is True
    assert "untrusted" in payload["untrusted_content_notice"].lower()


def test_qwen_fetch_tool_returns_provenance(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    tool = WebFetchTool()

    class FakeClient:
        def fetch(self, url, **kwargs):
            return FetchResponse(
                url=url,
                final_url=url,
                title="Law",
                content_type="text/html",
                retrieval_method="request",
                truncated=False,
                content="Article text",
            )

    tool.client = FakeClient()
    payload = json.loads(tool.call({"url": "https://example.com/law"}))

    assert payload["status"] == "ok"
    assert payload["provider"] == "open_websearch"
    assert payload["content"] == "Article text"
    assert payload["retrieved_at"]


def test_main_agent_assigns_web_tools_only_to_retrieval_and_verification(monkeypatch):
    from qwen_agent.agents import FnCallAgent
    from src.agent.main_agent import MainAgent

    def fake_agent_init(self, function_list=None, **kwargs):
        self.assigned_tools = list(function_list or [])

    monkeypatch.setattr(FnCallAgent, "__init__", fake_agent_init)
    agent = MainAgent(llm=None)

    expected_web_tools = {"WebSearchTool", "WebFetchTool"}
    assert expected_web_tools.issubset(agent.rag_agent.assigned_tools)
    assert expected_web_tools.issubset(agent.validate_agent.assigned_tools)
    assert expected_web_tools.issubset(agent.citation_verifier.assigned_tools)
    for analyst in agent.analysts.values():
        assert expected_web_tools.isdisjoint(analyst.assigned_tools)
    assert expected_web_tools.isdisjoint(agent.report_writer.assigned_tools)


def test_qwen_search_tool_enforces_run_budget(monkeypatch):
    from src.tools import web_search as web_search_module
    from src.tools.web_search import WebSearchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    monkeypatch.setattr(web_search_module, "SEARCH_BUDGET_PER_AGENT", 2)
    # The budget is per tool instance (each agent holds its own), so a fresh
    # instance always starts with a clean counter.
    tool = WebSearchTool()

    class FakeClient:
        def search(self, query, **kwargs):
            return SearchResponse(
                query=query,
                engines=kwargs["engines"],
                results=[SearchResult("IRS", "https://www.irs.gov/payments", "", "bing", "web")],
            )

    tool.client = FakeClient()
    assert json.loads(tool.call({"query": "a", "jurisdiction": "US"}))["status"] == "ok"
    assert json.loads(tool.call({"query": "b", "jurisdiction": "US"}))["status"] == "ok"

    payload = json.loads(tool.call({"query": "c", "jurisdiction": "US"}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "search_budget_exhausted"
    assert "STOP searching" in payload["error"]["message"]


def test_qwen_fetch_tool_enforces_budget_and_clamps_max_chars(monkeypatch):
    from src.tools import web_fetch as web_fetch_module
    from src.tools.web_fetch import WebFetchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    monkeypatch.setattr(web_fetch_module, "FETCH_BUDGET_PER_AGENT", 2)
    tool = WebFetchTool()

    seen_max_chars = []

    class FakeClient:
        def fetch(self, url, **kwargs):
            seen_max_chars.append(kwargs["max_chars"])
            return FetchResponse(
                url=url,
                final_url=url,
                title="Law",
                content_type="text/html",
                retrieval_method="request",
                truncated=False,
                content="Article text",
            )

    tool.client = FakeClient()
    assert json.loads(tool.call({"url": "https://a.gov.cn/1", "max_chars": 20000}))["status"] == "ok"
    assert json.loads(tool.call({"url": "https://a.gov.cn/2"}))["status"] == "ok"

    # max_chars is clamped to the server-side cap regardless of the request
    assert seen_max_chars[0] == web_fetch_module.MAX_FETCH_CHARS_CAP

    payload = json.loads(tool.call({"url": "https://a.gov.cn/3"}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "fetch_budget_exhausted"
    assert "STOP fetching" in payload["error"]["message"]
