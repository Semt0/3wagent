"""Anti-loop guards on AttachmentReadTool and the workflow fallbacks added
after the "hallucinated document_id from a PDF URL" incident: a user-supplied
URL basename like 3fbea410c6f24f56846afb57fc665630 looks exactly like an
attachment document_id, and unguarded failures let the model retry until the
framework LLM-call cap killed the whole workflow step."""

from __future__ import annotations

from pathlib import Path

import pytest
from src.attachments.storage import register_session_document, reset_session_documents
from src.config.attachments import AttachmentSettings
from src.tools.read_attachment import READ_BUDGET_PER_AGENT, AttachmentReadTool

SAFE_PDF_URL = ('http://m.safe.gov.cn/safe/file/file/20260506/'
                '3fbea410c6f24f56846afb57fc665630.pdf')


@pytest.fixture(autouse=True)
def _clean_session_docs():
    reset_session_documents()
    yield
    reset_session_documents()


@pytest.fixture()
def tool(tmp_path, monkeypatch):
    s = AttachmentSettings(storage_dir=str(tmp_path / 'attachments'))
    monkeypatch.setattr('src.tools.read_attachment.ATTACHMENT_SETTINGS', s)
    return AttachmentReadTool()


# ------------------------------------------------------------- URL guard


def test_full_url_as_document_id_redirects_to_webfetch(tool):
    out = tool.call({'document_id': SAFE_PDF_URL})
    assert out.startswith('error:')
    assert 'WebFetchTool' in out
    assert 'Do NOT retry' in out


def test_bare_pdf_filename_as_document_id_redirects_to_webfetch(tool):
    out = tool.call({'document_id': '3fbea410c6f24f56846afb57fc665630.pdf'})
    assert out.startswith('error:')
    assert 'WebFetchTool' in out


# ------------------------------------------------- missing-id guidance


def test_unknown_id_without_any_upload_explains_and_redirects(tool):
    out = tool.call({'document_id': '3fbea410c6f2'})
    assert 'document not found: 3fbea410c6f2' in out
    assert 'No attachment has been uploaded' in out
    assert 'WebFetchTool' in out


def test_unknown_id_lists_the_real_session_document_ids(tool):
    register_session_document('154db9df613a')
    out = tool.call({'document_id': '3fbea410c6f2'})
    assert '154db9df613a' in out
    assert 'Do NOT guess' in out


def test_missing_id_retry_is_refused(tool):
    tool.call({'document_id': '3fbea410c6f2'})
    out = tool.call({'document_id': '3fbea410c6f2', 'query': '保险机构'})
    assert 'already failed' in out
    assert 'Do NOT retry' in out


def test_exact_repeat_call_is_refused(tool):
    tool.call({'document_id': '3fbea410c6f2'})
    out = tool.call({'document_id': '3fbea410c6f2'})
    assert 'exact AttachmentReadTool call' in out
    assert 'STOP' in out


# ---------------------------------------------------------------- budget


def test_read_budget_exhaustion_stops_the_agent(tool):
    for i in range(READ_BUDGET_PER_AGENT):
        out = tool.call({'document_id': f'{i:012x}'})
        assert 'document not found' in out
    out = tool.call({'document_id': 'ffffffffffff'})
    assert 'budget is exhausted' in out
    assert 'STOP' in out


def test_guards_do_not_consume_budget(tool):
    # URL mistakes and repeat calls are refused before the budget check.
    tool.call({'document_id': SAFE_PDF_URL})
    tool.call({'document_id': '3fbea410c6f2'})
    tool.call({'document_id': '3fbea410c6f2'})
    assert tool._read_count == 1


# ----------------------------------------------- sub-agent result fallbacks


def test_back_prompt_truncates_long_results_and_points_to_file(monkeypatch, tmp_path):
    from src.agent import subagent as subagent_mod
    from src.agent.subagent import BaseSubAgent, RoutingSubAgent

    monkeypatch.setattr(subagent_mod, 'get_subagents_dir', lambda: tmp_path)
    monkeypatch.setattr(
        subagent_mod, 'get_run_dir_relative', lambda: Path('workspace/test-run')
    )
    (tmp_path / 'routing_subagent_result.md').write_text('x' * 9000, encoding='utf-8')

    agent = BaseSubAgent.__new__(RoutingSubAgent)
    agent._last_output_text = ''
    agent._truncated = False
    out = agent.get_back_prompt()
    assert 'result truncated at 8000 chars' in out
    assert 'workspace/test-run/sub_agents/routing_subagent_result.md' in out
