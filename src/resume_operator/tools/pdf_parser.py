"""Extract text from PDF files using PyMuPDF."""

from pathlib import Path

import fitz


def extract_text(pdf_path: Path) -> str:
    """Extract all text from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Concatenated text from all pages.

    Raises:
        FileNotFoundError: If the PDF file does not exist.
        ValueError: If the PDF contains no extractable text.
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    pages: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pages.append(page.get_text())

    text = "\n".join(pages).strip()

    if not text:
        raise ValueError(f"No extractable text found in PDF: {pdf_path}")

    return text
