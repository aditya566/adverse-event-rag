"""
event_classifier/classifier.py

Core orchestrator: takes a chart note, runs RAG over pharma docs,
returns a structured reportability decision.
"""

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from rag_pipeline.retrieval.retriever import retrieve_relevant_chunks
from rag_pipeline.prompts.reportability_prompt import build_reportability_prompt
from rag_pipeline.prompts.extraction_prompt import build_extraction_prompt
from event_classifier.schemas import (
    AdverseEventInput,
    ClassifierOutput,
    ReportabilityDecision,
)
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


def extract_event_data(chart_note: str, llm_client) -> dict:
    """
    Step 1: Use LLM to extract structured adverse event data from free-text chart notes.
    Pulls: drug name, symptoms, onset date, patient demographics, severity indicators.
    """
    prompt = build_extraction_prompt(chart_note)
    response = llm_client.complete(prompt)
    
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        logger.error("Failed to parse extraction response as JSON")
        raise ValueError("LLM did not return valid JSON for event extraction")


def classify_reportability(
    chart_note: str,
    drug_name: str,
    llm_client,
    vector_store,
    case_id: Optional[str] = None,
) -> ClassifierOutput:
    """
    Main classification function.
    
    Args:
        chart_note: Raw text from advocate's chart notes (PII already redacted)
        drug_name:  Name of the drug in question (used to filter vector store)
        llm_client: Initialized LLM client (OpenAI / Anthropic)
        vector_store: Initialized vector store client
        case_id:    Optional case identifier for audit logging

    Returns:
        ClassifierOutput with decision, confidence, reasoning, and citations
    """
    logger.info(f"Starting classification for case_id={case_id}, drug={drug_name}")

    # ── Step 1: Extract structured event data from chart note ─────────────────
    event_data = extract_event_data(chart_note, llm_client)
    logger.info(f"Extracted event data: {event_data}")

    # ── Step 2: Retrieve relevant pharma doc sections via RAG ─────────────────
    query = f"adverse events reporting requirements {drug_name} {' '.join(event_data.get('reported_symptoms', []))}"
    retrieved_chunks = retrieve_relevant_chunks(
        query=query,
        vector_store=vector_store,
        drug_name=drug_name,
        top_k=settings.RETRIEVER_TOP_K,
    )
    logger.info(f"Retrieved {len(retrieved_chunks)} chunks from knowledge base")

    if not retrieved_chunks:
        logger.warning(f"No pharma doc chunks found for drug: {drug_name}")
        return ClassifierOutput(
            case_id=case_id,
            decision=ReportabilityDecision.NEEDS_REVIEW,
            confidence_score=0.0,
            reasoning="No matching pharma documentation found in knowledge base. Manual review required.",
            supporting_doc_sections=[],
            extracted_event_data=event_data,
            retrieved_chunks=[],
            timestamp=datetime.utcnow().isoformat(),
        )

    # ── Step 3: Build prompt and call LLM ────────────────────────────────────
    prompt = build_reportability_prompt(
        chart_note=chart_note,
        event_data=event_data,
        retrieved_chunks=retrieved_chunks,
        drug_name=drug_name,
    )

    raw_response = llm_client.complete(prompt)

    # ── Step 4: Parse structured output ──────────────────────────────────────
    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM reportability response")
        raise ValueError("LLM did not return valid JSON for reportability decision")

    output = ClassifierOutput(
        case_id=case_id,
        decision=ReportabilityDecision(parsed["is_reportable"]),
        confidence_score=parsed["confidence_score"],
        reasoning=parsed["reasoning"],
        supporting_doc_sections=parsed.get("supporting_doc_sections", []),
        recommended_report_type=parsed.get("recommended_report_type"),
        extracted_event_data=event_data,
        retrieved_chunks=[c["content"] for c in retrieved_chunks],
        timestamp=datetime.utcnow().isoformat(),
    )

    logger.info(
        f"Classification complete: {output.decision} "
        f"(confidence={output.confidence_score:.2f}) for case_id={case_id}"
    )

    return output
