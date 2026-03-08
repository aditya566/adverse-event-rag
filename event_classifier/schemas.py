"""
event_classifier/schemas.py

Pydantic models for all inputs and outputs in the classification pipeline.
These enforce data contracts between modules.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class ReportabilityDecision(str, Enum):
    YES = "YES"               # Reportable — advocate should file report
    NO = "NO"                 # Not reportable — no action needed
    NEEDS_REVIEW = "NEEDS_REVIEW"  # Low confidence — escalate to senior advocate


class Severity(str, Enum):
    SERIOUS = "Serious"
    NON_SERIOUS = "Non-Serious"
    UNKNOWN = "Unknown"


class ExtractedEventData(BaseModel):
    drug_name: str
    patient_age: Optional[str] = None
    patient_gender: Optional[str] = None
    reported_symptoms: list[str] = []
    onset_date: Optional[str] = None
    duration: Optional[str] = None
    severity: Severity = Severity.UNKNOWN
    outcome: Optional[str] = None          # e.g. "hospitalized", "recovered"
    reporter_type: Optional[str] = None    # e.g. "patient", "physician"
    concomitant_medications: list[str] = []


class AdverseEventInput(BaseModel):
    """Input to the classifier — sourced from CRM chart notes."""
    case_id: str
    chart_note_text: str = Field(..., description="Raw advocate chart note (PII redacted)")
    drug_name: str
    call_date: str
    advocate_id: Optional[str] = None


class ClassifierOutput(BaseModel):
    """Output of the classification pipeline — reviewed by advocate."""
    case_id: Optional[str]
    decision: ReportabilityDecision
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    supporting_doc_sections: list[str]
    recommended_report_type: Optional[str] = None  # e.g. "15-day Alert Report"
    extracted_event_data: dict[str, Any]
    retrieved_chunks: list[str]
    timestamp: str

    @property
    def requires_human_review(self) -> bool:
        """Returns True if the advocate must manually review this case."""
        from config.settings import settings
        return (
            self.decision == ReportabilityDecision.NEEDS_REVIEW
            or self.confidence_score < settings.CONFIDENCE_THRESHOLD_AUTO
        )


class HumanReviewDecision(BaseModel):
    """Recorded when an advocate accepts, overrides, or escalates an AI decision."""
    case_id: str
    ai_decision: ReportabilityDecision
    advocate_decision: ReportabilityDecision
    overridden: bool
    override_reason: Optional[str] = None
    advocate_id: str
    review_timestamp: str
