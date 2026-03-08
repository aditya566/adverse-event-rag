# Adverse Event Reporting Automation (RAG-Based)

## Overview
This system automates the process of determining whether patient-reported adverse drug events are reportable to pharma manufacturers, using Retrieval-Augmented Generation (RAG) over pharma documentation.

## Architecture

```
Patient Call → Chart Notes (CRM) → [Ingestion] → RAG Pipeline → Classifier → Human Review → Report Generator → Pharma Submission
                                         ↑
                              Pharma Docs Knowledge Base
```

---

## Project Plan

### Phase 1 — Knowledge Base Construction (Weeks 1–3)
- Ingest pharma manufacturer PDFs/DOCX documentation
- Chunk, embed, and store in vector database (ChromaDB or Pinecone)
- Build document versioning so updated drug docs re-trigger re-indexing

### Phase 2 — RAG Pipeline + Classifier (Weeks 4–6)
- Extract structured adverse event data from chart notes
- Query vector store for relevant drug documentation sections
- LLM prompt determines: IS_REPORTABLE (Yes/No/Needs Review) + reasoning + citations from pharma doc

### Phase 3 — Human-in-the-Loop Review UI (Weeks 7–9)
- Lightweight review interface for advocates
- Shows: patient summary, AI decision, supporting doc excerpts, confidence score
- Advocate can Accept / Override / Escalate

### Phase 4 — Report Generation + Scheduling (Weeks 10–12)
- Auto-draft report in required format (MedWatch 3500A or E2B R3 XML)
- Scheduler batches daily submissions per pharma company
- Audit trail and logging for regulatory compliance

---

## Folder Structure

```
adverse-event-rag/
│
├── config/                         # Environment settings, API keys, model config
│   ├── settings.py
│   └── logging_config.yaml
│
├── ingestion/                      # Step 1: Load + parse pharma docs
│   ├── parsers/
│   │   ├── pdf_parser.py           # Extract text from PDFs
│   │   ├── docx_parser.py          # Extract text from Word docs
│   │   └── chunker.py              # Semantic chunking logic
│   └── loaders/
│       ├── doc_loader.py           # Orchestrates parsing + chunking
│       └── doc_versioner.py        # Tracks doc versions, triggers re-index
│
├── knowledge_base/                 # Step 2: Vector store management
│   ├── embeddings/
│   │   └── embedder.py             # Wraps embedding model (OpenAI/HuggingFace)
│   └── vector_store/
│       ├── store_manager.py        # CRUD for ChromaDB / Pinecone
│       └── index_builder.py        # Full re-index script
│
├── rag_pipeline/                   # Step 3: Core RAG logic
│   ├── retrieval/
│   │   ├── retriever.py            # Query vector store, return top-k chunks
│   │   └── reranker.py             # Optional: cross-encoder reranking
│   └── prompts/
│       ├── reportability_prompt.py # Main LLM prompt template
│       └── extraction_prompt.py    # Extract structured data from chart notes
│
├── event_classifier/               # Step 4: Classify reportability
│   ├── classifier.py               # Orchestrates RAG → LLM → structured output
│   └── schemas.py                  # Pydantic models for input/output
│
├── report_generator/               # Step 5: Generate submission reports
│   ├── templates/
│   │   ├── medwatch_3500a.py       # MedWatch 3500A report builder
│   │   └── e2b_r3_xml.py           # ICH E2B R3 XML report builder
│   └── formatters/
│       └── report_formatter.py     # Formats final report for submission
│
├── human_review/                   # Step 6: HITL review layer
│   ├── api/
│   │   └── review_api.py           # FastAPI endpoints for review UI
│   └── ui_mockup/
│       └── review_dashboard.html   # Simple HTML mockup of review interface
│
├── scheduler/                      # Step 7: Daily batch submission
│   ├── batch_runner.py             # Collects daily events, triggers reports
│   └── submission_client.py        # Sends report files to pharma companies
│
├── sample_data/
│   ├── pharma_docs/                # Place sample drug documentation PDFs here
│   └── chart_notes/                # Place sample chart note text files here
│
├── scripts/
│   ├── ingest_docs.py              # CLI: run full ingestion pipeline
│   ├── run_classifier.py           # CLI: run classifier on a chart note
│   └── reindex_knowledge_base.py   # CLI: force re-index of all pharma docs
│
├── tests/
│   ├── unit/
│   │   ├── test_parser.py
│   │   ├── test_classifier.py
│   │   └── test_report_generator.py
│   └── integration/
│       └── test_end_to_end.py
│
├── docs/
│   ├── ARCHITECTURE.md             # Detailed system architecture
│   ├── DATA_FLOW.md                # Data flow diagrams
│   └── HIPAA_COMPLIANCE.md        # Compliance notes
│
├── logs/                           # Runtime logs (gitignored)
├── .env.example                    # Environment variable template
└── requirements.txt                # Python dependencies
```

---

## Key Design Decisions

### RAG Strategy
- **Chunking**: Semantic chunking preferred over fixed-size; pharma docs have structured sections (adverse reactions, contraindications, etc.) that should stay intact
- **Metadata**: Each chunk tagged with drug name, doc version, section type → enables filtered retrieval
- **Top-k retrieval**: Return top 5 most relevant chunks, include source section + page reference for advocate traceability

### LLM Output Schema
```json
{
  "is_reportable": "YES | NO | NEEDS_REVIEW",
  "confidence_score": 0.92,
  "reasoning": "The patient reported rash and fever within 48hrs of starting Drug X. Section 6.1 of the prescribing information lists these as serious adverse reactions requiring mandatory reporting.",
  "supporting_doc_sections": ["Section 6.1 - Adverse Reactions", "Section 5.3 - Warnings"],
  "recommended_report_type": "15-day Alert Report",
  "extracted_event_data": {
    "drug_name": "...",
    "patient_age": "...",
    "reported_symptoms": [...],
    "onset_date": "...",
    "severity": "Serious | Non-Serious"
  }
}
```

### HIPAA Considerations
- All PII must be masked before sending to external LLM APIs (de-identification layer)
- Prefer Azure OpenAI or Anthropic (with BAA) for cloud deployments
- On-prem deployments can use self-hosted models (Llama 3, Mistral)
- Audit logs retained per regulatory requirements

---

## Open Configuration Questions
_(To be finalized based on stakeholder input)_

- [ ] Pharma doc format: PDF / DOCX / XML / Mix?
- [ ] Deployment: Cloud (AWS/Azure) or On-premise?
- [ ] LLM provider: OpenAI / Anthropic / Azure OpenAI?
- [ ] Report format: MedWatch 3500A / E2B R3 / Custom?
- [ ] CRM integration: How are chart notes exported?
- [ ] Submission method: SFTP / API / Email to pharma?
