"""Plain-text parser for .md/.txt/.yaml files.

Splits content into line-aligned chunks so large text files can still be
read in slices via AttachmentReadTool.
"""

from pathlib import Path

from src.attachments.models import ParsedChunk

CHUNK_CHARS = 20_000


def parse(path: Path, settings) -> tuple:
    content = path.read_text(encoding='utf-8', errors='replace')
    chunks = []
    buf, buf_len, idx = [], 0, 1
    for line in content.splitlines(keepends=True):
        if buf_len + len(line) > CHUNK_CHARS and buf:
            chunks.append(ParsedChunk(locator=f'text:c{idx}', kind='text', text=''.join(buf)))
            idx += 1
            buf, buf_len = [], 0
        buf.append(line)
        buf_len += len(line)
    if buf:
        chunks.append(ParsedChunk(locator=f'text:c{idx}', kind='text', text=''.join(buf)))
    if not chunks:
        chunks.append(ParsedChunk(locator='text:c1', kind='text', text='(empty file)'))
    return chunks, [], {'chunks': len(chunks)}
