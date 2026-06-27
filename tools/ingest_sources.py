#!/usr/bin/env python3
"""Ingest source snapshots into the local SQLite RAG index.

Examples:
  uv run python tools/ingest_sources.py --source-id cn-foreign-exchange-regulations --text-file law.md
  uv run python tools/ingest_sources.py --all-snapshots
  uv run python tools/ingest_sources.py --source-id hk-ird-dipn --fetch
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp_server.rag_index import SourceMetadata, connect, upsert_document  # noqa: E402

SOURCES_DIR = ROOT / "sources"
SNAPSHOTS_DIR = SOURCES_DIR / "snapshots"
INDEX_PATH = SOURCES_DIR / "index.sqlite"


class TextExtractor(HTMLParser):
    """Small HTML-to-text extractor for official pages and saved snapshots."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
        if tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        stripped = data.strip()
        if stripped:
            self.parts.append(stripped)
            self.parts.append(" ")

    def text(self) -> str:
        text = html.unescape("".join(self.parts))
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def load_registry_sources(sources_dir: Path) -> dict[str, SourceMetadata]:
    """Load source metadata from every sources/*.yaml registry."""
    sources: dict[str, SourceMetadata] = {}
    for path in sorted(sources_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        jurisdiction = data.get("jurisdiction", "")
        for source in data.get("sources", []):
            metadata = SourceMetadata.from_source(source, jurisdiction=jurisdiction)
            if metadata.source_id:
                sources[metadata.source_id] = metadata
    return sources


def read_text_file(path: Path) -> str:
    """Read a plain text, Markdown or HTML snapshot."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in {".html", ".htm"}:
        parser = TextExtractor()
        parser.feed(raw)
        return parser.text()
    return raw


def fetch_url(url: str, *, timeout: int = 20) -> str:
    """Fetch a URL using stdlib urllib and return extracted text for HTML."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "3wagent-source-ingestion/0.1 (+https://github.com/Semt0/3wagent)"
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        body = response.read()
    text = body.decode("utf-8", errors="replace")
    if "html" in content_type.lower() or "<html" in text[:500].lower():
        parser = TextExtractor()
        parser.feed(text)
        return parser.text()
    return text


def find_snapshot(snapshot_dir: Path, source_id: str) -> Path | None:
    """Find a saved snapshot for a source id under sources/snapshots/."""
    for suffix in (".md", ".txt", ".html", ".htm"):
        direct = snapshot_dir / f"{source_id}{suffix}"
        if direct.exists():
            return direct
        matches = sorted(snapshot_dir.glob(f"**/{source_id}{suffix}"))
        if matches:
            return matches[0]
    return None


def metadata_only_text(metadata: SourceMetadata) -> str:
    """Build a tiny fallback document from registry metadata."""
    lines = [
        f"# {metadata.title}",
        f"Authority: {metadata.authority}",
        f"Jurisdiction: {metadata.jurisdiction}",
        f"Domains: {', '.join(metadata.domains)}",
        f"Reliability: {metadata.reliability}",
        f"Source type: {metadata.source_type}",
        f"URL: {metadata.url}",
    ]
    return "\n".join(line for line in lines if line.strip())


def ingest_one(
    metadata: SourceMetadata,
    *,
    index_path: Path,
    text_file: Path | None = None,
    snapshot_dir: Path = SNAPSHOTS_DIR,
    fetch: bool = False,
    metadata_only: bool = False,
) -> tuple[str, int, str]:
    """Ingest one source and return (source_id, chunk_count, origin)."""
    origin = ""
    if text_file is not None:
        text = read_text_file(text_file)
        origin = str(text_file)
        metadata = SourceMetadata(**{**metadata.__dict__, "snapshot_path": str(text_file)})
    elif fetch:
        if not metadata.url:
            raise ValueError(f"{metadata.source_id}: cannot fetch without url")
        text = fetch_url(metadata.url)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / f"{metadata.source_id}.txt"
        snapshot_path.write_text(text, encoding="utf-8")
        origin = str(snapshot_path)
        metadata = SourceMetadata(**{**metadata.__dict__, "snapshot_path": str(snapshot_path)})
    else:
        snapshot = find_snapshot(snapshot_dir, metadata.source_id)
        if snapshot is not None:
            text = read_text_file(snapshot)
            origin = str(snapshot)
            metadata = SourceMetadata(**{**metadata.__dict__, "snapshot_path": str(snapshot)})
        elif metadata_only:
            text = metadata_only_text(metadata)
            origin = "registry metadata"
        else:
            raise FileNotFoundError(
                f"{metadata.source_id}: no snapshot found. Use --text-file, --fetch or --metadata-only."
            )

    with connect(index_path) as conn:
        count = upsert_document(conn, metadata, text)
    return metadata.source_id, count, origin


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest 3wagent sources into a local RAG index.")
    parser.add_argument("--sources-dir", type=Path, default=SOURCES_DIR)
    parser.add_argument("--snapshots-dir", type=Path, default=SNAPSHOTS_DIR)
    parser.add_argument("--index", type=Path, default=INDEX_PATH)
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--all-snapshots", action="store_true")
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--metadata-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sources = load_registry_sources(args.sources_dir)
    if not sources:
        print(f"No sources found under {args.sources_dir}", file=sys.stderr)
        return 1

    if args.text_file and len(args.source_id) != 1:
        print("--text-file requires exactly one --source-id", file=sys.stderr)
        return 2

    if args.all_snapshots:
        source_ids = [
            source_id for source_id in sources if find_snapshot(args.snapshots_dir, source_id) is not None
        ]
    else:
        source_ids = args.source_id

    if not source_ids:
        print("No source ids selected. Use --source-id, --all-snapshots or --metadata-only.", file=sys.stderr)
        return 2

    failures = 0
    for source_id in source_ids:
        metadata = sources.get(source_id)
        if metadata is None:
            print(f"{source_id}: not found in registry", file=sys.stderr)
            failures += 1
            continue
        try:
            _, count, origin = ingest_one(
                metadata,
                index_path=args.index,
                text_file=args.text_file,
                snapshot_dir=args.snapshots_dir,
                fetch=args.fetch,
                metadata_only=args.metadata_only,
            )
        except Exception as exc:  # noqa: BLE001 - CLI should report per-source failures.
            print(f"{source_id}: failed: {exc}", file=sys.stderr)
            failures += 1
            continue
        print(f"{source_id}: indexed {count} chunk(s) from {origin}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
