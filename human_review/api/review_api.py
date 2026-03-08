"""
human_review/api/review_api.py

FastAPI endpoints for the advocate review interface.
Advocates see AI decisions and can Accept / Override / Escalate.
"""

from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from event_classifier.schemas import (
    AdverseEventInput,
    ClassifierOutput,
    HumanReviewDecision,
    ReportabilityDecision,
)
from event_classifier.classifier import classify_reportability
from config.settings import settings

app = FastAPI(
    title="Adverse Event Reportability Review API",
    description="Human-in-the-loop review layer for AI-generated reportability decisions",
    version="1.0.0",
)


class ReviewRequest(BaseModel):
    case_id: str
    chart_note_text: str
    drug_name: str
    call_date: str
    advocate_id: Optional[str] = None


class AdvocateReviewInput(BaseModel):
    case_id: str
    ai_decision: ReportabilityDecision
    advocate_decision: ReportabilityDecision
    override_reason: Optional[str] = None
    advocate_id: str


@app.post("/classify", response_model=ClassifierOutput)
async def classify_event(request: ReviewRequest):
    """
    Run the RAG classifier on a chart note and return the AI decision.
    This is called when an advocate opens a case for review.
    """
    # NOTE: In production, initialize llm_client and vector_store
    # from dependency injection or app startup events
    try:
        from config.settings import get_llm_client, get_vector_store
        llm_client = get_llm_client()
        vector_store = get_vector_store()

        output = classify_reportability(
            chart_note=request.chart_note_text,
            drug_name=request.drug_name,
            llm_client=llm_client,
            vector_store=vector_store,
            case_id=request.case_id,
        )
        return output
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/review/submit", response_model=HumanReviewDecision)
async def submit_review(review: AdvocateReviewInput):
    """
    Submit advocate's final decision (Accept / Override / Escalate).
    Records whether the AI was overridden and why.
    Triggers report generation if decision = YES.
    """
    overridden = review.ai_decision != review.advocate_decision

    if overridden and not review.override_reason:
        raise HTTPException(
            status_code=400,
            detail="override_reason is required when overriding the AI decision"
        )

    decision_record = HumanReviewDecision(
        case_id=review.case_id,
        ai_decision=review.ai_decision,
        advocate_decision=review.advocate_decision,
        overridden=overridden,
        override_reason=review.override_reason,
        advocate_id=review.advocate_id,
        review_timestamp=datetime.utcnow().isoformat(),
    )

    # TODO: Persist to database
    # TODO: If advocate_decision == YES → trigger report_generator

    return decision_record


@app.get("/cases/pending")
async def get_pending_cases():
    """
    Returns list of cases awaiting human review.
    In production, this pulls from your CRM or case management DB.
    """
    # TODO: Connect to case management database
    return {"pending_cases": [], "message": "Connect to case database in production"}


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
