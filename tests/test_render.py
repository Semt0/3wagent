"""Tests for tools/render_report.py — slugify, markdown build, PDF fallback."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# Ensure tools/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_markdown import build_markdown, slugify_topic, write_markdown

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "templates" / "report.md"


class TestSlugifyTopic:
    def test_english_lowercase(self):
        assert slugify_topic("Cross Border Tax") == "cross-border-tax"

    def test_preserves_cjk(self):
        result = slugify_topic("跨境技术咨询服务费")
        assert "跨境" in result
        assert "技术" in result

    def test_strips_special_chars(self):
        result = slugify_topic("Hello! @World# 2024")
        assert "!" not in result
        assert "@" not in result

    def test_collapses_dashes(self):
        result = slugify_topic("a---b---c")
        assert result == "a-b-c"

    def test_empty_returns_default(self):
        assert slugify_topic("") == "policy-report"
        assert slugify_topic("   ") == "policy-report"

    def test_mixed_cjk_and_ascii(self):
        result = slugify_topic("中国 VAT 服务")
        assert "中国" in result
        assert "vat" in result


class TestBuildMarkdown:
    def test_from_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            template = Path(tmp) / "template.md"
            template.write_text("# $REPORT_TITLE\nDate: $REPORT_DATE", encoding="utf-8")
            result = build_markdown(
                source=None,
                template=template,
                title="Test Report",
                topic="test",
                report_date="20260601",
            )
            assert "# Test Report" in result
            assert "Date: 20260601" in result

    def test_from_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.md"
            source.write_text("# Existing Content\nHello", encoding="utf-8")
            result = build_markdown(
                source=source,
                template=DEFAULT_TEMPLATE,
                title="Ignored",
                topic="ignored",
                report_date="20260601",
            )
            assert "# Existing Content" in result
            assert "Hello" in result


class TestWriteMarkdown:
    def test_creates_directory_and_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "20260601-test"
            md = "# Test"
            path = write_markdown(md, report_dir, overwrite=False)
            assert path.exists()
            assert path.read_text(encoding="utf-8") == md

    def test_no_overwrite_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "20260601-test"
            write_markdown("# First", report_dir, overwrite=False)
            with pytest.raises(FileExistsError):
                write_markdown("# Second", report_dir, overwrite=False)

    def test_overwrite_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "20260601-test"
            write_markdown("# First", report_dir, overwrite=False)
            path = write_markdown("# Second", report_dir, overwrite=True)
            assert path.read_text(encoding="utf-8") == "# Second"
