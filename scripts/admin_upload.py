"""
scripts/admin_upload.py

Admin tool for manually uploading new pharma manufacturer PDFs into the knowledge base.
This is the only way pharma docs enter the system (no automated folder watch).

Usage:
    # Upload a new drug's prescribing information
    python scripts/admin_upload.py upload \
        --file /path/to/lipitor_prescribing_info.pdf \
        --drug "Lipitor" \
        --manufacturer "Pfizer" \
        --version "2024-03"

    # Update an existing drug's documentation (re-index)
    python scripts/admin_upload.py upload \
        --file /path/to/lipitor_pi_updated.pdf \
        --drug "Lipitor" \
        --manufacturer "Pfizer" \
        --version "2024-09" \
        --replace

    # List all drugs in the knowledge base
    python scripts/admin_upload.py list

    # Remove a drug's documentation (e.g., drug discontinued)
    python scripts/admin_upload.py remove --drug "Lipitor"

    # Show knowledge base stats
    python scripts/admin_upload.py stats
"""

import argparse
import json
import sys
import os
import shutil
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DRUG_REGISTRY_FILE = Path("./data/drug_registry.json")


# ── Drug Registry ──────────────────────────────────────────────────────────────
# Tracks which drugs are in the system, their versions, and source files

def load_registry() -> dict:
    if DRUG_REGISTRY_FILE.exists():
        with open(DRUG_REGISTRY_FILE) as f:
            return json.load(f)
    return {}


def save_registry(registry: dict):
    DRUG_REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DRUG_REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)


def register_drug(drug_name: str, manufacturer: str, version: str, source_file: str, chunks: int):
    registry = load_registry()
    drug_key = drug_name.lower().strip()
    registry[drug_key] = {
        "drug_name": drug_name,
        "manufacturer": manufacturer,
        "version": version,
        "source_file": source_file,
        "chunks_indexed": chunks,
        "indexed_at": datetime.utcnow().isoformat(),
        "indexed_by": os.getenv("USER", "admin"),
    }
    save_registry(registry)
    logger.info(f"Registry updated: {drug_name} v{version} ({chunks} chunks)")


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_upload(args):
    from ingestion.loaders.doc_loader import ingest_document
    from knowledge_base.vector_store.store_manager import get_vector_store

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"\n❌  File not found: {args.file}")
        sys.exit(1)
    if filepath.suffix.lower() != ".pdf":
        print(f"\n❌  Only PDF files are supported. Got: {filepath.suffix}")
        sys.exit(1)

    store = get_vector_store()
    drug_key = args.drug.lower().strip()
    registry = load_registry()

    print(f"\n{'='*60}")
    print(f"  Admin: Upload Pharma Documentation")
    print(f"{'='*60}")
    print(f"  File         : {filepath.name}")
    print(f"  Drug         : {args.drug}")
    print(f"  Manufacturer : {args.manufacturer}")
    print(f"  Version      : {args.version}")
    print(f"  Replace      : {args.replace}")
    print(f"{'='*60}\n")

    # Warn if drug already exists and --replace not set
    if drug_key in registry and not args.replace:
        existing = registry[drug_key]
        print(f"⚠️  '{args.drug}' is already in the knowledge base:")
        print(f"   Version   : {existing['version']}")
        print(f"   Indexed   : {existing['indexed_at']}")
        print(f"   File      : {existing['source_file']}")
        print(f"\nTo replace it, add --replace to your command.\n")
        sys.exit(0)

    # If replacing, delete old chunks first
    if args.replace and drug_key in registry:
        deleted = store.delete_by_drug(args.drug)
        print(f"🗑️  Removed {deleted} old chunks for '{args.drug}'")

    # Copy PDF to pharma_docs archive
    from config.settings import settings
    archive_dir = Path(settings.PHARMA_DOCS_DIR) / drug_key
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / filepath.name
    shutil.copy2(str(filepath), str(dest))
    print(f"📁 PDF archived to: {dest}")

    # Ingest
    print(f"⚙️  Parsing and indexing PDF...")
    chunks = ingest_document(
        filepath=str(dest),
        drug_name=args.drug,
        manufacturer=args.manufacturer,
        doc_version=args.version,
        force_reindex=args.replace,
    )

    if chunks == 0 and not args.replace:
        print(f"\n⏭  Already indexed (content unchanged). Use --replace to force.")
        return

    register_drug(
        drug_name=args.drug,
        manufacturer=args.manufacturer,
        version=args.version,
        source_file=filepath.name,
        chunks=chunks,
    )

    print(f"\n✅ Successfully indexed {chunks} chunks for '{args.drug}'")
    print(f"   Total KB size: {store.total_chunks} chunks across all drugs\n")


def cmd_list(args):
    registry = load_registry()
    from knowledge_base.vector_store.store_manager import get_vector_store
    store = get_vector_store()

    print(f"\n{'='*65}")
    print(f"  Knowledge Base — Indexed Drugs")
    print(f"  Total: {store.total_chunks} chunks | {len(registry)} drugs")
    print(f"{'='*65}")

    if not registry:
        print("  (empty — no drugs indexed yet)")
    else:
        for key, info in sorted(registry.items()):
            print(f"\n  {info['drug_name']}")
            print(f"    Manufacturer : {info['manufacturer']}")
            print(f"    Version      : {info['version']}")
            print(f"    Chunks       : {info['chunks_indexed']}")
            print(f"    Source file  : {info['source_file']}")
            print(f"    Indexed      : {info['indexed_at'][:10]}")
    print()


def cmd_remove(args):
    from knowledge_base.vector_store.store_manager import get_vector_store
    store = get_vector_store()
    registry = load_registry()
    drug_key = args.drug.lower().strip()

    if drug_key not in registry:
        print(f"\n⚠️  '{args.drug}' not found in registry.")
        return

    deleted = store.delete_by_drug(args.drug)
    del registry[drug_key]
    save_registry(registry)

    print(f"\n✅ Removed '{args.drug}': {deleted} chunks deleted from knowledge base.\n")


def cmd_stats(args):
    from knowledge_base.vector_store.store_manager import get_vector_store
    store = get_vector_store()
    registry = load_registry()

    print(f"\n{'='*50}")
    print(f"  Knowledge Base Statistics")
    print(f"{'='*50}")
    print(f"  Total chunks : {store.total_chunks}")
    print(f"  Drugs indexed: {len(registry)}")
    print(f"  Registry file: {DRUG_REGISTRY_FILE}")
    print()


# ── CLI Entry Point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Admin tool: manage pharma PDF documentation in the knowledge base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command")

    # upload
    up = subparsers.add_parser("upload", help="Upload a new pharma PDF")
    up.add_argument("--file", required=True, help="Path to PDF file")
    up.add_argument("--drug", required=True, help="Drug name (e.g. 'Lipitor')")
    up.add_argument("--manufacturer", required=True, help="Manufacturer name (e.g. 'Pfizer')")
    up.add_argument("--version", required=True, help="Doc version label (e.g. '2024-09')")
    up.add_argument("--replace", action="store_true", help="Replace existing indexed doc")

    # list
    subparsers.add_parser("list", help="List all indexed drugs")

    # remove
    rm = subparsers.add_parser("remove", help="Remove a drug's documentation")
    rm.add_argument("--drug", required=True, help="Drug name to remove")

    # stats
    subparsers.add_parser("stats", help="Show knowledge base statistics")

    args = parser.parse_args()

    if args.command == "upload":
        cmd_upload(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "remove":
        cmd_remove(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
