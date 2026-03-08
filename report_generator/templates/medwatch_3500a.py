"""
report_generator/templates/medwatch_3500a.py

Generates a MedWatch 3500A-style adverse event report as a PDF.
MedWatch 3500A is the FDA standard form for mandatory reporting of
serious adverse events by manufacturers, importers, and distributors.

Reference: https://www.fda.gov/safety/medwatch-fda-safety-information-and-adverse-event-reporting-program

Sections:
  A - Patient Information
  B - Adverse Event / Product Problem
  C - Suspect Product(s)
  D - Suspect Medical Device (N/A for drugs)
  E - Reporter Information
  F - For Use by User Facility / Importer (if applicable)
"""

from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER


# ── Color palette ─────────────────────────────────────────────────────────────
FDA_BLUE = colors.HexColor("#003366")
SECTION_BG = colors.HexColor("#E8EEF4")
FIELD_BG = colors.HexColor("#F9F9F9")
BORDER_GRAY = colors.HexColor("#CCCCCC")
ALERT_RED = colors.HexColor("#CC0000")


def get_styles():
    styles = getSampleStyleSheet()
    custom = {
        "FormTitle": ParagraphStyle(
            "FormTitle",
            parent=styles["Heading1"],
            fontSize=14,
            textColor=FDA_BLUE,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "FormSubtitle": ParagraphStyle(
            "FormSubtitle",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.gray,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "SectionHeader": ParagraphStyle(
            "SectionHeader",
            parent=styles["Heading2"],
            fontSize=10,
            textColor=colors.white,
            backColor=FDA_BLUE,
            leftIndent=6,
            spaceAfter=0,
            spaceBefore=8,
        ),
        "FieldLabel": ParagraphStyle(
            "FieldLabel",
            parent=styles["Normal"],
            fontSize=7,
            textColor=colors.gray,
            spaceAfter=1,
        ),
        "FieldValue": ParagraphStyle(
            "FieldValue",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.black,
            spaceAfter=6,
        ),
        "AIBox": ParagraphStyle(
            "AIBox",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#1a4a00"),
            backColor=colors.HexColor("#f0fff0"),
            leftIndent=6,
            rightIndent=6,
            spaceAfter=4,
        ),
        "Disclaimer": ParagraphStyle(
            "Disclaimer",
            parent=styles["Normal"],
            fontSize=7,
            textColor=colors.gray,
            alignment=TA_CENTER,
        ),
    }
    styles.add(custom["FormTitle"])
    styles.add(custom["FormSubtitle"])
    styles.add(custom["SectionHeader"])
    styles.add(custom["FieldLabel"])
    styles.add(custom["FieldValue"])
    styles.add(custom["AIBox"])
    styles.add(custom["Disclaimer"])
    return styles


def field_row(label: str, value: str, styles) -> list:
    """Returns a label + value pair as story elements."""
    return [
        Paragraph(label.upper(), styles["FieldLabel"]),
        Paragraph(str(value) if value else "—", styles["FieldValue"]),
    ]


def section_header(letter: str, title: str, styles) -> Paragraph:
    return Paragraph(
        f"&nbsp; SECTION {letter} — {title.upper()}",
        styles["SectionHeader"],
    )


def generate_medwatch_3500a(
    classifier_output: dict,
    case_id: str,
    advocate_id: str,
    call_date: str,
    output_path: str,
) -> str:
    """
    Generate a MedWatch 3500A-style PDF report.

    Args:
        classifier_output: dict from ClassifierOutput.model_dump()
        case_id:           Insurance case identifier
        advocate_id:       Reviewing advocate's ID
        call_date:         Date of patient call (YYYY-MM-DD)
        output_path:       Where to save the PDF

    Returns:
        Path to the generated PDF
    """
    event = classifier_output.get("extracted_event_data", {})
    styles = get_styles()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.6 * inch,
        leftMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph("MEDWATCH 3500A", styles["FormTitle"]))
    story.append(Paragraph(
        "FDA Safety Reporting — Mandatory Adverse Event Report (Drug)",
        styles["FormSubtitle"],
    ))
    story.append(Paragraph(
        f"Case ID: {case_id}  |  Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  |  Reviewed by: {advocate_id}",
        styles["FormSubtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=FDA_BLUE, spaceAfter=8))

    # ── AI Decision Box ───────────────────────────────────────────────────────
    decision = classifier_output.get("decision", "UNKNOWN")
    confidence = classifier_output.get("confidence_score", 0)
    reasoning = classifier_output.get("reasoning", "")
    doc_sections = classifier_output.get("supporting_doc_sections", [])

    ai_box_data = [
        ["AI REPORTABILITY ASSESSMENT", ""],
        ["Decision", decision],
        ["Confidence", f"{confidence:.1%}"],
        ["Supporting Documentation", "\n".join(doc_sections) if doc_sections else "—"],
        ["AI Reasoning", reasoning[:500] + ("..." if len(reasoning) > 500 else "")],
    ]
    ai_table = Table(ai_box_data, colWidths=[1.8 * inch, 5.5 * inch])
    ai_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a4a00")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("SPAN", (0, 0), (-1, 0)),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#e8f5e9")),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GRAY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5fff5")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(KeepTogether([ai_table, Spacer(1, 10)]))

    # ── Section A: Patient Information ────────────────────────────────────────
    story.append(section_header("A", "Patient Information", styles))
    a_data = [
        ["A1. Patient Identifier (de-identified)", f"CASE-{case_id}"],
        ["A2. Age", event.get("patient_age", "Not reported")],
        ["A3. Sex", event.get("patient_gender", "Not reported")],
        ["A4. Weight", "Not reported"],
        ["A5. Ethnicity", "Not reported"],
    ]
    story.append(_simple_table(a_data))
    story.append(Spacer(1, 6))

    # ── Section B: Adverse Event ───────────────────────────────────────────────
    story.append(section_header("B", "Adverse Event / Product Problem", styles))
    symptoms = ", ".join(event.get("reported_symptoms", [])) or "Not specified"
    b_data = [
        ["B1. Adverse Event", symptoms],
        ["B2. Date of Event", event.get("onset_date", "Not reported")],
        ["B3. Date of Report (Call Date)", call_date],
        ["B4. Describe Event", symptoms],
        ["B5. Relevant Tests / Lab Data", "See chart notes"],
        ["B6. Other Relevant History", f"Concomitant meds: {', '.join(event.get('concomitant_medications', [])) or 'None reported'}"],
    ]
    story.append(_simple_table(b_data))

    # Outcomes
    story.append(Spacer(1, 4))
    outcome = event.get("outcome", "")
    severity = event.get("severity", "Unknown")
    outcomes_checked = _get_outcomes(outcome, severity)
    story.append(Paragraph("<b>B7. Outcomes Attributed to Adverse Event:</b>", styles["FieldValue"]))
    for o in outcomes_checked:
        story.append(Paragraph(f"  ☑ {o}", styles["FieldValue"]))
    story.append(Spacer(1, 6))

    # ── Section C: Suspect Product ─────────────────────────────────────────────
    story.append(section_header("C", "Suspect Product(s)", styles))
    c_data = [
        ["C1. Name, Strength, Manufacturer", event.get("drug_name", "Not specified")],
        ["C2. Therapy Dates", f"Start: Unknown  |  End: {event.get('onset_date', 'Unknown')}"],
        ["C3. Indication for Use", "As prescribed — see chart notes"],
        ["C4. Dose, Frequency, Route", "Not reported"],
        ["C5. Therapy Duration", event.get("duration", "Not reported")],
        ["C6. Lot #", "Not reported"],
        ["C7. Exp. Date", "Not reported"],
        ["C8. NDC #", "Not reported"],
        ["C9. Concomitant Medications", ", ".join(event.get("concomitant_medications", [])) or "None reported"],
    ]
    story.append(_simple_table(c_data))
    story.append(Spacer(1, 6))

    # ── Section E: Reporter Information ───────────────────────────────────────
    story.append(section_header("E", "Reporter Information", styles))
    e_data = [
        ["E1. Name", f"Advocate ID: {advocate_id}"],
        ["E2. Health Professional?", "No — Insurance Advocate"],
        ["E3. Occupation", "Patient Care Advocate, Health Insurance"],
        ["E4. Address", "[Insurance Company Address — configure in settings]"],
        ["E5. Phone", "[Configure in settings]"],
        ["E6. Date Submitted", datetime.utcnow().strftime("%Y-%m-%d")],
        ["E7. Report Type", classifier_output.get("recommended_report_type", "15-day Alert Report")],
    ]
    story.append(_simple_table(e_data))
    story.append(Spacer(1, 10))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_GRAY))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "⚠ This report was AI-assisted. A licensed advocate has reviewed and approved the reportability decision. "
        "This document is generated for submission to the pharmaceutical manufacturer per regulatory obligations. "
        "Retain for 7 years per 21 CFR Part 314.",
        styles["Disclaimer"],
    ))

    doc.build(story)
    return output_path


def _simple_table(data: list[list]) -> Table:
    """Creates a two-column label/value table."""
    t = Table(data, colWidths=[2.2 * inch, 5.1 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (0, -1), FIELD_BG),
        ("TEXTCOLOR", (0, 0), (0, -1), FDA_BLUE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_GRAY),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white, colors.HexColor("#f5f8fc")]),
    ]))
    return t


def _get_outcomes(outcome: str, severity: str) -> list[str]:
    """Map extracted outcome/severity to MedWatch outcome checkboxes."""
    outcomes = []
    outcome_lower = (outcome or "").lower()
    if "death" in outcome_lower:
        outcomes.append("Death")
    if "hospitali" in outcome_lower:
        outcomes.append("Hospitalization — Initial or Prolonged")
    if "disab" in outcome_lower:
        outcomes.append("Disability or Permanent Damage")
    if "life" in outcome_lower or "threatening" in outcome_lower:
        outcomes.append("Life-Threatening")
    if severity == "Serious" and not outcomes:
        outcomes.append("Required Intervention to Prevent Permanent Impairment/Damage")
    if not outcomes:
        outcomes.append("Other Serious (Important Medical Event)")
    return outcomes
