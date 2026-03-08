"""
knowledge_base/vector_store/store_manager.py

Manages ChromaDB as the local vector store.
ChromaDB is chosen for the standalone internal tool deployment —
no cloud account needed, data stays on-premise.
"""

import logging
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from config.settings import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "pharma_docs"


class VectorStoreManager:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # Cosine similarity for embeddings
        )
        logger.info(f"VectorStore ready. Collection '{COLLECTION_NAME}' has {self.collection.count()} documents.")

    def document_exists(self, file_hash: str) -> bool:
        """Check if a document with this hash has already been indexed."""
        results = self.collection.get(where={"file_hash": file_hash}, limit=1)
        return len(results["ids"]) > 0

    def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """Add a batch of chunks to the vector store."""
        import uuid
        ids = [str(uuid.uuid4()) for _ in texts]
        self.collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(f"Added {len(texts)} chunks to vector store")

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        drug_name_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Query the vector store for relevant chunks.

        Args:
            query_embedding:   Embedding vector for the query
            n_results:         Number of results to return
            drug_name_filter:  If provided, restrict to this drug's documentation

        Returns:
            List of chunk dicts with content, metadata, and distance score
        """
        where = {}
        if drug_name_filter:
            where["drug_name"] = drug_name_filter.lower()

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where if where else None,
            include=["documents", "metadatas", "distances"],
        )

        chunks = []
        for i, doc in enumerate(results["documents"][0]):
            metadata = results["metadatas"][0][i]
            distance = results["distances"][0][i]
            chunks.append({
                "content": doc,
                "section": metadata.get("section", "Unknown"),
                "source_doc": metadata.get("source_doc", "Unknown"),
                "page": metadata.get("page", -1),
                "drug_name": metadata.get("drug_name", ""),
                "is_high_priority": metadata.get("is_high_priority", False),
                "similarity_score": 1 - distance,  # Convert distance to similarity
            })

        # Sort by high-priority first, then similarity
        chunks.sort(key=lambda x: (not x["is_high_priority"], -x["similarity_score"]))
        return chunks

    def delete_by_drug(self, drug_name: str) -> int:
        """Remove all chunks for a given drug (e.g., to re-index updated docs)."""
        results = self.collection.get(where={"drug_name": drug_name.lower()})
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            logger.info(f"Deleted {len(results['ids'])} chunks for drug: {drug_name}")
            return len(results["ids"])
        return 0

    def list_indexed_drugs(self) -> list[str]:
        """Return list of all drugs currently in the knowledge base."""
        results = self.collection.get(include=["metadatas"])
        drugs = set(m.get("drug_name", "") for m in results["metadatas"])
        return sorted(d for d in drugs if d)

    @property
    def total_chunks(self) -> int:
        return self.collection.count()


# Singleton
_store_instance = None

def get_vector_store() -> VectorStoreManager:
    global _store_instance
    if _store_instance is None:
        _store_instance = VectorStoreManager()
    return _store_instance
