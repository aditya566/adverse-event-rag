"""
ingestion/loaders/doc_loader.py

Orchestrates loading, parsing, chunking, and indexing of pharma manufacturer docs.
Run this whenever new drug documentation is added or updated.
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import Optional

from ingestion.parsers.pdf_parser import parse_pdf
from ingestion.parsers.docx_parser import parse_docx
from ingestion.parsers.chunker import semantic_chunk
from knowledge_base.embeddings.embedder import get_embedder
from knowledge_base.vector_store.store_manager import get_vector_store
from config.settings import settings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc"}


def get_file_hash(filepath: str) -> str:
    """Returns MD5 hash of file — used to detect if doc has changed."""
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def ingest_document(
    filepath: str,
    drug_name: str,
    manufacturer: str,
    doc_version: Optional[str] = None,
    force_reindex: bool = False,
) -> int:
    """
    Ingest a single pharma document into the knowledge base.

    Args:
        filepath:      Path to the PDF or DOCX file
        drug_name:     Name of the drug (used as metadata filter key)
        manufacturer:  Pharma manufacturer name
        doc_version:   Optional version label (e.g. "2024-Q1")
        force_reindex: Re-index even if file hash hasn't changed

    Returns:
        Number of chunks indexed
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {filepath}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: {SUPPORTED_EXTENSIONS}")

    file_hash = get_file_hash(filepath)
    vector_store = get_vector_store()

    # Check if already indexed (by hash stored as metadata)
    if not force_reindex and vector_store.document_exists(file_hash):
        logger.info(f"Document {path.name} already indexed (hash={file_hash}). Skipping.")
        return 0

    logger.info(f"Ingesting: {path.name} | Drug: {drug_name} | Hash: {file_hash}")

    # ── Parse ──────────────────────────────────────────────────────────────────
    if suffix == ".pdf":
        pages = parse_pdf(filepath)
    else:
        pages = parse_docx(filepath)

    logger.info(f"Parsed {len(pages)} pages/sections")

    # ── Chunk ──────────────────────────────────────────────────────────────────
    chunks = semantic_chunk(
        pages=pages,
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
    )
    logger.info(f"Created {len(chunks)} chunks")

    # ── Embed + Store ──────────────────────────────────────────────────────────
    embedder = get_embedder()
    texts = [c["content"] for c in chunks]
    embeddings = embedder.embed_documents(texts)

    metadatas = [
        {
            "drug_name": drug_name.lower(),
            "manufacturer": manufacturer,
            "source_doc": path.name,
            "doc_version": doc_version or "unknown",
            "file_hash": file_hash,
            "section": c.get("section", "unknown"),
            "page": c.get("page", -1),
        }
        for c in chunks
    ]

    vector_store.add_documents(
        texts=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    logger.info(f"Successfully indexed {len(chunks)} chunks for {drug_name}")
    return len(chunks)


def ingest_directory(
    directory: str,
    drug_name: str,
    manufacturer: str,
    doc_version: Optional[str] = None,
) -> dict:
    """Ingest all supported documents in a directory."""
    results = {}
    for filepath in Path(directory).rglob("*"):
        if filepath.suffix.lower() in SUPPORTED_EXTENSIONS:
            try:
                count = ingest_document(
                    filepath=str(filepath),
                    drug_name=drug_name,
                    manufacturer=manufacturer,
                    doc_version=doc_version,
                )
                results[filepath.name] = {"status": "success", "chunks": count}
            except Exception as e:
                logger.error(f"Failed to ingest {filepath.name}: {e}")
                results[filepath.name] = {"status": "error", "error": str(e)}
    return results
