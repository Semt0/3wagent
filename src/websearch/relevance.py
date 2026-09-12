"""Lightweight, topic-independent relevance scoring for search discovery."""

from __future__ import annotations

import re
import unicodedata

_BOOK_TITLE_RE = re.compile(r"《([^》]{2,})》")
_QUOTED_RE = re.compile(r"[\"“”']([^\"“”']{3,})[\"“”']")
_SITE_RE = re.compile(r"\bsite\s*:\s*[^\s]+", re.IGNORECASE)
_ASCII_WORD_RE = re.compile(r"[a-z0-9][a-z0-9._-]+", re.IGNORECASE)
_CJK_RUN_RE = re.compile(r"[\u3400-\u9fff]{2,}")


def normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(char for char in normalized if char.isalnum())


def strip_site_operators(query: str) -> str:
    return re.sub(r"\s+", " ", _SITE_RE.sub(" ", query)).strip()


def query_phrases(query: str) -> list[str]:
    """Extract useful fragments without requiring a Chinese tokenizer."""

    clean = strip_site_operators(query)
    phrases: list[str] = []
    phrases.extend(_BOOK_TITLE_RE.findall(clean))
    phrases.extend(_QUOTED_RE.findall(clean))
    unquoted = _BOOK_TITLE_RE.sub(" ", _QUOTED_RE.sub(" ", clean))
    phrases.extend(_CJK_RUN_RE.findall(unquoted))
    phrases.extend(_ASCII_WORD_RE.findall(clean))

    unique: list[str] = []
    seen: set[str] = set()
    for phrase in phrases:
        normalized = normalize_search_text(phrase)
        if len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def relevance_score(query: str, title: str, snippet: str = "") -> float:
    """Return a stable 0..1 discovery score for one result."""

    title_text = normalize_search_text(title)
    body_text = normalize_search_text(f"{title} {snippet}")
    if not body_text:
        return 0.0

    explicit = [
        normalize_search_text(value)
        for value in (*_BOOK_TITLE_RE.findall(query), *_QUOTED_RE.findall(query))
        if len(normalize_search_text(value)) >= 3
    ]
    if any(phrase in title_text for phrase in explicit):
        return 1.0
    if any(phrase in body_text for phrase in explicit):
        return 0.92

    terms = query_phrases(query)
    if not terms:
        query_text = normalize_search_text(strip_site_operators(query))
        if not query_text:
            return 0.0
        return 1.0 if query_text in body_text else _ngram_overlap(query_text, title_text)

    weights = [min(len(term), 24) for term in terms]
    covered = sum(weight for term, weight in zip(terms, weights) if term in body_text)
    coverage = covered / max(1, sum(weights))
    partial = _ngram_overlap(max(terms, key=len), title_text)
    return round(min(1.0, 0.78 * coverage + 0.22 * partial), 4)


def _ngram_overlap(left: str, right: str, size: int = 2) -> float:
    if not left or not right:
        return 0.0
    if len(left) < size or len(right) < size:
        return 1.0 if left == right else 0.0
    left_grams = {left[index : index + size] for index in range(len(left) - size + 1)}
    right_grams = {right[index : index + size] for index in range(len(right) - size + 1)}
    return len(left_grams & right_grams) / max(1, len(left_grams))
