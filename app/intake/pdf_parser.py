def parse_pdf_bytes(data: bytes) -> str:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to parse PDF files.") from exc

    document = fitz.open(stream=data, filetype="pdf")
    pages = [page.get_text("text") for page in document]
    return "\n".join(pages).strip()

