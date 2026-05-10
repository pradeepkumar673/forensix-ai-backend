"""
PATCH: Add this function to app/services/llm_service.py

Find the line that starts "_extract_json_block" function definition (around line 7432)
and INSERT the _build_response function ABOVE it (or anywhere before get_llm_response).

The simplest fix: add it right after the _settings() and _ollama_url() helpers.
Look for this block:

    def _ollama_url() -> str:
        return f"{_settings().OLLAMA_BASE_URL}/api/generate"

And add the function right AFTER it.
"""

# ============================================================
# MISSING FUNCTION — paste this into llm_service.py
# Place it right after _ollama_url() definition (~line 7429)
# ============================================================

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
