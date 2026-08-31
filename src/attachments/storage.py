"""Storage for uploaded files and their parse results.

Layout per document::

    workspace/attachments/<document_id>/
    ├── original<suffix>    # verbatim copy of the upload
    ├── manifest.json       # ParsedDocument metadata
    ├── document.md         # all chunks rendered with locator headers
    └── chunks.jsonl        # one ParsedChunk per line

``document_id`` is derived from the content hash, so identical uploads dedupe
naturally. Per-session isolation and cache expiry can be layered on later by
prefixing the directory with a session id.
"""

import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from src.tools.common import PROJECT_ROOT

# Ids of documents ingested during this process lifetime. AttachmentReadTool
# uses it to answer "document not found" with the real choices (or the fact
# that nothing was uploaded) instead of letting the model guess ids.
_session_documents: set[str] = set()


def register_session_document(document_id: str) -> None:
    if document_id:
        _session_documents.add(document_id)


def session_document_ids() -> list[str]:
    return sorted(_session_documents)


def reset_session_documents() -> None:
    """Clear process-local state. Intended for tests."""
    _session_documents.clear()


def _root(settings) -> Path:
    root = PROJECT_ROOT / settings.storage_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def store_upload(src_path: Path, settings) -> tuple:
    """Copy an upload into the attachment store; return (document_id, stored_path)."""
    digest = hashlib.sha256(src_path.read_bytes()).hexdigest()
    document_id = digest[:12]
    doc_dir = _root(settings) / document_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    stored = doc_dir / f'original{src_path.suffix.lower()}'
    if not stored.exists():
        shutil.copyfile(src_path, stored)
    return document_id, stored, digest


def save_parsed(doc, settings) -> Path:
    doc_dir = _root(settings) / doc.document_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    manifest = asdict(doc)
    chunks = manifest.pop('chunks')
    (doc_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    with (doc_dir / 'chunks.jsonl').open('w', encoding='utf-8') as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk, ensure_ascii=False) + '\n')

    rendered = []
    for chunk in doc.chunks:
        rendered.append(f'\n[{doc.filename}, {chunk.locator}]\n{chunk.text}\n')
    (doc_dir / 'document.md').write_text(''.join(rendered), encoding='utf-8')
    return doc_dir


def load_document(document_id: str, settings) -> tuple:
    """Load (manifest, chunks) for a stored document. Raises FileNotFoundError."""
    if not document_id or not all(c in '0123456789abcdef' for c in document_id):
        raise FileNotFoundError(f'invalid document_id: {document_id!r}')
    doc_dir = _root(settings) / document_id
    manifest_path = doc_dir / 'manifest.json'
    chunks_path = doc_dir / 'chunks.jsonl'
    if not manifest_path.is_file() or not chunks_path.is_file():
        raise FileNotFoundError(f'document not found: {document_id}')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    chunks = [
        json.loads(line)
        for line in chunks_path.read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]
    return manifest, chunks
