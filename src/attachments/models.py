"""Parser-agnostic data model for parsed attachments.

Downstream code (context injection, AttachmentReadTool, citation verifier)
depends only on these structures, never on parser-specific output formats.
"""

from dataclasses import dataclass, field


@dataclass
class ParsedChunk:
    """One addressable piece of a parsed document.

    ``locator`` is the canonical citation handle, e.g. ``pdf:p12``,
    ``xlsx:Sheet1!B4:F18``, ``docx:c2``, ``text:c1``.
    """

    locator: str
    kind: str  # text | table | heading | footnote
    text: str
    page: int | None = None
    sheet: str | None = None
    bbox: list | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedDocument:
    document_id: str
    filename: str
    mime_type: str
    content_hash: str
    parser: str
    parser_version: str
    chunks: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def total_chars(self) -> int:
        return sum(len(c.text) for c in self.chunks)

    def outline(self, max_chars: int = 4000) -> str:
        """Compact table of contents for large documents that are not inlined."""
        lines = []
        for chunk in self.chunks:
            preview = ' '.join(chunk.text.split())[:80]
            lines.append(f'- [{chunk.locator}] ({chunk.kind}, {len(chunk.text)} chars) {preview}')
            if sum(len(line) for line in lines) > max_chars:
                lines.append('- ... (truncated, use AttachmentReadTool for more)')
                break
        return '\n'.join(lines)

    def render_inline(self, max_chars: int) -> str:
        """Full content with locator markers, for small documents."""
        parts = []
        used = 0
        for chunk in self.chunks:
            header = f'\n[{self.filename}, {chunk.locator}]\n'
            if used + len(header) + len(chunk.text) > max_chars:
                parts.append('\n... (inline truncated, use AttachmentReadTool for the rest)\n')
                break
            parts.append(header + chunk.text)
            used += len(header) + len(chunk.text)
        return ''.join(parts)
