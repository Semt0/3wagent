#!/usr/bin/env python3
"""Markdown generation utilities for 3wagent reports."""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from string import Template


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "templates" / "report.md"


def slugify_topic(value: str) -> str:
    """Return a filesystem-friendly topic slug while keeping CJK characters."""
    slug = value.strip().lower()
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "policy-report"


def local_now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def build_markdown(
    source: Path | None,
    template: Path,
    title: str,
    topic: str,
    report_date: str,
) -> str:
    if source:
        return source.read_text(encoding="utf-8").rstrip() + "\n"

    generated_at = local_now().isoformat(timespec="seconds")
    raw_template = template.read_text(encoding="utf-8")
    markdown = Template(raw_template).safe_substitute(
        REPORT_TITLE=title,
        GENERATED_AT=generated_at,
        TOPIC=topic,
        REPORT_DATE=report_date,
    )
    return markdown.rstrip() + "\n"


def write_markdown(markdown: str, report_dir: Path, overwrite: bool) -> Path:
    report_path = report_dir / "report.md"
    if report_path.exists() and not overwrite:
        raise FileExistsError(f"{report_path} already exists; pass --overwrite to replace it.")

    report_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(markdown, encoding="utf-8")
    return report_path
