"""
scripts/run_classifier.py

CLI tool for running the adverse event classifier on a single chart note.
Usage:
    python scripts/run_classifier.py --case-id CASE123 --chart-note notes.txt --drug "DrugName"
"""

import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_classifier.classifier import classify_reportability
from event_classifier.schemas import ReportabilityDecision


def main():
    parser = argparse.ArgumentParser(description="Run adverse event reportability classifier")
    parser.add_argument("--case-id", required=True, help="Case identifier")
    parser.add_argument("--chart-note", required=True, help="Path to chart note text file")
    parser.add_argument("--drug", required=True, help="Drug name")
    parser.add_argument("--output", default=None, help="Output JSON file path (optional)")
    args = parser.parse_args()

    # Load chart note
    with open(args.chart_note, "r") as f:
        chart_note_text = f.read()

    print(f"\n{'='*60}")
    print(f"  Adverse Event Reportability Classifier")
    print(f"{'='*60}")
    print(f"  Case ID : {args.case_id}")
    print(f"  Drug    : {args.drug}")
    print(f"{'='*60}\n")

    # Initialize clients (reads from .env)
    from config.settings import get_llm_client, get_vector_store
    llm_client = get_llm_client()
    vector_store = get_vector_store()

    print("Running classification...\n")
    result = classify_reportability(
        chart_note=chart_note_text,
        drug_name=args.drug,
        llm_client=llm_client,
        vector_store=vector_store,
        case_id=args.case_id,
    )

    # ── Print results ──────────────────────────────────────────────────────────
    decision_emoji = {
        ReportabilityDecision.YES: "🔴 REPORTABLE",
        ReportabilityDecision.NO: "🟢 NOT REPORTABLE",
        ReportabilityDecision.NEEDS_REVIEW: "🟡 NEEDS HUMAN REVIEW",
    }

    print(f"DECISION      : {decision_emoji[result.decision]}")
    print(f"CONFIDENCE    : {result.confidence_score:.1%}")
    print(f"HUMAN REVIEW? : {'YES' if result.requires_human_review else 'NO'}\n")
    print(f"REASONING:\n{result.reasoning}\n")

    if result.supporting_doc_sections:
        print(f"SUPPORTING SECTIONS:")
        for section in result.supporting_doc_sections:
            print(f"  - {section}")

    if result.recommended_report_type:
        print(f"\nREPORT TYPE: {result.recommended_report_type}")

    # ── Save output ────────────────────────────────────────────────────────────
    output_path = args.output or f"output_{args.case_id}.json"
    with open(output_path, "w") as f:
        json.dump(result.model_dump(), f, indent=2)
    print(f"\nFull output saved to: {output_path}")


if __name__ == "__main__":
    main()
