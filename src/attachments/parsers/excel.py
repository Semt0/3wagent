"""Excel (.xlsx/.xlsm) parser built on openpyxl.

Two read-only passes are used: ``data_only=False`` yields formula text,
``data_only=True`` yields the last cached calculation results. openpyxl never
evaluates formulas, so cached values are annotated as potentially stale.

Macros, external links and embedded objects are never executed.

Known limitation: merged-cell ranges and hidden row/column state are not
available in read_only mode and are not preserved.
"""

import zipfile
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from src.attachments.models import ParsedChunk

CHUNK_CHARS = 20_000


def _check_zip_size(path: Path, settings) -> None:
    limit = settings.xlsx_max_uncompressed_mb * 1024 * 1024
    with zipfile.ZipFile(path) as zf:
        total = sum(info.file_size for info in zf.infolist())
    if total > limit:
        raise ValueError(
            f'XLSX decompresses to {total // (1024 * 1024)} MB, '
            f'exceeding the limit of {settings.xlsx_max_uncompressed_mb} MB'
        )


def _sheet_cells(ws) -> dict:
    """Return ``{row_no: [(col_letter, value), ...]}`` for non-empty cells.

    read_only mode materializes gaps as EmptyCell (no row/column metadata),
    so positions come from enumeration instead of cell attributes.
    """
    rows = {}
    for row_no, row in enumerate(ws.iter_rows(), start=1):
        entries = [
            (get_column_letter(col_no), cell.value)
            for col_no, cell in enumerate(row, start=1)
            if cell.value is not None
        ]
        if entries:
            rows[row_no] = entries
    return rows


def parse(path: Path, settings) -> tuple:
    _check_zip_size(path, settings)
    warnings = []

    wb_formula = load_workbook(path, read_only=True, data_only=False)
    wb_values = load_workbook(path, read_only=True, data_only=True)

    chunks = []
    nonempty_cells = 0
    try:
        sheet_names = wb_formula.sheetnames
        if len(sheet_names) > settings.workbook_max_sheets:
            raise ValueError(
                f'workbook has {len(sheet_names)} sheets, '
                f'exceeding the limit of {settings.workbook_max_sheets}'
            )

        for name in sheet_names:
            ws_f = wb_formula[name]
            ws_v = wb_values[name]
            formula_rows = _sheet_cells(ws_f)
            value_rows = _sheet_cells(ws_v)
            nonempty_cells += sum(len(v) for v in formula_rows.values())
            if nonempty_cells > settings.workbook_max_nonempty_cells:
                raise ValueError(
                    f'workbook exceeds {settings.workbook_max_nonempty_cells} non-empty cells'
                )

            lines = []
            row_numbers = sorted(set(formula_rows) | set(value_rows))
            for row_no in row_numbers:
                f_cells = dict(formula_rows.get(row_no, []))
                v_cells = dict(value_rows.get(row_no, []))
                parts = []
                for col in sorted(set(f_cells) | set(v_cells),
                                  key=lambda c: (len(c), c)):
                    f_val, v_val = f_cells.get(col), v_cells.get(col)
                    if isinstance(f_val, str) and f_val.startswith('='):
                        cached = v_val if v_val is not None else '(no cached value)'
                        parts.append(f'{col}{row_no}={cached} [formula: {f_val}]')
                    else:
                        parts.append(f'{col}{row_no}={f_val if f_val is not None else v_val}')
                lines.append(f'row {row_no}: ' + ' | '.join(parts) + '\n')

            if not lines:
                continue

            # One chunk per sheet; split into row ranges when too large.
            buf, buf_len, start_idx = [], 0, 0
            for i, line in enumerate(lines):
                if buf_len + len(line) > CHUNK_CHARS and buf:
                    chunks.append(_sheet_chunk(name, row_numbers[start_idx],
                                               row_numbers[i - 1], ''.join(buf)))
                    buf, buf_len, start_idx = [], 0, i
                buf.append(line)
                buf_len += len(line)
            if buf:
                chunks.append(_sheet_chunk(name, row_numbers[start_idx],
                                           row_numbers[-1], ''.join(buf)))
    finally:
        wb_formula.close()
        wb_values.close()

    if not chunks:
        chunks.append(ParsedChunk(locator='xlsx:(empty)', kind='table',
                                  text='(workbook has no non-empty cells)'))
    if any('[formula:' in c.text and '(no cached value)' in c.text for c in chunks):
        warnings.append('部分公式单元格没有缓存计算值，数值可能需要重新计算。')
    warnings.append('公式缓存值来自文件上次保存时的计算结果，可能不是最新值。')
    return chunks, warnings, {'sheets': len(chunks), 'nonempty_cells': nonempty_cells}


def _sheet_chunk(sheet: str, row_start: int, row_end: int, text: str) -> ParsedChunk:
    return ParsedChunk(
        locator=f'xlsx:{sheet}!rows{row_start}-{row_end}',
        kind='table',
        text=f'Sheet: {sheet} (rows {row_start}-{row_end})\n' + text,
        sheet=sheet,
        metadata={'row_start': row_start, 'row_end': row_end},
    )
