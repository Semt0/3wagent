"""Lightweight PDF parser: pypdf for structure, pdfplumber for page text.

Complex PDFs (scans, multi-column, heavy formulas) should be escalated to a
heavy parser (e.g. MinerU via an isolated CLI/HTTP service); this parser only
emits a quality warning so the caller can surface it.
"""

from pathlib import Path

from src.attachments.models import ParsedChunk


def parse(path: Path, settings) -> tuple:
    import pdfplumber
    from pypdf import PdfReader

    warnings = []

    reader = PdfReader(str(path))
    total_pages = len(reader.pages)
    metadata = {
        'pages': total_pages,
        'pdf_metadata': {k: str(v) for k, v in (reader.metadata or {}).items()},
    }
    if total_pages > settings.pdf_max_pages:
        raise ValueError(
            f'PDF has {total_pages} pages, exceeding the limit of {settings.pdf_max_pages}'
        )

    chunks = []
    with pdfplumber.open(str(path)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            chunks.append(ParsedChunk(
                locator=f'pdf:p{page_no}',
                kind='text',
                text=text.strip() or '(no extractable text on this page)',
                page=page_no,
            ))

    if total_pages:
        avg_chars = sum(len(c.text) for c in chunks) / total_pages
        if avg_chars < settings.pdf_min_chars_per_page:
            warnings.append(
                f'平均每页仅 {avg_chars:.0f} 字符，可能是扫描件或图片型 PDF；'
                '建议接入 MinerU 做高精度解析（当前为轻量解析结果）。'
            )
    return chunks, warnings, metadata
