"""Tests for the WebUI display helpers (grouping and side panels)."""

from pathlib import Path
from types import SimpleNamespace

from src.agent.webui import (
    MAIN_AGENT_NAME,
    THEME_CSS_PATH,
    ThemedWebUI,
    group_responses_for_display,
)


def _msg(content, name=None, role='assistant'):
    return {'role': role, 'content': content, 'name': name}


def test_group_folds_consecutive_subagent_messages():
    responses = [
        _msg('main answer', MAIN_AGENT_NAME),
        _msg('rag call 1', 'rag_subagent'),
        _msg('rag call 2', 'rag_subagent'),
        _msg('main again', None),
        _msg('validate call', 'validate_subagent'),
    ]
    units = group_responses_for_display(responses)
    assert len(units) == 4
    assert units[0]['content'] == 'main answer'
    assert '<details>' in units[1]['content']
    assert 'open>' not in units[1]['content']  # collapsed by default
    assert 'rag_subagent' in units[1]['content']
    assert 'rag call 1' in units[1]['content'] and 'rag call 2' in units[1]['content']
    assert units[2]['content'] == 'main again'
    assert 'validate_subagent' in units[3]['content']


def test_group_empty_and_main_only():
    assert group_responses_for_display([]) == []
    responses = [_msg('a'), _msg('b', MAIN_AGENT_NAME)]
    units = group_responses_for_display(responses)
    assert [u['content'] for u in units] == ['a', 'b']


def test_theme_overrides_vendor_details_nowrap_and_bounds_wide_content():
    css = Path(THEME_CSS_PATH).read_text(encoding='utf-8')

    assert 'white-space: normal !important;' in css
    assert '.gradio-container .markdown-body details' in css
    assert '.gradio-container .markdown-body table' in css
    assert 'max-width: 100%;' in css
    assert 'overflow-x: auto;' in css


def test_render_side_panels(tmp_path, monkeypatch):
    from src.config import runtime

    monkeypatch.setattr(runtime, '_run_id', 'test-run')
    monkeypatch.setattr(runtime, 'WORKSPACE_DIR', tmp_path)
    sub_dir = tmp_path / 'test-run' / 'sub_agents'
    sub_dir.mkdir(parents=True)
    (sub_dir / 'routing_subagent_result.md').write_text('# 路由\n内容 <b>x</b>', encoding='utf-8')
    (sub_dir / 'rag_subagent_result.md').write_text('# 检索', encoding='utf-8')

    fake_self = SimpleNamespace(
        agent_list=[SimpleNamespace(mode=SimpleNamespace(value='working'), current_step='Step 3')]
    )
    status_html, results_html = ThemedWebUI._render_side_panels(fake_self)

    assert 'test-run' in status_html
    assert '工作模式' in status_html
    assert 'Step 3' in status_html
    assert results_html.count("class='w3-result-link'") == 2
    assert results_html.count("class='w3-modal'") == 2
    assert 'routing_subagent_result.md' in results_html
    assert '<h1>' in results_html  # markdown is rendered, not shown raw
    assert '&lt;b&gt;' in results_html  # raw HTML in the markdown stays escaped


def test_render_side_panels_without_run(tmp_path, monkeypatch):
    from src.config import runtime

    monkeypatch.setattr(runtime, '_run_id', None)
    fake_self = SimpleNamespace(
        agent_list=[SimpleNamespace(mode=SimpleNamespace(value='normal'), current_step=None)]
    )
    status_html, results_html = ThemedWebUI._render_side_panels(fake_self)
    assert '对话模式' in status_html
    assert '暂无子代理结果' in results_html


def test_side_panels_render_plain_strings_repeatedly(tmp_path, monkeypatch):
    from src.config import runtime

    monkeypatch.setattr(runtime, '_run_id', None)
    fake_self = SimpleNamespace(
        agent_list=[SimpleNamespace(mode=SimpleNamespace(value='normal'), current_step=None)]
    )
    # The page polls every second; every call returns full content and the
    # client-side diffing decides whether to touch the DOM.
    for _ in range(2):
        status_html, results_html = ThemedWebUI._render_side_panels(fake_self)
        assert isinstance(status_html, str) and isinstance(results_html, str)
        assert '对话模式' in status_html
