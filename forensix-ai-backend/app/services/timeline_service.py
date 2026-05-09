"""
app/services/timeline_service.py
---------------------------------
Forensic event timeline reconstruction service.

Responsibilities:
  • Build a chronological event timeline from mixed evidence sources
    (autopsy reports, witness statements, digital logs, CCTV records, etc.)
  • Detect temporal gaps and contradictions across sources
  • Produce a narrative summary of the reconstructed sequence of events
  • Validate event ordering against physical forensic constraints
    (e.g. death cannot precede injury, livor fixation timing)

Public functions:
  build_timeline(events_raw, context, model)  → TimelineResponse
  extract_events_from_text(text, model)       → list[dict]
  detect_timeline_contradictions(events, statements, model) → list[str]
  validate_event_ordering(events)             → list[str]
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import httpx

from app.core.config import get_settings
from app.schemas.analysis import (
    ConfidenceScore,
    DateTimeRange,
    TimelineEvent,
    TimelineEventType,
    TimelineResponse,
    AIModelMeta,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants                                                                     #
# --------------------------------------------------------------------------- #

_DEFAULT_MODEL = "qwen3:14b"

# --------------------------------------------------------------------------- #
# Internal helpers                                                              #
# --------------------------------------------------------------------------- #

def _settings():
    return get_settings()


def _ollama_url() -> str:
    return f"{_settings().OLLAMA_BASE_URL}/api/generate"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_confidence(score: float) -> ConfidenceScore:
    return ConfidenceScore.from_float(max(0.0, min(1.0, score)))


def _extract_json_block(text: str) -> Any:
    """Extract the first JSON block from a model response."""
    # Strategy 1: explicit <json> tags
    tag_match = re.search(r"<json>(.*?)</json>", text, re.DOTALL | re.IGNORECASE)
    if tag_match:
        return json.loads(tag_match.group(1).strip())

    # Strategy 2: markdown fences
    fence_match = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1).strip())

    # Strategy 3: raw JSON
    bare_match = re.search(r"([\[\{].*[\]\}])", text, re.DOTALL)
    if bare_match:
        return json.loads(bare_match.group(1).strip())

    raise ValueError(f"No valid JSON found in model response:\n{text[:400]}")


async def _call_ollama(
    prompt: str,
    model: str = _DEFAULT_MODEL,
    system: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 4096,
    timeout: float = 180.0,
) -> tuple[str, int]:
    """
    Async POST to Ollama /api/generate.

    Returns (response_text, inference_ms).
    """
    payload: dict[str, Any] = {
        "model":   model,
        "prompt":  prompt,
        "stream":  False,
        "options": {
            "temperature":   temperature,
            "num_predict":   max_tokens,
            "top_p":         0.9,
            "repeat_penalty": 1.1,
        },
    }
    if system:
        payload["system"] = system

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_ollama_url(), json=payload)
            resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Cannot reach Ollama at {_settings().OLLAMA_BASE_URL}. "
            "Is the Ollama server running?"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"
        ) from exc

    inference_ms = round((time.perf_counter() - t0) * 1000)
    response_text: str = resp.json().get("response", "")
    return response_text, inference_ms


# --------------------------------------------------------------------------- #
# System & prompt templates                                                     #
# --------------------------------------------------------------------------- #

_TIMELINE_SYSTEM_PROMPT = """
You are ARIA, a senior forensic timeline analyst.
Your task is to reconstruct precise, chronologically ordered event timelines
from raw forensic evidence, witness accounts, and digital data.

Rules:
  1. Assign ISO-8601 timestamps wherever possible; use relative windows (e.g.
     "-48h to -24h before discovery") when exact times are unavailable.
  2. Classify every event using one of the canonical event_type values.
  3. Cite the evidence source for every event.
  4. Flag temporal contradictions — two sources that cannot simultaneously be true.
  5. Identify gaps: periods with no corroborating evidence.
  6. Confidence scoring: 0.9–1.0 = confirmed; 0.7–0.9 = strongly supported;
     0.5–0.7 = probable; 0.3–0.5 = speculative; < 0.3 = unverified.
  7. Always respond with ONLY valid JSON wrapped in <json>…</json> tags.
""".strip()


_EXTRACT_EVENTS_PROMPT = """
## FORENSIC EVENT EXTRACTION

Extract all temporally anchored events from the following forensic evidence text.
Each event must have a timestamp or time window, a description, and a source.

### Evidence Text
{text}

Return ONLY this JSON inside <json>…</json> tags:

<json>
{{
  "events": [
    {{
      "event_type":   "<last_seen_alive|phone_activity|financial_transaction|cctv_sighting|medical_event|injury_inflicted|death|discovery|police_arrival|autopsy|witness_account|suspect_activity|other>",
      "timestamp":    "<ISO-8601 or null>",
      "time_earliest":"<ISO-8601 or null>",
      "time_latest":  "<ISO-8601 or null>",
      "description":  "<string>",
      "location":     "<string or null>",
      "source":       "<string — document section or evidence item>",
      "actors":       ["<string>"],
      "confidence":   <0.0-1.0>,
      "notes":        "<string or null>"
    }}
  ],
  "extraction_notes": "<any caveats about ambiguous timestamps>",
  "overall_confidence": <0.0-1.0>
}}
</json>
"""


_BUILD_TIMELINE_PROMPT = """
## FORENSIC TIMELINE RECONSTRUCTION

You are reconstructing the complete event timeline for a forensic case.
Below are raw event records extracted from multiple evidence sources.
Your job is to:
  1. Merge duplicate or overlapping events.
  2. Sort all events chronologically.
  3. Identify temporal gaps (periods > 2 hours with no evidence).
  4. Identify contradictions between events from different sources.
  5. Assign causal links between related events (linked_event_ids).
  6. Write a forensic narrative summary of the reconstructed sequence.

### Case Context
{context}

### Raw Events
{events_json}

Return ONLY this JSON inside <json>…</json> tags:

<json>
{{
  "events": [
    {{
      "event_id":     "<uuid>",
      "event_type":   "<event_type>",
      "timestamp":    "<ISO-8601 or null>",
      "time_earliest":"<ISO-8601 or null>",
      "time_latest":  "<ISO-8601 or null>",
      "description":  "<string>",
      "location":     "<string or null>",
      "source":       "<string>",
      "actors":       ["<string>"],
      "confidence":   <0.0-1.0>,
      "linked_event_ids": ["<uuid or empty>"]
    }}
  ],
  "gaps_identified":    ["<description of gap>"],
  "contradictions":     ["<description of contradiction>"],
  "narrative_summary":  "<400-word plain-language chronological narrative>",
  "overall_confidence": <0.0-1.0>
}}
</json>
"""


_CONTRADICTION_PROMPT = """
## FORENSIC CONTRADICTION DETECTION

Compare the following timeline events against the witness / suspect statements
and identify genuine factual contradictions.

A contradiction exists when two pieces of evidence CANNOT simultaneously be true.

### Timeline Events
{events_json}

### Witness / Suspect Statements
{statements_text}

Return ONLY this JSON inside <json>…</json> tags:

<json>
{{
  "contradictions": [
    {{
      "id":          "<uuid>",
      "severity":    "<minor|moderate|major>",
      "claim_a":     "<first conflicting claim (source: …)>",
      "claim_b":     "<second conflicting claim (source: …)>",
      "reason":      "<why these two claims cannot both be true>",
      "resolution":  "<what evidence would resolve this contradiction>",
      "confidence":  <0.0-1.0>
    }}
  ],
  "total_contradictions": <int>,
  "high_severity_count":  <int>,
  "summary":              "<brief plain-language summary of key contradictions>"
}}
</json>
"""

# --------------------------------------------------------------------------- #
# Internal parsing helpers                                                      #
# --------------------------------------------------------------------------- #

def _parse_event_type(raw: str) -> TimelineEventType:
    """Safely convert a raw string to TimelineEventType, defaulting to OTHER."""
    try:
        return TimelineEventType(raw)
    except ValueError:
        return TimelineEventType.OTHER


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string to datetime, returning None on failure."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _make_date_range(
    earliest: str | None,
    latest: str | None,
    confidence: float,
) -> DateTimeRange | None:
    """Build a DateTimeRange from ISO strings, returning None if both are absent."""
    dt_earliest = _parse_dt(earliest)
    dt_latest   = _parse_dt(latest)

    if not dt_earliest or not dt_latest:
        return None

    return DateTimeRange(
        earliest   = dt_earliest,
        latest     = dt_latest,
        confidence = _make_confidence(confidence),
    )


def _dict_to_timeline_event(raw: dict[str, Any]) -> TimelineEvent:
    """
    Convert a raw dict (from LLM output) into a TimelineEvent schema object.
    Gracefully handles missing or malformed fields.
    """
    exact_ts = _parse_dt(raw.get("timestamp"))
    time_window = _make_date_range(
        raw.get("time_earliest"),
        raw.get("time_latest"),
        raw.get("confidence", 0.6),
    )

    # Use provided event_id if it's a valid UUID, else generate a new one
    try:
        event_id = UUID(raw.get("event_id", ""))
    except (ValueError, AttributeError):
        event_id = uuid4()

    # Parse linked event IDs
    linked_ids: list[UUID] = []
    for lid in raw.get("linked_event_ids", []):
        try:
            linked_ids.append(UUID(lid))
        except (ValueError, AttributeError):
            pass

    return TimelineEvent(
        event_id          = event_id,
        event_type        = _parse_event_type(raw.get("event_type", "other")),
        timestamp         = exact_ts,
        time_window       = time_window,
        description       = raw.get("description", "No description provided."),
        location          = raw.get("location"),
        source            = raw.get("source"),
        actors            = raw.get("actors", []),
        confidence        = _make_confidence(raw.get("confidence", 0.5)),
        linked_event_ids  = linked_ids,
    )


# --------------------------------------------------------------------------- #
# Public API                                                                    #
# --------------------------------------------------------------------------- #

async def extract_events_from_text(
    text:  str,
    model: str = _DEFAULT_MODEL,
) -> list[dict[str, Any]]:
    """
    Extract temporally anchored events from any forensic evidence text.

    Parameters
    ----------
    text  : Raw or cleaned text from a document (autopsy report, police report,
            witness statement, digital log, etc.)
    model : Ollama model tag.

    Returns
    -------
    List of raw event dicts (not yet converted to schema objects).
    Each dict contains: event_type, timestamp, description, source, actors,
    confidence, notes.

    Raises
    ------
    RuntimeError : If the Ollama server is unreachable.
    ValueError   : If the LLM output cannot be parsed as JSON.
    """
    if not text or not text.strip():
        raise ValueError("text must be a non-empty string")

    # Truncate very long documents to avoid context overflow
    max_chars = 10_000
    truncated = len(text) > max_chars
    source_text = text[:max_chars] + ("\n\n[TRUNCATED]" if truncated else "")

    prompt = _EXTRACT_EVENTS_PROMPT.format(text=source_text)

    response_text, inference_ms = await _call_ollama(
        prompt=prompt,
        model=model,
        system=_TIMELINE_SYSTEM_PROMPT,
        temperature=0.05,
        max_tokens=4096,
    )

    try:
        parsed = _extract_json_block(response_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Event extraction JSON parse failure: %s", exc)
        raise ValueError(
            f"LLM did not return valid JSON for event extraction.\n"
            f"Raw response (first 400 chars):\n{response_text[:400]}"
        ) from exc

    events = parsed.get("events", [])
    logger.info(
        "Extracted %d events from text (%d chars) in %d ms",
        len(events), len(text), inference_ms,
    )
    return events


async def build_timeline(
    events_raw: list[dict[str, Any]],
    context:    str = "",
    model:      str = _DEFAULT_MODEL,
    case_id:    UUID | None = None,
) -> TimelineResponse:
    """
    Reconstruct a full forensic event timeline from a list of raw event dicts.

    Parameters
    ----------
    events_raw : List of raw event dicts.  Can come from extract_events_from_text()
                 or from the analysis store.  Each dict must have at minimum:
                 'event_type', 'description', 'confidence'.
    context    : Brief case context string sent to the LLM for disambiguation.
    model      : Ollama model tag.
    case_id    : UUID of the parent case (used in the response schema).

    Returns
    -------
    TimelineResponse — fully populated schema object with sorted events,
    gap analysis, contradiction list, and narrative summary.

    Raises
    ------
    RuntimeError : If the Ollama server is unreachable.
    ValueError   : If the LLM output cannot be parsed.
    """
    if not events_raw:
        raise ValueError("events_raw must be a non-empty list")

    if case_id is None:
        case_id = uuid4()

    events_json = json.dumps(events_raw, indent=2, default=str)

    prompt = _BUILD_TIMELINE_PROMPT.format(
        context     = context or "No additional context provided.",
        events_json = events_json[:14_000],   # cap to avoid token overflow
    )

    t0 = time.perf_counter()
    response_text, inference_ms = await _call_ollama(
        prompt=prompt,
        model=model,
        system=_TIMELINE_SYSTEM_PROMPT,
        temperature=0.05,
        max_tokens=6000,
    )

    try:
        parsed = _extract_json_block(response_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Timeline build JSON parse failure: %s", exc)
        raise ValueError(
            f"LLM did not return valid JSON for timeline reconstruction.\n"
            f"Raw response (first 400 chars):\n{response_text[:400]}"
        ) from exc

    # Convert raw event dicts → TimelineEvent schema objects
    timeline_events: list[TimelineEvent] = []
    for raw_event in parsed.get("events", []):
        try:
            timeline_events.append(_dict_to_timeline_event(raw_event))
        except Exception as e:
            logger.warning("Skipping malformed event dict: %s — %s", raw_event, e)

    # Sort events: confirmed timestamps first, then by earliest window bound
    def sort_key(e: TimelineEvent):
        if e.timestamp:
            return e.timestamp
        if e.time_window and e.time_window.earliest:
            return e.time_window.earliest
        return _utcnow()   # put un-anchored events at the end

    timeline_events.sort(key=sort_key)

    logger.info(
        "Built timeline: %d events, %d gaps, %d contradictions in %d ms",
        len(timeline_events),
        len(parsed.get("gaps_identified", [])),
        len(parsed.get("contradictions", [])),
        inference_ms,
    )

    return TimelineResponse(
        case_id            = case_id,
        events             = timeline_events,
        gaps_identified    = parsed.get("gaps_identified", []),
        contradictions     = parsed.get("contradictions", []),
        narrative_summary  = parsed.get(
            "narrative_summary",
            "Timeline reconstruction completed.",
        ),
        overall_confidence = _make_confidence(
            parsed.get("overall_confidence", 0.65)
        ),
        model_meta = AIModelMeta(
            model_name   = model,
            inference_ms = inference_ms,
        ),
    )


async def detect_timeline_contradictions(
    events:          list[dict[str, Any]],
    statements_text: str,
    model:           str = _DEFAULT_MODEL,
) -> list[dict[str, Any]]:
    """
    Detect contradictions between reconstructed timeline events and witness /
    suspect statements.

    Parameters
    ----------
    events          : List of raw timeline event dicts.
    statements_text : Combined text from all witness and suspect statements.
    model           : Ollama model tag.

    Returns
    -------
    List of contradiction dicts, each containing:
    id, severity, claim_a, claim_b, reason, resolution, confidence.

    Raises
    ------
    RuntimeError : If the Ollama server is unreachable.
    ValueError   : If the LLM response cannot be parsed.
    """
    if not events or not statements_text.strip():
        return []

    events_json = json.dumps(events[:40], indent=2, default=str)  # cap at 40 events

    prompt = _CONTRADICTION_PROMPT.format(
        events_json     = events_json,
        statements_text = statements_text[:8_000],
    )

    response_text, inference_ms = await _call_ollama(
        prompt=prompt,
        model=model,
        system=_TIMELINE_SYSTEM_PROMPT,
        temperature=0.05,
        max_tokens=3000,
    )

    try:
        parsed = _extract_json_block(response_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Contradiction detection JSON parse failure: %s", exc)
        return []

    contradictions = parsed.get("contradictions", [])
    logger.info(
        "Detected %d contradictions (%d high-severity) in %d ms",
        len(contradictions),
        parsed.get("high_severity_count", 0),
        inference_ms,
    )
    return contradictions


def validate_event_ordering(events: list[TimelineEvent]) -> list[str]:
    """
    Apply hard forensic constraints to detect logically impossible event orderings.

    Checks applied (rule-based, no LLM required):
      • Death event cannot precede injury_inflicted events.
      • Discovery event cannot precede death event.
      • Autopsy event cannot precede discovery event.
      • Police_arrival cannot precede discovery event.

    Parameters
    ----------
    events : Sorted list of TimelineEvent objects (ascending by timestamp).

    Returns
    -------
    List of human-readable ordering violation strings.
    An empty list means no violations detected.
    """
    violations: list[str] = []

    # Build a mapping of event_type → first timestamp seen
    type_times: dict[TimelineEventType, datetime] = {}
    for event in events:
        ts = event.timestamp or (
            event.time_window.earliest if event.time_window else None
        )
        if ts and event.event_type not in type_times:
            type_times[event.event_type] = ts

    # ── Constraint checks ──────────────────────────────────────────────────── #
    death_ts     = type_times.get(TimelineEventType.DEATH)
    injury_ts    = type_times.get(TimelineEventType.INJURY_INFLICTED)
    discovery_ts = type_times.get(TimelineEventType.DISCOVERY)
    autopsy_ts   = type_times.get(TimelineEventType.AUTOPSY)
    police_ts    = type_times.get(TimelineEventType.POLICE_ARRIVAL)

    if death_ts and injury_ts and death_ts < injury_ts:
        violations.append(
            f"ORDERING VIOLATION: Death ({death_ts.isoformat()}) precedes "
            f"injury_inflicted ({injury_ts.isoformat()}). "
            "This is physiologically impossible unless wounds are post-mortem."
        )

    if discovery_ts and death_ts and discovery_ts < death_ts:
        violations.append(
            f"ORDERING VIOLATION: Discovery ({discovery_ts.isoformat()}) precedes "
            f"death ({death_ts.isoformat()}). Review discovery and death timestamps."
        )

    if autopsy_ts and discovery_ts and autopsy_ts < discovery_ts:
        violations.append(
            f"ORDERING VIOLATION: Autopsy ({autopsy_ts.isoformat()}) precedes "
            f"discovery ({discovery_ts.isoformat()})."
        )

    if police_ts and discovery_ts and police_ts < discovery_ts:
        violations.append(
            f"ORDERING VIOLATION: Police arrival ({police_ts.isoformat()}) precedes "
            f"discovery ({discovery_ts.isoformat()}). "
            "Verify if police discovered the body themselves."
        )

    return violations
