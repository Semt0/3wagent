"""Generic, bounded text extraction for verified public PDF URLs."""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from src.websearch.client import OpenWebSearchError, _validate_public_url

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 300


class PdfReaderError(RuntimeError):
    """A remote PDF could not be safely downloaded or parsed."""


@dataclass(frozen=True)
class PdfText:
    final_url: str
    title: str
    content: str
    page_count: int
    truncated: bool


class _PublicRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_resolved_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PublicPdfReader:
    """Download and parse any provenance-approved public PDF."""

    def __init__(self, *, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds
        self._opener = build_opener(ProxyHandler({}), _PublicRedirectHandler())

    def fetch(self, url: str, *, max_chars: int) -> PdfText:
        from pypdf import PdfReader

        raw, final_url = self._download(url)
        if not raw.startswith(b"%PDF-"):
            raise PdfReaderError("the endpoint did not return a PDF file")
        try:
            reader = PdfReader(BytesIO(raw))
            if len(reader.pages) > MAX_PDF_PAGES:
                raise PdfReaderError(f"PDF exceeds the {MAX_PDF_PAGES}-page safety limit")
            page_texts = [page.extract_text() or "" for page in reader.pages]
        except PdfReaderError:
            raise
        except Exception as exc:
            raise PdfReaderError(f"PDF text extraction failed: {exc}") from exc

        if not any(text.strip() for text in page_texts):
            raise PdfReaderError(
                "PDF contains no extractable text; it may require OCR for scanned pages"
            )
        content = "\n\n".join(
            f"[PDF page {page_no}]\n{text.strip()}"
            for page_no, text in enumerate(page_texts, start=1)
            if text.strip()
        )
        metadata = reader.metadata or {}
        title = str(metadata.get("/Title") or "").strip() or _infer_title(page_texts)
        return PdfText(
            final_url=final_url,
            title=title or "PDF document",
            content=content[:max_chars],
            page_count=len(reader.pages),
            truncated=len(content) > max_chars,
        )

    def _download(self, url: str) -> tuple[bytes, str]:
        clean_url = _validate_resolved_public_url(url)
        request = Request(
            clean_url,
            headers={
                "Accept": "application/pdf,application/octet-stream;q=0.8",
                "Accept-Encoding": "identity",
                "User-Agent": "3WAgent/1.0 public PDF retrieval",
            },
        )
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                final_url = _validate_resolved_public_url(response.geturl())
                raw = response.read(MAX_PDF_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise PdfReaderError(f"PDF download failed: {exc}") from exc
        if len(raw) > MAX_PDF_BYTES:
            raise PdfReaderError("PDF exceeds the 25 MB safety limit")
        return raw, final_url


def is_pdf_response(url: str, content_type: str) -> bool:
    media_type = content_type.partition(";")[0].strip().lower()
    return media_type == "application/pdf" or urlparse(url).path.lower().endswith(".pdf")


def _validate_resolved_public_url(url: str) -> str:
    try:
        clean_url = _validate_public_url(url)
    except OpenWebSearchError as exc:
        raise PdfReaderError(exc.message) from exc
    parsed = urlparse(clean_url)
    hostname = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise PdfReaderError(f"PDF host resolution failed: {exc}") from exc
    if not addresses:
        raise PdfReaderError("PDF host did not resolve")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise PdfReaderError("PDF URL resolved to a private or local address")
    return clean_url


def _infer_title(page_texts: list[str]) -> str:
    for line in (page_texts[0] if page_texts else "").splitlines():
        candidate = line.strip()
        if candidate and not candidate.isdigit():
            return candidate[:200]
    return ""
