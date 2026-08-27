"""Attachment ingestion settings.

Single source of truth for upload limits, inline thresholds and storage
location. Kept as a Python dataclass (consistent with the other modules in
``src/config``); expose as YAML later if operators need to tune it.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AttachmentSettings:
    max_file_size_mb: int = 25
    inline_max_chars_per_file: int = 30_000
    inline_max_chars_total: int = 60_000
    pdf_max_pages: int = 300
    workbook_max_sheets: int = 50
    workbook_max_nonempty_cells: int = 200_000
    # XLSX is a ZIP archive; guard against decompression bombs.
    xlsx_max_uncompressed_mb: int = 200
    # Low text yield per page => probably a scan; suggest heavy parsing.
    pdf_min_chars_per_page: int = 50
    storage_dir: str = 'workspace/attachments'


ATTACHMENT_SETTINGS = AttachmentSettings()
