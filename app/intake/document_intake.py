from fastapi import UploadFile

from app.intake.pdf_parser import parse_pdf_bytes
from app.intake.word_parser import parse_docx_bytes


async def extract_upload_text(file: UploadFile) -> str:
    data = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        return parse_pdf_bytes(data)
    if filename.endswith(".docx"):
        return parse_docx_bytes(data)

    return data.decode("utf-8", errors="ignore")

