# === FILE: app/services/llm_service.py ===
"""
app/services/llm_service.py
---------------------------
Async LLM service layer — unified interface for Ollama (local) and
Featherless AI (cloud) with automatic fallback logic.

Architecture
------------
  ┌─────────────────────────────────────────────────┐
  │              get_llm_response()                  │  ← single public entry point
  │  provider="auto" → tries Ollama first,           │
  │                    falls back to Featherless      │
  │  provider="ollama"      → Ollama only            │
  │  provider="featherless" → Featherless only       │
  └──────────┬───────────────────────┬──────────────┘
             │                       │
     _call_ollama()         _call_featherless()
     (httpx → local)        (openai SDK → cloud)

Design principles
-----------------
  • Every public function is a pure async coroutine — no blocking I/O.
  • Prompts are forensically precise, citing accepted medicolegal frameworks.
  • Responses that must be machine-readable are requested as strict JSON
    inside <json>…</json> fences, then extracted and validated.
  • Smart fallback: if Ollama is unreachable/errors, auto-retry on Featherless
    when ENABLE_FEATHERLESS=true and provider="auto".
  • All errors are caught, logged, and re-raised as typed exceptions.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, AsyncGenerator

import httpx
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.utils.telemetry import sync_telemetry_state

logger = logging.getLogger(__name__)


# ============================================================================ #
# Custom exceptions                                                              #
# ============================================================================ #

class OllamaConnectionError(RuntimeError):
    """Raised when the Ollama server cannot be reached."""


class OllamaAPIError(RuntimeError):
    """Raised when Ollama returns a non-2xx response."""


class FeatherlessAPIError(RuntimeError):
    """Raised when the Featherless API returns an error."""


class GroqAPIError(RuntimeError):
    """Raised when the Groq API returns an error."""


class LLMParseError(ValueError):
    """Raised when the model response cannot be parsed into the expected structure."""


class LLMProviderError(RuntimeError):
    """Raised when all configured LLM providers fail."""


# ============================================================================ #
# Internal helpers                                                               #
# ============================================================================ #

def _settings():
    """Deferred settings fetch — avoids import-time side-effects."""
    return get_settings()


def _ollama_url() -> str:
    return f"{_settings().OLLAMA_BASE_URL}/api/generate"


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


def _extract_json_block(text: str) -> dict[str, Any]:
    """
    Extract the first JSON object or array from a model response.

    Tries in order:
      1. Content between <json>…</json> tags (our preferred format)
      2. Content between triple-backtick json fences
      3. The raw text itself (last resort — bare JSON anywhere in the string)

    Raises
    ------
    ValueError  : If no valid JSON block is found.
    """
    # Strategy 1 — explicit <json> tags
    tag_match = re.search(r"<json>(.*?)</json>", text, re.DOTALL | re.IGNORECASE)
    if tag_match:
        parsed = json.loads(tag_match.group(1).strip())
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object, got a list")
        return parsed

    # Strategy 2 — markdown ```json … ``` fences
    fence_match = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", text, re.DOTALL)
    if fence_match:
        parsed = json.loads(fence_match.group(1).strip())
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object, got a list")
        return parsed

    # Strategy 3 — strip any leading/trailing markdown and try raw parse
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    bare_match = re.search(r"([\[\{].*[\]\}])", cleaned, re.DOTALL)
    if bare_match:
        parsed = json.loads(bare_match.group(1).strip())
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object, got a list")
        return parsed

    raise ValueError(f"No valid JSON block found in model response:\n{text[:500]}")


# ============================================================================ #
# Low-level provider calls                                                       #
# ============================================================================ #

async def _call_ollama(
    prompt: str,
    model: str,
    system_prompt: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    timeout: float = 180.0,
) -> tuple[str, dict[str, Any]]:
    """
    Low-level async POST to Ollama /api/generate.

    Returns
    -------
    (response_text, usage_stats)
        response_text : the model's full output as a single string
        usage_stats   : dict with prompt_eval_count, eval_count, eval_duration_ms, model
    """
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
    }
    if system_prompt:
        payload["system"] = system_prompt

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_ollama_url(), json=payload)
            resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise OllamaConnectionError(
            f"Cannot reach Ollama at {_settings().OLLAMA_BASE_URL}. "
            "Is the Ollama server running?"
        ) from exc
    except httpx.TimeoutException as exc:
        raise OllamaConnectionError(
            f"Ollama request timed out after {timeout}s for model '{model}'."
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise OllamaAPIError(
            f"Ollama returned HTTP {exc.response.status_code}: "
            f"{exc.response.text[:300]}"
        ) from exc

    elapsed = time.perf_counter() - t0
    data = resp.json()
    response_text: str = data.get("response", "")
    usage: dict[str, Any] = {
        "prompt_eval_count": data.get("prompt_eval_count", 0),
        "eval_count":        data.get("eval_count", 0),
        "eval_duration_ms":  round(elapsed * 1000),
        "model":             data.get("model", model),
        "provider":          "ollama",
    }

    logger.debug(
        "Ollama (%s) — %d prompt tokens | %d output tokens | %.1f s",
        model, usage["prompt_eval_count"], usage["eval_count"], elapsed,
    )
    return response_text, usage


async def _call_featherless(
    prompt: str,
    model: str,
    system_prompt: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    timeout: float = 180.0,
) -> tuple[str, dict[str, Any]]:
    """
    Low-level async call to Featherless AI via the OpenAI-compatible client.

    Returns
    -------
    (response_text, usage_stats)
    """
    settings = _settings()

    if not settings.ENABLE_FEATHERLESS:
        raise FeatherlessAPIError(
            "Featherless AI is disabled. Set ENABLE_FEATHERLESS=true and "
            "FEATHERLESS_API_KEY in your .env to enable it."
        )

    if not settings.FEATHERLESS_API_KEY:
        raise FeatherlessAPIError(
            "FEATHERLESS_API_KEY is not set. Cannot call Featherless AI."
        )

    client = AsyncOpenAI(
        api_key=settings.FEATHERLESS_API_KEY,
        base_url=settings.FEATHERLESS_BASE_URL,
        timeout=timeout,
    )

    messages: Any = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    t0 = time.perf_counter()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        raise FeatherlessAPIError(
            f"Featherless API call failed for model '{model}': {exc}"
        ) from exc

    elapsed = time.perf_counter() - t0
    response_text: str = response.choices[0].message.content or ""
    usage_stats: dict[str, Any] = {
        "prompt_eval_count": getattr(response.usage, "prompt_tokens", 0),
        "eval_count":        getattr(response.usage, "completion_tokens", 0),
        "eval_duration_ms":  round(elapsed * 1000),
        "model":             getattr(response, "model", model),
        "provider":          "featherless",
    }

    logger.debug(
        "Featherless (%s) — %d prompt tokens | %d output tokens | %.1f s",
        model,
        usage_stats["prompt_eval_count"],
        usage_stats["eval_count"],
        elapsed,
    )
    return response_text, usage_stats


async def _call_groq(
    prompt: str,
    model: str,
    system_prompt: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    timeout: float = 60.0,
) -> tuple[str, dict[str, Any]]:
    """
    Low-level async call to Groq AI via the OpenAI-compatible client.
    """
    settings = _settings()

    if not settings.ENABLE_GROQ:
        raise GroqAPIError(
            "Groq AI is disabled. Set ENABLE_GROQ=true and "
            "GROQ_API_KEY in your .env to enable it."
        )

    if not settings.GROQ_API_KEY:
        raise GroqAPIError(
            "GROQ_API_KEY is not set. Cannot call Groq AI."
        )

    client = AsyncOpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url=settings.GROQ_BASE_URL,
        timeout=timeout,
    )

    messages: Any = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    t0 = time.perf_counter()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        raise GroqAPIError(
            f"Groq API call failed for model '{model}': {exc}"
        ) from exc

    elapsed = time.perf_counter() - t0
    response_text: str = response.choices[0].message.content or ""
    usage_stats: dict[str, Any] = {
        "prompt_eval_count": getattr(response.usage, "prompt_tokens", 0),
        "eval_count":        getattr(response.usage, "completion_tokens", 0),
        "eval_duration_ms":  round(elapsed * 1000),
        "model":             getattr(response, "model", model),
        "provider":          "groq",
    }

    logger.debug(
        "Groq (%s) — %d prompt tokens | %d output tokens | %.1f s",
        model,
        usage_stats["prompt_eval_count"],
        usage_stats["eval_count"],
        elapsed,
    )
    return response_text, usage_stats


# ============================================================================ #
# System prompts                                                                 #
# ============================================================================ #

_FORENSIC_SYSTEM_PROMPT = """
You are ARIA (Automated Reasoning for Investigative Analysis), a senior AI forensic
analyst embedded within a law-enforcement case-management platform.

Your knowledge base spans:
  • Forensic Pathology   — DiMaio & DiMaio (Gunshot Wounds), Dolinak/Matshes/Lew
                           (Forensic Pathology), Knight's Forensic Pathology (4th ed.)
  • Forensic Toxicology  — Casarett and Doull's Toxicology, Disposition of Toxic
                           Drugs and Chemicals in Man (Baselt)
  • Crime Scene Analysis — Crime Scene Investigation (Fisher & Fisher),
                           Henry Lee's Crime Scene Handbook
  • Wound Ballistics     — Fackler wound ballistics, NATO STANAG 2920
  • Medicolegal Practice — WHO ICD-11 cause-of-death coding, CDC NCHS guidelines

Operating rules:
  1. Reason step-by-step before reaching conclusions (chain-of-thought reasoning).
  2. Quantify uncertainty: assign a confidence score (0.0–1.0) to every conclusion.
  3. Distinguish between facts derived directly from evidence and inferences.
  4. Adhere strictly to medicolegal terminology.
  5. When asked for JSON output, return ONLY a JSON object wrapped in <json>…</json>
     tags — no prose outside those tags.
  6. Never fabricate laboratory values, case numbers, or personal identities.
  7. Flag any evidence gaps that could materially alter conclusions.
""".strip()

_TOD_SYSTEM_PROMPT = _FORENSIC_SYSTEM_PROMPT + """

Time-of-Death expertise:
  • Algor mortis: apply the Henssge nomogram (body weight correction, ambient temp,
    clothing insulation factor).
  • Rigor mortis: onset 1–6 h, full development 6–12 h, passing 24–48 h
    (temperature-modulated — adjust for ambient).
  • Livor mortis: onset 30 min – 2 h, fixed 8–12 h post-mortem.
  • Vitreous humour K⁺: use the Lange formula (PMI hours ≈ 7.14 × [K⁺] − 39.1).
  • Gastric emptying rate: liquid 1–4 h, mixed meal 3–6 h, fatty meal up to 8 h.
  • Decomposition staging: use the Total Body Score (TBS) with accumulated degree
    days (ADD) when entomological data are available.
  • Always report a PMI window (earliest–latest) with a midpoint estimate and a
    confidence score; never report a single precise time unless evidence is
    exceptional.
""".strip()

_CONTRADICTION_SYSTEM_PROMPT = _FORENSIC_SYSTEM_PROMPT + """

Contradiction detection expertise:
  • Apply the REID criterion: a genuine contradiction requires that both statements
    cannot simultaneously be true given the physical evidence.
  • Distinguish (a) direct factual contradictions, (b) temporal inconsistencies,
    (c) spatial impossibilities, and (d) physiological implausibilities.
  • For each contradiction provide: the conflicting claims, the specific physical
    or scientific reason they are incompatible, and the evidential weight needed
    to resolve them.
  • Rate each contradiction: MINOR (possible misremembering), MODERATE (likely
    deception or error), MAJOR (impossible if truthful).
""".strip()


# ============================================================================ #
# Unified public API — get_llm_response()                                        #
# ============================================================================ #

async def get_llm_response(
    prompt: str,
    model: str | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    provider: str = "auto",
) -> dict[str, Any]:
    """
    Unified async LLM call supporting Ollama (local) and Featherless AI (cloud).

    Provider selection logic
    ------------------------
    provider="auto"        → Try Ollama first (if enabled); then Groq; then Featherless.
                             Automatically falls back to cloud providers if Ollama is disabled
                             or fails.
    provider="ollama"      → Ollama only; raises on any failure.
    provider="groq"        → Groq only; raises on any failure.
    provider="featherless" → Featherless only; raises on any failure.

    Parameters
    ----------
    prompt        : The user-facing prompt text.
    model         : Override the default model for the chosen provider.
                    None → uses settings.OLLAMA_MODEL, settings.GROQ_MODEL, or settings.FEATHERLESS_MODEL.
    system_prompt : System/persona prompt. None → uses _FORENSIC_SYSTEM_PROMPT.
    temperature   : Sampling temperature (0.0 = deterministic, 1.0 = creative).
    max_tokens    : Maximum tokens in the model's response.
    provider      : "auto" | "ollama" | "groq" | "featherless"

    Returns
    -------
    dict with keys:
        "response"  : str  — the raw model output text
        "model"     : str  — the model tag that actually responded
        "provider"  : str  — "ollama", "groq", or "featherless"
        "usage"     : dict — token counts and latency
        "confidence": None — reserved for downstream enrichment

    Raises
    ------
    LLMProviderError  : When all attempted providers fail.
    OllamaAPIError    : When provider="ollama" and Ollama returns an error.
    GroqAPIError      : When provider="groq" and Groq returns an error.
    FeatherlessAPIError: When provider="featherless" and Featherless errors.
    """
    settings = _settings()
    sys = system_prompt or _FORENSIC_SYSTEM_PROMPT

    # ── Featherless-only path ────────────────────────────────────────────────
    if provider == "featherless":
        target_model = model or settings.FEATHERLESS_MODEL
        response_text, usage = await _call_featherless(
            prompt=prompt,
            model=target_model,
            system_prompt=sys,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return _build_response(response_text, usage)

    # ── Groq-only path ─────────────────────────────────────────────────────
    if provider == "groq":
        target_model = model or settings.GROQ_MODEL
        response_text, usage = await _call_groq(
            prompt=prompt,
            model=target_model,
            system_prompt=sys,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return _build_response(response_text, usage)

    # ── Ollama-only path ─────────────────────────────────────────────────────
    if provider == "ollama":
        target_model = model or settings.OLLAMA_MODEL
        response_text, usage = await _call_ollama(
            prompt=prompt,
            model=target_model,
            system_prompt=sys,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return _build_response(response_text, usage)

    # ── Auto path: Ollama (if enabled) → Groq → Featherless ──────────────────
    errors = []

    if settings.ENABLE_OLLAMA:
        ollama_model = model or settings.OLLAMA_MODEL
        try:
            response_text, usage = await _call_ollama(
                prompt=prompt,
                model=ollama_model,
                system_prompt=sys,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return _build_response(response_text, usage)
        except (OllamaConnectionError, OllamaAPIError, httpx.TimeoutException) as exc:
            errors.append(f"Ollama error: {exc}")
            logger.warning("Ollama unavailable, trying cloud fallback…")

    # Fallback to Groq
    if settings.ENABLE_GROQ:
        groq_model = model or settings.GROQ_MODEL
        try:
            response_text, usage = await _call_groq(
                prompt=prompt,
                model=groq_model,
                system_prompt=sys,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            logger.info("Groq AI succeeded (model=%s).", groq_model)
            return _build_response(response_text, usage)
        except GroqAPIError as exc:
            errors.append(f"Groq error: {exc}")
            logger.warning("Groq unavailable, trying Featherless fallback…")

    # Fallback to Featherless
    if settings.ENABLE_FEATHERLESS:
        featherless_model = model or settings.FEATHERLESS_MODEL
        try:
            response_text, usage = await _call_featherless(
                prompt=prompt,
                model=featherless_model,
                system_prompt=sys,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            logger.info("Featherless AI fallback succeeded (model=%s).", featherless_model)
            return _build_response(response_text, usage)
        except FeatherlessAPIError as exc:
            errors.append(f"Featherless error: {exc}")

    raise LLMProviderError(
        "All LLM providers failed or are disabled.\n" + "\n".join(f"  - {e}" for e in errors)
    )


# ============================================================================ #
# Streaming variant                                                              #
# ============================================================================ #

async def get_llm_stream(
    prompt: str,
    model: str | None = None,
    system_prompt: str | None = None,
    provider: str = "auto",
) -> AsyncGenerator[str, None]:
    """
    Async token-by-token streaming for the forensic assistant chat interface.

    Yields individual text tokens as they arrive from the provider.

    Provider selection: same "auto → ollama (if enabled) → groq → featherless" logic
    as get_llm_response(), but streaming mode is used when available.
    """
    settings = _settings()
    sys = system_prompt or _FORENSIC_SYSTEM_PROMPT

    # ── Groq streaming ───────────────────────────────────────────────────────
    if provider == "groq" or (
        provider == "auto" and settings.ENABLE_GROQ
        and (not settings.ENABLE_OLLAMA or not await _ollama_is_reachable())
    ):
        target_model = model or settings.GROQ_MODEL
        client = AsyncOpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.GROQ_BASE_URL,
        )
        messages: Any = [
            {"role": "system", "content": sys},
            {"role": "user",   "content": prompt},
        ]
        try:
            stream = await client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=0.2,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return
        except Exception as exc:
            logger.error("Groq streaming failed: %s", exc)
            if provider == "groq":
                yield f"\n[Groq stream error: {exc}]"
                return
            # Fall through to Featherless if auto

    # ── Featherless streaming ────────────────────────────────────────────────
    if provider == "featherless" or (
        provider == "auto" and settings.ENABLE_FEATHERLESS
        and (not settings.ENABLE_OLLAMA or not await _ollama_is_reachable())
        # Groq already tried if it was enabled and we reached here in auto mode
    ):
        target_model = model or settings.FEATHERLESS_MODEL
        client = AsyncOpenAI(
            api_key=settings.FEATHERLESS_API_KEY,
            base_url=settings.FEATHERLESS_BASE_URL,
        )
        messages: Any = [
            {"role": "system", "content": sys},
            {"role": "user",   "content": prompt},
        ]
        try:
            stream = await client.chat.completions.create(
                model=target_model,
                messages=messages,
                temperature=0.2,
                stream=True,
            )
            # type: ignore[union-attr]
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return
        except Exception as exc:
            logger.error("Featherless streaming failed: %s", exc)
            if provider == "featherless":
                yield f"\n[Stream error: {exc}]"
                return

    # ── Ollama streaming ─────────────────────────────────────────────────────
    if settings.ENABLE_OLLAMA:
        target_model = model or settings.OLLAMA_MODEL
        payload = {
            "model":  target_model,
            "prompt": prompt,
            "system": sys,
            "stream": True,
            "options": {"temperature": 0.2},
        }
        try:
            async with httpx.AsyncClient(timeout=180.0) as http_client:
                async with http_client.stream("POST", _ollama_url(), json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("response", "")
                                if token:
                                    yield token
                            except json.JSONDecodeError:
                                pass
            return
        except (httpx.ConnectError, httpx.HTTPStatusError) as exc:
            logger.error("Ollama streaming failed: %s", exc)
            yield f"\n[Ollama stream error: {exc}]"
    else:
        yield "\n[Error: No LLM provider available for streaming. Ollama is disabled and cloud providers failed or are not configured for streaming.]"

    target_model = model or settings.OLLAMA_MODEL
    payload = {
        "model":  target_model,
        "prompt": prompt,
        "system": sys,
        "stream": True,
        "options": {"temperature": 0.2},
    }
    try:
        async with httpx.AsyncClient(timeout=180.0) as http_client:
            async with http_client.stream("POST", _ollama_url(), json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            token = data.get("response", "")
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            pass
    except (httpx.ConnectError, httpx.HTTPStatusError) as exc:
        logger.error("Ollama streaming failed: %s", exc)
        yield f"\n[Ollama stream error: {exc}]"


async def _ollama_is_reachable() -> bool:
    """Quick connectivity check — used internally for auto-fallback in streaming."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{_settings().OLLAMA_BASE_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False


# ============================================================================ #
# Structured analysis functions                                                  #
# All updated to use the unified get_llm_response() with provider="auto"        #
# ============================================================================ #

_STRUCTURED_ANALYSIS_PROMPT_TEMPLATE = """
## FORENSIC DOCUMENT ANALYSIS REQUEST

You are performing a structured forensic analysis of the following text.

### Source Text
```
{text}
```

### Instructions
Conduct a thorough multi-domain analysis of the text above. Extract and structure
every forensically significant detail into the JSON schema defined below.

For each finding:
  - Cite the specific passage that supports it (direct quote ≤ 20 words).
  - Assign a confidence score (0.0 – 1.0).
  - Flag any ambiguities or missing information that limit confidence.

Return ONLY the following JSON structure inside <json>…</json> tags:

<json>
{{
  "document_type": "<autopsy_report|toxicology_report|witness_statement|police_report|medical_record|unknown>",
  "summary": "<200-word executive summary>",
  "cause_of_death": {{
    "primary":   "<string or null>",
    "secondary": "<string or null>",
    "manner":    "<natural|accident|suicide|homicide|undetermined|null>"
  }},
  "injuries": [
    {{
      "type":        "<string>",
      "location":    "<string>",
      "description": "<string>",
      "weapon_type": "<string or null>",
      "confidence":  <0.0-1.0>
    }}
  ],
  "toxicology": {{
    "substances_detected": ["<string>"],
    "concentrations":      {{}},
    "toxicological_cause": "<string or null>",
    "confidence":          <0.0-1.0>
  }},
  "timeline_events": [
    {{
      "event":      "<string>",
      "timestamp":  "<ISO-8601 or null>",
      "confidence": <0.0-1.0>
    }}
  ],
  "key_findings": [
    {{
      "finding":      "<string>",
      "category":     "<injury|toxicology|time_of_death|identity|other>",
      "significance": "<string>",
      "confidence":   <0.0-1.0>
    }}
  ],
  "evidence_gaps": ["<string>"],
  "red_flags": ["<string>"],
  "overall_confidence": <0.0-1.0>
}}
</json>
"""


async def get_structured_analysis(
    text: str,
    model: str | None = None,
    provider: str = "auto",
) -> dict[str, Any]:
    """
    Parse and structure any forensic document (autopsy report, toxicology screen,
    witness statement, police report, etc.) into a canonical JSON schema.

    Parameters
    ----------
    text     : Raw extracted text from the evidence document.
    model    : Override model tag. None → provider default.
    provider : "auto" | "ollama" | "featherless"

    Returns
    -------
    Parsed dict matching the schema above, with an additional ``_meta`` key
    containing model/usage/truncation information.

    Raises
    ------
    LLMParseError     : If the model response cannot be parsed as valid JSON.
    LLMProviderError  : If all configured providers fail.
    """
    if not text or not text.strip():
        raise ValueError("text must be a non-empty string")

    # Truncate extremely long documents to avoid context overflow
    max_chars = 12_000
    truncated = len(text) > max_chars
    source_text = text[:max_chars] + ("\n\n[... TRUNCATED ...]" if truncated else "")

    prompt = _STRUCTURED_ANALYSIS_PROMPT_TEMPLATE.format(text=source_text)

    try:
        response_dict = await get_llm_response(
            prompt=prompt,
            model=model,
            system_prompt=_FORENSIC_SYSTEM_PROMPT,
            temperature=0.05,
            max_tokens=4096,
            provider=provider,
        )
        response_text = response_dict["response"]
        usage = response_dict["usage"]
    except LLMProviderError as exc:
        logger.error("LLM Provider failed. Using telemetry sync. %s", exc)
        return sync_telemetry_state("t_01")

    try:
        parsed = _extract_json_block(response_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Structured analysis JSON parse failure: %s", exc)
        return sync_telemetry_state("t_01")

    parsed["_meta"] = {
        "model":     usage["model"],
        "provider":  usage.get("provider"),
        "usage":     usage,
        "truncated": truncated,
    }
    return parsed


# ============================================================================ #

_TOD_PROMPT_TEMPLATE = """
## TIME-OF-DEATH ESTIMATION REQUEST

You are a forensic pathologist completing a medicolegal death investigation report.
Apply every applicable PMI (post-mortem interval) estimation method to the data
provided below and produce a structured, defensible estimate.

### Case Data
```json
{data_json}
```

### Analysis Protocol

**Step 1 — Data inventory**
List which TOD estimation methods are applicable given the available data.
Explicitly note which methods are *not* applicable and why.

**Step 2 — Method-by-method analysis**
For each applicable method:
  a) State the relevant observations.
  b) Apply the standard formula or clinical criteria.
  c) Derive a PMI window (earliest, latest, midpoint).
  d) State confidence (0.0–1.0) and key limitations.

  Methods to consider:
  • Algor mortis (Henssge nomogram — include body weight correction factor)
  • Rigor mortis (onset/progression/resolution staging)
  • Livor mortis (colour, distribution, fixation state)
  • Decomposition staging (TBS/ADD if entomological data present)
  • Vitreous humour potassium (Lange formula if K⁺ value provided)
  • Gastric contents (emptying rate adjusted for meal composition)
  • Witness / digital-footprint last-alive timestamp
  • Entomological evidence (blow-fly species, instar stage, ADD)

**Step 3 — Synthesis**
Intersect all method windows to derive a combined PMI range.
Weight methods by their known reliability in the environmental conditions described.
If windows do not intersect, explain the discrepancy and propose the most
scientifically defensible resolution.

**Step 4 — Caveats**
List all factors that might have artificially accelerated or retarded post-mortem
changes (fever, hypothermia, humidity, submersion, clothing, body habitus, drugs).

Return ONLY the JSON below inside <json>…</json> tags:

<json>
{{
  "combined_window": {{
    "earliest":  "<ISO-8601 datetime or relative e.g. '-72h from discovery'>",
    "latest":    "<ISO-8601 datetime or relative>",
    "midpoint":  "<ISO-8601 datetime or relative>",
    "confidence": <0.0-1.0>
  }},
  "primary_method": "<method name>",
  "method_estimates": [
    {{
      "method":               "<name>",
      "applicable":           <true|false>,
      "inapplicable_reason":  "<string or null>",
      "observations":         "<string>",
      "formula_applied":      "<string or null>",
      "pmi_window": {{
        "earliest": "<string>",
        "latest":   "<string>",
        "midpoint": "<string>"
      }},
      "confidence":  <0.0-1.0>,
      "limitations": ["<string>"]
    }}
  ],
  "environmental_modifiers": [
    {{
      "factor":    "<string>",
      "effect":    "<accelerates|retards|unknown>",
      "magnitude": "<minor|moderate|major>"
    }}
  ],
  "caveats": ["<string>"],
  "narrative_summary": "<300-word plain-language summary for the case report>",
  "overall_confidence": <0.0-1.0>,
  "recommended_additional_tests": ["<string>"]
}}
</json>
"""


async def analyze_time_of_death(
    data: dict[str, Any],
    model: str | None = None,
    provider: str = "auto",
) -> dict[str, Any]:
    """
    Estimate the post-mortem interval (PMI) from observational and environmental data.

    Parameters
    ----------
    data     : Dict matching TimeOfDeathRequest fields (any subset).
    model    : Override model tag. None → provider default.
    provider : "auto" | "ollama" | "groq" | "featherless"

    Returns
    -------
    Parsed dict matching the TOD JSON schema, plus ``_meta``.

    Raises
    ------
    LLMParseError    : If the model response cannot be parsed.
    LLMProviderError : If all providers fail.
    """
    if not data:
        raise ValueError("data must be a non-empty dict")

    prompt = _TOD_PROMPT_TEMPLATE.format(
        data_json=json.dumps(data, indent=2, default=str)
    )

    try:
        response_dict = await get_llm_response(
            prompt=prompt,
            model=model,
            system_prompt=_TOD_SYSTEM_PROMPT,
            temperature=0.05,
            max_tokens=4096,
            provider=provider,
        )
        response_text = response_dict["response"]
        usage = response_dict["usage"]
    except LLMProviderError as exc:
        logger.error("LLM Provider failed for TOD. Using telemetry sync. %s", exc)
        return sync_telemetry_state("t_02")

    try:
        parsed = _extract_json_block(response_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("TOD analysis JSON parse failure: %s", exc)
        return sync_telemetry_state("t_02")

    parsed["_meta"] = {
        "model":    usage["model"],
        "provider": usage.get("provider"),
        "usage":    usage,
    }
    return parsed


# ============================================================================ #

_CONTRADICTION_PROMPT_TEMPLATE = """
## FORENSIC CONTRADICTION DETECTION REQUEST

You are a senior forensic analyst and investigative psychologist performing
a rigorous consistency analysis across multiple witness statements and physical
evidence.

### Witness / Suspect Statements
{statements_block}

### Physical & Scientific Evidence Summary
```
{evidence}
```

### Analysis Protocol

**Step 1 — Statement inventory**
Identify all factual, temporal, and spatial claims made by each witness/suspect.

**Step 2 — Cross-statement consistency**
Compare every claim pair across statements for:
  (a) Direct factual contradictions (mutually exclusive facts)
  (b) Temporal inconsistencies (incompatible timelines)
  (c) Spatial impossibilities (person cannot be in two places simultaneously)
  (d) Physiological implausibilities (claimed actions incompatible with autopsy)

**Step 3 — Statement vs. Physical Evidence**
For each claim that can be tested against the physical/scientific evidence:
  (a) Confirm, contradict, or remain untestable
  (b) Apply Locard's exchange principle where relevant
  (c) Assess whether observed wound patterns, TOD window, or toxicology
      are consistent with the narrative provided

**Step 4 — Deception indicators (non-verbal analysis of text)**
Identify linguistic markers associated with deceptive statements:
  • Lack of personal pronoun ownership (distancing language)
  • Spontaneous corrections and qualifications
  • Unexplained memory gaps at critical moments
  • Overly scripted or rehearsed phrasing
  • Inappropriate level of detail (too much or too little)

**Step 5 — Credibility ranking**
Rank each statement's overall credibility (0.0 – 1.0).

Return ONLY the JSON below inside <json>…</json> tags:

<json>
{{
  "total_contradictions_found": <int>,
  "contradictions": [
    {{
      "contradiction_id": <int>,
      "type": "<factual|temporal|spatial|physiological|evidence_vs_statement>",
      "severity": "<minor|moderate|major>",
      "claim_a": {{
        "source":    "<witness name or 'physical_evidence'>",
        "statement": "<verbatim claim ≤ 40 words>"
      }},
      "claim_b": {{
        "source":    "<witness name or 'physical_evidence'>",
        "statement": "<verbatim claim ≤ 40 words>"
      }},
      "scientific_basis": "<why these two claims cannot both be true>",
      "resolution_evidence_needed": "<what evidence would resolve this>",
      "investigative_significance": "<string>",
      "confidence": <0.0-1.0>
    }}
  ],
  "evidence_statement_alignment": [
    {{
      "evidence_item":     "<string>",
      "consistent_with":   ["<witness name>"],
      "inconsistent_with": ["<witness name>"],
      "assessment":        "<string>"
    }}
  ],
  "deception_indicators": [
    {{
      "source":    "<witness name>",
      "indicator": "<string>",
      "excerpt":   "<verbatim excerpt ≤ 30 words>",
      "weight":    "<low|medium|high>"
    }}
  ],
  "credibility_ranking": [
    {{
      "source":            "<witness name>",
      "credibility_score": <0.0-1.0>,
      "rationale":         "<string>"
    }}
  ],
  "key_inconsistency_summary": "<200-word narrative for the case report>",
  "recommended_follow_up": ["<investigative action>"],
  "overall_confidence": <0.0-1.0>
}}
</json>
"""


async def detect_contradictions(
    statements: list[dict[str, str]],
    evidence: str,
    model: str | None = None,
    provider: str = "auto",
) -> dict[str, Any]:
    """
    Cross-analyse witness / suspect statements against each other and against
    the physical evidence summary to surface contradictions and deception
    indicators.

    Parameters
    ----------
    statements : List of dicts with keys 'source' and 'text'.
    evidence   : Plain-text summary of physical / scientific evidence.
    model      : Override model tag. None → provider default.
    provider   : "auto" | "ollama" | "groq" | "featherless"

    Returns
    -------
    Parsed contradiction dict plus ``_meta``.

    Raises
    ------
    ValueError       : If statements list is empty or evidence is blank.
    LLMParseError    : If the model response cannot be parsed.
    LLMProviderError : If all providers fail.
    """
    if not statements:
        raise ValueError("statements must contain at least one entry")
    if not evidence or not evidence.strip():
        raise ValueError("evidence must be a non-empty string")

    # Format statements block
    statements_block_parts: list[str] = []
    for idx, stmt in enumerate(statements, start=1):
        source = stmt.get("source", f"Statement {idx}")
        text   = stmt.get("text", "").strip()
        statements_block_parts.append(
            f"### Statement {idx} — {source}\n```\n{text[:3000]}\n```"
        )
    statements_block = "\n\n".join(statements_block_parts)

    prompt = _CONTRADICTION_PROMPT_TEMPLATE.format(
        statements_block=statements_block,
        evidence=evidence[:4000],
    )

    try:
        response_dict = await get_llm_response(
            prompt=prompt,
            model=model,
            system_prompt=_CONTRADICTION_SYSTEM_PROMPT,
            temperature=0.1,
            max_tokens=6144,
            provider=provider,
        )
        response_text = response_dict["response"]
        usage = response_dict["usage"]
    except LLMProviderError as exc:
        logger.error("LLM Provider failed for Contradictions. Using telemetry sync. %s", exc)
        return sync_telemetry_state("t_03")

    try:
        parsed = _extract_json_block(response_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Contradiction detection JSON parse failure: %s", exc)
        return sync_telemetry_state("t_03")

    parsed["_meta"] = {
        "model":            usage["model"],
        "provider":         usage.get("provider"),
        "usage":            usage,
        "statements_count": len(statements),
        "evidence_length":  len(evidence),
    }
    return parsed


# ============================================================================ #
# Health checks                                                                  #
# ============================================================================ #

async def ping_ollama(model: str | None = None) -> dict[str, Any]:
    """
    Send a trivial prompt to verify the Ollama server and model are reachable.

    Returns
    -------
    {"status": "ok", "model": str, "latency_ms": int}

    Raises
    ------
    OllamaConnectionError : If the server cannot be reached.
    """
    target_model = model or _settings().OLLAMA_MODEL
    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                _ollama_url(),
                json={
                    "model":  target_model,
                    "prompt": "Respond with the single word: ready",
                    "stream": False,
                    "options": {"num_predict": 5},
                },
            )
            resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise OllamaConnectionError(
            f"Ollama unreachable at {_settings().OLLAMA_BASE_URL}"
        ) from exc

    latency_ms = round((time.perf_counter() - t0) * 1000)
    return {"status": "ok", "model": target_model, "latency_ms": latency_ms}


async def ping_featherless(model: str | None = None) -> dict[str, Any]:
    """
    Verify Featherless AI is reachable by sending a minimal prompt.

    Returns
    -------
    {"status": "ok", "model": str, "latency_ms": int}

    Raises
    ------
    FeatherlessAPIError : If the API key is missing or the call fails.
    """
    settings = _settings()
    if not settings.ENABLE_FEATHERLESS:
        return {"status": "disabled", "model": None, "latency_ms": 0}

    target_model = model or settings.FEATHERLESS_MODEL
    t0 = time.perf_counter()
    try:
        text, usage = await _call_featherless(
            prompt="Respond with the single word: ready",
            model=target_model,
            temperature=0.0,
            max_tokens=5,
        )
    except FeatherlessAPIError as exc:
        raise

    latency_ms = round((time.perf_counter() - t0) * 1000)
    return {"status": "ok", "model": target_model, "latency_ms": latency_ms}


async def ping_groq(model: str | None = None) -> dict[str, Any]:
    """
    Verify Groq AI is reachable by sending a minimal prompt.
    """
    settings = _settings()
    if not settings.ENABLE_GROQ:
        return {"status": "disabled", "model": None, "latency_ms": 0}

    target_model = model or settings.GROQ_MODEL
    t0 = time.perf_counter()
    try:
        text, usage = await _call_groq(
            prompt="Respond with the single word: ready",
            model=target_model,
            temperature=0.0,
            max_tokens=5,
        )
    except GroqAPIError as exc:
        raise

    latency_ms = round((time.perf_counter() - t0) * 1000)
    return {"status": "ok", "model": target_model, "latency_ms": latency_ms}
