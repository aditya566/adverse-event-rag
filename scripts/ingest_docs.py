"""
scripts/ingest_docs.py

CLI tool for ingesting pharma manufacturer PDF documentation into the knowledge base.

Usage examples:

  # Ingest a single PDF
  python scripts/ingest_docs.py --file docs/lipitor_pi.pdf --drug "Lipitor" --manufacturer "Pfizer"

  # Ingest all PDFs in a folder for one drug
  python scripts/ingest_docs.py --dir docs/lipitor/ --drug "Lipitor" --manufacturer "Pfizer" --version "2024-Q1"

  # Force re-index (even if already indexed)
  python scripts/ingest_docs.py --file docs/lipitor_pi.pdf --drug "Lipitor" --manufacturer "Pfizer" --force

  # List all currently indexed drugs
  python scripts/ingest_docs.py --list
"""

import argparse
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from ingestion.loaders.doc_loader import ingest_document, ingest_directory
from knowledge_base.vector_store.store_manager import get_vector_store


def main():
    parser = argparse.ArgumentParser(
        description="Ingest pharma manufacturer PDFs into the adverse event knowledge base"
    )
    parser.add_argument("--file", help="Path to a single PDF file")
    parser.add_argument("--dir", help="Directory containing PDFs to ingest")
    parser.add_argument("--drug", help="Drug name (required unless --list)")
    parser.add_argument("--manufacturer", help="Manufacturer name", default="Unknown")
    parser.add_argument("--version", help="Document version label (e.g. 2024-Q1)", default=None)
    parser.add_argument("--force", action="store_true", help="Force re-index even if already indexed")
    parser.add_argument("--list", action="store_true", help="List all indexed drugs and exit")
    parser.add_argument("--delete-drug", help="Remove all indexed chunks for a drug and exit")

    args = parser.parse_args()

    store = get_vector_store()

    # ── List indexed drugs ─────────────────────────────────────────────────────
    if args.list:
        drugs = store.list_indexed_drugs()
        print(f"\n{'='*50}")
        print(f"  Knowledge Base: {store.total_chunks} total chunks")
        print(f"  Indexed drugs ({len(drugs)}):")
        for d in drugs:
            print(f"    - {d}")
        print(f"{'='*50}\n")
        return

    # ── Delete a drug ──────────────────────────────────────────────────────────
    if args.delete_drug:
        deleted = store.delete_by_drug(args.delete_drug)
        print(f"Deleted {deleted} chunks for drug: {args.delete_drug}")
        return

    # ── Validate required args ─────────────────────────────────────────────────
    if not args.drug:
        print("ERROR: --drug is required for ingestion. Use --list to see indexed drugs.")
        sys.exit(1)

    if not args.file and not args.dir:
        print("ERROR: Either --file or --dir is required.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Pharma Doc Ingestion Pipeline")
    print(f"{'='*60}")
    print(f"  Drug         : {args.drug}")
    print(f"  Manufacturer : {args.manufacturer}")
    print(f"  Version      : {args.version or 'unspecified'}")
    print(f"  Force reindex: {args.force}")
    print(f"{'='*60}\n")

    # ── Single file ────────────────────────────────────────────────────────────
    if args.file:
        count = ingest_document(
            filepath=args.file,
            drug_name=args.drug,
            manufacturer=args.manufacturer,
            doc_version=args.version,
            force_reindex=args.force,
        )
        if count > 0:
            print(f"\n✅ Successfully indexed {count} chunks from {args.file}")
        else:
            print(f"\n⏭  Already indexed (use --force to re-index)")

    # ── Directory ──────────────────────────────────────────────────────────────
    elif args.dir:
        results = ingest_directory(
            directory=args.dir,
            drug_name=args.drug,
            manufacturer=args.manufacturer,
            doc_version=args.version,
        )
        print(f"\nIngestion Results:")
        total_chunks = 0
        for filename, result in results.items():
            status = "✅" if result["status"] == "success" else "❌"
            if result["status"] == "success":
                total_chunks += result.get("chunks", 0)
                print(f"  {status} {filename}: {result['chunks']} chunks")
            else:
                print(f"  {status} {filename}: ERROR — {result['error']}")
        print(f"\nTotal: {total_chunks} chunks indexed for '{args.drug}'")

    print(f"\nKnowledge base now contains {store.total_chunks} total chunks.")
    print(f"Indexed drugs: {', '.join(store.list_indexed_drugs())}\n")


if __name__ == "__main__":
    main()
