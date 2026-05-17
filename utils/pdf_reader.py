"""Extracts plain text from selectable-text PDF files using pdfplumber."""
import os
import pdfplumber

from utils.logger import setup_logger

logger = setup_logger(__name__)


def get_page_count(path: str) -> int:
    """Return the total number of pages in the PDF at *path*."""
    with pdfplumber.open(path) as pdf:
        return len(pdf.pages)


def extract_text(
    path: str,
    start_page: int = 1,
    end_page: int | None = None,
) -> str:
    """Return text extracted from *path*, optionally restricted to a page range.

    *start_page* and *end_page* are 1-based and inclusive.  When *end_page*
    is ``None`` all pages from *start_page* to the end are extracted.

    Returns an empty string if the PDF contains no selectable text
    (e.g. scanned image-only PDFs).
    """
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        first = max(1, start_page) - 1          # convert to 0-based
        last  = min(total, end_page or total)    # inclusive, 1-based
        for page in pdf.pages[first:last]:
            text = page.extract_text()
            if text:
                pages.append(text.strip())

    result = '\n\n'.join(pages)
    logger.info(
        'Extracted %d chars from "%s" (pages %d-%d)',
        len(result), os.path.basename(path), start_page, end_page or last,
    )
    return result
