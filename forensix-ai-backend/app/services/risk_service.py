"""
app/services/risk_service.py

Handles risk scoring, anomaly detection, contradiction detection,
and lead recommendations for forensic case analysis.
"""

import re
import json
import logging
from typing import Any
from app.services.llm_service import get_llm_response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_json(raw: str) -> dict | list:
    """Strip markdown fences and parse JSON from LLM output."""
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Risk Scoring
# ---------------------------------------------------------------------------

async def compute_risk_score(case_data: dict) -> dict:
    """
    Compute a multi-dimensional forensic risk score for the case.

    Args:
        case_data: dict containing any combination of:
            - report_text (str)
            - statements (list[str])
            - evidence_summary (str)
            - timeline_events (list[dict])

    Returns:
        {
            "overall_risk": float,          # 0-100
            "dimensions": {
                "evidence_integrity": float,
                "witness_reliability": float,
                "timeline_consistency": float,
                "motive_strength": float,
                "forensic_gaps": float
            },
            "verdict": str,                 # LOW / MEDIUM / HIGH / CRITICAL
            "rationale": str
        }
    """
    prompt = f"""
You are a senior forensic analyst AI. Analyze the following case data and produce a
structured risk score in pure JSON (no markdown, no explanation outside JSON).

Case Data:
{json.dumps(case_data, indent=2)}

Return ONLY a JSON object with exactly these keys:
{{
  "overall_risk": <float 0-100>,
  "dimensions": {{
    "evidence_integrity": <float 0-100>,
    "witness_reliability": <float 0-100>,
    "timeline_consistency": <float 0-100>,
    "motive_strength": <float 0-100>,
    "forensic_gaps": <float 0-100>
  }},
  "verdict": "<LOW|MEDIUM|HIGH|CRITICAL>",
  "rationale": "<two-sentence explanation>"
}}
"""
    resp = await get_llm_response(prompt)
    raw_text = resp.get("response", "") if isinstance(resp, dict) else resp
    result = _safe_json(raw_text)
    logger.info("Risk score computed: overall=%.1f verdict=%s",
                result.get("overall_risk", 0), result.get("verdict"))
    return result


# ---------------------------------------------------------------------------
# Anomaly Detection
# ---------------------------------------------------------------------------

async def detect_anomalies(
    evidence_items: list[dict],
    report_text: str = ""
) -> dict:
    """
    Identify anomalies in evidence items and/or autopsy report text.

    Args:
        evidence_items: list of dicts, e.g.
            [{"type": "photo", "description": "...", "timestamp": "..."}]
        report_text: raw autopsy / forensic report text (optional)

    Returns:
        {
            "anomalies": [
                {
                    "id": str,
                    "severity": "LOW|MEDIUM|HIGH",
                    "description": str,
                    "affected_items": list[str],
                    "suggested_action": str
                }
            ],
            "anomaly_count": int,
            "summary": str
        }
    """
    prompt = f"""
You are a forensic anomaly detection AI.

Evidence Items:
{json.dumps(evidence_items, indent=2)}

Report Text (excerpt):
{report_text[:3000] if report_text else "Not provided"}

Identify all anomalies — inconsistencies in timestamps, missing chain-of-custody,
unexplained injuries, suspicious patterns in evidence.

Return ONLY a JSON object:
{{
  "anomalies": [
    {{
      "id": "<short unique id>",
      "severity": "<LOW|MEDIUM|HIGH>",
      "description": "<what is anomalous and why>",
      "affected_items": ["<item ref>"],
      "suggested_action": "<recommended follow-up>"
    }}
  ],
  "anomaly_count": <int>,
  "summary": "<overall assessment in one sentence>"
}}
"""
    resp = await get_llm_response(prompt)
    raw_text = resp.get("response", "") if isinstance(resp, dict) else resp
    result = _safe_json(raw_text)
    logger.info("Anomaly detection: %d anomaly/anomalies found",
                result.get("anomaly_count", 0))
    return result


# ---------------------------------------------------------------------------
# Contradiction Detection
# ---------------------------------------------------------------------------

async def detect_contradictions(
    statements: list[str],
    evidence_summary: str = "",
    report_text: str = ""
) -> dict:
    """
    Cross-examine witness statements against evidence and forensic report.

    Args:
        statements: list of witness/suspect statements (raw text each)
        evidence_summary: brief summary of physical evidence
        report_text: autopsy or forensic report text

    Returns:
        {
            "contradictions": [
                {
                    "id": str,
                    "type": "STATEMENT_VS_STATEMENT | STATEMENT_VS_EVIDENCE | STATEMENT_VS_REPORT",
                    "severity": "LOW|MEDIUM|HIGH|CRITICAL",
                    "statement_refs": list[int],   # indices into `statements`
                    "description": str,
                    "implication": str
                }
            ],
            "contradiction_count": int,
            "credibility_scores": list[float],     # per statement, 0-100
            "overall_credibility": float,
            "summary": str
        }
    """
    numbered = [f"[{i}] {s}" for i, s in enumerate(statements)]
    prompt = f"""
You are a forensic contradiction analysis AI with expertise in statement analysis
and evidence cross-referencing.

Witness / Suspect Statements:
{chr(10).join(numbered)}

Physical Evidence Summary:
{evidence_summary or "Not provided"}

Forensic / Autopsy Report (excerpt):
{report_text[:2000] if report_text else "Not provided"}

Detect all contradictions between statements, and between statements and
evidence/report. Rate severity. Also score each statement's overall credibility.

Return ONLY a JSON object:
{{
  "contradictions": [
    {{
      "id": "<short id>",
      "type": "<STATEMENT_VS_STATEMENT|STATEMENT_VS_EVIDENCE|STATEMENT_VS_REPORT>",
      "severity": "<LOW|MEDIUM|HIGH|CRITICAL>",
      "statement_refs": [<int indices>],
      "description": "<what contradicts what, specifically>",
      "implication": "<forensic / legal implication>"
    }}
  ],
  "contradiction_count": <int>,
  "credibility_scores": [<float per statement, 0-100>],
  "overall_credibility": <float 0-100>,
  "summary": "<one-paragraph case assessment>"
}}
"""
    resp = await get_llm_response(prompt)
    raw_text = resp.get("response", "") if isinstance(resp, dict) else resp
    result = _safe_json(raw_text)
    logger.info("Contradiction detection: %d found",
                result.get("contradiction_count", 0))
    return result


# ---------------------------------------------------------------------------
# Lead Recommendations
# ---------------------------------------------------------------------------

async def generate_lead_recommendations(
    case_summary: dict,
    anomalies: list[dict] | None = None,
    contradictions: list[dict] | None = None,
    risk_score: dict | None = None
) -> dict:
    """
    Generate actionable investigative leads based on all available analysis.

    Args:
        case_summary: high-level case details (victim, location, known facts, etc.)
        anomalies: output from detect_anomalies (optional)
        contradictions: output from detect_contradictions (optional)
        risk_score: output from compute_risk_score (optional)

    Returns:
        {
            "leads": [
                {
                    "id": str,
                    "priority": "LOW|MEDIUM|HIGH|URGENT",
                    "category": str,        # e.g. "Witness Re-interview", "Digital Forensics"
                    "title": str,
                    "description": str,
                    "expected_outcome": str,
                    "estimated_effort": str # e.g. "2-4 hours"
                }
            ],
            "lead_count": int,
            "top_priority_lead": str,       # id of highest priority lead
            "investigative_summary": str
        }
    """
    prompt = f"""
You are an expert forensic investigator AI. Based on the full case analysis below,
generate a prioritized list of actionable investigative leads.

Case Summary:
{json.dumps(case_summary, indent=2)}

Detected Anomalies:
{json.dumps(anomalies or [], indent=2)}

Detected Contradictions:
{json.dumps(contradictions or [], indent=2)}

Risk Assessment:
{json.dumps(risk_score or {{}}, indent=2)}

Produce practical, specific leads an investigator can act on immediately.
Cover all relevant categories: witness re-interviews, digital forensics,
physical evidence re-examination, CCTV / location checks, financial records,
phone records, medical review, etc.

Return ONLY a JSON object:
{{
  "leads": [
    {{
      "id": "<short id>",
      "priority": "<LOW|MEDIUM|HIGH|URGENT>",
      "category": "<category>",
      "title": "<one-line title>",
      "description": "<what to do and why>",
      "expected_outcome": "<what this lead should confirm or rule out>",
      "estimated_effort": "<time estimate>"
    }}
  ],
  "lead_count": <int>,
  "top_priority_lead": "<id>",
  "investigative_summary": "<concise paragraph summarising the investigative direction>"
}}
"""
    resp = await get_llm_response(prompt)
    raw_text = resp.get("response", "") if isinstance(resp, dict) else resp
    result = _safe_json(raw_text)
    logger.info("Lead recommendations generated: %d leads", result.get("lead_count", 0))
    return result
