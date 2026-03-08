# HIPAA Compliance Notes

## Overview
This system processes Protected Health Information (PHI) and must comply with HIPAA
Security and Privacy Rules (45 CFR Parts 160 and 164).

## PII De-identification (Before LLM Calls)

**All patient chart notes must be de-identified before being sent to any external LLM API.**

The `ingestion` pipeline includes a de-identification step using Microsoft Presidio:

```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

results = analyzer.analyze(text=chart_note, language="en")
redacted = anonymizer.anonymize(text=chart_note, analyzer_results=results)
```

Entities redacted: NAME, DATE_OF_BIRTH, PHONE_NUMBER, EMAIL_ADDRESS,
US_SSN, MEDICAL_RECORD_NUMBER, US_PASSPORT, LOCATION (street-level).

**Retained for clinical context:** Age ranges, gender, symptom dates (month/year),
drug names, severity indicators.

## LLM Provider Selection (Standalone Tool)

For a standalone internal tool, choose ONE of these HIPAA-eligible providers:

| Provider | HIPAA BAA | Notes |
|---|---|---|
| **Azure OpenAI** | ✅ Available | Recommended. Data stays in Azure tenant. |
| **Anthropic Claude** | ✅ Available (Enterprise) | Requires Enterprise plan + signed BAA. |
| **OpenAI** | ✅ Available (Enterprise) | Requires ChatGPT Enterprise or API Enterprise. |
| **Local Llama 3 (Ollama)** | N/A (no data leaves) | Fully air-gapped; lower quality. |

> ⚠️ **Never use consumer-tier API keys for production.** Sign a BAA with your chosen provider.

## Data Storage

- **ChromaDB** stores only embeddings and de-identified text chunks — no PHI
- **Case records** (with PHI) stay in your existing CRM — never copied to this system's DB
- **Generated reports** (MedWatch PDFs) contain de-identified patient identifiers only
- **Audit logs** must be retained for **7 years** per 21 CFR Part 314 and HIPAA

## Access Controls

- Limit system access to credentialed patient care advocates only
- Use role-based access: Advocate (review/approve), Admin (ingest docs), Auditor (read logs)
- All advocate actions logged with timestamp, user ID, and decision rationale

## Audit Trail

Every classification and review action is logged:
```
{timestamp} | case_id | advocate_id | ai_decision | advocate_decision | override_reason
```

Logs written to `./logs/audit.log` — configure log rotation and 7-year retention.

## Regulatory References

- HIPAA Privacy Rule: 45 CFR Part 164, Subpart E
- HIPAA Security Rule: 45 CFR Part 164, Subpart C
- FDA Adverse Event Reporting: 21 CFR Part 314.81 (NDA post-marketing reports)
- MedWatch 3500A: https://www.fda.gov/safety/medwatch
