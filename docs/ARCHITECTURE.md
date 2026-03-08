# System Architecture

## Data Flow

```
1. PATIENT CALL
   └─> Advocate documents chart notes in CRM

2. INGESTION TRIGGER (manual or automated CRM export)
   └─> chart note pulled into pipeline

3. PII REDACTION LAYER
   └─> presidio strips patient identifiers before LLM call

4. EVENT EXTRACTION (LLM Call #1)
   └─> Structured JSON: drug name, symptoms, severity, onset date

5. KNOWLEDGE BASE QUERY (RAG)
   └─> Query: "[symptoms] + [drug name] + reportability criteria"
   └─> Returns: top-5 relevant chunks from pharma documentation
       with section name, page number, and source doc metadata

6. REPORTABILITY CLASSIFICATION (LLM Call #2)
   └─> Input: extracted event + retrieved pharma doc chunks
   └─> Output: YES / NO / NEEDS_REVIEW + confidence + reasoning

7. HUMAN REVIEW QUEUE
   ├─> Confidence ≥ 0.90     → Shown to advocate for quick confirmation
   ├─> Confidence 0.60–0.89  → Shown to advocate for full review  
   └─> Confidence < 0.60     → Escalated to senior pharmacovigilance reviewer

8. REPORT GENERATION
   └─> If decision = YES (after human confirmation):
       Auto-draft MedWatch 3500A or E2B R3 XML

9. DAILY BATCH SUBMISSION
   └─> Scheduler collects all approved reports
   └─> Submits to pharma manufacturers via SFTP/API/email
   └─> Stores submission audit trail
```

## Component Responsibilities

| Component | Responsibility |
|---|---|
| `ingestion/` | Parse pharma PDFs/DOCX, chunk, embed, store in vector DB |
| `knowledge_base/` | Vector store management, embedding model wrapper |
| `rag_pipeline/` | Retrieve relevant chunks, build LLM prompts |
| `event_classifier/` | Orchestrate extraction → retrieval → classification |
| `human_review/` | FastAPI for advocate review UI, record decisions |
| `report_generator/` | Build MedWatch or E2B XML from confirmed events |
| `scheduler/` | Daily batch job, submission tracking |

## Confidence Score Thresholds

| Confidence | Action |
|---|---|
| ≥ 0.90 | Auto-route to standard review queue |
| 0.60 – 0.89 | Route to full manual review |
| < 0.60 | Escalate to senior reviewer |

These thresholds are configurable in `.env`.

## HIPAA Compliance Notes
- PII redacted before ANY LLM API call
- All audit logs retained 7 years
- Azure OpenAI or Anthropic (with signed BAA) recommended for cloud deployment
- On-premise: use self-hosted Llama 3 / Mistral via Ollama
