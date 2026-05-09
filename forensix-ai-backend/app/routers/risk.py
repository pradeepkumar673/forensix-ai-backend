"""
app/routers/risk.py

FastAPI router exposing risk analysis endpoints:
  - POST /risk/score          → risk scoring
  - POST /risk/anomalies      → anomaly detection
  - POST /risk/contradictions → contradiction detection
  - POST /risk/leads          → lead recommendations
  - POST /risk/full           → all four in one call
"""

import logging
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.risk_service import (
    compute_risk_score,
    detect_anomalies,
    detect_contradictions,
    generate_lead_recommendations,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk", tags=["Risk Analysis"])


# ---------------------------------------------------------------------------
# Request / Response schemas (local, lightweight)
# ---------------------------------------------------------------------------

class RiskScoreRequest(BaseModel):
    report_text: str = Field("", description="Raw autopsy / forensic report text")
    statements: list[str] = Field(default_factory=list, description="Witness / suspect statements")
    evidence_summary: str = Field("", description="Summary of physical evidence")
    timeline_events: list[dict] = Field(default_factory=list, description="Timeline event dicts")

    model_config = {"json_schema_extra": {"example": {
        "report_text": "Victim found at 03:00 hrs...",
        "statements": ["I was home all night", "I saw him leave at midnight"],
        "evidence_summary": "Blood spatter on wall, fingerprints on door handle",
        "timeline_events": []
    }}}


class AnomalyRequest(BaseModel):
    evidence_items: list[dict] = Field(..., description="List of evidence item dicts")
    report_text: str = Field("", description="Autopsy / forensic report text (optional)")

    model_config = {"json_schema_extra": {"example": {
        "evidence_items": [
            {"type": "photo", "description": "Crime scene photo", "timestamp": "2024-01-15T03:00:00"}
        ],
        "report_text": ""
    }}}


class ContradictionRequest(BaseModel):
    statements: list[str] = Field(..., min_length=1, description="Witness / suspect statements")
    evidence_summary: str = Field("", description="Physical evidence summary")
    report_text: str = Field("", description="Autopsy / forensic report excerpt")

    model_config = {"json_schema_extra": {"example": {
        "statements": [
            "I was at home the entire night.",
            "He told me he went out around midnight."
        ],
        "evidence_summary": "CCTV shows suspect's vehicle leaving at 23:45",
        "report_text": "Time of death estimated between 00:00 and 02:00"
    }}}


class LeadRequest(BaseModel):
    case_summary: dict = Field(..., description="High-level case details")
    anomalies: list[dict] = Field(default_factory=list, description="Anomaly detection output")
    contradictions: list[dict] = Field(default_factory=list, description="Contradiction detection output")
    risk_score: dict = Field(default_factory=dict, description="Risk score output")

    model_config = {"json_schema_extra": {"example": {
        "case_summary": {
            "victim": "John Doe",
            "location": "123 Main St",
            "date": "2024-01-15",
            "known_facts": "Victim found with blunt force trauma"
        },
        "anomalies": [],
        "contradictions": [],
        "risk_score": {}
    }}}


class FullRiskRequest(BaseModel):
    """Single-payload request that runs all four analyses sequentially."""
    report_text: str = Field("", description="Autopsy / forensic report text")
    statements: list[str] = Field(default_factory=list)
    evidence_summary: str = Field("")
    evidence_items: list[dict] = Field(default_factory=list)
    timeline_events: list[dict] = Field(default_factory=list)
    case_summary: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/score",
    summary="Compute forensic risk score",
    response_description="Multi-dimensional risk score with verdict"
)
async def risk_score(request: RiskScoreRequest):
    """
    Compute a multi-dimensional forensic risk score for the case.

    Returns an overall risk score (0-100), dimension breakdown,
    a severity verdict (LOW / MEDIUM / HIGH / CRITICAL) and rationale.
    """
    try:
        result = await compute_risk_score(request.model_dump())
        return {"status": "success", "data": result}
    except Exception as exc:
        logger.exception("Risk scoring failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk scoring failed: {str(exc)}"
        )


@router.post(
    "/anomalies",
    summary="Detect anomalies in evidence and report",
    response_description="List of anomalies with severity and suggested actions"
)
async def anomaly_detection(request: AnomalyRequest):
    """
    Detect anomalies in the provided evidence items and/or forensic report text.

    Returns a list of anomalies with severity ratings and recommended follow-up actions.
    """
    try:
        result = await detect_anomalies(
            evidence_items=request.evidence_items,
            report_text=request.report_text,
        )
        return {"status": "success", "data": result}
    except Exception as exc:
        logger.exception("Anomaly detection failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Anomaly detection failed: {str(exc)}"
        )


@router.post(
    "/contradictions",
    summary="Detect contradictions in statements vs evidence",
    response_description="Contradictions list with credibility scores"
)
async def contradiction_detection(request: ContradictionRequest):
    """
    Cross-examine witness / suspect statements against each other and
    against physical evidence / forensic report.

    Returns contradiction list, per-statement credibility scores,
    and an overall credibility rating.
    """
    if len(request.statements) < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one statement is required."
        )
    try:
        result = await detect_contradictions(
            statements=request.statements,
            evidence_summary=request.evidence_summary,
            report_text=request.report_text,
        )
        return {"status": "success", "data": result}
    except Exception as exc:
        logger.exception("Contradiction detection failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Contradiction detection failed: {str(exc)}"
        )


@router.post(
    "/leads",
    summary="Generate investigative lead recommendations",
    response_description="Prioritised list of actionable investigative leads"
)
async def lead_recommendations(request: LeadRequest):
    """
    Generate a prioritised list of actionable investigative leads based on
    the case summary plus any available anomaly, contradiction, and risk data.

    Returns leads categorised by type (witness re-interview, digital forensics,
    CCTV checks, etc.) with priority, effort estimate, and expected outcome.
    """
    try:
        result = await generate_lead_recommendations(
            case_summary=request.case_summary,
            anomalies=request.anomalies or None,
            contradictions=request.contradictions or None,
            risk_score=request.risk_score or None,
        )
        return {"status": "success", "data": result}
    except Exception as exc:
        logger.exception("Lead recommendation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lead recommendation failed: {str(exc)}"
        )


@router.post(
    "/full",
    summary="Full risk analysis pipeline (all four analyses)",
    response_description="Combined risk score, anomalies, contradictions, and leads"
)
async def full_risk_analysis(request: FullRiskRequest):
    """
    Run all four risk analyses in sequence using a single payload:

    1. Risk scoring
    2. Anomaly detection
    3. Contradiction detection
    4. Lead recommendations (seeded with results from 1-3)

    Returns a combined payload with all four result sets.
    """
    try:
        # 1. Risk score
        case_data = {
            "report_text": request.report_text,
            "statements": request.statements,
            "evidence_summary": request.evidence_summary,
            "timeline_events": request.timeline_events,
        }
        risk = await compute_risk_score(case_data)

        # 2. Anomaly detection
        anomaly_result = await detect_anomalies(
            evidence_items=request.evidence_items,
            report_text=request.report_text,
        )

        # 3. Contradiction detection (only if statements provided)
        contradiction_result = {}
        if request.statements:
            contradiction_result = await detect_contradictions(
                statements=request.statements,
                evidence_summary=request.evidence_summary,
                report_text=request.report_text,
            )

        # 4. Lead recommendations (seeded with above results)
        case_summary = request.case_summary or {
            "evidence_summary": request.evidence_summary,
            "statement_count": len(request.statements),
        }
        leads = await generate_lead_recommendations(
            case_summary=case_summary,
            anomalies=anomaly_result.get("anomalies"),
            contradictions=contradiction_result.get("contradictions"),
            risk_score=risk,
        )

        return {
            "status": "success",
            "data": {
                "risk_score": risk,
                "anomalies": anomaly_result,
                "contradictions": contradiction_result,
                "leads": leads,
            }
        }

    except Exception as exc:
        logger.exception("Full risk analysis pipeline failed")
        # Still return 200 with partial telemetry — avoids opaque 500s when LLM or JSON parsing flakes.
        from app.services.risk_service import (
            _fallback_anomalies,
            _fallback_contradictions,
            _fallback_leads,
            _fallback_risk_score,
        )

        case_stub = {
            "report_text": request.report_text,
            "statements": request.statements,
            "evidence_summary": request.evidence_summary,
            "timeline_events": request.timeline_events,
        }
        return {
            "status": "partial",
            "error": str(exc),
            "data": {
                "risk_score": _fallback_risk_score(case_stub),
                "anomalies": _fallback_anomalies(str(exc)),
                "contradictions": _fallback_contradictions(
                    len(request.statements), str(exc)
                ),
                "leads": _fallback_leads(str(exc)),
            },
        }
