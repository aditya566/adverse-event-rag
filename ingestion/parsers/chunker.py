"""
ingestion/parsers/chunker.py

Chunks parsed pharma PDF pages into LLM-ready segments.

Strategy:
- Respects section boundaries — never splits a section header from its content
- High-priority sections (Adverse Reactions, Warnings) get smaller chunks
  for more precise retrieval
- Preserves section + page metadata on every chunk
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Smaller chunks for high-priority sections = more precise retrieval
HIGH_PRIORITY_CHUNK_SIZE = 400    # tokens approx (chars / 4)
DEFAULT_CHUNK_SIZE = 800
CHUNK_OVERLAP_CHARS = 150


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English."""
    return len(text) // 4


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, preserving structure."""
    # Split on sentence-ending punctuation followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def semantic_chunk(
    pages: list[dict],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP_CHARS,
) -> list[dict]:
    """
    Convert page-level records into overlapping chunks suitable for embedding.

    Args:
        pages:        Output from pdf_parser.parse_pdf()
        chunk_size:   Target chunk size in characters
        chunk_overlap: Overlap between consecutive chunks in characters

    Returns:
        List of chunk dicts:
        {
            "content": str,
            "page": int,
            "section": str | None,
            "is_high_priority": bool,
            "source_file": str,
            "chunk_index": int,
        }
    """
    chunks = []
    chunk_index = 0

    for page in pages:
        content = page["content"]
        section = page.get("section")
        is_high_priority = page.get("is_high_priority", False)
        page_num = page["page"]
        source_file = page["source_file"]

        # Use smaller chunks for high-priority sections
        effective_chunk_size = HIGH_PRIORITY_CHUNK_SIZE if is_high_priority else chunk_size

        # If page is short enough, keep it as one chunk
        if len(content) <= effective_chunk_size:
            chunks.append({
                "content": content,
                "page": page_num,
                "section": section,
                "is_high_priority": is_high_priority,
                "source_file": source_file,
                "chunk_index": chunk_index,
            })
            chunk_index += 1
            continue

        # Split longer pages into overlapping chunks
        sentences = split_into_sentences(content)
        current_chunk = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            if current_len + sentence_len > effective_chunk_size and current_chunk:
                # Emit current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "content": chunk_text,
                    "page": page_num,
                    "section": section,
                    "is_high_priority": is_high_priority,
                    "source_file": source_file,
                    "chunk_index": chunk_index,
                })
                chunk_index += 1

                # Overlap: keep last N chars worth of sentences
                overlap_text = ""
                overlap_sentences = []
                for s in reversed(current_chunk):
                    if len(overlap_text) + len(s) <= chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_text += s
                    else:
                        break

                current_chunk = overlap_sentences
                current_len = sum(len(s) for s in current_chunk)

            current_chunk.append(sentence)
            current_len += sentence_len

        # Emit remaining sentences
        if current_chunk:
            chunks.append({
                "content": " ".join(current_chunk),
                "page": page_num,
                "section": section,
                "is_high_priority": is_high_priority,
                "source_file": source_file,
                "chunk_index": chunk_index,
            })
            chunk_index += 1

    logger.info(f"Chunking complete: {len(pages)} pages → {len(chunks)} chunks")
    high_priority_count = sum(1 for c in chunks if c["is_high_priority"])
    logger.info(f"  High-priority chunks: {high_priority_count} / {len(chunks)}")

    return chunks
