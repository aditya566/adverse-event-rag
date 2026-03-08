"""
rag_pipeline/retrieval/retriever.py

Retrieves the most relevant pharma doc chunks for a given adverse event query.
Filters by drug name so only the relevant manufacturer's documentation is searched.
"""

import logging
from typing import Optional
from knowledge_base.vector_store.store_manager import get_vector_store
from knowledge_base.embeddings.embedder import get_embedder
from config.settings import settings

logger = logging.getLogger(__name__)


def retrieve_relevant_chunks(
    query: str,
    drug_name: str,
    top_k: Optional[int] = None,
    vector_store=None,
) -> list[dict]:
    """
    Retrieve the top-k most relevant pharma documentation chunks for the query.

    Args:
        query:        Natural language query (symptoms + drug + context)
        drug_name:    Drug name used to filter to the correct manufacturer's docs
        top_k:        Number of chunks to retrieve (defaults to settings.RETRIEVER_TOP_K)
        vector_store: Optional injected store (for testing); uses singleton if None

    Returns:
        List of chunk dicts ordered by relevance (high-priority sections first)
    """
    k = top_k or settings.RETRIEVER_TOP_K
    store = vector_store or get_vector_store()
    embedder = get_embedder()

    logger.info(f"Retrieving top-{k} chunks for drug='{drug_name}', query='{query[:80]}...'")

    # Build targeted query — emphasizes reportability criteria
    augmented_query = (
        f"adverse event reporting requirements {drug_name} "
        f"reportable serious adverse reaction warnings contraindications {query}"
    )

    query_embedding = embedder.embed_query(augmented_query)

    chunks = store.query(
        query_embedding=query_embedding,
        n_results=k,
        drug_name_filter=drug_name,
    )

    if not chunks:
        logger.warning(f"No chunks found for drug='{drug_name}'. "
                       f"Ensure the drug's documentation has been ingested.")

    for i, chunk in enumerate(chunks):
        logger.debug(
            f"  [{i+1}] Section: {chunk['section']} | "
            f"Page: {chunk['page']} | "
            f"Similarity: {chunk['similarity_score']:.3f} | "
            f"High-priority: {chunk['is_high_priority']}"
        )

    return chunks


def retrieve_for_multiple_symptoms(
    symptoms: list[str],
    drug_name: str,
    top_k: Optional[int] = None,
) -> list[dict]:
    """
    Run separate retrievals for each symptom and deduplicate results.
    Useful when a patient reports multiple distinct adverse events.
    """
    all_chunks = []
    seen_content = set()

    for symptom in symptoms:
        query = f"{symptom} adverse reaction {drug_name} reportable"
        chunks = retrieve_relevant_chunks(query=query, drug_name=drug_name, top_k=3)
        for chunk in chunks:
            content_hash = hash(chunk["content"][:100])
            if content_hash not in seen_content:
                seen_content.add(content_hash)
                all_chunks.append(chunk)

    # Re-sort deduplicated results
    all_chunks.sort(key=lambda x: (not x["is_high_priority"], -x["similarity_score"]))

    k = top_k or settings.RETRIEVER_TOP_K
    return all_chunks[:k]
