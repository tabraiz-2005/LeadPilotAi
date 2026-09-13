"""Utilities for extracting text from portfolio artifacts used by the LeadPilot RAG pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from docx import Document
from pypdf import PdfReader


def parse_pdf(file_path: str) -> str:
    """Read a PDF file and return all extracted text content.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        Extracted text from the PDF with page breaks normalized to newline characters.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())

    extracted_text = "\n".join(pages)
    return extracted_text.strip()


def parse_docx(file_path: str) -> str:
    """Read a DOCX file and return the concatenated text from all paragraphs.

    Args:
        file_path: Absolute or relative path to the DOCX file.

    Returns:
        Text content from the document, normalized to newline-separated paragraphs.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"DOCX file not found: {file_path}")

    document = Document(str(path))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n".join(paragraphs).strip()


def parse_txt(file_path: str) -> str:
    """Read a plain-text file and return its contents.

    Args:
        file_path: Absolute or relative path to the text file.

    Returns:
        The file content as-is, without trailing whitespace trimming.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Text file not found: {file_path}")

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.read().strip()


def parse_file(file_path: str) -> str:
    """Parse a supported portfolio file by automatically detecting its type.

    Supported extensions are .pdf, .docx, and .txt. Unsupported file types raise
    a ValueError.

    Args:
        file_path: Absolute or relative path to the file to parse.

    Returns:
        The extracted text content from the file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file extension is unsupported.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()
    parser_map: dict[str, Callable[[str], str]] = {
        ".pdf": parse_pdf,
        ".docx": parse_docx,
        ".txt": parse_txt,
    }

    parser = parser_map.get(suffix)
    if parser is None:
        raise ValueError(f"Unsupported file type: {suffix or 'no extension'}")

    return parser(str(path))


__all__ = ["parse_pdf", "parse_docx", "parse_txt", "parse_file"]
