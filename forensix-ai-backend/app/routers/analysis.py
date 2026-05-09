"""
app/routers/analysis.py
-----------------------
Forensic analysis endpoints for the Forensix AI backend.

Endpoints:
  POST /analyze/report          → Parse & analyse an autopsy / forensic PDF report
  POST /analyze/time-of-death   → Estimate time of death from physical observations
  POST /analyze/images          → Analyse one or more crime-scene / evidence images
  GET  /analyze/combined        → Return aggregated ForensicAnalysisResponse for a case

All heavy lifting is delegated to:
  • app.services.llm_service      — LLM prompting via Ollama
  • app.services.document_service — PDF / text extraction
  • app.services.vision_service   — Vision-model image analysis
"""

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse

# ── Internal services ──────────────────────────────────────────────────────── #
from app.services.document_service import (
    extract_text_from_pdf,
    clean_text,
)
from app.services.llm_service import (
    get_structured_analysis,
    analyze_time_of_death,
)
from app.services.vision_service import analyze_image
import docx

def _read_docx(file_path: str) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as exc:
        raise RuntimeError(f"DOCX extraction failed: {exc}")

# ── Schemas ────────────────────────────────────────────────────────────────── #
from app.schemas.analysis import (
    AutopsyReportResponse,
    AutopsyExternalExam,
    AutopsyInternalExam,
    TimeOfDeathRequest,
    TimeOfDeathResponse,
    TimeOfDeathEstimate,
    TimeOfDeathMethod,
    ImageAnalysisResponse,
    ForensicAnalysisResponse,
    ConfidenceScore,
    AIModelMeta,
    DateTimeRange,
    Finding,
    Severity,
)

# --------------------------------------------------------------------------- #
# Router                                                                        #
# --------------------------------------------------------------------------- #

router = APIRouter(
    prefix="/analyze",
    tags=["Analysis"],
)

# --------------------------------------------------------------------------- #
# Constants                                                                     #
# --------------------------------------------------------------------------- #

# Temporary directory for files uploaded directly to analysis endpoints
_ANALYSIS_UPLOAD_DIR = Path("uploads") / "analysis_temp"
_ANALYSIS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed MIME types for report uploads
_REPORT_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# Allowed MIME types for image uploads
_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/bmp",
    "image/webp",
}

# --------------------------------------------------------------------------- #
# Shared helpers                                                                #
# --------------------------------------------------------------------------- #

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_confidence(score: float) -> ConfidenceScore:
    """Wrap a raw float in a ConfidenceScore schema object."""
    return ConfidenceScore.from_float(score)


def _make_model_meta(model_name: str, inference_ms: int) -> AIModelMeta:
    return AIModelMeta(model_name=model_name, inference_ms=inference_ms)


async def _save_temp_file(file: UploadFile) -> Path:
    """
    Persist an UploadFile to the analysis temp directory.
    Returns the saved Path.
    """
    contents  = await file.read()
    safe_name = f"{uuid.uuid4().hex[:8]}_{Path(file.filename or 'unknown').name}"
    dest      = _ANALYSIS_UPLOAD_DIR / safe_name
    dest.write_bytes(contents)
    return dest


# --------------------------------------------------------------------------- #
# POST /analyze/report                                                          #
# --------------------------------------------------------------------------- #

@router.post(
    "/report",
    summary="Analyse a forensic / autopsy report",
    description=(
        "Upload a PDF, DOCX, or TXT forensic report. The service extracts text, "
        "runs the LLM structured-analysis pipeline, and returns a detailed "
        "AutopsyReportResponse containing parsed findings, cause of death, "
        "toxicology summary, and AI extraction confidence."
    ),
    status_code=status.HTTP_200_OK,
    response_model=AutopsyReportResponse,
)
async def analyze_report(
    file:    UploadFile = File(..., description="Forensic / autopsy report (PDF, DOCX, TXT)"),
    case_id: UUID       = Query(..., description="Parent case UUID this report belongs to"),
) -> AutopsyReportResponse:
    """
    Forensic report analysis pipeline:

    1. Validate file type.
    2. Extract raw text via document_service.
    3. Clean and normalise the text.
    4. Call llm_service.get_structured_analysis() to parse the report.
    5. Map the LLM output onto AutopsyReportResponse fields.
    6. Return the structured response.
    """

    # ── 1. Validate MIME type ─────────────────────────────────────────────── #
    if file.content_type not in _REPORT_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{file.content_type}'. "
                f"Accepted: {sorted(_REPORT_MIME_TYPES)}"
            ),
        )

    # ── 2. Save temporarily & extract text ───────────────────────────────── #
    t0 = time.perf_counter()
    try:
        temp_path = await _save_temp_file(file)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {exc}",
        )

    try:
        if file.content_type == "application/pdf":
            raw_text = (await extract_text_from_pdf(str(temp_path))).full_text
        elif file.content_type in ("application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
            raw_text = _read_docx(str(temp_path))
        else:
            # TXT — read raw
            raw_text = temp_path.read_text(errors="replace")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Text extraction failed: {exc}",
        )

    # ── 3. Clean text ─────────────────────────────────────────────────────── #
    cleaned_text = clean_text(raw_text)

    if not cleaned_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No readable text could be extracted from the uploaded file.",
        )

    # ── 4. LLM structured analysis ─────────────────────────────────────────── #
    try:
        llm_result: dict[str, Any] = await get_structured_analysis(cleaned_text)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM analysis service error: {exc}",
        )

    inference_ms = round((time.perf_counter() - t0) * 1000)

    # ── 5. Map LLM output → schema ─────────────────────────────────────────── #
    # get_structured_analysis returns a dict; keys may vary by prompt design.
    # Gracefully fall back to empty / None for missing keys.

    # External exam
    external_exam = AutopsyExternalExam(
        height_cm         = llm_result.get("height_cm"),
        weight_kg         = llm_result.get("weight_kg"),
        body_condition    = llm_result.get("body_condition"),
        skin_colour       = llm_result.get("skin_colour"),
        identifying_marks = llm_result.get("identifying_marks", []),
        external_injuries = [
            Finding(
                category    = inj.get("category", "injury"),
                description = inj.get("description", ""),
                severity    = Severity(inj.get("severity", "none")),
                confidence  = _make_confidence(inj.get("confidence", 0.6)),
                tags        = inj.get("tags", []),
            )
            for inj in llm_result.get("external_injuries", [])
        ],
    )

    # Internal exam
    internal_exam = AutopsyInternalExam(
        cause_of_death_primary   = llm_result.get("cause_of_death_primary"),
        cause_of_death_secondary = llm_result.get("cause_of_death_secondary"),
        manner_of_death          = llm_result.get("manner_of_death"),
        cardiovascular_findings  = llm_result.get("cardiovascular_findings", []),
        respiratory_findings     = llm_result.get("respiratory_findings", []),
        neurological_findings    = llm_result.get("neurological_findings", []),
        gastrointestinal_findings= llm_result.get("gastrointestinal_findings", []),
        musculoskeletal_findings = llm_result.get("musculoskeletal_findings", []),
        other_organ_findings     = llm_result.get("other_organ_findings", []),
        internal_injuries        = [
            Finding(
                category    = inj.get("category", "injury"),
                description = inj.get("description", ""),
                severity    = Severity(inj.get("severity", "none")),
                confidence  = _make_confidence(inj.get("confidence", 0.6)),
            )
            for inj in llm_result.get("internal_injuries", [])
        ],
    )

    # ── 6. Build & return response ─────────────────────────────────────────── #
    return AutopsyReportResponse(
        case_id          = case_id,
        report_number    = llm_result.get("report_number"),
        pathologist_name = llm_result.get("pathologist_name"),
        autopsy_date     = llm_result.get("autopsy_date"),
        report_date      = llm_result.get("report_date"),
        facility         = llm_result.get("facility"),

        external_exam    = external_exam,
        internal_exam    = internal_exam,

        toxicology_summary           = llm_result.get("toxicology_summary"),
        cause_of_death               = llm_result.get("cause_of_death_primary"),
        manner_of_death              = llm_result.get("manner_of_death"),
        contributing_conditions      = llm_result.get("contributing_conditions", []),
        estimated_survival_interval  = llm_result.get("estimated_survival_interval"),

        extraction_confidence = _make_confidence(
            llm_result.get("extraction_confidence", 0.65)
        ),
        unextracted_sections = llm_result.get("unextracted_sections", []),
        raw_text_snippet     = cleaned_text[:1024],

        model_meta = _make_model_meta(
            model_name   = llm_result.get("_model", "qwen3:14b"),
            inference_ms = inference_ms,
        ),
    )


# --------------------------------------------------------------------------- #
# POST /analyze/time-of-death                                                   #
# --------------------------------------------------------------------------- #

@router.post(
    "/time-of-death",
    summary="Estimate time of death from physical observations",
    description=(
        "Accept structured physical-observation data (rigor mortis, livor mortis, "
        "algor mortis, decomposition stage, stomach contents, entomology notes, "
        "and environmental context) and return a multi-method time-of-death "
        "estimate with per-method confidence scores and a combined window."
    ),
    status_code=status.HTTP_200_OK,
    response_model=TimeOfDeathResponse,
)
async def analyze_time_of_death_endpoint(
    payload: TimeOfDeathRequest,
) -> TimeOfDeathResponse:
    """
    Time-of-death estimation pipeline:

    1. Convert the Pydantic request to a plain dict for the LLM service.
    2. Call llm_service.analyze_time_of_death() which returns a structured dict.
    3. Build per-method TimeOfDeathEstimate objects.
    4. Compute the combined window across methods.
    5. Return the full TimeOfDeathResponse.
    """

    # ── 1. Prepare data dict ──────────────────────────────────────────────── #
    t0       = time.perf_counter()
    data_dict = payload.model_dump(mode="json", exclude_none=True)

    # ── 2. Call LLM service ────────────────────────────────────────────────── #
    try:
        tod_result: dict[str, Any] = await analyze_time_of_death(data_dict)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Time-of-death LLM service error: {exc}",
        )

    inference_ms = round((time.perf_counter() - t0) * 1000)

    # ── 3. Parse per-method estimates ─────────────────────────────────────── #
    method_estimates: list[TimeOfDeathEstimate] = []

    for method_dict in tod_result.get("method_estimates", []):
        try:
            method = TimeOfDeathMethod(method_dict.get("method", "combined"))
        except ValueError:
            method = TimeOfDeathMethod.COMBINED

        # Build the estimated window for this method
        earliest_str = method_dict.get("earliest")
        latest_str   = method_dict.get("latest")
        midpoint_str = method_dict.get("midpoint")

        try:
            estimated_window = DateTimeRange(
                earliest  = datetime.fromisoformat(earliest_str) if earliest_str else _utcnow(),
                latest    = datetime.fromisoformat(latest_str)   if latest_str   else _utcnow(),
                midpoint  = datetime.fromisoformat(midpoint_str) if midpoint_str else None,
                confidence= _make_confidence(method_dict.get("confidence", 0.5)),
                notes     = method_dict.get("notes"),
            )
        except Exception:
            # If ISO parse fails, leave a placeholder window
            estimated_window = DateTimeRange(
                earliest  = _utcnow(),
                latest    = _utcnow(),
                confidence= _make_confidence(0.1),
                notes     = "Window could not be parsed from LLM output",
            )

        method_estimates.append(
            TimeOfDeathEstimate(
                method                   = method,
                estimated_window         = estimated_window,
                method_specific_findings = method_dict.get("specific_findings", {}),
                confidence               = _make_confidence(method_dict.get("confidence", 0.5)),
                limitations              = method_dict.get("limitations", []),
            )
        )

    # ── 4. Build combined window ───────────────────────────────────────────── #
    combined_raw = tod_result.get("combined_window", {})
    earliest_str  = combined_raw.get("earliest")
    latest_str    = combined_raw.get("latest")
    midpoint_str  = combined_raw.get("midpoint")

    try:
        combined_window = DateTimeRange(
            earliest   = datetime.fromisoformat(earliest_str) if earliest_str else _utcnow(),
            latest     = datetime.fromisoformat(latest_str)   if latest_str   else _utcnow(),
            midpoint   = datetime.fromisoformat(midpoint_str) if midpoint_str else None,
            confidence = _make_confidence(tod_result.get("overall_confidence", 0.6)),
            notes      = combined_raw.get("notes"),
        )
    except Exception:
        combined_window = DateTimeRange(
            earliest   = _utcnow(),
            latest     = _utcnow(),
            confidence = _make_confidence(0.1),
            notes      = "Combined window could not be parsed",
        )

    # ── 5. Determine primary method ─────────────────────────────────────────── #
    raw_primary = tod_result.get("primary_method", "combined")
    try:
        primary_method = TimeOfDeathMethod(raw_primary)
    except ValueError:
        primary_method = TimeOfDeathMethod.COMBINED

    # ── 6. Return response ─────────────────────────────────────────────────── #
    return TimeOfDeathResponse(
        case_id            = payload.case_id,
        combined_window    = combined_window,
        overall_confidence = _make_confidence(
            tod_result.get("overall_confidence", 0.6)
        ),
        primary_method     = primary_method,
        method_estimates   = method_estimates,
        narrative_summary  = tod_result.get(
            "narrative_summary",
            "Time-of-death estimate generated from available forensic indicators.",
        ),
        caveats            = tod_result.get("caveats", []),
        model_meta         = _make_model_meta(
            model_name   = tod_result.get("_model", "qwen3:14b"),
            inference_ms = inference_ms,
        ),
    )


# --------------------------------------------------------------------------- #
# POST /analyze/images                                                          #
# --------------------------------------------------------------------------- #

@router.post(
    "/images",
    summary="Analyse crime-scene or evidence images",
    description=(
        "Upload one or more images (JPEG, PNG, TIFF, WEBP). Each image is "
        "individually analysed by the vision model for: detected objects, "
        "blood-spatter patterns, weapon indicators, body position, staging "
        "indicators, struggle evidence, and scene classification. "
        "Results for all images are returned as a list."
    ),
    status_code=status.HTTP_200_OK,
)
async def analyze_images(
    files:   List[UploadFile] = File(..., description="One or more evidence images"),
    case_id: UUID             = Query(..., description="Parent case UUID"),
    context: Optional[str]   = Query(
        None,
        description="Brief case context to pass to the vision model (max 500 chars)",
        max_length=500,
    ),
) -> JSONResponse:
    """
    Bulk image analysis pipeline:

    1. Validate each file's MIME type.
    2. Save files temporarily.
    3. For each image, call vision_service.analyze_crime_scene_image().
    4. Map the result dict to ImageAnalysisResponse.
    5. Return a list of all results, plus a per-image error report.
    """

    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image files provided.",
        )

    # Validate MIME types before doing any heavy work
    for f in files:
        if f.content_type not in _IMAGE_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    f"File '{f.filename}' has unsupported type '{f.content_type}'. "
                    f"Accepted: {sorted(_IMAGE_MIME_TYPES)}"
                ),
            )

    results: list[dict] = []
    errors:  list[dict] = []

    for file in files:
        t0 = time.perf_counter()
        try:
            # Save to temp location
            temp_path = await _save_temp_file(file)

            # Call vision service
            vision_result_obj = await analyze_image(
                source  = temp_path,
                context = context or "",
            )
            import dataclasses
            vision_result: dict[str, Any] = dataclasses.asdict(vision_result_obj)

            inference_ms = round((time.perf_counter() - t0) * 1000)

            # ── Map to ImageAnalysisResponse ──────────────────────────────── #
            from app.schemas.analysis import (
                DetectedObject,
                BloodSpatterPattern,
            )

            detected_objects = [
                DetectedObject(
                    label                 = obj.get("label", "unknown"),
                    confidence            = obj.get("confidence", 0.5),
                    bounding_box          = obj.get("bounding_box"),
                    forensic_significance = obj.get("forensic_significance"),
                )
                for obj in vision_result.get("detected_objects", [])
            ]

            blood_spatter = [
                BloodSpatterPattern(
                    pattern_type      = bp.get("pattern_type", "unknown"),
                    origin_estimate   = bp.get("origin_estimate"),
                    directionality    = bp.get("directionality"),
                    coverage_percent  = bp.get("coverage_percent"),
                    confidence        = _make_confidence(bp.get("confidence", 0.5)),
                )
                for bp in vision_result.get("blood_spatter", [])
            ]

            image_response = ImageAnalysisResponse(
                case_id               = case_id,
                image_width           = vision_result.get("image_width"),
                image_height          = vision_result.get("image_height"),
                image_format          = vision_result.get("image_format"),
                detected_objects      = detected_objects,
                blood_spatter         = blood_spatter,
                weapon_indicators     = vision_result.get("weapon_indicators", []),
                body_position         = vision_result.get("body_position"),
                environmental_cues    = vision_result.get("environmental_cues", []),
                scene_type            = vision_result.get("scene_type"),
                staging_indicators    = vision_result.get("staging_indicators", []),
                struggle_evidence     = vision_result.get("struggle_evidence", False),
                narrative_description = vision_result.get(
                    "narrative_description",
                    "No narrative generated.",
                ),
                overall_confidence    = _make_confidence(
                    vision_result.get("overall_confidence", 0.6)
                ),
                model_meta            = _make_model_meta(
                    model_name   = vision_result.get("_model", "llava"),
                    inference_ms = inference_ms,
                ),
            )

            results.append(image_response.model_dump(mode="json"))

        except HTTPException:
            raise
        except Exception as exc:
            errors.append({
                "filename": file.filename,
                "error":    str(exc),
            })

    if not results and errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "All image analyses failed.", "errors": errors},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status":        "success" if not errors else "partial",
            "case_id":       str(case_id),
            "total_images":  len(files),
            "analysed":      len(results),
            "failed":        len(errors),
            "results":       results,
            "errors":        errors,
            "analysed_at":   _utcnow().isoformat(),
        },
    )


# --------------------------------------------------------------------------- #
# GET /analyze/combined                                                         #
# --------------------------------------------------------------------------- #

@router.get(
    "/combined",
    summary="Get aggregated forensic analysis for a case",
    description=(
        "Retrieve the full ForensicAnalysisResponse for a given case_id. "
        "This endpoint aggregates all sub-analyses that have been completed "
        "(report, time-of-death, images, toxicology, wounds, etc.) and returns "
        "them in a single response together with an LLM-generated executive summary "
        "and primary investigative hypothesis.\n\n"
        "**Note:** Results are drawn from the in-memory analysis store. "
        "Run the individual POST endpoints first to populate the data."
    ),
    status_code=status.HTTP_200_OK,
    response_model=ForensicAnalysisResponse,
)
async def get_combined_analysis(
    case_id: UUID = Query(..., description="Case UUID to retrieve combined analysis for"),
) -> ForensicAnalysisResponse:
    """
    Combined (aggregated) analysis retrieval:

    1. Look up all completed sub-analyses for `case_id` in the in-memory store.
    2. Call the LLM to synthesise a cross-analysis executive summary and hypothesis.
    3. Return the full ForensicAnalysisResponse.

    In a production system, replace the in-memory store with a database lookup.
    """

    # ── 1. Retrieve sub-analyses from the in-memory store ────────────────── #
    stored = _ANALYSIS_STORE.get(str(case_id))

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No analysis data found for case_id '{case_id}'. "
                "Run POST /analyze/report, /analyze/time-of-death, or "
                "/analyze/images first."
            ),
        )

    # ── 2. Build context text for LLM synthesis ───────────────────────────── #
    context_parts: list[str] = []

    if stored.get("autopsy_report"):
        rpt = stored["autopsy_report"]
        context_parts.append(
            f"AUTOPSY REPORT:\n"
            f"  Cause of death: {rpt.get('cause_of_death', 'unknown')}\n"
            f"  Manner: {rpt.get('manner_of_death', 'unknown')}\n"
            f"  Toxicology: {rpt.get('toxicology_summary', 'not available')}"
        )

    if stored.get("time_of_death"):
        tod = stored["time_of_death"]
        context_parts.append(
            f"TIME OF DEATH:\n"
            f"  Narrative: {tod.get('narrative_summary', 'not available')}\n"
            f"  Primary method: {tod.get('primary_method', 'unknown')}"
        )

    if stored.get("image_analyses"):
        imgs = stored["image_analyses"]
        descs = [
            img.get("narrative_description", "")[:200]
            for img in imgs[:5]            # cap at 5 to avoid token overflow
        ]
        context_parts.append(
            f"IMAGE ANALYSES ({len(imgs)} image(s) analysed):\n"
            + "\n".join(f"  • {d}" for d in descs)
        )

    combined_context = "\n\n".join(context_parts) or "No detailed analysis available yet."

    # ── 3. LLM synthesis ──────────────────────────────────────────────────── #
    t0 = time.perf_counter()
    synthesis_prompt = (
        f"You are a senior forensic pathologist reviewing all available case evidence.\n\n"
        f"AVAILABLE ANALYSIS DATA:\n{combined_context}\n\n"
        f"Provide:\n"
        f"1. A concise primary investigative hypothesis (2-3 sentences).\n"
        f"2. 2-3 alternative hypotheses.\n"
        f"3. Top 5 key findings in order of forensic significance.\n"
        f"4. 3-5 recommended next steps for investigators.\n"
        f"5. Notable evidence gaps.\n"
        f"6. An executive summary (4-6 sentences, court-report quality).\n"
        f"Respond only in structured JSON."
    )

    try:
        synthesis: dict[str, Any] = await get_structured_analysis(synthesis_prompt)
    except Exception:
        # Fall back to minimal synthesis if LLM is unavailable
        synthesis = {
            "primary_hypothesis":       "Insufficient data for hypothesis at this stage.",
            "alternative_hypotheses":   [],
            "key_findings":             [],
            "recommended_next_steps":   ["Complete remaining analysis modules."],
            "evidence_gaps":            ["Full analysis not yet complete."],
            "executive_summary":        (
                "Partial forensic analysis is available. "
                "Additional analysis modules should be run to reach conclusions."
            ),
        }

    inference_ms = round((time.perf_counter() - t0) * 1000)

    # ── 4. Determine completeness ─────────────────────────────────────────── #
    all_modules   = [
        "autopsy_report", "time_of_death", "image_analyses",
        "toxicology", "wound_analysis", "risk_score",
        "entity_graph", "geospatial",
    ]
    completed = [m for m in all_modules if stored.get(m)]
    pending   = [m for m in all_modules if not stored.get(m)]

    # ── 5. Map key findings ───────────────────────────────────────────────── #
    key_findings: list[Finding] = []
    for kf in synthesis.get("key_findings", [])[:10]:
        if isinstance(kf, str):
            key_findings.append(
                Finding(
                    category    = "synthesised",
                    description = kf,
                    severity    = Severity.MODERATE,
                    confidence  = _make_confidence(0.65),
                )
            )
        elif isinstance(kf, dict):
            key_findings.append(
                Finding(
                    category    = kf.get("category", "synthesised"),
                    description = kf.get("description", ""),
                    severity    = Severity(kf.get("severity", "moderate")),
                    confidence  = _make_confidence(kf.get("confidence", 0.65)),
                    tags        = kf.get("tags", []),
                )
            )

    # Confidence scales with number of completed modules
    overall_confidence_score = min(0.3 + (len(completed) * 0.1), 0.95)

    # ── 6. Assemble ForensicAnalysisResponse ──────────────────────────────── #
    return ForensicAnalysisResponse(
        case_id              = case_id,
        analysed_at          = _utcnow(),

        # Sub-analysis references (raw dicts stored; full objects would require
        # a proper DB layer — use these as reference payloads for now)
        time_of_death        = stored.get("time_of_death"),
        autopsy_report       = stored.get("autopsy_report"),
        image_analyses       = stored.get("image_analyses", []),
        toxicology           = stored.get("toxicology"),
        wound_analysis       = stored.get("wound_analysis"),
        risk_score           = stored.get("risk_score"),
        entity_graph         = stored.get("entity_graph"),
        geospatial           = stored.get("geospatial"),

        # Synthesised findings
        key_findings             = key_findings,
        cause_of_death           = stored.get("autopsy_report", {}).get("cause_of_death"),
        manner_of_death          = stored.get("autopsy_report", {}).get("manner_of_death"),
        primary_hypothesis       = synthesis.get(
            "primary_hypothesis",
            "Hypothesis pending further analysis.",
        ),
        alternative_hypotheses   = synthesis.get("alternative_hypotheses", []),
        recommended_next_steps   = synthesis.get("recommended_next_steps", []),

        # Quality & completeness
        analyses_completed       = completed,
        analyses_pending         = pending,
        overall_confidence       = _make_confidence(overall_confidence_score),
        evidence_gaps            = synthesis.get("evidence_gaps", []),

        # Report
        executive_summary        = synthesis.get(
            "executive_summary",
            "Analysis in progress. Please run all sub-analysis endpoints.",
        ),
        model_meta               = _make_model_meta(
            model_name   = "qwen3:14b",
            inference_ms = inference_ms,
        ),
    )


# --------------------------------------------------------------------------- #
# In-memory analysis store                                                      #
#                                                                               #
# Maps case_id (str) → dict of sub-analysis results.                           #
# In production: replace with a database (PostgreSQL, MongoDB, Redis, etc.)    #
# The upload & individual analysis endpoints should call store_analysis_result  #
# after completing each sub-analysis.                                           #
# --------------------------------------------------------------------------- #

_ANALYSIS_STORE: dict[str, dict[str, Any]] = {}


def store_analysis_result(case_id: str, key: str, result: Any) -> None:
    """
    Persist a sub-analysis result in the in-memory store.

    Parameters
    ----------
    case_id : str   — UUID of the parent case (as string)
    key     : str   — Sub-analysis name, e.g. 'autopsy_report', 'time_of_death'
    result  : Any   — Serialisable analysis result (dict or list)

    Usage (call this from analysis endpoints after completing each run):
        from app.routers.analysis import store_analysis_result
        store_analysis_result(str(case_id), "autopsy_report", response.model_dump())
    """
    if case_id not in _ANALYSIS_STORE:
        _ANALYSIS_STORE[case_id] = {}
    _ANALYSIS_STORE[case_id][key] = result


# ===========================================================================
# Advanced Analysis Endpoints
# ===========================================================================

from app.services.audio_service import analyze_audio_stress, transcribe_audio
from app.services.vision_service import (
    analyze_wound_segmentation,
    analyze_pose_and_defensive_wounds,
    classify_wound_type_and_weapon,
    detect_image_tampering,
    detect_report_vs_image_inconsistencies
)
from app.schemas.analysis import (
    AudioAnalysisResponse, TranscriptionResponse, TamperingResponse,
    SegmentationResponse, PoseResponse, InconsistencyResponse
)

@router.post('/audio/stress', response_model=AudioAnalysisResponse)
async def api_analyze_audio_stress(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    result = await analyze_audio_stress(audio_bytes)
    return result

@router.post('/audio/transcribe', response_model=TranscriptionResponse)
async def api_transcribe_audio(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    result = await transcribe_audio(audio_bytes)
    return result

@router.post('/vision/segmentation', response_model=SegmentationResponse)
async def api_wound_segmentation(file: UploadFile = File(...)):
    image_bytes = await file.read()
    result = await analyze_wound_segmentation(image_bytes)
    return result

@router.post('/vision/pose', response_model=PoseResponse)
async def api_pose_estimation(file: UploadFile = File(...)):
    image_bytes = await file.read()
    result = await analyze_pose_and_defensive_wounds(image_bytes)
    return result

@router.post('/vision/tampering', response_model=TamperingResponse)
async def api_detect_tampering(file: UploadFile = File(...)):
    image_bytes = await file.read()
    result = await detect_image_tampering(image_bytes)
    return result

