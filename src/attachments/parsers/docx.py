"""DOCX parser built on python-docx.

Paragraphs and tables are extracted in document order; headings keep their
``heading`` kind so outlines stay meaningful.
"""

from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from src.attachments.models import ParsedChunk

CHUNK_CHARS = 20_000


def _iter_block_items(doc):
    from docx.oxml.ns import qn

    for child in doc.element.body.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, doc)
        elif child.tag == qn('w:tbl'):
            yield Table(child, doc)


def parse(path: Path, settings) -> tuple:
    doc = Document(str(path))
    lines = []
    table_no = 0
    for block in _iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                kind = 'heading' if block.style.name.lower().startswith('heading') else 'text'
                lines.append((kind, text + '\n'))
        else:
            table_no += 1
            lines.append(('text', f'[table {table_no}]\n'))
            for row in block.rows:
                cells = ' | '.join(cell.text.strip() for cell in row.cells)
                lines.append(('table', cells + '\n'))

    chunks = []
    buf, buf_len, idx = [], 0, 1
    for kind, line in lines:
        if buf_len + len(line) > CHUNK_CHARS and buf:
            chunks.append(ParsedChunk(locator=f'docx:c{idx}', kind='text', text=''.join(buf)))
            idx += 1
            buf, buf_len = [], 0
        buf.append(line)
        buf_len += len(line)
    if buf:
        chunks.append(ParsedChunk(locator=f'docx:c{idx}', kind='text', text=''.join(buf)))
    if not chunks:
        chunks.append(ParsedChunk(locator='docx:c1', kind='text', text='(empty document)'))
    return chunks, [], {'chunks': len(chunks), 'tables': table_no}
