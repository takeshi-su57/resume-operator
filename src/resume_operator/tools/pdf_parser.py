"""Extract text from PDF files using PyMuPDF."""

from pathlib import Path


def extract_text(pdf_path: Path) -> str:
    """Extract all text from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Concatenated text from all pages.
    """
    # TODO: Use fitz (PyMuPDF) to open PDF and extract text per page
    raise NotImplementedError
