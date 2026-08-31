"""Offline tests for the open-websearch client, policy, and Qwen tools."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

import pytest
from src.config.websearch import WebSearchSettings
from src.websearch.client import OpenWebSearchClient, OpenWebSearchError
from src.websearch.pdf_reader import PdfText, is_pdf_response
from src.websearch.policy import is_official_url, load_jurisdiction_search_policy
from src.websearch.protocol import FetchResponse, SearchResponse, SearchResult
from src.websearch.provenance import (
    get_url_provenance,
    register_discovered_urls,
    register_user_provided_urls,
    reset_provenance_state,
)
from src.websearch.safe_site import SafeListing, SafeOfficialSiteClient


@pytest.fixture(autouse=True)
def _reset_web_provenance():
    reset_provenance_state()
    yield
    reset_provenance_state()


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

    oversized_fetch = WebSearchSettings.from_env({"WEBFETCH_MAX_CHARS": "200000"})
    assert oversized_fetch.max_fetch_chars == 8_000


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


@pytest.mark.parametrize(
    "url",
    [
        "http://2130706433/admin",
        "http://0x7f000001/admin",
        "http://127.1/admin",
    ],
)
def test_fetch_rejects_legacy_numeric_loopback_spellings_before_transport(url):
    def fail_transport(request, timeout):
        raise AssertionError("unsafe target must not reach the daemon transport")

    client = OpenWebSearchClient(WebSearchSettings(), transport=fail_transport)

    with pytest.raises(OpenWebSearchError, match="private or local"):
        client.fetch(url)


def test_fetch_rejects_hostname_resolving_to_private_address_before_transport():
    def private_resolver(hostname, port, **kwargs):
        return [(2, 1, 6, "", ("127.0.0.1", port))]

    def fail_transport(request, timeout):
        raise AssertionError("private DNS target must not reach the daemon transport")

    client = OpenWebSearchClient(
        WebSearchSettings(),
        transport=fail_transport,
        resolver=private_resolver,
    )

    with pytest.raises(OpenWebSearchError, match="resolves to a private or local"):
        client.fetch("https://private.example.test/document")


def test_fetch_allows_public_dns_answer_with_injected_resolver():
    envelope = {
        "status": "ok",
        "data": {
            "url": "https://public.example.test/document",
            "finalUrl": "https://public.example.test/document",
            "contentType": "text/html",
            "title": "Public document",
            "retrievalMethod": "request",
            "truncated": False,
            "content": "Public text",
            "links": [],
        },
    }

    def public_resolver(hostname, port, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", port))]

    client = OpenWebSearchClient(
        WebSearchSettings(),
        transport=_json_transport(envelope),
        resolver=public_resolver,
    )

    assert client.fetch("https://public.example.test/document").content == "Public text"


def test_fetch_allows_configured_clash_fake_dns_answer(monkeypatch):
    envelope = {
        "status": "ok",
        "data": {
            "url": "https://proxied.example.test/document",
            "finalUrl": "https://proxied.example.test/document",
            "contentType": "text/html",
            "title": "Proxied document",
            "retrievalMethod": "request",
            "truncated": False,
            "content": "Proxied text",
            "links": [],
        },
    }

    def fake_ip_resolver(hostname, port, **kwargs):
        return [(2, 1, 6, "", ("198.18.0.42", port))]

    monkeypatch.setenv("FAKE_IP_CIDRS", "198.18.0.0/15")
    client = OpenWebSearchClient(
        WebSearchSettings(),
        transport=_json_transport(envelope),
        resolver=fake_ip_resolver,
    )

    assert client.fetch("https://proxied.example.test/document").content == "Proxied text"


def test_fetch_never_allows_literal_fake_ip_target(monkeypatch):
    monkeypatch.setenv("FAKE_IP_CIDRS", "198.18.0.0/15")
    client = OpenWebSearchClient(WebSearchSettings(), transport=lambda *_: None)

    with pytest.raises(OpenWebSearchError, match="private or local"):
        client.fetch("http://198.18.0.42/internal")


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
    register_discovered_urls(["https://example.com/law"], source="test_search")
    payload = json.loads(tool.call({"url": "https://example.com/law"}))

    assert payload["status"] == "ok"
    assert payload["provider"] == "open_websearch"
    assert payload["content"] == "Article text"
    assert payload["retrieved_at"]


def test_qwen_fetch_rejects_a_model_guessed_url_before_network(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    tool = WebFetchTool()

    class FailIfCalledClient:
        def fetch(self, url, **kwargs):
            raise AssertionError("unverified URL must not reach the network")

    tool.client = FailIfCalledClient()
    payload = json.loads(
        tool.call({"url": "https://www.safe.gov.cn/safe/guessed/2026/12345.html"})
    )

    assert payload["status"] == "error"
    assert payload["error"]["code"] == "unverified_url"
    assert "Do NOT guess" in payload["error"]["message"]
    assert tool._fetch_count == 0


def test_search_result_can_be_fetched_by_another_tool_instance(monkeypatch):
    from src.tools.web_fetch import WebFetchTool
    from src.tools.web_search import WebSearchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    search_tool = WebSearchTool()
    fetch_tool = WebFetchTool()

    class FakeSearchClient:
        def search(self, query, **kwargs):
            return SearchResponse(
                query=query,
                engines=kwargs["engines"],
                results=[
                    SearchResult(
                        "SAFE regulation",
                        "https://www.safe.gov.cn/safe/2020/0520/24015.html",
                        "",
                        "bing",
                        "web",
                    )
                ],
            )

    class FakeFetchClient:
        def fetch(self, url, **kwargs):
            return FetchResponse(
                url=url,
                final_url=url,
                title="SAFE regulation",
                content_type="text/html",
                retrieval_method="request",
                truncated=False,
                content="Official text",
            )

    search_tool.client = FakeSearchClient()
    fetch_tool.client = FakeFetchClient()
    search_tool.call({"query": "exact title", "jurisdiction": "CN"})
    payload = json.loads(
        fetch_tool.call({"url": "https://www.safe.gov.cn/safe/2020/0520/24015.html"})
    )

    assert payload["status"] == "ok"
    assert payload["content"] == "Official text"


def test_registry_url_is_fetchable_without_guessing(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    tool = WebFetchTool()

    class FakeClient:
        def fetch(self, url, **kwargs):
            return FetchResponse(
                url=url,
                final_url=url,
                title="Foreign Exchange Regulation",
                content_type="text/html",
                retrieval_method="request",
                truncated=False,
                content="Regulation text",
            )

    tool.client = FakeClient()
    payload = json.loads(
        tool.call({"url": "https://www.safe.gov.cn/safe/2008/0806/5321.html"})
    )

    assert payload["status"] == "ok"


def test_qwen_fetch_records_404_and_blocks_repeat(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    url = "https://www.safe.gov.cn/safe/old-page.html"
    register_discovered_urls([url], source="test_search")
    tool = WebFetchTool()
    calls = 0

    class FakeClient:
        def fetch(self, url, **kwargs):
            nonlocal calls
            calls += 1
            raise OpenWebSearchError(
                "validation_failed",
                "Request failed with status code 404",
                status_code=400,
            )

    tool.client = FakeClient()
    first = json.loads(tool.call({"url": url}))
    second = json.loads(tool.call({"url": url}))

    assert first["error"]["code"] == "source_not_found"
    assert second["error"]["code"] == "previous_fetch_failed"
    assert calls == 1
    assert tool._fetch_count == 1


def test_main_agent_assigns_web_tools_to_main_retrieval_and_verification(monkeypatch):
    from qwen_agent.agents import FnCallAgent
    from src.agent.main_agent import MainAgent

    def fake_agent_init(self, function_list=None, **kwargs):
        self.assigned_tools = list(function_list or [])

    monkeypatch.setattr(FnCallAgent, "__init__", fake_agent_init)
    agent = MainAgent(llm=None)

    expected_web_tools = {"WebSearchTool", "WebFetchTool"}
    # The main agent keeps WebFetchTool only: its final synthesis can fetch
    # user-supplied URLs (provenance-gated and budgeted), but open-ended
    # searching stays with the retrieval/verification sub-agents.
    assert "WebFetchTool" in agent.assigned_tools
    assert "WebSearchTool" not in agent.assigned_tools
    assert agent.mode_detector.assigned_tools == ["WriteResult"]
    assert agent.analysts_selector.assigned_tools == ["WriteResult"]
    assert expected_web_tools.issubset(agent.rag_agent.assigned_tools)
    assert expected_web_tools.issubset(agent.validate_agent.assigned_tools)
    assert expected_web_tools.issubset(agent.citation_verifier.assigned_tools)
    for analyst in agent.analysts.values():
        assert expected_web_tools.isdisjoint(analyst.assigned_tools)
    assert expected_web_tools.isdisjoint(agent.report_writer.assigned_tools)


def test_user_message_urls_are_registered_as_fetch_provenance():
    url = "https://example.com/policy.pdf"

    extracted = register_user_provided_urls(f"请读取[{url}]({url})&#x20;")

    assert extracted == [url]
    assert get_url_provenance(url) == "user_provided_url"


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
    register_discovered_urls(
        ["https://a.gov.cn/1", "https://a.gov.cn/2", "https://a.gov.cn/3"],
        source="test_search",
    )
    assert json.loads(tool.call({"url": "https://a.gov.cn/1", "max_chars": 20000}))["status"] == "ok"
    assert json.loads(tool.call({"url": "https://a.gov.cn/2"}))["status"] == "ok"

    # max_chars is clamped to the server-side cap regardless of the request
    assert seen_max_chars[0] == web_fetch_module.MAX_FETCH_CHARS_CAP

    payload = json.loads(tool.call({"url": "https://a.gov.cn/3"}))
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "fetch_budget_exhausted"
    assert "STOP fetching" in payload["error"]["message"]


def test_safe_official_search_parser_extracts_highlighted_titles(monkeypatch):
    html = """
    <ul>
      <li class="ssjg">
        <h3 class="pt"><a href="/fujian/2022/0624/1755.html">
          一图看懂《<font color="red">优质企业</font>贸易外汇收支便利化试点政策》
        </a></h3>
        <span class="ft">官方政策解读</span>
        <span class="sj">2022-06-24<a href="/fujian/2022/0624/1755.html">path</a></span>
      </li>
    </ul>
    """.encode()
    client = SafeOfficialSiteClient()
    monkeypatch.setattr(client, "_get", lambda url: (html, url))

    results = client.search("优质企业贸易外汇收支便利化", limit=5)

    assert len(results) == 1
    assert results[0].title == "一图看懂《优质企业贸易外汇收支便利化试点政策》"
    assert results[0].url == "https://www.safe.gov.cn/fujian/2022/0624/1755.html"
    assert results[0].snippet == "官方政策解读"


def test_safe_listing_parser_returns_compact_policy_links(monkeypatch):
    html = """
    <html><head><title>政策法规_国家外汇管理局</title></head><body>
      <div class="list_conr"><ul><li><dt>
        <a href="/safe/2026/0805/27766.html" title="现行有效外汇管理主要法规目录">
          truncated display text
        </a></dt><dd>2026-08-05</dd>
      </li></ul></div>
    </body></html>
    """.encode()
    client = SafeOfficialSiteClient()
    monkeypatch.setattr(client, "_get", lambda url: (html, url))

    listing = client.fetch_listing(
        "https://www.safe.gov.cn/safe/zcfg/index.html", max_chars=8_000
    )

    assert listing.title == "政策法规_国家外汇管理局"
    assert "[2026-08-05] 现行有效外汇管理主要法规目录" in listing.content
    assert listing.links == [
        {
            "text": "现行有效外汇管理主要法规目录",
            "href": "https://www.safe.gov.cn/safe/2026/0805/27766.html",
        }
    ]


def test_qwen_search_prefers_safe_official_site_for_cn_foreign_exchange(monkeypatch):
    from src.tools.web_search import WebSearchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    tool = WebSearchTool()

    class FailGenericClient:
        def search(self, query, **kwargs):
            raise AssertionError("generic search should not run when SAFE has results")

    class FakeSafeClient:
        def search(self, query, **kwargs):
            return [
                SearchResult(
                    "优质企业贸易外汇收支便利化试点政策",
                    "https://www.safe.gov.cn/fujian/2022/0624/1755.html",
                    "官方政策解读",
                    "safe_site",
                    "official_site_search",
                )
            ]

    tool.client = FailGenericClient()
    tool.safe_client = FakeSafeClient()
    payload = json.loads(
        tool.call({"query": "优质企业贸易外汇收支便利化", "jurisdiction": "CN"})
    )

    assert payload["status"] == "ok"
    assert payload["provider"] == "safe_official_site"
    assert payload["results"][0]["is_official"] is True


def test_qwen_fetch_replaces_safe_footer_with_official_listing(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    url = "https://www.safe.gov.cn/safe/zcfg/index.html"
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    register_discovered_urls([url], source="test_search")
    tool = WebFetchTool()

    class FakeDaemonClient:
        def fetch(self, url, **kwargs):
            return FetchResponse(
                url=url,
                final_url=url,
                title="政策法规",
                content_type="text/html",
                retrieval_method="request",
                truncated=False,
                content="联系我们 | 网站声明",
                links=[],
            )

    class FakeSafeClient:
        def fetch_listing(self, url, **kwargs):
            return SafeListing(
                title="政策法规",
                content="[2026-08-05] 现行有效外汇管理主要法规目录\n"
                "https://www.safe.gov.cn/safe/2026/0805/27766.html",
                links=[
                    {
                        "text": "现行有效外汇管理主要法规目录",
                        "href": "https://www.safe.gov.cn/safe/2026/0805/27766.html",
                    }
                ],
                truncated=False,
            )

    tool.client = FakeDaemonClient()
    tool.safe_client = FakeSafeClient()
    payload = json.loads(tool.call({"url": url}))

    assert payload["status"] == "ok"
    assert payload["retrieval_method"] == "safe-official-html-listing"
    assert "现行有效外汇管理主要法规目录" in payload["content"]


def test_qwen_fetch_extracts_any_public_pdf_instead_of_returning_binary_stream(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    url = "https://regulator.example.org/guidance/answer.pdf"
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    register_discovered_urls([url], source="test_search")
    tool = WebFetchTool()

    class FakeDaemonClient:
        def fetch(self, url, **kwargs):
            return FetchResponse(
                url=url,
                final_url=url,
                title="",
                content_type="application/pdf",
                retrieval_method="request",
                truncated=False,
                content="%PDF FlateDecode binary stream",
                links=[],
            )

    class FakePdfReader:
        def fetch(self, url, **kwargs):
            return PdfText(
                final_url=url,
                title="Official policy FAQ",
                content="[PDF page 1]\nQuestion and official answer",
                page_count=3,
                truncated=False,
            )

    tool.client = FakeDaemonClient()
    tool.pdf_reader = FakePdfReader()
    payload = json.loads(tool.call({"url": url}))

    assert payload["status"] == "ok"
    assert payload["retrieval_method"] == "public-pdf-pypdf"
    assert payload["title"] == "Official policy FAQ"
    assert "official answer" in payload["content"]


def test_pdf_detection_uses_content_type_or_url_suffix():
    assert is_pdf_response("https://example.com/download?id=1", "application/pdf")
    assert is_pdf_response("https://example.com/document.PDF", "application/octet-stream")
    assert not is_pdf_response("https://example.com/page", "text/html")


def test_successful_url_is_not_fetched_twice_by_the_same_agent(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    url = "https://www.safe.gov.cn/shanghai/2023/1222/2059.html"
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    register_discovered_urls([url], source="test_search")
    tool = WebFetchTool()
    calls = 0

    class FakeClient:
        def fetch(self, url, **kwargs):
            nonlocal calls
            calls += 1
            return FetchResponse(
                url=url,
                final_url=url,
                title="Official notice",
                content_type="text/html",
                retrieval_method="request",
                truncated=False,
                content="Official text",
                links=[],
            )

    tool.client = FakeClient()
    first = json.loads(tool.call({"url": url}))
    duplicate = json.loads(tool.call({"url": url}))

    assert first["status"] == "ok"
    assert duplicate["status"] == "error"
    assert duplicate["error"]["code"] == "already_fetched"
    assert "STOP" in duplicate["error"]["message"]
    assert calls == 1
    assert tool._fetch_count == 1


def test_terminal_fetch_result_stops_the_agent_tool_loop():
    from src.agent.tool_loop_guard import (
        TerminalToolResult,
        raise_for_terminal_tool_result,
    )

    result = json.dumps(
        {
            "status": "error",
            "error": {"code": "already_fetched", "message": "use existing content"},
        }
    )

    with pytest.raises(TerminalToolResult) as caught:
        raise_for_terminal_tool_result("WebFetchTool", result)

    assert caught.value.code == "already_fetched"
    assert caught.value.tool_name == "WebFetchTool"


def test_main_agent_terminal_tool_result_forces_tool_free_finalization(monkeypatch):
    from qwen_agent.agents import FnCallAgent
    from qwen_agent.llm.schema import ASSISTANT, USER, Message
    from src.agent.main_agent import MainAgent
    from src.agent.tool_loop_guard import TerminalToolResult

    repeated_call = Message(role=ASSISTANT, content="repeated fetch requested")

    def fake_fncall_run(self, messages, **kwargs):
        yield [repeated_call]
        raise TerminalToolResult(
            tool_name="WebFetchTool",
            result=json.dumps(
                {
                    "status": "error",
                    "error": {"code": "already_fetched", "message": "use cached evidence"},
                }
            ),
            code="already_fetched",
        )

    finalization_calls = []

    def fake_call_llm(self, messages, functions=None, **kwargs):
        finalization_calls.append({"messages": messages, "functions": functions})
        yield [Message(role=ASSISTANT, content="final answer from existing evidence")]

    monkeypatch.setattr(FnCallAgent, "_run", fake_fncall_run)
    monkeypatch.setattr(MainAgent, "_call_llm", fake_call_llm)
    agent = object.__new__(MainAgent)

    frames = list(agent._run_fncall_with_guard([Message(role=USER, content="question")]))

    assert len(finalization_calls) == 1
    assert finalization_calls[0]["functions"] == []
    assert "already_fetched" in finalization_calls[0]["messages"][-1]["content"]
    assert frames[-1][-1]["content"] == "final answer from existing evidence"


def test_user_message_url_with_parentheses_is_registered_intact():
    url = "https://en.wikipedia.org/wiki/Value-added_tax_(China)"

    extracted = register_user_provided_urls(f"请读取 {url} 这个页面")

    assert extracted == [url]
    assert get_url_provenance(url) == "user_provided_url"


def test_markdown_link_closing_paren_is_stripped_but_balanced_parens_kept():
    url = "https://example.com/wiki/Foo_(bar)"

    extracted = register_user_provided_urls(f"见 [{url}]({url})")

    assert extracted == [url]
    assert get_url_provenance(url) == "user_provided_url"


def test_repeated_unverified_url_gets_terminal_previous_failure(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    url = "https://www.safe.gov.cn/hunan/2020/0903/1500.html"
    tool = WebFetchTool()

    class FailIfCalledClient:
        def fetch(self, url, **kwargs):
            raise AssertionError("rejected URL must not reach the network")

    tool.client = FailIfCalledClient()
    first = json.loads(tool.call({"url": url}))
    second = json.loads(tool.call({"url": url}))

    assert first["error"]["code"] == "unverified_url"
    assert second["error"]["code"] == "previous_fetch_failed"
    assert tool._fetch_count == 0


def test_unverified_url_fetchable_once_it_gains_provenance(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    url = "https://www.safe.gov.cn/hunan/2020/0903/1500.html"
    tool = WebFetchTool()

    class FakeClient:
        def fetch(self, url, **kwargs):
            return FetchResponse(
                url=url,
                final_url=url,
                title="Official notice",
                content_type="text/html",
                retrieval_method="request",
                truncated=False,
                content="Official text",
            )

    tool.client = FakeClient()
    rejected = json.loads(tool.call({"url": url}))
    assert rejected["error"]["code"] == "unverified_url"

    # The model followed the recovery instruction: an exact-title search
    # returned the same URL, so it must not stay blocked by the old rejection.
    register_discovered_urls([url], source="web_search_result")
    payload = json.loads(tool.call({"url": url}))

    assert payload["status"] == "ok"
    assert payload["content"] == "Official text"


def test_pdf_url_skips_daemon_fetch_and_goes_straight_to_pdf_reader(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    url = "https://regulator.example.org/guidance/answer.pdf"
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    register_discovered_urls([url], source="test_search")
    tool = WebFetchTool()

    class FailIfCalledClient:
        def fetch(self, url, **kwargs):
            raise AssertionError("PDF URLs must not be downloaded by the daemon first")

    class FakePdfReader:
        def fetch(self, url, **kwargs):
            return PdfText(
                final_url=url,
                title="Official policy FAQ",
                content="[PDF page 1]\nQuestion and official answer",
                page_count=3,
                truncated=False,
            )

    tool.client = FailIfCalledClient()
    tool.pdf_reader = FakePdfReader()
    payload = json.loads(tool.call({"url": url}))

    assert payload["status"] == "ok"
    assert payload["retrieval_method"] == "public-pdf-pypdf"
    assert "official answer" in payload["content"]


def test_pdf_failure_is_recorded_and_blocks_repeat(monkeypatch):
    from src.tools.web_fetch import WebFetchTool
    from src.websearch.pdf_reader import PdfReaderError

    url = "https://regulator.example.org/guidance/scanned.pdf"
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    register_discovered_urls([url], source="test_search")
    tool = WebFetchTool()
    calls = 0

    class FakePdfReader:
        def fetch(self, url, **kwargs):
            nonlocal calls
            calls += 1
            raise PdfReaderError("PDF contains no extractable text")

    tool.pdf_reader = FakePdfReader()
    first = json.loads(tool.call({"url": url}))
    second = json.loads(tool.call({"url": url}))

    assert first["error"]["code"] == "pdf_text_extraction_failed"
    assert second["error"]["code"] == "previous_fetch_failed"
    assert calls == 1
    assert tool._fetch_count == 1


def test_safe_listing_replacement_uses_final_url(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    original_url = "https://safe.gov.cn/safe/zcfg/index.html"
    final_url = "https://www.safe.gov.cn/safe/zcfg/index.html"
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    register_discovered_urls([original_url], source="test_search")
    tool = WebFetchTool()

    class FakeDaemonClient:
        def fetch(self, url, **kwargs):
            return FetchResponse(
                url=url,
                final_url=final_url,
                title="政策法规",
                content_type="text/html",
                retrieval_method="request",
                truncated=False,
                content="联系我们 | 网站声明",
                links=[],
            )

    seen_listing_urls = []

    class FakeSafeClient:
        def fetch_listing(self, url, **kwargs):
            seen_listing_urls.append(url)
            return SafeListing(
                title="政策法规",
                content="[2026-08-05] 现行有效外汇管理主要法规目录\n"
                "https://www.safe.gov.cn/safe/2026/0805/27766.html",
                links=[],
                truncated=False,
            )

    tool.client = FakeDaemonClient()
    tool.safe_client = FakeSafeClient()
    payload = json.loads(tool.call({"url": original_url}))

    assert seen_listing_urls == [final_url]
    assert payload["status"] == "ok"
    assert payload["retrieval_method"] == "safe-official-html-listing"


def test_retryable_fetch_failure_allows_one_retry_then_becomes_terminal(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    url = "https://example.com/transient"
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    register_discovered_urls([url], source="test_search")
    tool = WebFetchTool()
    calls = 0

    class FailingClient:
        def fetch(self, url, **kwargs):
            nonlocal calls
            calls += 1
            raise OpenWebSearchError(
                "service_unavailable",
                "temporary timeout",
                retryable=True,
            )

    tool.client = FailingClient()
    first = json.loads(tool.call({"url": url}))
    second = json.loads(tool.call({"url": url}))
    third = json.loads(tool.call({"url": url}))

    assert first["error"]["code"] == "service_unavailable"
    assert second["error"]["code"] == "previous_fetch_failed"
    assert third["error"]["code"] == "previous_fetch_failed"
    assert second["error"]["details"]["previous_failure"]["attempts"] == 2
    assert calls == 2
    assert tool._fetch_count == 2


def test_nonretryable_fetch_failure_uses_one_network_attempt(monkeypatch):
    from src.tools.web_fetch import WebFetchTool

    url = "https://example.com/broken-response"
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    register_discovered_urls([url], source="test_search")
    tool = WebFetchTool()
    calls = 0

    class FailingClient:
        def fetch(self, url, **kwargs):
            nonlocal calls
            calls += 1
            raise OpenWebSearchError("invalid_response", "malformed daemon response")

    tool.client = FailingClient()
    first = json.loads(tool.call({"url": url}))
    second = json.loads(tool.call({"url": url}))

    assert first["error"]["code"] == "invalid_response"
    assert second["error"]["code"] == "previous_fetch_failed"
    assert calls == 1
    assert tool._fetch_count == 1


@pytest.mark.parametrize(
    "arguments",
    [
        {"max_chars": None},
        {"max_chars": "not-an-integer"},
        {"render_mode": "invalid"},
    ],
)
def test_invalid_fetch_parameters_do_not_consume_budget(monkeypatch, arguments):
    from src.tools.web_fetch import WebFetchTool

    url = "https://example.com/document.pdf"
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    register_discovered_urls([url], source="test_search")
    tool = WebFetchTool()

    class FailPdfReader:
        def fetch(self, url, **kwargs):
            raise AssertionError("invalid arguments must be rejected before reading")

    tool.pdf_reader = FailPdfReader()
    payload = json.loads(tool.call({"url": url, **arguments}))

    assert payload["error"]["code"] == "invalid_arguments"
    assert tool._fetch_count == 0
