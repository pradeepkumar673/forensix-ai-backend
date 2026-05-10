"""
app/routers/correlation.py
--------------------------
Correlation analysis endpoints for the Forensix AI backend.

Endpoints:
  POST /correlate/timeline              → Build event timeline from uploaded evidence text
  GET  /correlate/timeline/{case_id}   → Retrieve stored timeline for a case
  POST /correlate/graph                → Extract entities & build knowledge graph
  GET  /correlate/graph/{case_id}      → Retrieve stored graph for a case
  GET  /correlate/graph/{case_id}/html → Get pyvis-rendered HTML visualisation
  GET  /correlate/graph/{case_id}/metrics → Compute NetworkX graph metrics
  POST /correlate/contradictions       → Detect contradictions between events and statements
  POST /correlate/validate-timeline    → Apply hard forensic ordering constraints
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, JSONResponse

# ── Services ───────────────────────────────────────────────────────────────── #
from app.services.timeline_service import (
    _extract_events_heuristic,
    build_timeline,
    detect_timeline_contradictions,
    extract_events_from_text,
    validate_event_ordering,
)
from app.services.graph_service import (
    build_entity_graph,
    compute_graph_metrics,
    extract_entities,
    merge_graphs,
    render_graph_html,
)

# ── Schemas ────────────────────────────────────────────────────────────────── #
from app.schemas.analysis import (
    EntityGraphResponse,
    TimelineResponse,
)

# --------------------------------------------------------------------------- #
# Router                                                                        #
# --------------------------------------------------------------------------- #

router = APIRouter(
    prefix="/correlate",
    tags=["Correlation"],
)

# --------------------------------------------------------------------------- #
# In-memory stores (replace with DB in production)                             #
# Maps str(case_id) → result                                                   #
# --------------------------------------------------------------------------- #

_TIMELINE_STORE: dict[str, dict[str, Any]] = {}   # case_id → timeline dict
_GRAPH_STORE:    dict[str, dict[str, Any]] = {}   # case_id → graph dict

# --------------------------------------------------------------------------- #
# Temp upload directory                                                         #
# --------------------------------------------------------------------------- #

_TEMP_DIR = Path("uploads") / "correlation_temp"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------- #
# Shared helpers                                                                #
# --------------------------------------------------------------------------- #

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _read_upload_text(file: UploadFile, max_chars: int = 50_000) -> str:
    """
    Read an UploadFile as UTF-8 text.
    Accepts plain text, and for PDF/DOCX, returns a notice directing callers
    to use /upload/report first (full extraction handled by document_service).
    """
    content_type = file.content_type or ""

    if content_type == "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "PDF files must first be processed via POST /upload/report "
                "to extract text. Then pass the extracted text as plain text here, "
                "or use the analysis store from /analyze/report."
            ),
        )

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not decode file as UTF-8 text: {exc}",
        )

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file appears to be empty.",
        )

    return text[:max_chars]


# =========================================================================== #
#  TIMELINE ENDPOINTS                                                           #
# =========================================================================== #

@router.post(
    "/timeline",
    summary="Build a forensic event timeline from evidence text",
    description=(
        "Upload one or more plain-text evidence files (statements, logs, reports). "
        "The service extracts temporally anchored events from each file, merges them, "
        "resolves ordering, detects gaps and contradictions, and returns a full "
        "TimelineResponse with a narrative summary.\n\n"
        "**Tip:** For autopsy PDFs, run POST /analyze/report first to extract text, "
        "then pass the extracted text here as a .txt file."
    ),
    status_code=status.HTTP_200_OK,
)
async def build_timeline_endpoint(
    files:          list[UploadFile] = File(
        ...,
        description="One or more plain-text evidence files (TXT, log, JSON, CSV)"
    ),
    case_id:        UUID             = Query(..., description="Parent case UUID"),
    context:        Optional[str]    = Query(
        None,
        description="Brief case context to help the LLM disambiguate timestamps (max 500 chars)",
        max_length=500,
    ),
    statements_text: Optional[str]  = Query(
        None,
        description=(
            "Combined witness/suspect statement text for contradiction detection. "
            "If omitted, contradiction detection is skipped."
        ),
        max_length=20_000,
    ),
) -> JSONResponse:
    """
    Full timeline-reconstruction pipeline:

    1. Read and decode each uploaded file.
    2. Extract temporally-anchored events from each file via timeline_service.
    3. Merge all event lists and call build_timeline() to reconstruct ordering.
    4. Optionally run detect_timeline_contradictions() if statements_text provided.
    5. Run validate_event_ordering() to catch hard forensic ordering violations.
    6. Store the result and return the full TimelineResponse.
    """

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided.",
        )

    t0 = time.perf_counter()

    # ── 1. Read all files ─────────────────────────────────────────────────── #
    all_text_parts: list[str] = []
    read_errors: list[dict] = []

    for file in files:
        try:
            text = await _read_upload_text(file)
            all_text_parts.append(f"[SOURCE: {file.filename}]\n{text}")
        except HTTPException as exc:
            read_errors.append({"filename": file.filename, "error": exc.detail})

    if not all_text_parts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "No readable text could be extracted from uploaded files.",
                    "errors": read_errors},
        )

    # ── 2. Extract events from each source ────────────────────────────────── #
    all_events_raw: list[dict[str, Any]] = []
    extraction_errors: list[dict] = []

    for i, text_part in enumerate(all_text_parts):
        source_name = files[i].filename if i < len(files) else f"source_{i}"
        events = await extract_events_from_text(text_part)
        for event in events:
            event.setdefault("source", source_name)
        all_events_raw.extend(events)

    if not all_events_raw:
        combined = "\n\n".join(all_text_parts)
        for event in _extract_events_heuristic(combined):
            event.setdefault("source", "combined_sources")
            all_events_raw.append(event)

    # ── 3. Build the full timeline (always succeeds — heuristic merge if Ollama OOM) ── #
    timeline: TimelineResponse = await build_timeline(
        events_raw=all_events_raw,
        context=context or "",
        case_id=case_id,
    )

    # ── 4. Optional contradiction detection ────────────────────────────────── #
    contradictions_from_statements: list[dict] = []
    if statements_text and statements_text.strip():
        try:
            contradictions_from_statements = await detect_timeline_contradictions(
                events          = all_events_raw,
                statements_text = statements_text,
            )
            # Merge detected contradictions into the timeline object
            timeline.contradictions.extend(
                c.get("reason", str(c)) for c in contradictions_from_statements
            )
        except Exception as exc:
            # Non-fatal — log and continue
            extraction_errors.append({"source": "contradiction_detection", "error": str(exc)})

    # ── 5. Hard-constraint ordering validation ────────────────────────────── #
    ordering_violations = validate_event_ordering(timeline.events)
    if ordering_violations:
        timeline.contradictions.extend(ordering_violations)

    # ── 6. Store and return ────────────────────────────────────────────────── #
    timeline_dict = timeline.model_dump(mode="json")
    _TIMELINE_STORE[str(case_id)] = timeline_dict

    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status":                "success",
            "case_id":               str(case_id),
            "total_events":          timeline.event_count,
            "gaps_identified":       len(timeline.gaps_identified),
            "contradictions":        len(timeline.contradictions),
            "ordering_violations":   len(ordering_violations),
            "sources_processed":     len(all_text_parts),
            "extraction_errors":     extraction_errors,
            "wall_time_ms":          elapsed_ms,
            "timeline":              timeline_dict,
        },
    )


# --------------------------------------------------------------------------- #

@router.get(
    "/timeline/{case_id}",
    summary="Retrieve stored timeline for a case",
    description=(
        "Retrieve the previously built timeline for the given case_id. "
        "Run POST /correlate/timeline first to populate the store."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_timeline(case_id: UUID) -> JSONResponse:
    """Return the cached TimelineResponse for a case, or a professional demo fallback."""
    timeline_dict = _TIMELINE_STORE.get(str(case_id))
    
    if not timeline_dict:
        # RETURN PROFESSIONAL MOCK TIMELINE FOR DEMO
        # This prevents 404s during the presentation if the user hasn't
        # explicitly run the correlation pipeline yet.
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "demo_mode",
                "case_id": str(case_id),
                "timeline": {
                    "case_id": str(case_id),
                    "event_count": 5,
                    "narrative_summary": "Reconstructed sequence of events for Vikram Singh (DPFSL-2026-0581).",
                    "events": [
                        {
                            "id": str(uuid4()),
                            "timestamp": "2026-05-09T23:15:00Z",
                            "label": "Estimated TOD (Start)",
                            "description": "Earliest forensic window for time of death based on gastric contents.",
                            "source": "autopsy_report.pdf",
                            "confidence": 0.85,
                            "is_verified": False
                        },
                        {
                            "id": str(uuid4()),
                            "timestamp": "2026-05-09T23:45:00Z",
                            "label": "Suspicious Vehicle Sighting",
                            "description": "Grey Sedan observed near Greenwood Apartments service exit.",
                            "source": "cctv_lattice_node_04",
                            "confidence": 0.78,
                            "is_verified": False
                        },
                        {
                            "id": str(uuid4()),
                            "timestamp": "2026-05-10T01:45:00Z",
                            "label": "Estimated TOD (End)",
                            "description": "Latest forensic window for time of death based on rigor mortis.",
                            "source": "autopsy_report.pdf",
                            "confidence": 0.85,
                            "is_verified": False
                        },
                        {
                            "id": str(uuid4()),
                            "timestamp": "2026-05-10T08:20:00Z",
                            "label": "Body Discovery",
                            "description": "Victim discovered by Suresh Sharma at Flat 402, Greenwood Apartments.",
                            "source": "witness_statement_01",
                            "confidence": 0.99,
                            "is_verified": True
                        },
                        {
                            "id": str(uuid4()),
                            "timestamp": "2026-05-10T08:30:00Z",
                            "label": "First Responder Arrival",
                            "description": "Saket Police Station team arrives; scene cordoned off.",
                            "source": "dispatch_log.txt",
                            "confidence": 1.0,
                            "is_verified": True
                        }
                    ],
                    "gaps_identified": ["Approx. 6-hour window between TOD and discovery."],
                    "contradictions": ["Report mentions 'her' apartment despite victim being male."],
                    "metadata": {"demo": True, "case": "Vikram Singh"}
                }
            }
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status":  "success",
            "case_id": str(case_id),
            "timeline": timeline_dict,
        },
    )


# =========================================================================== #
#  CONTRADICTION DETECTION ENDPOINT                                            #
# =========================================================================== #

@router.post(
    "/contradictions",
    summary="Detect contradictions between timeline events and statements",
    description=(
        "Accepts a list of raw event dicts (from a previously built timeline) "
        "and a block of witness/suspect statement text, then returns all detected "
        "factual contradictions with severity ratings and resolution guidance."
    ),
    status_code=status.HTTP_200_OK,
)
async def detect_contradictions_endpoint(
    case_id:         UUID          = Query(..., description="Case UUID for context"),
    statements_file: UploadFile    = File(..., description="Witness/suspect statements as plain text"),
) -> JSONResponse:
    """
    Contradiction detection pipeline:

    1. Load the stored timeline for case_id.
    2. Read the uploaded statements file.
    3. Call timeline_service.detect_timeline_contradictions().
    4. Return structured contradiction list with severity and resolution guidance.
    """

    # ── Load stored timeline ─────────────────────────────────────────────── #
    timeline_dict = _TIMELINE_STORE.get(str(case_id))
    if not timeline_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No timeline found for case_id '{case_id}'. "
                "Run POST /correlate/timeline first."
            ),
        )

    raw_events: list[dict] = timeline_dict.get("events", [])
    if not raw_events:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stored timeline contains no events.",
        )

    # ── Read statements file ─────────────────────────────────────────────── #
    statements_text = await _read_upload_text(statements_file, max_chars=15_000)

    # ── Run contradiction detection ──────────────────────────────────────── #
    try:
        contradictions = await detect_timeline_contradictions(
            events          = raw_events,
            statements_text = statements_text,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Contradiction detection service error: {exc}",
        )

    # Count by severity
    severity_counts = {"minor": 0, "moderate": 0, "major": 0}
    for c in contradictions:
        sev = c.get("severity", "minor").lower()
        if sev in severity_counts:
            severity_counts[sev] += 1

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status":              "success",
            "case_id":             str(case_id),
            "total_contradictions": len(contradictions),
            "severity_breakdown":  severity_counts,
            "contradictions":      contradictions,
            "analysed_at":         _utcnow().isoformat(),
        },
    )


# =========================================================================== #
#  KNOWLEDGE GRAPH ENDPOINTS                                                   #
# =========================================================================== #

@router.post(
    "/graph",
    summary="Extract entities and build a forensic knowledge graph",
    description=(
        "Upload one or more plain-text evidence files. The service extracts "
        "named entities (persons, locations, weapons, vehicles, etc.) and their "
        "relationships from each file, merges the results, and builds a complete "
        "EntityGraphResponse.\n\n"
        "The graph is stored internally and can be retrieved via "
        "GET /correlate/graph/{case_id}. "
        "A pyvis-rendered HTML visualisation is available at "
        "GET /correlate/graph/{case_id}/html."
    ),
    status_code=status.HTTP_200_OK,
)
async def build_knowledge_graph_endpoint(
    files:   list[UploadFile] = File(
        ...,
        description="One or more plain-text evidence files"
    ),
    case_id: UUID             = Query(..., description="Parent case UUID"),
    context: Optional[str]   = Query(
        None,
        description="Brief case context for the LLM (max 500 chars)",
        max_length=500,
    ),
) -> JSONResponse:
    """
    Knowledge graph construction pipeline:

    1. Read and decode each uploaded file.
    2. Extract entities and relationships from each file via graph_service.
    3. Merge all extractions and call build_entity_graph() to synthesise.
    4. Store the graph and return a summary response.
    """

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided.",
        )

    t0 = time.perf_counter()

    # ── 1. Read all files ─────────────────────────────────────────────────── #
    text_parts: list[tuple[str, str]] = []   # (filename, text)
    read_errors: list[dict] = []

    for file in files:
        try:
            text = await _read_upload_text(file)
            text_parts.append((file.filename or "unknown", text))
        except HTTPException as exc:
            read_errors.append({"filename": file.filename, "error": exc.detail})

    if not text_parts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "No readable text found in uploaded files.",
                    "errors":  read_errors},
        )

    # ── 2. Extract entities from each source ──────────────────────────────── #
    all_entities:      list[dict[str, Any]] = []
    all_relationships: list[dict[str, Any]] = []
    extraction_errors: list[dict] = []

    for filename, text in text_parts:
        try:
            entities, relationships = await extract_entities(text)
            all_entities.extend(entities)
            all_relationships.extend(relationships)
        except Exception as exc:
            extraction_errors.append({"source": filename, "error": str(exc)})

    if not all_entities:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "No entities could be extracted from the uploaded files.",
                "extraction_errors": extraction_errors,
                "tip": "Ensure files contain named persons, places, or objects.",
            },
        )

    # ── 3. Build the knowledge graph ──────────────────────────────────────── #
    try:
        graph: EntityGraphResponse = await build_entity_graph(
            entities_raw      = all_entities,
            relationships_raw = all_relationships,
            case_id           = case_id,
            context           = context or "",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Knowledge graph construction failed: {exc}",
        )

    # ── 4. Store and return ────────────────────────────────────────────────── #
    graph_dict = graph.model_dump(mode="json")
    _GRAPH_STORE[str(case_id)] = graph_dict

    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status":             "success",
            "case_id":            str(case_id),
            "entity_count":       graph.entity_count,
            "relationship_count": graph.relationship_count,
            "central_entities":   len(graph.central_entities),
            "suspect_entities":   len(graph.suspect_entities),
            "sources_processed":  len(text_parts),
            "extraction_errors":  extraction_errors,
            "wall_time_ms":       elapsed_ms,
            "graph": {
                "analysis_id":       str(graph.analysis_id),
                "entity_count":      graph.entity_count,
                "relationship_count":graph.relationship_count,
                "narrative_summary": graph.narrative_summary,
                "central_entities":  [str(uid) for uid in graph.central_entities],
                "suspect_entities":  [str(uid) for uid in graph.suspect_entities],
            },
        },
    )


# --------------------------------------------------------------------------- #

@router.get(
    "/graph/{case_id}",
    summary="Retrieve stored knowledge graph for a case",
    description=(
        "Retrieve the previously built entity relationship graph for the given "
        "case_id. Run POST /correlate/graph first to populate the store."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_knowledge_graph(case_id: UUID) -> JSONResponse:
    """Return the full cached EntityGraphResponse for a case, or professional demo fallback."""
    graph_dict = _GRAPH_STORE.get(str(case_id))
    
    if not graph_dict:
        # RETURN PROFESSIONAL MOCK GRAPH FOR DEMO
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "demo_mode",
                "case_id": str(case_id),
                "graph": {
                    "case_id": str(case_id),
                    "analysis_id": str(uuid4()),
                    "entity_count": 4,
                    "relationship_count": 3,
                    "entities": [
                        {"id": str(uuid4()), "label": "Vikram Singh (Victim)", "type": "person", "risk_score": 100},
                        {"id": str(uuid4()), "label": "Suresh Sharma", "type": "person", "risk_score": 15},
                        {"id": str(uuid4()), "label": "Assailant", "type": "person", "risk_score": 95},
                        {"id": str(uuid4()), "label": "Kitchen Knife", "type": "weapon", "risk_score": 90},
                        {"id": str(uuid4()), "label": "Greenwood Apartments", "type": "location", "risk_score": 50}
                    ],
                    "relationships": [
                        {"source": "Assailant", "target": "Vikram Singh (Victim)", "type": "attacked", "strength": 0.98},
                        {"source": "Suresh Sharma", "target": "Vikram Singh (Victim)", "type": "discovered", "strength": 0.95},
                        {"source": "Kitchen Knife", "target": "Vikram Singh (Victim)", "type": "caused_injuries", "strength": 0.99},
                        {"source": "Vikram Singh (Victim)", "target": "Greenwood Apartments", "type": "resided_at", "strength": 0.99}
                    ],
                    "narrative_summary": "Knowledge constellation for DPFSL-2026-0581 identifying critical contact between victim and unknown assailant.",
                    "central_entities": [],
                    "suspect_entities": []
                }
            }
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status":  "success",
            "case_id": str(case_id),
            "graph":   graph_dict,
        },
    )


# --------------------------------------------------------------------------- #

@router.get(
    "/graph/{case_id}/html",
    summary="Get pyvis interactive graph visualisation",
    description=(
        "Returns a standalone pyvis-rendered HTML page containing an interactive "
        "force-directed graph of all entities and relationships for the case.\n\n"
        "• Node colour    → risk score (red = high, blue = low)\n"
        "• Node shape     → entity type (dot = person, square = location, …)\n"
        "• Node size      → degree (more connections = larger)\n"
        "• Edge thickness → relationship strength\n\n"
        "Embed in React via `<iframe>` or serve as a static page."
    ),
    response_class=HTMLResponse,
    status_code=status.HTTP_200_OK,
)
async def get_graph_html(case_id: UUID) -> HTMLResponse:
    """Render and return the pyvis interactive HTML graph for a case."""
    graph_dict = _GRAPH_STORE.get(str(case_id))
    if not graph_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No graph found for case_id '{case_id}'. "
                "Run POST /correlate/graph first."
            ),
        )

    # Reconstruct EntityGraphResponse from the stored dict
    try:
        graph_response = EntityGraphResponse(**graph_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not deserialise stored graph: {exc}",
        )

    # Render pyvis HTML
    try:
        html_content = render_graph_html(graph_response)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph rendering failed: {exc}",
        )

    return HTMLResponse(content=html_content, status_code=200)


# --------------------------------------------------------------------------- #

@router.get(
    "/graph/{case_id}/metrics",
    summary="Compute NetworkX graph metrics for a case graph",
    description=(
        "Computes graph-theoretic metrics on the stored entity graph:\n\n"
        "• **degree_centrality** — how connected each node is (normalised)\n"
        "• **betweenness_centrality** — how often a node bridges paths between others\n"
        "• **pagerank** — recursive influence / importance score\n"
        "• **in/out_degree** — directional edge counts per node\n"
        "• **density** — ratio of actual to possible edges in the graph\n"
        "• **strongly_connected_components** — groups of mutually reachable nodes\n"
        "• **top_5_by_betweenness** — the 5 most 'bridging' entities by label\n\n"
        "High betweenness centrality often indicates key intermediaries (e.g. "
        "a fixer, a broker, or a location that connects otherwise separate groups)."
    ),
    status_code=status.HTTP_200_OK,
)
async def get_graph_metrics(case_id: UUID) -> JSONResponse:
    """Run NetworkX metrics on the stored graph and return the results."""
    graph_dict = _GRAPH_STORE.get(str(case_id))
    if not graph_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No graph found for case_id '{case_id}'. "
                "Run POST /correlate/graph first."
            ),
        )

    try:
        graph_response = EntityGraphResponse(**graph_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not deserialise stored graph: {exc}",
        )

    try:
        metrics = compute_graph_metrics(graph_response)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Metric computation failed: {exc}",
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status":  "success",
            "case_id": str(case_id),
            "metrics": metrics,
            "computed_at": _utcnow().isoformat(),
        },
    )


# =========================================================================== #
#  TIMELINE VALIDATION ENDPOINT                                                 #
# =========================================================================== #

@router.post(
    "/validate-timeline",
    summary="Apply hard forensic ordering constraints to a timeline",
    description=(
        "Apply rule-based forensic ordering validations to the stored timeline "
        "for a case.  Checks for impossible event orderings such as:\n\n"
        "• Death before injury_inflicted\n"
        "• Discovery before death\n"
        "• Autopsy before discovery\n"
        "• Police arrival before discovery\n\n"
        "Returns a list of ordering violations. An empty list means no violations "
        "were detected under the available evidence."
    ),
    status_code=status.HTTP_200_OK,
)
async def validate_timeline_endpoint(
    case_id: UUID = Query(..., description="Case UUID whose timeline should be validated"),
) -> JSONResponse:
    """Run hard-constraint ordering validation on the stored timeline."""
    timeline_dict = _TIMELINE_STORE.get(str(case_id))
    if not timeline_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No timeline found for case_id '{case_id}'. "
                "Run POST /correlate/timeline first."
            ),
        )

    try:
        timeline = TimelineResponse(**timeline_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not deserialise stored timeline: {exc}",
        )

    violations = validate_event_ordering(timeline.events)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status":              "success",
            "case_id":             str(case_id),
            "violations_found":    len(violations),
            "ordering_violations": violations,
            "validated_at":        _utcnow().isoformat(),
            "note": (
                "Violations indicate events that are physically or forensically "
                "impossible given the recorded timestamps. Review source evidence "
                "for data entry errors or deliberate falsification."
            ) if violations else "No ordering violations detected.",
        },
    )
