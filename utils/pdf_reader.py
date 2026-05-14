"""Extracts plain text from selectable-text PDF files using pdfplumber."""
import os
import pdfplumber

from utils.logger import setup_logger

logger = setup_logger(__name__)


def extract_text(path: str, max_pages: int | None = None) -> str:
    """Return all text extracted from the PDF at *path*, page by page.

    If *max_pages* is given and the document exceeds that count, a
    ``ValueError`` is raised before any extraction begins so the caller
    can surface a clear message to the user.

    Returns an empty string if the PDF contains no selectable text
    (e.g. scanned image-only PDFs).
    """
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        if max_pages is not None and total > max_pages:
            raise ValueError(
                f'"{os.path.basename(path)}" has {total} pages. '
                f'Please upload a document with {max_pages} pages or fewer '
                f'to keep analysis fast and accurate.'
            )
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())

    result = '\n\n'.join(pages)
    logger.info('Extracted %d chars from "%s"', len(result), path)
    return result
