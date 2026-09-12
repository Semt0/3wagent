"""Regression tests for query-aware, authority-first web discovery."""

from __future__ import annotations

import json

from src.tools.web_search import WebSearchTool
from src.websearch.protocol import SearchResponse, SearchResult
from src.websearch.relevance import relevance_score


def test_chinese_exact_title_rejects_dictionary_noise():
    query = '"境内企业境外发行证券和上市管理试行办法" 证监会公告 2023年第43号'

    assert relevance_score(query, "境内_百度百科", "术语解释") < 0.1
    assert relevance_score(
        query,
        "【第43号公告】《境内企业境外发行证券和上市管理试行办法》",
        "中国证券监督管理委员会",
    ) == 1.0


def test_precise_registry_match_avoids_network(monkeypatch):
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    tool = WebSearchTool()

    class FailNetworkClient:
        def search(self, query, **kwargs):
            raise AssertionError("precise registry matches must not spend a web-search call")

    tool.client = FailNetworkClient()
    payload = json.loads(
        tool.call(
            {
                "query": "请根据《境内企业境外发行证券和上市管理试行办法》及其发布页面说明备案主体",
                "jurisdiction": "CN",
            }
        )
    )

    assert payload["provider"] == "source_registry"
    assert payload["quality"] == "strong"
    assert any("正文" in item["title"] for item in payload["results"])
    assert all(item["is_official"] for item in payload["results"])


def test_low_quality_results_trigger_one_official_domain_retry(monkeypatch):
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    tool = WebSearchTool()
    calls = []

    class FakeClient:
        def search(self, query, **kwargs):
            calls.append((query, kwargs["engines"]))
            if len(calls) == 1:
                return SearchResponse(
                    query=query,
                    engines=kwargs["engines"],
                    results=[
                        SearchResult("境内_百度百科", "https://baike.baidu.com/item/x", "", "bing", "web"),
                        SearchResult("中国证券监督管理委员会", "https://www.csrc.gov.cn/", "", "bing", "web"),
                    ],
                    partial_failures=[
                        {"engine": "baidu", "code": "engine_error", "message": "302"},
                        {"engine": "sogou", "code": "engine_error", "message": "verification"},
                    ],
                )
            return SearchResponse(
                query=query,
                engines=kwargs["engines"],
                results=[
                    SearchResult(
                        "全新证券监管测试办法",
                        "https://www.csrc.gov.cn/csrc/new-rule/content.shtml",
                        "证监会发布全新证券监管测试办法",
                        "bing",
                        "web",
                    )
                ],
            )

    tool.client = FakeClient()
    payload = json.loads(
        tool.call({"query": "《全新证券监管测试办法》 证监会", "jurisdiction": "CN"})
    )

    assert calls[1][0].startswith("site:csrc.gov.cn ")
    assert calls[1][1] == ["bing"]
    assert payload["quality"] == "strong"
    assert payload["results"][0]["title"] == "全新证券监管测试办法"
    assert payload["discarded_low_relevance"] == 2
    assert set(payload["failed_engines"]) == {"baidu", "sogou"}


def test_failed_engines_are_skipped_for_later_calls(monkeypatch):
    monkeypatch.setenv("OPEN_WEBSEARCH_URL", "http://127.0.0.1:3210")
    tool = WebSearchTool()
    calls = []

    class FakeClient:
        def search(self, query, **kwargs):
            calls.append(kwargs["engines"])
            failures = []
            if len(calls) == 1:
                failures = [
                    {"engine": "baidu", "code": "engine_error", "message": "302"},
                    {"engine": "sogou", "code": "engine_error", "message": "verification"},
                ]
            return SearchResponse(
                query=query,
                engines=kwargs["engines"],
                results=[
                    SearchResult(
                        query,
                        "https://www.csrc.gov.cn/csrc/result.shtml",
                        query,
                        "bing",
                        "web",
                    )
                ],
                partial_failures=failures,
            )

    tool.client = FakeClient()
    first = json.loads(tool.call({"query": "测试规则甲", "jurisdiction": "CN"}))
    second = json.loads(tool.call({"query": "测试规则乙", "jurisdiction": "CN"}))

    assert first["status"] == second["status"] == "ok"
    assert calls == [["bing", "baidu", "sogou"], ["bing"]]
    assert second["skipped_unhealthy_engines"] == ["baidu", "sogou"]
