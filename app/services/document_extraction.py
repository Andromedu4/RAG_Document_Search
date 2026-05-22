from io import BytesIO

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.services.text import normalize_text

PDF_TYPES = {"application/pdf"}
DOCX_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/docx",
}
TEXT_TYPES = {"text/plain", "text/markdown"}
SUPPORTED_TYPES = PDF_TYPES | DOCX_TYPES | TEXT_TYPES


def extract_text_from_upload(content: bytes, *, filename: str, content_type: str) -> str:
    normalized_type = content_type.split(";")[0].strip().lower()
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if normalized_type in PDF_TYPES or suffix == "pdf":
        return normalize_text(_extract_pdf(content))
    if normalized_type in DOCX_TYPES or suffix == "docx":
        return normalize_text(_extract_docx(content))
    if normalized_type in TEXT_TYPES or suffix in {"txt", "md"}:
        return normalize_text(content.decode("utf-8", errors="ignore"))

    raise ValueError("Only PDF, DOCX, TXT, and Markdown uploads are supported.")


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(content: bytes) -> str:
    document = DocxDocument(BytesIO(content))
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n\n".join(paragraphs)
