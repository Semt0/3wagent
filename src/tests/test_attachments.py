"""Tests for the unified attachment ingestion layer."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from qwen_agent.llm.schema import ContentItem, Message
from src.agent.attachments import inline_uploaded_files
from src.attachments import registry
from src.attachments.service import ingest_file
from src.config.attachments import AttachmentSettings
from src.tools.read_attachment import AttachmentReadTool


@pytest.fixture()
def settings(tmp_path):
    return AttachmentSettings(storage_dir=str(tmp_path / 'attachments'))


@pytest.fixture()
def tool_settings(tmp_path, monkeypatch):
    s = AttachmentSettings(storage_dir=str(tmp_path / 'attachments'))
    monkeypatch.setattr('src.tools.read_attachment.ATTACHMENT_SETTINGS', s)
    return s


def _make_pdf(path: Path, text: str) -> None:
    """Minimal one-page PDF with extractable text."""
    stream = f'BT /F1 24 Tf 72 720 Td ({text}) Tj ET'.encode()
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
        b'<< /Length ' + str(len(stream)).encode() + b' >>\nstream\n' + stream + b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    out = [b'%PDF-1.4\n']
    offsets = []
    pos = len(out[0])
    for i, body in enumerate(objects, start=1):
        offsets.append(pos)
        chunk = f'{i} 0 obj\n'.encode() + body + b'\nendobj\n'
        out.append(chunk)
        pos += len(chunk)
    xref = [f'xref\n0 {len(objects) + 1}\n'.encode(), b'0000000000 65535 f \n']
    xref += [f'{off:010d} 00000 n \n'.encode() for off in offsets]
    trailer = (f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n'
               f'startxref\n{pos}\n%%EOF\n').encode()
    path.write_bytes(b''.join(out) + b''.join(xref) + trailer)


# ---------------------------------------------------------------- text


def test_text_file_inlined(tmp_path, settings):
    f = tmp_path / 'notes.md'
    f.write_text('# 合同要点\n付款条款：见第十二条。\n', encoding='utf-8')
    result = ingest_file(f, settings=settings)
    assert result.readable
    assert '不可信的参考资料' in result.inline_text
    assert '付款条款' in result.inline_text
    assert '[notes.md, text:c1]' in result.inline_text
    assert result.document.parser == 'text'


def test_large_file_not_inlined(tmp_path, settings):
    f = tmp_path / 'big.txt'
    f.write_text('预提所得税条款。\n' * 5000, encoding='utf-8')  # ~90k chars
    result = ingest_file(f, settings=settings)
    assert result.readable
    assert 'inlined="false"' in result.inline_text
    assert 'AttachmentReadTool' in result.inline_text
    assert result.document.document_id in result.inline_text


def test_inline_budget_forces_summary(tmp_path, settings):
    f = tmp_path / 'notes.md'
    f.write_text('x' * 1000, encoding='utf-8')
    result = ingest_file(f, settings=settings, inline_budget=10)
    assert result.readable
    assert 'inlined="false"' in result.inline_text


def test_unsupported_format(tmp_path, settings):
    f = tmp_path / 'logo.png'
    f.write_bytes(b'\x89PNG\r\n\x1a\n')
    result = ingest_file(f, settings=settings)
    assert not result.readable
    assert '暂不支持该格式' in result.inline_text
    assert '.pdf' in result.inline_text


def test_oversize_file_rejected(tmp_path):
    s = AttachmentSettings(max_file_size_mb=0, storage_dir=str(tmp_path / 'a'))
    f = tmp_path / 'big.md'
    f.write_text('x' * 100, encoding='utf-8')
    result = ingest_file(f, settings=s)
    assert not result.readable
    assert '上限' in result.inline_text


# ---------------------------------------------------------------- csv


def test_csv_rows_are_numbered(tmp_path, settings):
    f = tmp_path / '明细.csv'
    f.write_text('日期,金额\n2026-01,100\n2026-02,200\n', encoding='utf-8')
    result = ingest_file(f, settings=settings)
    assert result.readable
    assert 'row 2: 2026-01 | 100' in result.inline_text
    assert result.document.chunks[0].locator == 'csv:rows1-3'


# ---------------------------------------------------------------- excel


def test_xlsx_formula_and_cached_value(tmp_path, settings):
    from openpyxl import Workbook

    f = tmp_path / 'model.xlsx'
    wb = Workbook()
    ws = wb.active
    ws.title = '收入表'
    ws['B4'] = 12800
    ws['C4'] = 0.13
    ws['D4'] = '=B4*C4'
    wb.save(f)

    result = ingest_file(f, settings=settings)
    assert result.readable
    text = result.inline_text
    assert 'B4=12800' in text
    assert '[formula: =B4*C4]' in text
    assert result.document.chunks[0].sheet == '收入表'
    assert any('缓存' in w for w in result.document.warnings)


def test_xlsx_zip_bomb_guard(tmp_path):
    s = AttachmentSettings(xlsx_max_uncompressed_mb=0,
                           storage_dir=str(tmp_path / 'a'))
    f = tmp_path / 'bomb.xlsx'
    with zipfile.ZipFile(f, 'w') as zf:
        zf.writestr('xl/worksheets/sheet1.xml', 'x' * 1000)
    result = ingest_file(f, settings=s)
    assert not result.readable
    assert '解析失败' in result.inline_text


# ---------------------------------------------------------------- pdf


def test_pdf_pages_have_locators(tmp_path, settings):
    f = tmp_path / 'contract.pdf'
    _make_pdf(f, 'Hello Page One')
    result = ingest_file(f, settings=settings)
    assert result.readable
    assert '[contract.pdf, pdf:p1]' in result.inline_text
    assert 'Hello Page One' in result.inline_text
    assert result.document.metadata['pages'] == 1


def test_pdf_page_limit(tmp_path):
    s = AttachmentSettings(pdf_max_pages=0, storage_dir=str(tmp_path / 'a'))
    f = tmp_path / 'contract.pdf'
    _make_pdf(f, 'Hello')
    result = ingest_file(f, settings=s)
    assert not result.readable
    assert '解析失败' in result.inline_text


# ------------------------------------------------------- AttachmentReadTool


def test_read_tool_locator_and_query(tmp_path, tool_settings):
    pdf = tmp_path / 'contract.pdf'
    _make_pdf(pdf, 'Withholding tax clause')
    result = ingest_file(pdf, settings=tool_settings)
    doc_id = result.document.document_id
    tool = AttachmentReadTool()

    out = tool.call({'document_id': doc_id, 'locator': 'pdf:p1'})
    assert 'Withholding tax clause' in out
    assert '[contract.pdf, pdf:p1]' in out

    out = tool.call({'document_id': doc_id, 'query': 'withholding'})
    assert 'Withholding tax clause' in out

    out = tool.call({'document_id': doc_id, 'locator': 'pdf:p9'})
    assert 'no chunks match' in out

    out = tool.call({'document_id': 'zzzzzzzzzzzz'})
    assert 'error' in out


def test_read_tool_xlsx_row_range(tmp_path, tool_settings):
    from openpyxl import Workbook

    f = tmp_path / '交易明细.xlsx'
    wb = Workbook()
    ws = wb.active
    ws.title = 'Sheet1'
    for i in range(1, 6):
        ws.cell(row=i, column=1, value=f'row-{i}')
    wb.save(f)

    result = ingest_file(f, settings=tool_settings)
    doc_id = result.document.document_id
    tool = AttachmentReadTool()

    out = tool.call({'document_id': doc_id, 'locator': 'xlsx:Sheet1!A1:E5'})
    assert 'row-3' in out
    out = tool.call({'document_id': doc_id, 'locator': 'xlsx:Sheet1'})
    assert 'row-5' in out


# ------------------------------------------------- message-level integration


def test_inline_uploaded_files_resolves_copy(tmp_path, settings, monkeypatch):
    """P0 regression: resolution must mutate the message it is given, so the
    caller can pass the deepcopy that sub-agents actually consume."""
    monkeypatch.setattr('src.agent.attachments.ATTACHMENT_SETTINGS', settings)
    import src.agent.attachments as agent_att
    monkeypatch.setattr(agent_att, 'ingest_file',
                        lambda path, inline_budget=None: ingest_file(
                            path, settings=settings, inline_budget=inline_budget))

    f = tmp_path / '合同.txt'
    f.write_text('第十二条 付款与预提税', encoding='utf-8')
    message = Message(role='user', content=[
        ContentItem(text='请分析这份合同'),
        ContentItem(file=str(f)),
    ])
    resolution = inline_uploaded_files(message)
    assert resolution.had_uploads and resolution.readable_files == 1
    texts = ''.join(item.text or '' for item in message.content)
    assert '第十二条 付款与预提税' in texts
    assert not any(item.file for item in message.content)


def test_should_block_when_nothing_readable(tmp_path, settings, monkeypatch):
    import src.agent.attachments as agent_att
    monkeypatch.setattr(agent_att, 'ingest_file',
                        lambda path, inline_budget=None: ingest_file(
                            path, settings=settings, inline_budget=inline_budget))
    f = tmp_path / 'img.png'
    f.write_bytes(b'\x89PNG')
    message = Message(role='user', content=[ContentItem(file=str(f))])
    resolution = inline_uploaded_files(message)
    assert resolution.should_block


def test_registry_covers_planned_formats():
    suffixes = registry.supported_suffixes()
    for expected in ('.pdf', '.xlsx', '.xlsm', '.csv', '.tsv', '.docx',
                     '.md', '.txt', '.yaml'):
        assert expected in suffixes
