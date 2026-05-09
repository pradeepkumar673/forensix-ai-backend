"""
app/services/report_service.py

Generates a professional, multi-section forensic case PDF report
using ReportLab (Platypus high-level API).

Usage:
    from app.services.report_service import generate_case_report

    output_path = await generate_case_report(report_data)
    # returns absolute path to the generated PDF inside /outputs/
"""

import os
import uuid
import logging
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
    KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
OUTPUTS_DIR = Path("outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------
DARK_NAVY   = colors.HexColor("#0D1B2A")   # headers / title bar
ACCENT_BLUE = colors.HexColor("#1565C0")   # section headings
LIGHT_GRAY  = colors.HexColor("#F4F6F8")   # table row fill
MID_GRAY    = colors.HexColor("#90A4AE")   # secondary text
CRITICAL    = colors.HexColor("#B71C1C")
HIGH_COLOR  = colors.HexColor("#E65100")
MEDIUM_COLOR= colors.HexColor("#F9A825")
LOW_COLOR   = colors.HexColor("#2E7D32")


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _build_styles() -> dict:
    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontSize=22,
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=4,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontSize=11,
            textColor=colors.HexColor("#CFD8DC"),
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "section_heading": ParagraphStyle(
            "SectionHeading",
            parent=base["Heading1"],
            fontSize=13,
            textColor=ACCENT_BLUE,
            fontName="Helvetica-Bold",
            spaceBefore=14,
            spaceAfter=4,
            borderPad=(0, 0, 2, 0),
        ),
        "sub_heading": ParagraphStyle(
            "SubHeading",
            parent=base["Heading2"],
            fontSize=11,
            textColor=DARK_NAVY,
            fontName="Helvetica-Bold",
            spaceBefore=8,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "BodyText",
            parent=base["Normal"],
            fontSize=10,
            leading=15,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "SmallText",
            parent=base["Normal"],
            fontSize=8,
            textColor=MID_GRAY,
        ),
        "badge_critical": ParagraphStyle(
            "BadgeCritical", parent=base["Normal"],
            fontSize=9, fontName="Helvetica-Bold", textColor=CRITICAL,
        ),
        "badge_high": ParagraphStyle(
            "BadgeHigh", parent=base["Normal"],
            fontSize=9, fontName="Helvetica-Bold", textColor=HIGH_COLOR,
        ),
        "badge_medium": ParagraphStyle(
            "BadgeMedium", parent=base["Normal"],
            fontSize=9, fontName="Helvetica-Bold", textColor=MEDIUM_COLOR,
        ),
        "badge_low": ParagraphStyle(
            "BadgeLow", parent=base["Normal"],
            fontSize=9, fontName="Helvetica-Bold", textColor=LOW_COLOR,
        ),
    }
    return styles


def _severity_style(severity: str, styles: dict) -> ParagraphStyle:
    sev = (severity or "").upper()
    return {
        "CRITICAL": styles["badge_critical"],
        "HIGH":     styles["badge_high"],
        "MEDIUM":   styles["badge_medium"],
    }.get(sev, styles["badge_low"])


def _divider():
    return HRFlowable(width="100%", thickness=0.5, color=MID_GRAY, spaceAfter=6, spaceBefore=2)


# ---------------------------------------------------------------------------
# Page template (header / footer via canvas callbacks)
# ---------------------------------------------------------------------------

def _make_page_callback(case_id: str, generated_at: str):
    def _on_page(canvas, doc):
        canvas.saveState()
        w, h = A4

        # ── Header bar ──────────────────────────────────────────────────────
        canvas.setFillColor(DARK_NAVY)
        canvas.rect(0, h - 18 * mm, w, 18 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(15 * mm, h - 11 * mm, "ForensiX AI  |  Confidential Forensic Report")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 15 * mm, h - 11 * mm, f"Case: {case_id or 'N/A'}")

        # ── Footer bar ───────────────────────────────────────────────────────
        canvas.setFillColor(DARK_NAVY)
        canvas.rect(0, 0, w, 10 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(
            15 * mm, 3.5 * mm,
            f"Generated: {generated_at}  |  FOR OFFICIAL USE ONLY",
        )
        canvas.drawRightString(
            w - 15 * mm, 3.5 * mm,
            f"Page {doc.page}",
        )
        canvas.restoreState()

    return _on_page


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _section_case_overview(data: dict, styles: dict) -> list:
    elements = []
    ctx = data.get("case_context", {})

    elements.append(Paragraph("1. Case Overview", styles["section_heading"]))
    elements.append(_divider())

    rows = [
        ["Case ID",       ctx.get("case_id", "—")],
        ["Victim",        ctx.get("victim", "—")],
        ["Location",      ctx.get("location", "—")],
        ["Incident Date", ctx.get("date", "—")],
        ["Reporting Officer", ctx.get("reporting_officer", "—")],
        ["Classification",   ctx.get("classification", "—")],
    ]
    tbl = Table(rows, colWidths=[55 * mm, 115 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), LIGHT_GRAY),
        ("FONTNAME",   (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.25, MID_GRAY),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(tbl)
    elements.append(Spacer(1, 8))

    if ctx.get("report_summary"):
        elements.append(Paragraph("Forensic Summary", styles["sub_heading"]))
        elements.append(Paragraph(ctx["report_summary"], styles["body"]))

    if ctx.get("evidence_summary"):
        elements.append(Paragraph("Evidence Summary", styles["sub_heading"]))
        elements.append(Paragraph(ctx["evidence_summary"], styles["body"]))

    return elements


def _section_risk_score(data: dict, styles: dict) -> list:
    elements = []
    rs = data.get("risk_score", {})
    if not rs:
        return elements

    elements.append(Paragraph("2. Risk Assessment", styles["section_heading"]))
    elements.append(_divider())

    verdict = rs.get("verdict", "N/A")
    overall = rs.get("overall_risk", 0)
    badge_style = _severity_style(verdict, styles)

    # Overall score summary row
    summary_tbl = Table(
        [[
            Paragraph(f"Overall Risk Score", styles["sub_heading"]),
            Paragraph(f"{overall:.1f} / 100", styles["sub_heading"]),
            Paragraph(f"[{verdict}]", badge_style),
        ]],
        colWidths=[80 * mm, 50 * mm, 40 * mm],
    )
    summary_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GRAY),
        ("GRID",       (0, 0), (-1, -1), 0.25, MID_GRAY),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(summary_tbl)
    elements.append(Spacer(1, 6))

    # Dimension breakdown
    dims = rs.get("dimensions", {})
    if dims:
        elements.append(Paragraph("Dimension Breakdown", styles["sub_heading"]))
        dim_rows = [["Dimension", "Score"]]
        for dim, score in dims.items():
            label = dim.replace("_", " ").title()
            dim_rows.append([label, f"{score:.1f}"])
        dim_tbl = Table(dim_rows, colWidths=[120 * mm, 50 * mm])
        dim_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), DARK_NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("GRID",          (0, 0), (-1, -1), 0.25, MID_GRAY),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(dim_tbl)
        elements.append(Spacer(1, 4))

    if rs.get("rationale"):
        elements.append(Paragraph("Rationale", styles["sub_heading"]))
        elements.append(Paragraph(rs["rationale"], styles["body"]))

    return elements


def _section_anomalies(data: dict, styles: dict) -> list:
    elements = []
    anomaly_data = data.get("anomalies", {})
    anomalies = anomaly_data.get("anomalies", []) if isinstance(anomaly_data, dict) else anomaly_data
    if not anomalies:
        return elements

    elements.append(Paragraph("3. Anomaly Detection", styles["section_heading"]))
    elements.append(_divider())

    if isinstance(anomaly_data, dict) and anomaly_data.get("summary"):
        elements.append(Paragraph(anomaly_data["summary"], styles["body"]))

    rows = [["#", "Severity", "Description", "Suggested Action"]]
    for i, a in enumerate(anomalies, 1):
        rows.append([
            str(i),
            a.get("severity", "—"),
            a.get("description", "—"),
            a.get("suggested_action", "—"),
        ])

    tbl = Table(rows, colWidths=[8 * mm, 22 * mm, 85 * mm, 55 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK_NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.25, MID_GRAY),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("WORDWRAP",      (0, 0), (-1, -1), True),
    ]))
    elements.append(tbl)
    return elements


def _section_contradictions(data: dict, styles: dict) -> list:
    elements = []
    cont_data = data.get("contradictions", {})
    contradictions = cont_data.get("contradictions", []) if isinstance(cont_data, dict) else cont_data
    if not contradictions:
        return elements

    elements.append(Paragraph("4. Contradiction Analysis", styles["section_heading"]))
    elements.append(_divider())

    if isinstance(cont_data, dict):
        cred = cont_data.get("overall_credibility")
        if cred is not None:
            elements.append(Paragraph(
                f"Overall Witness Credibility Score: <b>{cred:.1f} / 100</b>",
                styles["body"]
            ))
        if cont_data.get("summary"):
            elements.append(Paragraph(cont_data["summary"], styles["body"]))

    rows = [["#", "Type", "Severity", "Description", "Implication"]]
    for i, c in enumerate(contradictions, 1):
        rows.append([
            str(i),
            c.get("type", "—").replace("_", " "),
            c.get("severity", "—"),
            c.get("description", "—"),
            c.get("implication", "—"),
        ])

    tbl = Table(rows, colWidths=[8 * mm, 32 * mm, 20 * mm, 75 * mm, 35 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK_NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.25, MID_GRAY),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(tbl)
    return elements


def _section_leads(data: dict, styles: dict) -> list:
    elements = []
    leads_data = data.get("leads", {})
    leads = leads_data.get("leads", []) if isinstance(leads_data, dict) else leads_data
    if not leads:
        return elements

    elements.append(Paragraph("5. Investigative Leads", styles["section_heading"]))
    elements.append(_divider())

    if isinstance(leads_data, dict) and leads_data.get("investigative_summary"):
        elements.append(Paragraph(leads_data["investigative_summary"], styles["body"]))

    rows = [["Priority", "Category", "Lead", "Expected Outcome", "Effort"]]
    for lead in leads:
        rows.append([
            lead.get("priority", "—"),
            lead.get("category", "—"),
            f"{lead.get('title','')}\n{lead.get('description','')}",
            lead.get("expected_outcome", "—"),
            lead.get("estimated_effort", "—"),
        ])

    tbl = Table(rows, colWidths=[18 * mm, 28 * mm, 70 * mm, 40 * mm, 14 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK_NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.25, MID_GRAY),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("WORDWRAP",      (0, 0), (-1, -1), True),
    ]))
    elements.append(tbl)
    return elements


def _section_timeline(data: dict, styles: dict) -> list:
    elements = []
    events = data.get("timeline_events", [])
    if not events:
        return elements

    elements.append(Paragraph("6. Case Timeline", styles["section_heading"]))
    elements.append(_divider())

    rows = [["Time / Date", "Event", "Source"]]
    for ev in events:
        rows.append([
            ev.get("timestamp", ev.get("time", "—")),
            ev.get("description", ev.get("event", "—")),
            ev.get("source", "—"),
        ])

    tbl = Table(rows, colWidths=[45 * mm, 100 * mm, 25 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), DARK_NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("GRID",          (0, 0), (-1, -1), 0.25, MID_GRAY),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(tbl)
    return elements


def _cover_page(data: dict, styles: dict, generated_at: str) -> list:
    """Dark-header cover page."""
    elements = []
    ctx = data.get("case_context", {})

    # Title band (simulate with a coloured table)
    cover_tbl = Table(
        [[
            Paragraph("FORENSIX AI", styles["title"]),
        ],
        [
            Paragraph("Forensic Analysis Report — CONFIDENTIAL", styles["subtitle"]),
        ]],
        colWidths=[170 * mm],
    )
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), DARK_NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
    ]))
    elements.append(cover_tbl)
    elements.append(Spacer(1, 20 * mm))

    meta_rows = [
        ["Case ID",       ctx.get("case_id", "—")],
        ["Victim",        ctx.get("victim", "—")],
        ["Location",      ctx.get("location", "—")],
        ["Incident Date", ctx.get("date", "—")],
        ["Generated",     generated_at],
        ["Classification","RESTRICTED – FOR OFFICIAL USE ONLY"],
    ]
    meta_tbl = Table(meta_rows, colWidths=[55 * mm, 115 * mm])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), LIGHT_GRAY),
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.4, MID_GRAY),
        ("ROWBACKGROUNDS",(0, 0), (-1, -1), [colors.white, LIGHT_GRAY]),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(meta_tbl)
    elements.append(PageBreak())
    return elements


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_case_report(report_data: dict) -> str:
    """
    Generate a multi-section forensic PDF report.

    Args:
        report_data: dict with any of:
            - case_context (dict): victim, location, date, report_summary, etc.
            - risk_score (dict): output from compute_risk_score()
            - anomalies (dict): output from detect_anomalies()
            - contradictions (dict): output from detect_contradictions()
            - leads (dict): output from generate_lead_recommendations()
            - timeline_events (list[dict]): ordered timeline events

    Returns:
        Absolute path string to the generated PDF.
    """
    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    case_id = report_data.get("case_context", {}).get("case_id", str(uuid.uuid4())[:8])
    filename = f"forensix_report_{case_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    output_path = OUTPUTS_DIR / filename

    styles = _build_styles()
    on_page = _make_page_callback(case_id, generated_at)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=22 * mm,      # leave room for header band
        bottomMargin=14 * mm,   # leave room for footer band
        title=f"ForensiX AI Report – {case_id}",
        author="ForensiX AI",
        subject="Confidential Forensic Case Report",
    )

    story: list = []

    # Cover page
    story.extend(_cover_page(report_data, styles, generated_at))

    # Content sections (only appended if they have data)
    story.extend(_section_case_overview(report_data, styles))
    story.extend(_section_risk_score(report_data, styles))
    story.extend(_section_anomalies(report_data, styles))
    story.extend(_section_contradictions(report_data, styles))
    story.extend(_section_leads(report_data, styles))
    story.extend(_section_timeline(report_data, styles))

    # Final disclaimer
    story.append(Spacer(1, 10 * mm))
    story.append(_divider())
    story.append(Paragraph(
        "This report was generated by ForensiX AI and is intended for authorised law enforcement "
        "and forensic personnel only. AI-generated insights are advisory and must be verified "
        "by qualified human experts before any action is taken.",
        styles["small"],
    ))

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)

    logger.info("PDF report generated: %s", output_path)
    return str(output_path.resolve())
