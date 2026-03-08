"""
knowledge_base/embeddings/embedder.py

Wraps embedding models. Supports:
  - OpenAI text-embedding-3-small (default, best quality for standalone tool)
  - sentence-transformers (fully local, no API key required)

Switch via EMBEDDING_MODEL in .env
"""

import logging
from config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIEmbedder:
    def __init__(self, model: str, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model
        logger.info(f"Using OpenAI embedder: {model}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of document chunks."""
        # Batch in groups of 100 to respect API limits
        all_embeddings = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.embeddings.create(input=batch, model=self.model)
            all_embeddings.extend([r.embedding for r in response.data])
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string."""
        response = self.client.embeddings.create(input=[query], model=self.model)
        return response.data[0].embedding


class LocalEmbedder:
    """Uses sentence-transformers for fully offline embedding — no API key needed."""

    def __init__(self, model: str):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model)
        logger.info(f"Using local sentence-transformer embedder: {model}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(texts, show_progress_bar=True, convert_to_list=True)
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        return self.model.encode([query], convert_to_list=True)[0]


# ── Singleton ──────────────────────────────────────────────────────────────────
_embedder_instance = None


def get_embedder():
    global _embedder_instance
    if _embedder_instance is not None:
        return _embedder_instance

    model_name = settings.EMBEDDING_MODEL

    if "text-embedding" in model_name:
        # OpenAI embedding model
        _embedder_instance = OpenAIEmbedder(
            model=model_name,
            api_key=settings.OPENAI_API_KEY,
        )
    else:
        # Local sentence-transformers model
        # e.g. "sentence-transformers/all-mpnet-base-v2"
        _embedder_instance = LocalEmbedder(model=model_name)

    return _embedder_instance
