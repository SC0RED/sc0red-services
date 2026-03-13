"""Text extraction from uploaded documents.

Supports PDF, DOCX, XLSX/XLS, and plain text formats.
Each document is capped at 15,000 characters to keep AI prompts within context limits.
"""

from __future__ import annotations

import io
from typing import Any

_MAX_CHARS_PER_DOCUMENT = 15_000
_MAX_CHARS_COMBINED = 25_000

_SUPPORTED_TYPES = frozenset({"pdf", "docx", "xlsx", "xls", "txt", "csv", "md"})


def extract_text(file_bytes: bytes, file_type: str) -> str:
    """Extract text content from file bytes based on file type.

    Args:
        file_bytes: Raw file content.
        file_type: File extension without dot (e.g. "pdf", "docx").

    Returns:
        Extracted text, capped at 15,000 characters.

    Raises:
        ValueError: If file_type is not supported.
    """
    normalised = file_type.lower().strip(".")
    if normalised not in _SUPPORTED_TYPES:
        supported = ", ".join(sorted(_SUPPORTED_TYPES))
        message = f"Unsupported file type: {normalised}. Supported: {supported}"
        raise ValueError(message)

    extractors: dict[str, Any] = {
        "pdf": _extract_pdf,
        "docx": _extract_docx,
        "xlsx": _extract_xlsx,
        "xls": _extract_xlsx,
        "txt": _extract_plain_text,
        "csv": _extract_plain_text,
        "md": _extract_plain_text,
    }

    text = extractors[normalised](file_bytes)
    return text[:_MAX_CHARS_PER_DOCUMENT]


def combine_document_texts(texts: list[str]) -> str:
    """Combine multiple document texts with separators, capped at 25,000 characters."""
    combined = "\n---\n".join(texts)
    if len(combined) > _MAX_CHARS_COMBINED:
        return combined[:_MAX_CHARS_COMBINED] + "\n[...truncated]"
    return combined


def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


def _extract_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX using python-docx."""
    from docx import Document

    document = Document(io.BytesIO(file_bytes))
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs)


def _extract_xlsx(file_bytes: bytes) -> str:
    """Extract text from XLSX/XLS using openpyxl."""
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    sheets = []
    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        rows = []
        for row in sheet.iter_rows(values_only=True):
            cells = [str(cell) if cell is not None else "" for cell in row]
            if any(cells):
                rows.append(",".join(cells))
        if rows:
            sheets.append(f"[Sheet: {sheet_name}]\n" + "\n".join(rows))
    workbook.close()
    return "\n\n".join(sheets)


def _extract_plain_text(file_bytes: bytes) -> str:
    """Decode plain text files as UTF-8."""
    return file_bytes.decode("utf-8", errors="replace")
