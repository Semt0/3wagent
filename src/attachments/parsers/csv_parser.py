"""CSV/TSV parser using the standard library.

Rows are numbered so citations like ``csv:rows10-30`` stay verifiable
against the original file.
"""

import csv
from pathlib import Path

from src.attachments.models import ParsedChunk

CHUNK_CHARS = 20_000


def parse(path: Path, settings) -> tuple:
    delimiter = '\t' if path.suffix.lower() == '.tsv' else ','
    chunks = []
    buf, buf_len = [], 0
    row_start = 1
    last_row = 0

    with path.open('r', encoding='utf-8', errors='replace', newline='') as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        for row_no, row in enumerate(reader, start=1):
            last_row = row_no
            line = f'row {row_no}: ' + ' | '.join(cell.strip() for cell in row) + '\n'
            if buf_len + len(line) > CHUNK_CHARS and buf:
                chunks.append(ParsedChunk(
                    locator=f'csv:rows{row_start}-{row_no - 1}',
                    kind='table',
                    text=''.join(buf),
                    metadata={'row_start': row_start, 'row_end': row_no - 1},
                ))
                buf, buf_len = [], 0
                row_start = row_no
            buf.append(line)
            buf_len += len(line)

    if buf:
        chunks.append(ParsedChunk(
            locator=f'csv:rows{row_start}-{last_row}',
            kind='table',
            text=''.join(buf),
            metadata={'row_start': row_start, 'row_end': last_row},
        ))
    if not chunks:
        chunks.append(ParsedChunk(locator='csv:rows0-0', kind='table', text='(empty file)'))
    return chunks, [], {'rows': last_row, 'chunks': len(chunks)}
