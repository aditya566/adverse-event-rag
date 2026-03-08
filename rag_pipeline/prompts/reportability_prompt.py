"""
rag_pipeline/prompts/reportability_prompt.py

Builds the LLM prompt for determining whether an adverse event is reportable,
given retrieved pharma documentation chunks.
"""


def build_reportability_prompt(
    chart_note: str,
    event_data: dict,
    retrieved_chunks: list[dict],
    drug_name: str,
) -> str:
    """
    Builds a structured prompt asking the LLM to determine reportability.
    The LLM must cite specific sections from the pharma documentation.
    """

    chunks_text = "\n\n".join([
        f"[Source: {chunk.get('source_doc', 'Unknown')} | "
        f"Section: {chunk.get('section', 'Unknown')} | "
        f"Page: {chunk.get('page', '?')}]\n{chunk['content']}"
        for chunk in retrieved_chunks
    ])

    return f"""You are a pharmacovigilance expert assistant helping a health insurance company determine 
whether an adverse drug event must be reported to the pharmaceutical manufacturer.

You must base your decision ONLY on the provided pharmaceutical documentation excerpts below.
Do NOT use general medical knowledge to override what the documentation says.

## Drug Name
{drug_name}

## Adverse Event Summary (extracted from patient call)
{event_data}

## Relevant Pharmaceutical Documentation
{chunks_text}

## Your Task
Based strictly on the pharmaceutical documentation above, determine:
1. Is this adverse event REPORTABLE to the manufacturer?
2. What specific section(s) of the documentation support your decision?
3. What type of report is required, if any?

## Output Format (respond ONLY with valid JSON, no preamble)
{{
    "is_reportable": "YES | NO | NEEDS_REVIEW",
    "confidence_score": <float between 0.0 and 1.0>,
    "reasoning": "<clear explanation citing specific doc sections>",
    "supporting_doc_sections": ["<Section X.X - Title>", ...],
    "recommended_report_type": "<e.g. 15-day Alert Report, Periodic Report, or null>",
    "key_criteria_matched": ["<criterion from doc that was matched>", ...]
}}

Rules:
- Use "NEEDS_REVIEW" if the documentation is ambiguous or your confidence is below 0.75
- Always cite the specific section name/number from the documentation in your reasoning
- If the event clearly does NOT match any reportable criteria in the docs, return "NO"
- If the event clearly DOES match reportable criteria, return "YES"
"""


def build_extraction_prompt(chart_note: str) -> str:
    """
    Builds the prompt for extracting structured adverse event data from chart notes.
    """
    return f"""You are a clinical data extraction assistant. Extract structured adverse event 
information from the following patient call chart note.

## Chart Note
{chart_note}

## Output Format (respond ONLY with valid JSON, no preamble)
{{
    "drug_name": "<name of drug mentioned>",
    "patient_age": "<age if mentioned, else null>",
    "patient_gender": "<gender if mentioned, else null>",
    "reported_symptoms": ["<symptom 1>", "<symptom 2>", ...],
    "onset_date": "<date symptoms started, else null>",
    "duration": "<how long symptoms lasted, else null>",
    "severity": "Serious | Non-Serious | Unknown",
    "outcome": "<e.g. hospitalized, recovered, ongoing, null>",
    "reporter_type": "<patient | physician | caregiver | null>",
    "concomitant_medications": ["<other med 1>", ...]
}}

Rules:
- Extract only what is explicitly stated in the notes
- Use null for any field not mentioned
- "Serious" severity = hospitalization, disability, life-threatening, or death
"""
