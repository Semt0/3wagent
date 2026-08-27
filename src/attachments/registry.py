"""Parser registry: route files to the right parser by suffix.

Each parser is a ``parse(path, settings) -> (chunks, warnings, metadata)``
function plus name/version constants. Heavy parsers (e.g. MinerU for complex
PDFs) plug in here later without touching downstream code.
"""

from src.attachments.parsers import csv_parser, docx, excel, pdf_basic, text

PARSER_VERSION = '1.0'

_REGISTRY = {
    '.md': ('text', text.parse),
    '.markdown': ('text', text.parse),
    '.txt': ('text', text.parse),
    '.yaml': ('text', text.parse),
    '.yml': ('text', text.parse),
    '.csv': ('csv', csv_parser.parse),
    '.tsv': ('csv', csv_parser.parse),
    '.pdf': ('pdf_basic', pdf_basic.parse),
    '.xlsx': ('excel', excel.parse),
    '.xlsm': ('excel', excel.parse),
    '.docx': ('docx', docx.parse),
}


def supported_suffixes() -> list:
    return sorted(_REGISTRY)


def get_parser(suffix: str):
    """Return ``(parser_name, parse_fn)`` or ``None`` for unsupported types."""
    return _REGISTRY.get(suffix.lower())
