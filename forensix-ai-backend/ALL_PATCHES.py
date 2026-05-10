# =============================================================================
# FORENSIX AI — EMERGENCY PATCHES  (2026-05-10)
# =============================================================================
# Apply all 4 patches below. Each section says exactly what file to edit
# and what to find/replace. Do NOT paste this entire file — only paste the
# relevant code blocks into their target files.
# =============================================================================


# =============================================================================
# PATCH 1 — app/services/llm_service.py
# FIX: NameError: name '_build_response' is not defined
# =============================================================================
#
# INSTRUCTION:
#   Open app/services/llm_service.py
#   Find the line:
#       def _ollama_url() -> str:
#           return f"{_settings().OLLAMA_BASE_URL}/api/generate"
#
#   Paste the function below IMMEDIATELY AFTER _ollama_url().
# -----------------------------------------------------------------------------

def _build_response(response_text: str, usage: dict) -> dict:
    """
    Build the standard response envelope returned by get_llm_response().

    Returns
    -------
    dict with keys:
        "response"   : str  — raw model output text
        "model"      : str  — model tag that produced the response
        "provider"   : str  — "ollama", "groq", or "featherless"
        "usage"      : dict — token counts and latency
        "confidence" : None — reserved for downstream enrichment
    """
    return {
        "response":   response_text,
        "model":      usage.get("model", "unknown"),
        "provider":   usage.get("provider", "unknown"),
        "usage":      usage,
        "confidence": None,
    }


# =============================================================================
# PATCH 2 — app/services/graph_service.py
# FIX: 422 on POST /correlate/graph — Ollama llama3 not found
# =============================================================================
#
# INSTRUCTION:
#   Open app/services/graph_service.py
#
#   Step A) Add this import at the top (after existing imports):
#       from app.services.llm_service import get_llm_response
#
#   Step B) Replace the body of _llm_extract_entities_chunk() with:

async def _llm_extract_entities_chunk(
    source_text: str,
    model: str,
) -> tuple[list[dict], list[dict], int]:
    import time as _time
    prompt = _EXTRACT_ENTITIES_PROMPT.format(text=source_text)
    t0 = _time.perf_counter()
    resp = await get_llm_response(
        prompt=prompt,
        system_prompt=_GRAPH_SYSTEM_PROMPT,
        temperature=0.05,
        max_tokens=5000,
        provider="auto",
    )
    inference_ms = round((_time.perf_counter() - t0) * 1000)
    response_text = resp.get("response", "")
    try:
        parsed = _extract_json_block(response_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Entity extraction JSON parse failure: %s", exc)
        raise ValueError(
            f"LLM did not return valid JSON for entity extraction.\n"
            f"Raw response (first 400 chars):\n{response_text[:400]}"
        ) from exc
    entities = parsed.get("entities", [])
    relationships = parsed.get("relationships", [])
    return entities, relationships, inference_ms

#
#   Step C) Inside build_entity_graph(), replace the nested _llm_graph_merge() with:

        async def _llm_graph_merge(m: str) -> tuple[dict, int]:
            import time as _time
            t0 = _time.perf_counter()
            resp = await get_llm_response(
                prompt=prompt,
                system_prompt=_GRAPH_SYSTEM_PROMPT,
                temperature=0.05,
                max_tokens=6000,
                provider="auto",
            )
            inference_ms = round((_time.perf_counter() - t0) * 1000)
            response_text = resp.get("response", "")
            try:
                parsed = _extract_json_block(response_text)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.error("Graph build JSON parse failure: %s", exc)
                raise ValueError(
                    f"LLM did not return valid JSON for graph construction.\n"
                    f"Raw response (first 400 chars):\n{response_text[:400]}"
                ) from exc
            return parsed, inference_ms


# =============================================================================
# PATCH 3 — app/routers/analysis.py
# FIX: GET /analyze/combined returns 404 when no analyses run yet
# =============================================================================
#
# INSTRUCTION:
#   Open app/routers/analysis.py
#   Find the async def get_combined_analysis() function.
#   Find this block near the top of the function (after the stored = ... line):
#
#       if not stored:
#           raise HTTPException(
#               status_code=status.HTTP_404_NOT_FOUND,
#               detail=(
#                   f"No analysis data found for case_id '{case_id}'. "
#                   "Run POST /analyze/report, /analyze/time-of-death, or "
#                   "/analyze/images first."
#               ),
#           )
#
#   REPLACE that entire if block with:

    if not stored:
        # Return a structured empty response instead of 404
        # so the frontend dashboard loads without errors.
        from app.schemas.analysis import ForensicAnalysisResponse, AIModelMeta, ConfidenceScore
        return ForensicAnalysisResponse(
            case_id=case_id,
            analysed_at=_utcnow(),
            key_findings=[],
            primary_hypothesis="No analysis data yet. Run report upload and analysis endpoints first.",
            alternative_hypotheses=[],
            recommended_next_steps=[
                "Upload a forensic report via POST /api/v1/upload/report",
                "Run POST /api/v1/analyze/report with the uploaded file",
                "Run POST /api/v1/correlate/timeline to build event timeline",
                "Run POST /api/v1/risk/full for risk analysis",
            ],
            analyses_completed=[],
            analyses_pending=[
                "autopsy_report", "time_of_death", "image_analyses",
                "toxicology", "wound_analysis", "risk_score",
                "entity_graph", "geospatial",
            ],
            overall_confidence=ConfidenceScore.from_float(0.0),
            evidence_gaps=["No evidence has been analysed yet."],
            executive_summary=(
                "No analysis data has been collected for this case yet. "
                "Please upload evidence documents and run the analysis endpoints "
                "to populate the forensic workspace."
            ),
            model_meta=_make_model_meta(model_name="none", inference_ms=0),
        )


# =============================================================================
# PATCH 4 — Konva warning (frontend) — OPTIONAL, low priority
# FIX: "Stage has 6 layers" warning in browser console
# =============================================================================
#
# This is just a warning, not an error. No action needed for the evaluation.
# If you want to suppress it: consolidate your Konva layers in BodyMapStage.tsx
# so you have ≤4 layers. Wrap related components in <Layer> groups instead of
# using a separate <Layer> per component.
#
# =============================================================================
# SUMMARY OF WHAT EACH PATCH FIXES
# =============================================================================
#
# PATCH 1 → Fixes 500 on POST /assistant/chat
#            Fixes "Risk score LLM/parse failed: name '_build_response' is not defined"
#            Fixes "build_timeline failed: name '_build_response' is not defined"
#            Fixes "Lead recommendations LLM/parse failed: name '_build_response' is not defined"
#
# PATCH 2 → Fixes 422 on POST /correlate/graph
#            (Ollama 'llama3' not found — now routes through Groq like everything else)
#
# PATCH 3 → Fixes 404 on GET /analyze/combined
#            (now returns empty-but-valid response when no analyses have run yet)
#
# After applying patches, restart the server:
#   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
