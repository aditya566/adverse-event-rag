"""
scripts/run_pipeline.py

End-to-end pipeline runner.

Workflow:
  1. Scan CRM intake directory for new chart note exports (.txt / .csv)
  2. For each note: redact PII → extract event data → RAG classify
  3. Save classification results to review queue
  4. Print summary for advocate review

Usage:
    # Process all new chart notes in the intake directory
    python scripts/run_pipeline.py

    # Process a specific file
    python scripts/run_pipeline.py --file data/crm_intake/case_001.txt

    # Dry run (classify but don't move files or save results)
    python scripts/run_pipeline.py --dry-run

    # Override drug name (if not in note header)
    python scripts/run_pipeline.py --file case.txt --drug "Humira"
"""

import argparse
import json
import sys
import os
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

REVIEW_QUEUE_DIR = Path("./data/review_queue")


def save_to_review_queue(case_id: str, chart_note, classifier_output) -> str:
    """Write classification result to review queue as JSON."""
    REVIEW_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{datetime.today().strftime('%Y-%m-%d')}_{case_id}_{timestamp}.json"
    filepath = REVIEW_QUEUE_DIR / filename

    record = {
        "case_id": case_id,
        "call_date": chart_note.call_date,
        "drug_name": chart_note.drug_name,
        "advocate_id": chart_note.advocate_id,
        "source_file": chart_note.source_file,
        "classifier_output": classifier_output.model_dump(),
        "status": "PENDING_REVIEW",
        "queued_at": datetime.utcnow().isoformat(),
    }

    with open(filepath, "w") as f:
        json.dump(record, f, indent=2)

    return str(filepath)


def print_result_summary(chart_note, result):
    """Print a clean summary of one classification result."""
    from event_classifier.schemas import ReportabilityDecision

    icons = {
        ReportabilityDecision.YES: "🔴",
        ReportabilityDecision.NO: "🟢",
        ReportabilityDecision.NEEDS_REVIEW: "🟡",
    }
    icon = icons.get(result.decision, "⚪")

    print(f"\n  {'─'*55}")
    print(f"  Case     : {chart_note.case_id}")
    print(f"  Drug     : {chart_note.drug_name or '(not extracted)'}")
    print(f"  Decision : {icon}  {result.decision.value}")
    print(f"  Confidence: {result.confidence_score:.0%}")
    if result.requires_human_review:
        print(f"  ⚠️  REQUIRES HUMAN REVIEW")
    if result.supporting_doc_sections:
        print(f"  Citing   : {result.supporting_doc_sections[0]}")


def run_pipeline(
    specific_file: str = None,
    drug_override: str = None,
    dry_run: bool = False,
):
    from ingestion.loaders.crm_adapter import scan_intake_directory, parse_text_export
    from event_classifier.classifier import classify_reportability
    from knowledge_base.vector_store.store_manager import get_vector_store
    from config.settings import get_llm_client, settings

    print(f"\n{'='*60}")
    print(f"  Adverse Event RAG Pipeline")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if dry_run:
        print(f"  *** DRY RUN — no files will be moved or saved ***")
    print(f"{'='*60}")

    # Initialize shared clients once
    llm_client = get_llm_client()
    vector_store = get_vector_store()

    logger.info(
        f"Knowledge base loaded: {vector_store.total_chunks} chunks, "
        f"drugs: {vector_store.list_indexed_drugs()}"
    )

    # Load chart notes
    if specific_file:
        note = parse_text_export(specific_file)
        notes = [note] if note else []
    else:
        notes = scan_intake_directory() if not dry_run else scan_intake_directory()

    if not notes:
        print("\n  No chart notes found in intake directory.")
        print(f"  Drop .txt or .csv exports to: {settings.CHART_NOTES_INTAKE_DIR}\n")
        return

    print(f"\n  Processing {len(notes)} chart note(s)...\n")

    results = {"reportable": 0, "not_reportable": 0, "needs_review": 0, "errors": 0}

    for chart_note in notes:
        # Apply drug override if note didn't include drug name
        drug_name = drug_override or chart_note.drug_name
        if not drug_name:
            logger.warning(
                f"Case {chart_note.case_id}: no drug name found. "
                f"Use --drug to specify, or add 'Drug: <name>' to the note header."
            )
            results["errors"] += 1
            continue

        chart_note.drug_name = drug_name

        try:
            result = classify_reportability(
                chart_note=chart_note.note_text,
                drug_name=drug_name,
                llm_client=llm_client,
                vector_store=vector_store,
                case_id=chart_note.case_id,
            )

            print_result_summary(chart_note, result)

            # Tally
            if result.decision.value == "YES":
                results["reportable"] += 1
            elif result.decision.value == "NO":
                results["not_reportable"] += 1
            else:
                results["needs_review"] += 1

            # Save to review queue
            if not dry_run:
                queue_path = save_to_review_queue(chart_note.case_id, chart_note, result)
                logger.info(f"Saved to review queue: {queue_path}")

        except Exception as e:
            logger.error(f"Classification failed for case {chart_note.case_id}: {e}")
            results["errors"] += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"  Pipeline Complete")
    print(f"{'─'*60}")
    print(f"  🔴 Reportable      : {results['reportable']}")
    print(f"  🟡 Needs Review    : {results['needs_review']}")
    print(f"  🟢 Not Reportable  : {results['not_reportable']}")
    print(f"  ❌ Errors          : {results['errors']}")
    if not dry_run and (results["reportable"] + results["needs_review"]) > 0:
        print(f"\n  Review queue: {REVIEW_QUEUE_DIR}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Run the adverse event RAG classification pipeline"
    )
    parser.add_argument("--file", help="Process a single chart note file")
    parser.add_argument("--drug", help="Drug name override (if not in note header)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Classify but don't save results or move files",
    )
    args = parser.parse_args()

    run_pipeline(
        specific_file=args.file,
        drug_override=args.drug,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
