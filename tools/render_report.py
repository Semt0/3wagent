#!/usr/bin/env python3
"""Render a 3wagent Markdown report and optionally convert it to PDF."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from string import Template


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "templates" / "report.md"
DEFAULT_OUTPUT_ROOT = ROOT / "reports"


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


def convert_with_pandoc(markdown_path: Path, pdf_path: Path, title: str) -> tuple[bool, str]:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        return False, "pandoc not found"

    command = [
        pandoc,
        str(markdown_path),
        "-o",
        str(pdf_path),
        "--metadata",
        f"title={title}",
    ]
    if shutil.which("xelatex"):
        command.extend(
            [
                "--pdf-engine=xelatex",
                "-V",
                "mainfont=Songti SC",
                "-V",
                "CJKmainfont=Songti SC",
            ]
        )
    result = subprocess.run(command, capture_output=True, check=False, text=True)
    if result.returncode == 0 and pdf_path.exists():
        return True, "converted with pandoc"

    stderr = result.stderr.strip() or result.stdout.strip() or "pandoc failed"
    return False, stderr


def escape_inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def markdown_to_html(markdown: str, title: str) -> str:
    html_lines = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{html.escape(title)}</title>",
        "<style>",
        "body { font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', "
        "'Hiragino Sans GB', 'Songti SC', sans-serif; color: #111827; "
        "line-height: 1.65; margin: 32px; }",
        "h1 { font-size: 28px; margin-bottom: 20px; }",
        "h2 { font-size: 20px; margin-top: 28px; border-bottom: 1px solid #e5e7eb; }",
        "h3 { font-size: 16px; margin-top: 20px; }",
        "p, li { font-size: 12px; }",
        "code, pre { font-family: 'SFMono-Regular', Consolas, monospace; }",
        "pre { white-space: pre-wrap; background: #f9fafb; padding: 8px; }",
        "table { border-collapse: collapse; width: 100%; font-size: 11px; }",
        "th, td { border: 1px solid #d1d5db; padding: 6px; vertical-align: top; }",
        "@page { size: A4; margin: 18mm; }",
        "</style>",
        "</head>",
        "<body>",
    ]

    in_code_block = False
    list_open = False

    def close_list() -> None:
        nonlocal list_open
        if list_open:
            html_lines.append("</ul>")
            list_open = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            close_list()
            html_lines.append("</pre>" if in_code_block else "<pre>")
            in_code_block = not in_code_block
            continue

        if in_code_block:
            html_lines.append(html.escape(line))
            continue

        if not line.strip():
            close_list()
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            close_list()
            level = min(len(heading.group(1)), 3)
            html_lines.append(f"<h{level}>{escape_inline_markdown(heading.group(2))}</h{level}>")
            continue

        if line.lstrip().startswith(("- ", "* ")):
            if not list_open:
                html_lines.append("<ul>")
                list_open = True
            html_lines.append(f"<li>{escape_inline_markdown(line.lstrip()[2:].strip())}</li>")
            continue

        close_list()
        if line.strip().startswith("|"):
            html_lines.append(f"<pre>{html.escape(line)}</pre>")
        else:
            html_lines.append(f"<p>{escape_inline_markdown(line)}</p>")

    close_list()
    if in_code_block:
        html_lines.append("</pre>")
    html_lines.extend(["</body>", "</html>"])
    return "\n".join(html_lines)


def convert_with_weasyprint(markdown_path: Path, pdf_path: Path, title: str) -> tuple[bool, str]:
    weasyprint = shutil.which("weasyprint")
    if not weasyprint:
        return False, "weasyprint not found"

    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(
        markdown_to_html(markdown_path.read_text(encoding="utf-8"), title),
        encoding="utf-8",
    )
    try:
        result = subprocess.run(
            [weasyprint, str(html_path), str(pdf_path)],
            capture_output=True,
            check=False,
            text=True,
        )
    finally:
        html_path.unlink(missing_ok=True)

    if result.returncode == 0 and pdf_path.exists():
        return True, "converted with weasyprint"

    stderr = result.stderr.strip() or result.stdout.strip() or "weasyprint failed"
    return False, stderr


def paragraph_style(styles: object, name: str) -> object:
    return getattr(styles, name) if hasattr(styles, name) else styles[name]


def markdown_to_flowables(markdown: str, styles: object) -> list[object]:
    from reportlab.platypus import Paragraph, Preformatted, Spacer

    flowables: list[object] = []
    in_code_block = False
    code_lines: list[str] = []

    heading_map = {
        1: paragraph_style(styles, "Title"),
        2: paragraph_style(styles, "Heading2"),
        3: paragraph_style(styles, "Heading3"),
    }
    body_style = paragraph_style(styles, "BodyText")
    code_style = paragraph_style(styles, "Code")

    def flush_code() -> None:
        if not code_lines:
            return
        flowables.append(Preformatted("\n".join(code_lines), code_style))
        flowables.append(Spacer(1, 6))
        code_lines.clear()

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if line.startswith("```"):
            if in_code_block:
                flush_code()
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        if not line.strip():
            flowables.append(Spacer(1, 6))
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = len(heading.group(1))
            style = heading_map.get(level, paragraph_style(styles, "Heading3"))
            flowables.append(Paragraph(html.escape(heading.group(2)), style))
            continue

        if line.lstrip().startswith(("- ", "* ")):
            text = html.escape(line.lstrip()[2:].strip())
            flowables.append(Paragraph(text, body_style, bulletText="-"))
            continue

        if line.strip().startswith("|"):
            flowables.append(Preformatted(line, code_style))
            continue

        flowables.append(Paragraph(html.escape(line), body_style))

    flush_code()
    return flowables


def convert_with_reportlab(markdown_path: Path, pdf_path: Path, title: str) -> tuple[bool, str]:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import SimpleDocTemplate
    except ImportError as exc:
        return False, f"reportlab not available: {exc}"

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "STSong-Light"
        style.leading = max(style.leading, style.fontSize + 4)

    markdown = markdown_path.read_text(encoding="utf-8")
    story = markdown_to_flowables(markdown, styles)
    if not story:
        return False, "report is empty"

    def add_footer(canvas: object, doc: object) -> None:
        canvas.saveState()
        canvas.setFont("STSong-Light", 9)
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        title=title,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    return True, "converted with reportlab"


def convert_to_pdf(markdown_path: Path, pdf_path: Path, title: str) -> tuple[Path | None, list[dict]]:
    attempts: list[dict] = []
    for name, converter in (
        ("pandoc", convert_with_pandoc),
        ("weasyprint", convert_with_weasyprint),
        ("reportlab", convert_with_reportlab),
    ):
        ok, message = converter(markdown_path, pdf_path, title)
        attempts.append({"converter": name, "ok": ok, "message": message})
        if ok:
            return pdf_path, attempts

    return None, attempts


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
