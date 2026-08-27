"""Unified attachment ingestion layer.

Parses uploaded files of different formats into a parser-agnostic
``ParsedDocument`` model, persists parse results under
``workspace/attachments/<document_id>/``, and decides whether content is
inlined into the model context or read on demand via ``AttachmentReadTool``.
"""

from src.attachments.models import ParsedChunk, ParsedDocument
from src.attachments.service import IngestionResult, ingest_file

__all__ = ['IngestionResult', 'ParsedChunk', 'ParsedDocument', 'ingest_file']
