#!/usr/bin/env python3
"""Render a 3wagent Markdown report and optionally convert it to PDF.

Thin orchestration layer — delegates to build_markdown and convert_pdf modules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from build_markdown import build_markdown, local_now, slugify_topic, write_markdown
from convert_pdf import convert_to_pdf

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "templates" / "report.md"
DEFAULT_OUTPUT_ROOT = ROOT / "reports"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Existing Markdown file to archive.")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--title", default="3wagent Policy Report")
    parser.add_argument("--topic", help="Topic slug or report folder suffix.")
    parser.add_argument("--date", help="Report date in YYYYMMDD format.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--require-pdf", action="store_true")
    parser.add_argument("--print-json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report_date = args.date or local_now().strftime("%Y%m%d")
    topic = slugify_topic(args.topic or args.title)
    report_dir = args.output_root / f"{report_date}-{topic}"

    markdown = build_markdown(args.source, args.template, args.title, topic, report_date)
    markdown_path = write_markdown(markdown, report_dir, args.overwrite)

    pdf_path: Path | None = None
    pdf_attempts: list[dict] = []
    if not args.no_pdf:
        pdf_path, pdf_attempts = convert_to_pdf(markdown_path, report_dir / "report.pdf", args.title)

    if args.require_pdf and pdf_path is None:
        result_code = 2
    else:
        result_code = 0

    result = {
        "report_dir": str(report_dir),
        "markdown": str(markdown_path),
        "pdf": str(pdf_path) if pdf_path else None,
        "pdf_attempts": pdf_attempts,
    }
    if args.print_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Markdown: {markdown_path}")
        print(f"PDF: {pdf_path if pdf_path else 'not generated'}")
        for attempt in pdf_attempts:
            status = "ok" if attempt["ok"] else "failed"
            print(f"- {attempt['converter']}: {status}: {attempt['message']}")

    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
