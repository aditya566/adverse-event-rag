# Quick Start Guide

## Prerequisites
- Python 3.11+
- Anthropic API key (with HIPAA BAA signed for production)

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_lg   # for PII redaction
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY at minimum
```

### 3. Create required directories
```bash
mkdir -p data/crm_intake data/crm_processed data/approved_cases
mkdir -p reports/output/submission_queue reports/output/archive
mkdir -p knowledge_base/vector_store/chroma_db
mkdir -p logs
```

---

## Admin: Adding Pharma Documentation

When a new drug needs to be covered, an admin runs:
```bash
# Upload and index a drug's prescribing information PDF
python scripts/admin_upload.py upload \
  --file /path/to/lipitor_prescribing_info.pdf \
  --drug "Lipitor" \
  --manufacturer "Pfizer" \
  --version "2024-03"

# Verify it's indexed
python scripts/admin_upload.py list

# Update when manufacturer releases new documentation
python scripts/admin_upload.py upload \
  --file /path/to/lipitor_pi_v2.pdf \
  --drug "Lipitor" \
  --manufacturer "Pfizer" \
  --version "2024-09" \
  --replace
```

---

## Advocate Workflow: Processing Chart Notes

### Step 1: Export chart notes from CRM
After documenting a patient call, export the note as a `.txt` file with this header format:
```
Date: 2024-03-15
Case ID: CASE-2024-0891
Advocate ID: ADV-0042
Drug: Lipitor

PATIENT CALL SUMMARY
────────────────────
Patient called to report...
```
Drop the file into: `data/crm_intake/`

### Step 2: Run the pipeline
```bash
python scripts/run_pipeline.py
```
This will:
- Redact PII from all notes
- Run RAG classification against pharma docs
- Output results to `data/review_queue/`

### Step 3: Review in the dashboard
Open `human_review/ui_mockup/review_dashboard.html` in a browser.
Each case shows:
- AI decision (Reportable / Not Reportable / Needs Review)
- Confidence score
- Specific pharma doc sections cited
- Extracted event data

Advocate choices: **Accept** | **Override** (with reason) | **Escalate**

### Step 4: Report generation (if reportable)
After advocate accepts a reportable case, generate the MedWatch 3500A PDF:
```bash
python -c "
from report_generator.templates.medwatch_3500a import generate_medwatch_3500a
import json
with open('data/approved_cases/CASE-2024-0891.json') as f:
    case = json.load(f)
generate_medwatch_3500a(
    classifier_output=case['classifier_output'],
    case_id=case['case_id'],
    advocate_id=case['advocate_id'],
    call_date=case['call_date'],
    output_path='reports/output/CASE-2024-0891_MedWatch.pdf'
)
"
```

### Step 5: Daily batch (automated)
The scheduler runs at 5:00 PM ET and batches all approved reports:
```bash
python scheduler/batch_runner.py   # manual trigger
# OR
python -c "from scheduler.batch_runner import start_scheduler; start_scheduler()"   # cron mode
```
Generated PDFs land in `reports/output/outbox/` for submission to manufacturers.

---

## Testing the System (without real pharma docs)

```bash
# 1. Create a minimal test pharma doc PDF
# (any PDF with text mentioning adverse events / warnings)

# 2. Index it
python scripts/admin_upload.py upload \
  --file test_drug_info.pdf --drug "TestDrug" \
  --manufacturer "TestCo" --version "test"

# 3. Drop the sample chart note
cp sample_data/chart_notes/sample_chart_note_001.txt data/crm_intake/

# 4. Edit the note to say Drug: TestDrug

# 5. Run pipeline
python scripts/run_pipeline.py --dry-run
```

---

## File Reference

| Script | Purpose |
|--------|---------|
| `scripts/admin_upload.py` | Admin: add/update/remove pharma PDFs |
| `scripts/run_pipeline.py` | Advocates: process CRM note exports |
| `scripts/ingest_docs.py` | Lower-level doc ingestion (called by admin_upload) |
| `scripts/run_classifier.py` | Classify a single file (testing/debugging) |
| `scheduler/batch_runner.py` | Daily report batch job |
| `human_review/ui_mockup/review_dashboard.html` | Advocate review UI |
