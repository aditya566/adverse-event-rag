"""
config/settings.py

Confirmed stack:
  - LLM:          Anthropic Claude (claude-sonnet-4-6)
  - Vector store: ChromaDB (local, standalone)
  - Doc format:   PDF only
  - Report:       MedWatch 3500A
  - Chart notes:  CRM free-text export (.txt files)
  - Doc updates:  Admin manual upload via CLI
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent


class Settings:
    # LLM - Anthropic Claude
    LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Embeddings - defaults to fully local (no extra API key needed)
    # Options: "sentence-transformers/all-mpnet-base-v2" (local)
    #          "text-embedding-3-small" (OpenAI, needs OPENAI_API_KEY)
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")  # only needed if using OpenAI embeddings

    # Vector Store: ChromaDB - persists locally, no cloud account needed
    CHROMA_PERSIST_DIR: str = os.getenv(
        "CHROMA_PERSIST_DIR",
        str(BASE_DIR / "knowledge_base" / "vector_store" / "chroma_db"),
    )

    # PDF Ingestion - admin drops new PDFs here, runs ingest_docs.py
    PHARMA_DOCS_DIR: str = os.getenv(
        "PHARMA_DOCS_DIR", str(BASE_DIR / "sample_data" / "pharma_docs")
    )
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "100"))

    # CRM Chart Note Intake - advocates export free-text notes as .txt here
    CHART_NOTES_INTAKE_DIR: str = os.getenv(
        "CHART_NOTES_INTAKE_DIR", str(BASE_DIR / "data" / "crm_intake")
    )
    CHART_NOTES_PROCESSED_DIR: str = os.getenv(
        "CHART_NOTES_PROCESSED_DIR", str(BASE_DIR / "data" / "crm_processed")
    )

    # Classifier Thresholds
    RETRIEVER_TOP_K: int = int(os.getenv("RETRIEVER_TOP_K", "5"))
    CONFIDENCE_THRESHOLD_AUTO: float = float(os.getenv("CONFIDENCE_THRESHOLD_AUTO", "0.90"))
    CONFIDENCE_THRESHOLD_ESCALATE: float = float(os.getenv("CONFIDENCE_THRESHOLD_ESCALATE", "0.60"))

    # HIPAA - always redact PII before LLM calls
    ENABLE_PII_REDACTION: bool = os.getenv("ENABLE_PII_REDACTION", "true").lower() == "true"

    # Report Generation - MedWatch 3500A
    REPORT_OUTPUT_DIR: str = os.getenv(
        "REPORT_OUTPUT_DIR", str(BASE_DIR / "reports" / "output")
    )

    # Daily Batch Scheduler
    BATCH_SUBMISSION_TIME: str = os.getenv("BATCH_SUBMISSION_TIME", "17:00")
    BATCH_TIMEZONE: str = os.getenv("BATCH_TIMEZONE", "America/New_York")

    # Audit Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = str(BASE_DIR / "logs")
    AUDIT_LOG_RETENTION_DAYS: int = int(os.getenv("AUDIT_LOG_RETENTION_DAYS", "2555"))

    # Company Info (printed on MedWatch form)
    COMPANY_NAME: str = os.getenv("COMPANY_NAME", "[Insurance Company Name]")
    COMPANY_ADDRESS: str = os.getenv("COMPANY_ADDRESS", "[Address]")
    COMPANY_PHONE: str = os.getenv("COMPANY_PHONE", "[Phone]")


settings = Settings()


def get_llm_client():
    """
    Returns an initialized Anthropic Claude wrapper.
    temperature=0 ensures deterministic, auditable classification decisions.
    """
    import anthropic

    _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    class ClaudeClient:
        def complete(self, prompt: str, system: str = None) -> str:
            kwargs = dict(
                model=settings.LLM_MODEL,
                max_tokens=2000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            if system:
                kwargs["system"] = system
            response = _client.messages.create(**kwargs)
            return response.content[0].text

    return ClaudeClient()


def get_vector_store():
    """Returns the singleton ChromaDB vector store manager."""
    from knowledge_base.vector_store.store_manager import get_vector_store as _get
    return _get()
