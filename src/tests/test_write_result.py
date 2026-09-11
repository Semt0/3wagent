"""Tests for the WriteResult tool, including the lenient salvage parser."""

import json

from src.tools.common import PROJECT_ROOT
from src.tools.write_result import WriteResult, _salvage_params


def test_write_result_happy_path():
    tool = WriteResult()
    rel = "workspace/test_write_result_happy.md"
    payload = json.dumps({"file_path": rel, "file_content": "# 标题\n正文"})
    result = tool.call(payload)
    assert result.startswith("ok:")
    assert (PROJECT_ROOT / rel).read_text(encoding="utf-8") == "# 标题\n正文"
    (PROJECT_ROOT / rel).unlink()


def test_salvage_double_encoded_with_broken_escape():
    # The model wrapped arguments in a quoted string AND broke an escape inside
    # the large content; strict JSON parsing fails but salvage should recover.
    broken = (
        '{"file_path": "workspace/x_result.md", "file_content": "# 报告\\n\\n'
        '第一行\\n第二行 with "quotes" and bad \\x escape"}'
    )
    par = _salvage_params(broken)
    assert par is not None
    assert par["file_path"] == "workspace/x_result.md"
    assert "第一行\n第二行" in par["file_content"]


def test_salvage_returns_none_without_markers():
    assert _salvage_params("not json at all") is None
    assert _salvage_params('{"file_path": "a.md"}') is None
    assert _salvage_params(123) is None


def test_markdown_read_tool_is_idempotent():
    from src.tools.read_markdown_files import MarkDownReadTool

    tool = MarkDownReadTool()
    first = tool.call({"file_path": "config/routing.yaml"})
    assert "error" not in first[:20]
    second = tool.call({"file_path": "config/routing.yaml"})
    assert second == first


def test_yaml_read_tool_is_idempotent():
    from src.tools.read_yaml_files import YamlReadTool

    tool = YamlReadTool()
    first = tool.call({"file_path": "config/routing.yaml"})
    assert "error" not in first[:20]
    second = tool.call({"file_path": "config/routing.yaml"})
    assert second == first


def test_failed_read_does_not_poison_later_reads():
    from src.tools.read_yaml_files import YamlReadTool

    tool = YamlReadTool()
    missing = tool.call({"file_path": "config/does-not-exist.yaml"})
    assert missing == "error: file not found: config/does-not-exist.yaml"
    assert tool.call({"file_path": "config/does-not-exist.yaml"}) == missing
