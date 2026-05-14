"""
OCR / text extraction service.
Supports PDF (via pdfplumber) and DOCX (via python-docx).
"""

from __future__ import annotations
import io
import logging

logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF file using pdfplumber."""
    try:
        import pdfplumber

        text_parts: list[str] = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text.strip())

        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}")
        # Fallback: try PyPDF2 if installed
        try:
            import PyPDF2

            reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            for page in reader.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t.strip())
            return "\n\n".join(text_parts)
        except Exception as e2:
            logger.error(f"PyPDF2 fallback also failed: {e2}")
            raise RuntimeError(f"Could not extract text from PDF: {e}") from e


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract all text from a DOCX file using python-docx."""
    try:
        from docx import Document

        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if cell_text and cell_text not in paragraphs:
                        paragraphs.append(cell_text)

        return "\n".join(paragraphs)
    except Exception as e:
        logger.error(f"python-docx extraction failed: {e}")
        raise RuntimeError(f"Could not extract text from DOCX: {e}") from e


def extract_text(file_bytes: bytes, content_type: str) -> str:
    """
    Dispatcher: choose extraction method based on MIME type.

    Supported types:
    - application/pdf
    - application/vnd.openxmlformats-officedocument.wordprocessingml.document (DOCX)
    """
    content_type = content_type.lower()

    if content_type == "application/pdf":
        text = extract_text_from_pdf(file_bytes)
    elif content_type in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        text = extract_text_from_docx(file_bytes)
    else:
        raise ValueError(
            f"Unsupported file type: {content_type}. "
            "Only PDF and DOCX files are supported."
        )

    if not text.strip():
        raise ValueError(
            "No text could be extracted from the file. "
            "The document may be image-based (scanned) or empty."
        )

    logger.info(f"Extracted {len(text)} characters from {content_type} file")
    return text
