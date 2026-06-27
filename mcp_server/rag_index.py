"""Lightweight local RAG index for 3wagent source snapshots.

The index is intentionally small: SQLite stores source chunks and FTS5 provides
keyword recall. Legal/policy metadata stays attached to every chunk so retrieval
can be filtered before analysis.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RELIABILITY_RANK = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}


@dataclass(frozen=True)
class SourceMetadata:
    """Metadata copied from sources/*.yaml and preserved on each chunk."""

    source_id: str
    title: str
    authority: str = ""
    url: str = ""
    jurisdiction: str = ""
    domains: tuple[str, ...] = ()
    subdomains: tuple[str, ...] = ()
    reliability: str = ""
    source_type: str = ""
    publication_date: str = ""
    effective_date: str = ""
    status: str = ""
    retrieved_at: str = ""
    snapshot_path: str = ""

    @classmethod
    def from_source(cls, source: dict[str, Any], jurisdiction: str = "") -> SourceMetadata:
        domains = source.get("domains") or ()
        subdomains = source.get("subdomains") or ()
        return cls(
            source_id=str(source.get("id", "")),
            title=str(source.get("title", "")),
            authority=str(source.get("authority", "")),
            url=str(source.get("url", "")),
            jurisdiction=str(source.get("jurisdiction") or jurisdiction),
            domains=tuple(domains if isinstance(domains, list) else [domains]),
            subdomains=tuple(subdomains if isinstance(subdomains, list) else [subdomains]),
            reliability=str(source.get("reliability", "")),
            source_type=str(source.get("source_type", "")),
            publication_date=str(source.get("publication_date", "")),
            effective_date=str(source.get("effective_date", "")),
            status=str(source.get("status", "")),
            retrieved_at=str(source.get("retrieved_date") or source.get("retrieved_at") or ""),
            snapshot_path=str(source.get("snapshot_path", "")),
        )


def connect(index_path: Path) -> sqlite3.Connection:
    """Open an index connection and ensure the schema exists."""
    index_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(index_path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the SQLite and FTS tables if needed."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
          id INTEGER PRIMARY KEY,
          source_id TEXT NOT NULL,
          title TEXT NOT NULL,
          authority TEXT,
          url TEXT,
          jurisdiction TEXT,
          domains TEXT NOT NULL DEFAULT '[]',
          subdomains TEXT NOT NULL DEFAULT '[]',
          reliability TEXT,
          source_type TEXT,
          publication_date TEXT,
          effective_date TEXT,
          status TEXT,
          retrieved_at TEXT,
          snapshot_path TEXT,
          heading TEXT,
          chunk_index INTEGER NOT NULL,
          text TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
          source_id,
          title,
          authority,
          jurisdiction,
          domains,
          heading,
          text,
          content='documents',
          content_rowid='id'
        );

        CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);
        CREATE INDEX IF NOT EXISTS idx_documents_jurisdiction ON documents(jurisdiction);
        CREATE INDEX IF NOT EXISTS idx_documents_reliability ON documents(reliability);
        """
    )
    conn.commit()


def chunk_text(text: str, *, max_chars: int = 1800, overlap: int = 180) -> list[tuple[str, str]]:
    """Split Markdown/plain text into overlapping chunks with nearby headings."""
    clean_text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not clean_text:
        return []

    paragraphs = re.split(r"\n\s*\n", clean_text)
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    current_len = 0
    heading = ""

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunk = "\n\n".join(current).strip()
            if chunk:
                chunks.append((heading, chunk))
            tail = chunk[-overlap:] if overlap > 0 else ""
            current = [tail] if tail else []
            current_len = len(tail)

    for paragraph in paragraphs:
        stripped = paragraph.strip()
        if not stripped:
            continue
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            heading = heading_match.group(2).strip()
        if len(stripped) > max_chars:
            flush()
            for start in range(0, len(stripped), max_chars - overlap):
                part = stripped[start : start + max_chars].strip()
                if part:
                    chunks.append((heading, part))
            current = []
            current_len = 0
            continue
        next_len = current_len + len(stripped) + 2
        if next_len > max_chars:
            flush()
        current.append(stripped)
        current_len += len(stripped) + 2

    flush()
    return chunks


def upsert_document(conn: sqlite3.Connection, metadata: SourceMetadata, text: str) -> int:
    """Replace all chunks for a source and insert fresh chunks."""
    if not metadata.source_id:
        raise ValueError("source_id is required")
    chunks = chunk_text(text)
    now = datetime.now(timezone.utc).isoformat()
    retrieved_at = metadata.retrieved_at or now

    existing_ids = [
        row["id"] for row in conn.execute("SELECT id FROM documents WHERE source_id = ?", (metadata.source_id,))
    ]
    if existing_ids:
        conn.executemany("DELETE FROM documents_fts WHERE rowid = ?", [(row_id,) for row_id in existing_ids])
    conn.execute("DELETE FROM documents WHERE source_id = ?", (metadata.source_id,))

    for index, (heading, chunk) in enumerate(chunks):
        cursor = conn.execute(
            """
            INSERT INTO documents (
              source_id, title, authority, url, jurisdiction, domains, subdomains,
              reliability, source_type, publication_date, effective_date, status,
              retrieved_at, snapshot_path, heading, chunk_index, text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata.source_id,
                metadata.title,
                metadata.authority,
                metadata.url,
                metadata.jurisdiction,
                json.dumps(list(metadata.domains), ensure_ascii=False),
                json.dumps(list(metadata.subdomains), ensure_ascii=False),
                metadata.reliability,
                metadata.source_type,
                metadata.publication_date,
                metadata.effective_date,
                metadata.status,
                retrieved_at,
                metadata.snapshot_path,
                heading,
                index,
                chunk,
            ),
        )
        row_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO documents_fts (
              rowid, source_id, title, authority, jurisdiction, domains, heading, text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row_id,
                metadata.source_id,
                metadata.title,
                metadata.authority,
                metadata.jurisdiction,
                " ".join(metadata.domains),
                heading,
                chunk,
            ),
        )

    conn.commit()
    return len(chunks)


def search_documents(
    conn: sqlite3.Connection,
    query: str,
    *,
    jurisdictions: list[str] | None = None,
    domains: list[str] | None = None,
    reliability: list[str] | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search indexed chunks with metadata filters and reliability-aware ranking."""
    query = query.strip()
    if not query:
        return []

    filters, params = _metadata_filters(jurisdictions, domains, reliability)
    rows = _fts_rows(conn, query, filters, params)
    if not rows:
        rows = _like_rows(conn, query, filters, params)

    scored = [_row_to_result(row, query) for row in rows]
    scored.sort(
        key=lambda item: (
            item["score"],
            RELIABILITY_RANK.get(item.get("reliability", ""), 0),
            -item.get("chunk_index", 0),
        ),
        reverse=True,
    )
    return scored[: max(1, min(limit, 50))]


def read_source(conn: sqlite3.Connection, source_id: str) -> dict[str, Any] | None:
    """Read all indexed chunks for one source as a single document."""
    rows = conn.execute(
        "SELECT * FROM documents WHERE source_id = ? ORDER BY chunk_index", (source_id,)
    ).fetchall()
    if not rows:
        return None
    first = _row_to_dict(rows[0])
    first["text"] = "\n\n".join(row["text"] for row in rows)
    first["chunks"] = len(rows)
    return first


def _metadata_filters(
    jurisdictions: list[str] | None,
    domains: list[str] | None,
    reliability: list[str] | None,
) -> tuple[list[str], list[str]]:
    filters: list[str] = []
    params: list[str] = []
    if jurisdictions:
        placeholders = ", ".join("?" for _ in jurisdictions)
        filters.append(f"jurisdiction IN ({placeholders})")
        params.extend(j.upper() for j in jurisdictions)
    if reliability:
        placeholders = ", ".join("?" for _ in reliability)
        filters.append(f"reliability IN ({placeholders})")
        params.extend(level.upper() for level in reliability)
    if domains:
        domain_filters = []
        for domain in domains:
            domain_filters.append("domains LIKE ?")
            params.append(f'%"{domain.lower()}"%')
        filters.append("(" + " OR ".join(domain_filters) + ")")
    return filters, params


def _fts_rows(
    conn: sqlite3.Connection, query: str, filters: list[str], params: list[str]
) -> list[sqlite3.Row]:
    fts_query = _fts_query(query)
    if not fts_query:
        return []
    where = ["documents_fts MATCH ?"]
    if filters:
        where.extend(f"documents.{flt}" for flt in filters)
    sql = f"""
        SELECT documents.*, bm25(documents_fts) AS fts_rank
        FROM documents_fts
        JOIN documents ON documents_fts.rowid = documents.id
        WHERE {" AND ".join(where)}
        LIMIT 100
    """
    try:
        return conn.execute(sql, [fts_query, *params]).fetchall()
    except sqlite3.OperationalError:
        return []


def _like_rows(
    conn: sqlite3.Connection, query: str, filters: list[str], params: list[str]
) -> list[sqlite3.Row]:
    terms = _query_terms(query)
    if not terms:
        return []
    like_filters = []
    like_params: list[str] = []
    for term in terms:
        like_filters.append("(title LIKE ? OR heading LIKE ? OR text LIKE ?)")
        pattern = f"%{term}%"
        like_params.extend([pattern, pattern, pattern])
    where = ["(" + " OR ".join(like_filters) + ")"]
    if filters:
        where.extend(filters)
    sql = f"""
        SELECT documents.*, 0.0 AS fts_rank
        FROM documents
        WHERE {" AND ".join(where)}
        LIMIT 100
    """
    return conn.execute(sql, [*like_params, *params]).fetchall()


def _fts_query(query: str) -> str:
    terms = _query_terms(query)
    if not terms:
        return ""
    return " OR ".join(f'"{term}"' for term in terms[:12])


def _query_terms(query: str) -> list[str]:
    terms = re.findall(r"[\w\u4e00-\u9fff]+", query.lower())
    if not terms and query.strip():
        return [query.strip().lower()]
    return [term for term in terms if len(term) > 1 or "\u4e00" <= term <= "\u9fff"]


def _row_to_result(row: sqlite3.Row, query: str) -> dict[str, Any]:
    item = _row_to_dict(row)
    terms = _query_terms(query)
    haystacks = {
        "title": item.get("title", "").lower(),
        "heading": item.get("heading", "").lower(),
        "text": item.get("text", "").lower(),
    }
    score = RELIABILITY_RANK.get(item.get("reliability", ""), 0) * 2
    for term in terms:
        score += haystacks["title"].count(term) * 6
        score += haystacks["heading"].count(term) * 4
        score += min(haystacks["text"].count(term), 5)
    fts_rank = item.pop("fts_rank", 0.0) or 0.0
    score += max(0.0, 10.0 - abs(float(fts_rank)))
    item["score"] = round(score, 3)
    item["text_excerpt"] = _excerpt(item.get("text", ""), terms)
    item.pop("text", None)
    return item


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["domains"] = _json_list(item.get("domains"))
    item["subdomains"] = _json_list(item.get("subdomains"))
    return item


def _json_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        data = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [str(value)]
    return data if isinstance(data, list) else [str(data)]


def _excerpt(text: str, terms: list[str], *, radius: int = 180) -> str:
    lowered = text.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    if not positions:
        return text[: radius * 2].strip()
    start = max(0, min(positions) - radius)
    end = min(len(text), min(positions) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"
