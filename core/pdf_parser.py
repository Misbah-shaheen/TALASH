"""
talash.core.pdf_parser
Extracts clean text from PDFs using pdfplumber.
Handles multi-column structured form layouts (NUST HR export format).
"""

import pdfplumber
import re
from pathlib import Path


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    """
    Extract and clean text from a PDF, preserving table structure.
    Returns a single string suitable for LLM consumption.
    """
    pdf_path = Path(pdf_path)
    pages_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            # Strategy: extract tables first (structured sections), then free text
            page_content = _extract_page(page, page_num)
            if page_content.strip():
                pages_text.append(page_content)

    full_text = "\n\n--- PAGE BREAK ---\n\n".join(pages_text)
    return _clean_text(full_text)


def _extract_page(page, page_num: int) -> str:
    """Extract a single page — tables get priority, then remaining text."""
    sections = []

    # Extract tables with structure preserved
    tables = page.extract_tables()
    table_bboxes = []

    for table in tables:
        if not table:
            continue
        rows = []
        for row in table:
            if row:
                # Filter out completely empty rows
                cells = [str(c).strip() if c else "" for c in row]
                if any(cells):
                    rows.append(" | ".join(cells))
        if rows:
            sections.append("\n".join(rows))

        # Track table bounding boxes to avoid re-extracting as text
        try:
            bbox = page.find_tables()[len(table_bboxes)].bbox if page.find_tables() else None
            if bbox:
                table_bboxes.append(bbox)
        except Exception:
            pass

    # Extract text outside tables
    if table_bboxes:
        # Crop out table areas and get remaining text
        try:
            remaining_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            sections.insert(0, remaining_text)
        except Exception:
            pass
    else:
        text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
        if text.strip():
            sections.insert(0, text)

    return "\n".join(sections)


def _clean_text(text: str) -> str:
    """Remove noise while preserving structural information."""
    # Remove form-feed characters
    text = text.replace("\f", "\n--- PAGE BREAK ---\n")

    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse multiple spaces (but preserve alignment cues with 2-space tabs)
    text = re.sub(r" {4,}", "   ", text)

    # Remove null bytes
    text = text.replace("\x00", "")

    return text.strip()


def get_pdf_metadata(pdf_path: str | Path) -> dict:
    """Return basic PDF metadata for logging."""
    pdf_path = Path(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        return {
            "filename": pdf_path.name,
            "page_count": len(pdf.pages),
            "file_size_kb": round(pdf_path.stat().st_size / 1024, 1),
        }
