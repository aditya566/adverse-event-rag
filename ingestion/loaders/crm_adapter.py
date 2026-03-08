"""
ingestion/loaders/crm_adapter.py

Adapter for ingesting free-text chart notes exported from a CRM system.

CRM exports are typically plain .txt or .csv files dropped to a shared folder
by advocates after documenting a patient call. This module:
  1. Scans the intake directory for new note files
  2. Parses known CRM export formats (plain text, CSV export)
  3. Extracts the case metadata header (case ID, date, advocate ID)
  4. Applies PII redaction before returning note for classification
  5. Moves processed files to the processed directory

Supported CRM export formats:
  - Plain .txt with header block (most common)
  - Single-row .csv export from CRM (case_id, date, advocate_id, note_text)

To add a new CRM format, implement a new parse_* function and register it
in PARSERS below.
"""

import os
import re
import csv
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)


# ── Data class for a parsed chart note ────────────────────────────────────────

class ChartNote:
    def __init__(
        self,
        case_id: str,
        note_text: str,
        drug_name: str,
        call_date: str,
        advocate_id: str,
        raw_text: str,
        source_file: str,
    ):
        self.case_id = case_id
        self.note_text = note_text        # PII-redacted text
        self.drug_name = drug_name
        self.call_date = call_date
        self.advocate_id = advocate_id
        self.raw_text = raw_text          # Original (kept locally, never sent to LLM)
        self.source_file = source_file

    def __repr__(self):
        return f"ChartNote(case_id={self.case_id}, drug={self.drug_name}, date={self.call_date})"


# ── PII Redaction ──────────────────────────────────────────────────────────────

def redact_pii(text: str) -> str:
    """
    Remove PHI/PII from chart note text before sending to Claude.

    Uses Microsoft Presidio when available (production).
    Falls back to regex-based redaction for common patterns.

    Redacts: full names, SSNs, phone numbers, email addresses,
             street addresses, MRNs, full dates of birth.
    Preserves: drug names, symptom descriptions, age ranges,
               month/year dates, severity indicators.
    """
    if not settings.ENABLE_PII_REDACTION:
        logger.warning("PII redaction is DISABLED — never use in production!")
        return text

    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()

        results = analyzer.analyze(
            text=text,
            language="en",
            entities=[
                "PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS",
                "US_SSN", "US_PASSPORT", "LOCATION",
                "MEDICAL_RECORD_NUMBER", "DATE_TIME",
            ],
        )
        # Preserve month/year dates — only redact full DOB patterns
        results = [
            r for r in results
            if not (r.entity_type == "DATE_TIME" and _is_partial_date(text[r.start:r.end]))
        ]

        redacted = anonymizer.anonymize(text=text, analyzer_results=results)
        return redacted.text

    except ImportError:
        logger.warning(
            "presidio not installed — falling back to regex PII redaction. "
            "Install presidio-analyzer and presidio-anonymizer for production use."
        )
        return _regex_redact(text)


def _is_partial_date(date_str: str) -> bool:
    """Returns True if this is a month/year (not a full DOB) — preserve these."""
    partial = re.match(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}$", date_str)
    return bool(partial)


def _regex_redact(text: str) -> str:
    """Fallback regex-based PII redaction."""
    # Phone numbers
    text = re.sub(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", "[PHONE]", text)
    # SSN
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", text)
    # Email
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]", text)
    # Full dates of birth (MM/DD/YYYY or MM-DD-YYYY)
    text = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b", "[DATE]", text)
    # Names (heuristic: "Patient: First Last" or "patient name: ...")
    text = re.sub(r"(?i)(patient\s*(name)?[:–]\s*)[A-Z][a-z]+\s+[A-Z][a-z]+", r"\1[NAME]", text)
    return text


# ── CRM Format Parsers ────────────────────────────────────────────────────────

def parse_text_export(filepath: str) -> Optional[ChartNote]:
    """
    Parse a plain-text CRM export with a header block.

    Expected format:
        Date: 2024-03-15
        Advocate ID: ADV-0042
        Case ID: CASE-2024-0891

        PATIENT CALL SUMMARY
        ─────────────────────
        <free text note body>
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        raw_text = f.read()

    # Extract header fields
    case_id = _extract_field(raw_text, r"Case\s*ID\s*[:–]\s*(\S+)")
    advocate_id = _extract_field(raw_text, r"Advocate\s*(?:ID)?\s*[:–]\s*(\S+)")
    call_date = _extract_field(raw_text, r"Date\s*[:–]\s*(\d{4}-\d{2}-\d{2})")
    drug_name = _extract_field(raw_text, r"Drug\s*(?:Name)?\s*[:–]\s*(.+?)(?:\n|$)")

    if not case_id:
        # Fall back to using filename as case ID
        case_id = Path(filepath).stem
        logger.warning(f"Could not extract Case ID from {filepath} — using filename: {case_id}")

    if not call_date:
        call_date = datetime.today().strftime("%Y-%m-%d")

    # Strip header lines to get the note body
    note_body = re.sub(
        r"^(Date|Advocate\s*ID|Case\s*ID|Drug\s*(?:Name)?).*\n?",
        "", raw_text, flags=re.MULTILINE | re.IGNORECASE,
    ).strip()

    redacted_note = redact_pii(note_body)

    return ChartNote(
        case_id=case_id or Path(filepath).stem,
        note_text=redacted_note,
        drug_name=drug_name or "",
        call_date=call_date,
        advocate_id=advocate_id or "UNKNOWN",
        raw_text=raw_text,
        source_file=Path(filepath).name,
    )


def parse_csv_export(filepath: str) -> list[ChartNote]:
    """
    Parse a CSV export from CRM where each row is one case.

    Expected columns: case_id, call_date, advocate_id, drug_name, note_text
    Column names are case-insensitive.
    """
    notes = []
    with open(filepath, "r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        # Normalize column names to lowercase
        for row in reader:
            row = {k.lower().strip(): v for k, v in row.items()}
            note_text = row.get("note_text") or row.get("notes") or row.get("chart_note", "")
            redacted = redact_pii(note_text)
            notes.append(ChartNote(
                case_id=row.get("case_id", "UNKNOWN"),
                note_text=redacted,
                drug_name=row.get("drug_name") or row.get("drug", ""),
                call_date=row.get("call_date") or row.get("date", ""),
                advocate_id=row.get("advocate_id") or row.get("advocate", "UNKNOWN"),
                raw_text=note_text,
                source_file=Path(filepath).name,
            ))
    return notes


def _extract_field(text: str, pattern: str) -> Optional[str]:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


# ── Intake Directory Scanner ───────────────────────────────────────────────────

def scan_intake_directory() -> list[ChartNote]:
    """
    Scan the CRM intake directory for new chart note files.
    Returns all parsed ChartNote objects ready for classification.
    Moves processed files to the processed directory.
    """
    intake_dir = Path(settings.CHART_NOTES_INTAKE_DIR)
    processed_dir = Path(settings.CHART_NOTES_PROCESSED_DIR)
    intake_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    all_notes = []

    txt_files = list(intake_dir.glob("*.txt"))
    csv_files = list(intake_dir.glob("*.csv"))

    logger.info(
        f"Intake scan: {len(txt_files)} .txt files, {len(csv_files)} .csv files"
    )

    for filepath in txt_files:
        try:
            note = parse_text_export(str(filepath))
            if note:
                all_notes.append(note)
                _move_to_processed(filepath, processed_dir)
        except Exception as e:
            logger.error(f"Failed to parse {filepath.name}: {e}")

    for filepath in csv_files:
        try:
            notes = parse_csv_export(str(filepath))
            all_notes.extend(notes)
            _move_to_processed(filepath, processed_dir)
        except Exception as e:
            logger.error(f"Failed to parse CSV {filepath.name}: {e}")

    logger.info(f"Loaded {len(all_notes)} chart notes from intake directory")
    return all_notes


def _move_to_processed(filepath: Path, processed_dir: Path):
    """Move file to processed directory with timestamp suffix."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = processed_dir / f"{filepath.stem}_{timestamp}{filepath.suffix}"
    shutil.move(str(filepath), str(dest))
    logger.debug(f"Moved {filepath.name} → {dest.name}")
