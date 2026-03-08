"""
ingestion/parsers/pdf_parser.py

Parses pharma manufacturer PDF documentation using pdfplumber.
Designed for drug prescribing information (PI) / package inserts,
which have structured sections like:
  - 5. WARNINGS AND PRECAUTIONS
  - 6. ADVERSE REACTIONS
  - 17. PATIENT COUNSELING INFORMATION

Extracts text per page with section detection metadata.
"""

import re
import logging
import pdfplumber
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Common section header patterns in FDA prescribing information
SECTION_HEADER_PATTERN = re.compile(
    r"^(\d{1,2}(?:\.\d{1,2})?)\s+([A-Z][A-Z\s,/()&-]{3,})\s*$",
    re.MULTILINE,
)

KNOWN_REPORTABLE_SECTIONS = {
    "adverse reactions",
    "warnings and precautions",
    "warnings",
    "contraindications",
    "boxed warning",
    "black box warning",
    "postmarketing experience",
    "clinical pharmacology",
    "drug interactions",
}


def detect_section(text: str) -> Optional[str]:
    """
    Attempt to detect which section of a prescribing information doc
    this page/chunk belongs to, based on header patterns.
    """
    matches = SECTION_HEADER_PATTERN.findall(text)
    if matches:
        # Return the last matched header (most specific for this page)
        section_num, section_name = matches[-1]
        return f"Section {section_num} - {section_name.strip().title()}"
    return None


def is_high_priority_section(section: Optional[str]) -> bool:
    """
    Flag sections that are most relevant to reportability decisions.
    These get higher priority weighting in retrieval.
    """
    if not section:
        return False
    section_lower = section.lower()
    return any(kw in section_lower for kw in KNOWN_REPORTABLE_SECTIONS)


def parse_pdf(filepath: str) -> list[dict]:
    """
    Parse a pharma manufacturer PDF into a list of page-level records.

    Args:
        filepath: Path to the PDF file

    Returns:
        List of dicts, each representing one page:
        {
            "content": str,        # Full text of the page
            "page": int,           # 1-indexed page number
            "section": str | None, # Detected section header
            "is_high_priority": bool,
            "has_table": bool,
            "source_file": str,
        }
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {filepath}")

    pages = []
    current_section = None

    logger.info(f"Parsing PDF: {path.name}")

    with pdfplumber.open(filepath) as pdf:
        logger.info(f"  Total pages: {len(pdf.pages)}")

        for i, page in enumerate(pdf.pages):
            page_num = i + 1

            # Extract text
            text = page.extract_text() or ""
            text = text.strip()

            if not text:
                logger.debug(f"  Page {page_num}: empty, skipping")
                continue

            # Detect section
            detected = detect_section(text)
            if detected:
                current_section = detected
                logger.debug(f"  Page {page_num}: new section → {current_section}")

            # Check for tables (useful metadata for chunker)
            tables = page.extract_tables()
            has_table = len(tables) > 0

            # If page has tables, extract table text and append
            if has_table:
                table_texts = []
                for table in tables:
                    for row in table:
                        cleaned = [cell or "" for cell in row]
                        table_texts.append(" | ".join(cleaned))
                table_block = "\n".join(table_texts)
                text = text + "\n\n[TABLE DATA]\n" + table_block

            pages.append({
                "content": text,
                "page": page_num,
                "section": current_section,
                "is_high_priority": is_high_priority_section(current_section),
                "has_table": has_table,
                "source_file": path.name,
            })

    logger.info(f"  Parsed {len(pages)} non-empty pages from {path.name}")
    return pages
