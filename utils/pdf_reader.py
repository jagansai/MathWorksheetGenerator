"""Extracts plain text from selectable-text PDF files using pdfplumber."""
import pdfplumber

from utils.logger import setup_logger

logger = setup_logger(__name__)


def extract_text(path: str) -> str:
    """Return all text extracted from the PDF at *path*, page by page.

    Returns an empty string if the PDF contains no selectable text
    (e.g. scanned image-only PDFs).
    """
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())

    result = '\n\n'.join(pages)
    logger.info('Extracted %d chars from "%s"', len(result), path)
    return result
