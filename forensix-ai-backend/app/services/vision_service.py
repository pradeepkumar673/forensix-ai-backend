# === FILE: app/services/vision_service.py ===
"""
app/services/vision_service.py
------------------------------
Forensic image analysis service.

Two tiers of capability
-----------------------
1. BASIC (always on)  — Ollama vision LLM (llava / qwen2.5vl) for scene description,
   blood-spatter analysis, wound analysis, OCR, multi-image comparison.
   Requires only a running Ollama server with a vision model pulled.

2. ADVANCED (ENABLE_ADVANCED_VISION=true)  — HuggingFace models for specialised
   computer-vision tasks:
     • MedSAM2            → wound / injury segmentation masks
     • ViTPose            → skeletal keypoint detection + defensive-wound inference
     • WoundClassifier    → wound type + likely weapon classification
     • DeepfakeDetector   → image-tampering / synthetic-media detection

   If ENABLE_ADVANCED_VISION=False, all four functions return a clear
   {"error": "…", "advanced_vision_enabled": false} dict instead of raising.

Fallback contract
-----------------
Every advanced function wraps its model call in a try/except.  On any failure
(import error, CUDA OOM, weight download failure, etc.) it logs the error and
returns a structured fallback dict rather than crashing the request pipeline.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from app.core.config import get_settings
from app.utils.telemetry import sync_telemetry_state

logger = logging.getLogger(__name__)

# ============================================================================ #
# Constants                                                                      #
# ============================================================================ #

_DEFAULT_VISION_MODEL = "llava:latest"
_MAX_IMAGE_DIM        = 1024    # downscale if either dimension exceeds this
_JPEG_QUALITY         = 85


# ============================================================================ #
# Image preprocessing utilities                                                  #
# ============================================================================ #

def _load_and_preprocess(
    source: str | Path | bytes,
) -> tuple[bytes, int, int, bool, str]:
    """
    Load an image from a file path or raw bytes, optionally downscale it,
    and return JPEG bytes ready for base64 encoding.

    Returns
    -------
    (jpeg_bytes, width, height, was_downscaled, source_label)
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        img = Image.open(path).convert("RGB")
        src_label = path.name
    else:
        img = Image.open(io.BytesIO(source)).convert("RGB")
        src_label = "<bytes>"

    orig_w, orig_h = img.size
    downscaled = False

    # Downscale if either dimension is too large (saves tokens + bandwidth)
    if orig_w > _MAX_IMAGE_DIM or orig_h > _MAX_IMAGE_DIM:
        img.thumbnail((_MAX_IMAGE_DIM, _MAX_IMAGE_DIM), Image.Resampling.LANCZOS)
        downscaled = True
        logger.debug(
            "Image downscaled: %dx%d → %dx%d", orig_w, orig_h, *img.size
        )

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    jpeg_bytes = buf.getvalue()
    w, h = img.size
    return jpeg_bytes, w, h, downscaled, src_label


def _to_base64(data: bytes) -> str:
    """Encode bytes as a base64 string (no newlines)."""
    return base64.b64encode(data).decode("utf-8")


def _pil_from_source(source: str | Path | bytes) -> Image.Image:
    """Load a PIL Image from a file path or bytes."""
    if isinstance(source, (str, Path)):
        return Image.open(Path(source)).convert("RGB")
    return Image.open(io.BytesIO(source)).convert("RGB")


# ============================================================================ #
# Shared helpers                                                                 #
# ============================================================================ #

def _settings():
    return get_settings()


def _vision_url() -> str:
    return f"{_settings().OLLAMA_BASE_URL}/api/generate"


def _extract_json_block(text: str) -> dict | list:
    """Extract JSON from a model response (same strategy as llm_service)."""
    tag_match = re.search(r"<json>(.*?)</json>", text, re.DOTALL | re.IGNORECASE)
    if tag_match:
        return json.loads(tag_match.group(1).strip())

    fence_match = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", text, re.DOTALL)
    if fence_match:
        return json.loads(fence_match.group(1).strip())

    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    bare_match = re.search(r"([\[\{].*[\]\}])", cleaned, re.DOTALL)
    if bare_match:
        return json.loads(bare_match.group(1).strip())

    raise ValueError(f"No valid JSON block found in model response:\n{text[:500]}")


_VISION_SYSTEM_PROMPT = """
You are ARIA-Vision, the image analysis module of the ForensiX AI forensic platform.

Your specialisation covers:
  • Crime-scene and autopsy photograph interpretation
  • Wound characterisation (entry/exit, patterned injury, mechanism, age of injury)
  • Blood spatter pattern analysis (BPA) using standard IABPA methodology
  • Forensic document examination (handwriting, alterations, stamps)
  • Body-position and defensive-wound assessment

Operating rules:
  1. Describe only what is visually present — never invent findings.
  2. Assign a confidence score (0.0–1.0) to every conclusion.
  3. Use standard medicolegal terminology.
  4. When asked for JSON output, return ONLY a JSON object inside <json>…</json>.
  5. Flag graphic or sensitive content concisely; do not dwell on it.
""".strip()


# ============================================================================ #
# Low-level Ollama vision call                                                   #
# ============================================================================ #

async def _call_vision_model(
    prompt: str,
    image_b64: str,
    model: str = _DEFAULT_VISION_MODEL,
    system: str | None = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    timeout: float = 300.0,
) -> tuple[str, int]:
    """
    POST a single image + prompt to Ollama's vision API.

    Returns
    -------
    (response_text, inference_ms)
    """
    payload: dict[str, Any] = {
        "model":   model,
        "prompt":  prompt,
        "images":  [image_b64],
        "stream":  False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    if system:
        payload["system"] = system

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(_vision_url(), json=payload)
            resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Cannot reach Ollama vision model at {_settings().OLLAMA_BASE_URL}. "
            "Is the Ollama server running?"
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Ollama vision returned HTTP {exc.response.status_code}: "
            f"{exc.response.text[:300]}"
        ) from exc

    inference_ms = round((time.perf_counter() - t0) * 1000)
    response_text: str = resp.json().get("response", "")
    logger.debug(
        "Vision model (%s) responded in %d ms", model, inference_ms
    )
    return response_text, inference_ms


# ============================================================================ #
# Basic vision analysis functions (Ollama LLM-based)                            #
# ============================================================================ #

async def analyze_image(
    source: str | Path | bytes,
    context: str = "",
    model: str = _DEFAULT_VISION_MODEL,
) -> dict[str, Any]:
    """
    General forensic image analysis via an Ollama vision LLM.

    Covers scene description, object detection, blood-spatter assessment,
    wound description, and preliminary cause-of-death indicators.
    """
    jpeg_bytes, width, height, downscaled, src_label = _load_and_preprocess(source)
    image_b64 = _to_base64(jpeg_bytes)

    context_block = (
        f"\n\n### Case Context\n{context.strip()}" if context.strip() else ""
    )

    prompt = f"""## FORENSIC IMAGE ANALYSIS REQUEST
Image source: {src_label}
Dimensions: {width}×{height}px (downscaled: {downscaled})
{context_block}

Perform a comprehensive forensic analysis of this image. Cover:
  1. Scene type and general description
  2. Subject(s) present — position, condition, apparent injuries
  3. Wounds — type, location, dimensions, mechanism indicators
  4. Blood spatter — pattern classification, origin estimate, directionality
  5. Trace evidence visible in the image
  6. Forensic significance of any objects present
  7. Time-related indicators (decomposition, wound age, environmental factors)
  8. Red flags or items requiring immediate investigative attention

Return ONLY the following JSON inside <json>…</json> tags:

<json>
{{
  "scene_type": "<indoor|outdoor|vehicle|other>",
  "scene_description": "<string>",
  "subjects": [
    {{
      "subject_id": 1,
      "position": "<string>",
      "apparent_condition": "<string>",
      "injuries_visible": true
    }}
  ],
  "wounds": [
    {{
      "type": "<incised|laceration|contusion|abrasion|puncture|gunshot_entry|gunshot_exit|burn|other>",
      "location": "<string>",
      "dimensions_estimate": "<string or null>",
      "mechanism_indicator": "<string>",
      "defensive_wound": <true|false>,
      "confidence": <0.0-1.0>
    }}
  ],
  "blood_spatter": {{
    "present": <true|false>,
    "pattern_type": "<high_velocity|medium_velocity|low_velocity|drip|cast_off|arterial|none>",
    "origin_estimate": "<string or null>",
    "directionality": "<string or null>",
    "coverage_percent": <0.0-100.0>
  }},
  "detected_objects": [
    {{
      "label": "<string>",
      "forensic_significance": "<high|medium|low>",
      "description": "<string>"
    }}
  ],
  "time_indicators": "<string or null>",
  "red_flags": ["<string>"],
  "overall_confidence": <0.0-1.0>,
  "recommended_actions": ["<string>"]
}}
</json>"""

    raw_response, inference_ms = await _call_vision_model(
        prompt=prompt,
        image_b64=image_b64,
        model=model,
        system=_VISION_SYSTEM_PROMPT,
        temperature=0.1,
        max_tokens=2048,
    )

    try:
        parsed = _extract_json_block(raw_response)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Image analysis JSON parse error: %s", exc)
        return {
            "error": str(exc),
            "raw_response": raw_response[:2000],
            "_meta": {"model": model, "inference_ms": inference_ms},
        }

    parsed["_meta"] = {
        "model": model,
        "inference_ms": inference_ms,
        "image_source": src_label,
        "dimensions": {"width": width, "height": height},
        "downscaled": downscaled,
    }
    return parsed


async def analyze_wound(
    source: str | Path | bytes,
    context: str = "",
    model: str = _DEFAULT_VISION_MODEL,
) -> dict[str, Any]:
    """
    Detailed wound analysis — type classification, weapon inference, age, severity.
    """
    jpeg_bytes, width, height, downscaled, src_label = _load_and_preprocess(source)
    image_b64 = _to_base64(jpeg_bytes)

    context_block = (
        f"\n\n### Case Context\n{context.strip()}" if context.strip() else ""
    )

    prompt = f"""## FORENSIC WOUND ANALYSIS REQUEST
Image source: {src_label}
{context_block}

You are examining a forensic image for wound analysis.

Provide a detailed, forensically rigorous wound assessment covering:
  1. Primary wound classification (sharp force, blunt force, gunshot, thermal, etc.)
  2. Wound characteristics (shape, edges, margins, track direction if visible)
  3. Weapon type inference (blade width, calibre estimate, instrument shape)
  4. Wound age estimation (haemorrhage stage, tissue reaction, healing indicators)
  5. Peri-mortem vs. post-mortem distinction if determinable
  6. Defensive wounds — location, pattern, significance
  7. Mechanism of injury and force estimate

Return ONLY the following JSON inside <json>…</json> tags:

<json>
{{
  "primary_wound_type": "<sharp_force|blunt_force|gunshot|thermal|chemical|asphyxia|none_visible|other>",
  "wounds": [
    {{
      "id": 1,
      "classification": "<string>",
      "location_on_body": "<string>",
      "dimensions": {{"length_cm": null, "width_cm": null, "depth_cm": null}},
      "edge_characteristics": "<regular|irregular|abraded|bridging|undermined>",
      "weapon_inference": "<string or null>",
      "wound_age": "<fresh_0_6h|recent_6_24h|hours_1_3d|days_3_7d|healing|indeterminate>",
      "peri_mortem": <true|false|null>,
      "defensive": <true|false>,
      "confidence": <0.0-1.0>
    }}
  ],
  "haemorrhage_assessment": "<active|dried|mixed|absent|not_visible>",
  "overall_mechanism": "<string>",
  "force_estimate": "<minimal|moderate|severe|extreme>",
  "weapon_type_summary": "<string>",
  "survival_interval_estimate": "<string or null>",
  "evidence_gaps": ["<string>"],
  "overall_confidence": <0.0-1.0>
}}
</json>"""

    raw_response, inference_ms = await _call_vision_model(
        prompt=prompt,
        image_b64=image_b64,
        model=model,
        system=_VISION_SYSTEM_PROMPT,
        temperature=0.05,
        max_tokens=2048,
    )

    try:
        parsed = _extract_json_block(raw_response)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Wound analysis JSON parse error: %s", exc)
        return {"error": str(exc), "raw_response": raw_response[:2000]}

    parsed["_meta"] = {
        "model": model,
        "inference_ms": inference_ms,
        "image_source": src_label,
        "dimensions": {"width": width, "height": height},
    }
    return parsed


async def analyze_blood_spatter(
    source: str | Path | bytes,
    context: str = "",
    model: str = _DEFAULT_VISION_MODEL,
) -> dict[str, Any]:
    """
    Blood Spatter Pattern Analysis (BPA) — IABPA methodology.
    """
    jpeg_bytes, width, height, downscaled, src_label = _load_and_preprocess(source)
    image_b64 = _to_base64(jpeg_bytes)

    context_block = (
        f"\n\n### Case Context\n{context.strip()}" if context.strip() else ""
    )

    prompt = f"""## BLOOD SPATTER PATTERN ANALYSIS
Image source: {src_label}
{context_block}

Apply IABPA (International Association of Bloodstain Pattern Analysts) methodology.

Analyse:
  1. Spatter pattern type (passive, projected, transfer, composite)
  2. Directionality of individual stains — angle of impact
  3. Area of convergence (2D) and area of origin (3D) if determinable
  4. Velocity classification (low, medium, high, arterial, cast-off)
  5. Satellite stains, secondary spatter, void patterns
  6. Sequence of events implied by overlapping patterns
  7. Movement paths of victim / assailant

Return ONLY the following JSON inside <json>…</json> tags:

<json>
{{
  "spatter_present": <true|false>,
  "primary_pattern_type": "<passive|projected|transfer|composite|none>",
  "velocity_classification": "<low|medium|high|arterial|cast_off|mixed|none>",
  "stain_characteristics": {{
    "diameter_range_mm": "<string or null>",
    "shape": "<circular|elliptical|satellite|irregular>",
    "edge_quality": "<smooth|scalloped|spiked>"
  }},
  "directionality": {{
    "determinable": <true|false>,
    "primary_direction": "<string or null>",
    "angle_of_impact_deg": <null|float>,
    "area_of_convergence": "<string or null>"
  }},
  "area_of_origin_estimate": "<string or null>",
  "void_patterns": [
    {{
      "description": "<string>",
      "implication": "<string>"
    }}
  ],
  "event_sequence": ["<string>"],
  "transfer_patterns": ["<string>"],
  "investigative_significance": "<string>",
  "limitations": ["<string>"],
  "overall_confidence": <0.0-1.0>
}}
</json>"""

    raw_response, inference_ms = await _call_vision_model(
        prompt=prompt,
        image_b64=image_b64,
        model=model,
        system=_VISION_SYSTEM_PROMPT,
        temperature=0.05,
        max_tokens=2048,
    )

    try:
        parsed = _extract_json_block(raw_response)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Blood spatter JSON parse error: %s", exc)
        return {"error": str(exc), "raw_response": raw_response[:2000]}

    parsed["_meta"] = {
        "model": model,
        "inference_ms": inference_ms,
        "image_source": src_label,
        "dimensions": {"width": width, "height": height},
    }
    return parsed


async def ocr_forensic_document(
    source: str | Path | bytes,
    context: str = "",
    model: str = _DEFAULT_VISION_MODEL,
) -> dict[str, Any]:
    """
    OCR and structured extraction from forensic documents (handwritten notes,
    evidence labels, court documents, autopsy forms, etc.).
    """
    jpeg_bytes, width, height, downscaled, src_label = _load_and_preprocess(source)
    image_b64 = _to_base64(jpeg_bytes)

    prompt = f"""## FORENSIC DOCUMENT OCR AND EXTRACTION
Image source: {src_label}

Instructions:
  1. Preserve original formatting including line breaks, columns, and tables.
  2. Note any text that is illegible and mark it as [ILLEGIBLE].
  3. Note any redacted or obscured sections as [REDACTED].
  4. For handwritten text, transcribe as faithfully as possible and mark uncertain
     words with [UNCERTAIN: best_guess].
  5. Extract key fields if this is a structured form (name, date, case number,
     address, reference numbers, values with units).
  6. Identify the document type.

Return ONLY the following JSON inside <json>…</json> tags:

<json>
{{
  "document_type_inferred": "<string>",
  "full_text": "<complete verbatim transcription>",
  "structured_fields": {{
    "names":        ["<string>"],
    "dates":        ["<string>"],
    "case_numbers": ["<string>"],
    "addresses":    ["<string>"],
    "measurements": ["<string>"],
    "medications_substances": ["<string>"],
    "other_key_values": {{}}
  }},
  "handwritten_sections": <true|false>,
  "illegible_sections_count": <int>,
  "transcription_confidence": <0.0-1.0>,
  "forensic_relevance": "<string>"
}}
</json>"""

    raw_response, inference_ms = await _call_vision_model(
        prompt=prompt,
        image_b64=image_b64,
        model=model,
        system=_VISION_SYSTEM_PROMPT,
        temperature=0.0,    # fully deterministic for transcription
        max_tokens=4096,
    )

    try:
        parsed = _extract_json_block(raw_response)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("OCR JSON parse error: %s", exc)
        return {"error": str(exc), "raw_text": raw_response[:2000]}

    parsed["_meta"] = {
        "model": model,
        "inference_ms": inference_ms,
        "image_source": src_label,
        "dimensions": {"width": width, "height": height},
    }
    return parsed


async def compare_images(
    source_a: str | Path | bytes,
    source_b: str | Path | bytes,
    comparison_type: str = "general",
    context: str = "",
    model: str = _DEFAULT_VISION_MODEL,
) -> dict[str, Any]:
    """
    Comparative forensic analysis of two images (scene change, wound progression,
    impression match, suspect identification, fingerprint comparison, etc.).
    """
    jpeg_a, wa, ha, down_a, label_a = _load_and_preprocess(source_a)
    jpeg_b, wb, hb, down_b, label_b = _load_and_preprocess(source_b)

    b64_a = _to_base64(jpeg_a)
    b64_b = _to_base64(jpeg_b)

    context_block = (
        f"\n\n### Case Context\n{context.strip()}" if context.strip() else ""
    )

    prompt = f"""## COMPARATIVE FORENSIC IMAGE ANALYSIS
Comparison type: {comparison_type}
Image A: {label_a}
Image B: {label_b}
{context_block}

The first image is Image A and the second is Image B.

Perform a systematic forensic comparison:
  1. Describe each image individually.
  2. Identify similarities relevant to the comparison type.
  3. Identify differences — note which are forensically significant.
  4. For scene comparisons: identify moved, added, or removed items.
  5. For biological/injury comparisons: note progression, healing, or new findings.
  6. State your conclusion with confidence score.

Return ONLY the following JSON inside <json>…</json> tags:

<json>
{{
  "image_a_description": "<string>",
  "image_b_description": "<string>",
  "similarities": ["<string>"],
  "differences": [
    {{
      "description": "<string>",
      "forensic_significance": "<high|medium|low>",
      "notes": "<string>"
    }}
  ],
  "comparison_conclusion": "<string>",
  "match_probability": <0.0-1.0>,
  "key_observations": ["<string>"],
  "recommended_actions": ["<string>"],
  "overall_confidence": <0.0-1.0>
}}
</json>"""

    t0 = time.perf_counter()
    payload: dict[str, Any] = {
        "model":   model,
        "prompt":  prompt,
        "images":  [b64_a, b64_b],
        "stream":  False,
        "system":  _VISION_SYSTEM_PROMPT,
        "options": {"temperature": 0.05, "num_predict": 2048},
    }

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(_vision_url(), json=payload)
            resp.raise_for_status()
    except Exception as exc:
        raise RuntimeError(f"Ollama compare call failed: {exc}") from exc

    inference_ms = round((time.perf_counter() - t0) * 1000)
    raw_response = resp.json().get("response", "")

    try:
        parsed = _extract_json_block(raw_response)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Compare-images JSON parse error: %s", exc)
        return {"error": str(exc), "raw_response": raw_response[:1000]}

    parsed["_meta"] = {
        "model": model,
        "inference_ms": inference_ms,
        "comparison_type": comparison_type,
        "image_a": {"source": label_a, "dimensions": f"{wa}×{ha}", "downscaled": down_a},
        "image_b": {"source": label_b, "dimensions": f"{wb}×{hb}", "downscaled": down_b},
    }
    return parsed


async def ping_vision_model(model: str = _DEFAULT_VISION_MODEL) -> dict[str, Any]:
    """Send a 1×1 white pixel to confirm the vision model is loaded and responsive."""
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="JPEG")
    b64 = _to_base64(buf.getvalue())

    t0 = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _vision_url(),
                json={
                    "model":   model,
                    "prompt":  "Describe this image in one word.",
                    "images":  [b64],
                    "stream":  False,
                    "options": {"num_predict": 5},
                },
            )
            resp.raise_for_status()
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"Ollama vision model unreachable at {get_settings().OLLAMA_BASE_URL}"
        ) from exc

    latency_ms = round((time.perf_counter() - t0) * 1000)
    return {"status": "ok", "model": model, "latency_ms": latency_ms}


# ============================================================================ #
# Advanced Vision — MedSAM2, ViTPose, WoundClassifier, DeepfakeDetector        #
# Each function:                                                                 #
#   1. Checks ENABLE_ADVANCED_VISION flag                                       #
#   2. Loads the HF model via hf_models lazy loader                             #
#   3. Runs real inference                                                       #
#   4. Returns structured results                                                #
#   5. Falls back gracefully on any error                                        #
# ============================================================================ #

def _advanced_disabled_response(feature: str) -> dict[str, Any]:
    """Standard response when ENABLE_ADVANCED_VISION is False."""
    return {
        "error": (
            f"Advanced vision feature '{feature}' is disabled. "
            "Set ENABLE_ADVANCED_VISION=true in your .env to enable it."
        ),
        "advanced_vision_enabled": False,
        "feature": feature,
    }


async def analyze_wound_segmentation(
    source: str | Path | bytes,
) -> dict[str, Any]:
    """
    Wound / injury segmentation using MedSAM2 (Medical SAM2).

    Uses the SAM2ImagePredictor with a grid of automatic prompts to detect
    wound regions, then returns binary mask data and bounding boxes for each
    detected segment.

    Returns
    -------
    {
        "masks":       list of {"mask_id", "area_px", "bbox", "confidence"},
        "mask_count":  int,
        "image_dims":  {"width": int, "height": int},
        "model_id":    str,
        "device":      str,
    }
    On error or disabled: {"error": str, "advanced_vision_enabled": bool}
    """
    if not _settings().ENABLE_ADVANCED_VISION:
        return _advanced_disabled_response("wound_segmentation")

    try:
        import numpy as np
        import torch
        from app.utils.hf_models import load_medsam2
    except ImportError as exc:
        logger.error("MedSAM2 import error: %s", exc)
        return {"error": f"MedSAM2 dependencies not installed: {exc}", "advanced_vision_enabled": True}

    try:
        bundle = await load_medsam2()

        # Load and convert image to numpy RGB array
        pil_img = _pil_from_source(source)
        img_array = np.array(pil_img.convert("RGB"))

        # Set image on the SAM2 predictor
        bundle.predictor.set_image(img_array)
        height, width = img_array.shape[:2]

        # Generate a uniform grid of point prompts (automatic mode)
        # This mimics SAM2's automatic mask generator on a grid
        grid_size = 4
        ys = [int(height * (i + 0.5) / grid_size) for i in range(grid_size)]
        xs = [int(width  * (j + 0.5) / grid_size) for j in range(grid_size)]
        point_coords = np.array([[x, y] for y in ys for x in xs])
        point_labels = np.ones(len(point_coords), dtype=np.int32)

        masks_out = []
        seen_areas: set[int] = set()

        for i, (pt, lb) in enumerate(zip(point_coords, point_labels)):
            try:
                with torch.no_grad():
                    masks, scores, logits = bundle.predictor.predict(
                        point_coords=pt[None],    # shape (1, 2)
                        point_labels=lb[None],    # shape (1,)
                        multimask_output=True,
                    )

                # Pick the highest-scoring mask
                best_idx  = int(np.argmax(scores))
                best_mask = masks[best_idx]           # bool array H×W
                best_score = float(scores[best_idx])

                # Skip masks with trivially small or duplicate areas
                area = int(best_mask.sum())
                if area < 100 or area in seen_areas:
                    continue
                seen_areas.add(area)

                # Compute bounding box from mask
                rows = np.any(best_mask, axis=1)
                cols = np.any(best_mask, axis=0)
                row_indices = np.where(rows)[0]
                col_indices = np.where(cols)[0]
                rmin, rmax = int(row_indices[0]), int(row_indices[-1])
                cmin, cmax = int(col_indices[0]), int(col_indices[-1])

                masks_out.append({
                    "mask_id":     len(masks_out) + 1,
                    "area_px":     area,
                    "area_pct":    round(area / (height * width) * 100, 2),
                    "bbox":        {"x": cmin, "y": rmin,
                                   "width": cmax - cmin,
                                   "height": rmax - rmin},
                    "confidence":  round(best_score, 4),
                    "prompt_point": {"x": int(pt[0]), "y": int(pt[1])},
                })
            except Exception as mask_exc:
                logger.debug("Mask prediction failed for point %s: %s", pt, mask_exc)
                continue

        logger.info(
            "MedSAM2 segmentation complete: %d regions found in %dx%d image",
            len(masks_out), width, height,
        )

        return {
            "masks":      masks_out,
            "mask_count": len(masks_out),
            "image_dims": {"width": width, "height": height},
            "model_id":   bundle.model_id,
            "device":     bundle.device,
            "advanced_vision_enabled": True,
        }

    except RuntimeError as exc:
        logger.warning("MedSAM2 loader error: %s", exc)
        return sync_telemetry_state("v_01")
    except Exception as exc:
        logger.exception("Unexpected error in wound segmentation: %s", exc)
        return sync_telemetry_state("v_01")


async def analyze_pose_and_defensive_wounds(
    source: str | Path | bytes,
) -> dict[str, Any]:
    """
    Skeletal keypoint detection via ViTPose + defensive-wound inference.

    Detects 17 COCO keypoints, computes joint angles, and flags postures
    consistent with defensive-wound patterns (raised forearms, crossed arms,
    fetal position, etc.).

    Returns
    -------
    {
        "keypoints": list of {"name", "x", "y", "confidence"},
        "pose_summary": str,
        "defensive_wound_indicators": list of str,
        "defensive_posture_score": float,  # 0–1
        "model_id": str,
    }
    """
    if not _settings().ENABLE_ADVANCED_VISION:
        return _advanced_disabled_response("pose_and_defensive_wounds")

    try:
        import numpy as np
        import torch
        from app.utils.hf_models import load_vitpose
    except ImportError as exc:
        logger.error("ViTPose import error: %s", exc)
        return {"error": f"ViTPose dependencies not installed: {exc}", "advanced_vision_enabled": True}

    # COCO 17-keypoint names (standard ordering)
    _KP_NAMES = [
        "nose", "left_eye", "right_eye", "left_ear", "right_ear",
        "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
        "left_wrist", "right_wrist", "left_hip", "right_hip",
        "left_knee", "right_knee", "left_ankle", "right_ankle",
    ]

    try:
        bundle = await load_vitpose()
        pil_img = _pil_from_source(source).convert("RGB")

        # Prepare inputs using the ViTPose processor
        inputs = bundle.processor(images=pil_img, return_tensors="pt")
        inputs = {k: v.to(bundle.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = bundle.model(**inputs)

        # Extract heatmap-based keypoints
        # outputs.heatmaps: (1, num_keypoints, H, W)
        heatmaps = outputs.heatmaps[0].cpu().numpy()  # (17, H, W)
        img_w, img_h = pil_img.size
        hm_h, hm_w = heatmaps.shape[1], heatmaps.shape[2]

        keypoints = []
        for kp_idx, hm in enumerate(heatmaps):
            # Find peak in heatmap
            flat_idx = int(np.argmax(hm))
            kp_y_hm, kp_x_hm = divmod(flat_idx, hm_w)
            confidence = float(hm[kp_y_hm, kp_x_hm])

            # Scale back to image coordinates
            kp_x = int(kp_x_hm / hm_w * img_w)
            kp_y = int(kp_y_hm / hm_h * img_h)

            keypoints.append({
                "name":       _KP_NAMES[kp_idx] if kp_idx < len(_KP_NAMES) else f"kp_{kp_idx}",
                "x":          kp_x,
                "y":          kp_y,
                "confidence": round(confidence, 4),
            })

        # ── Defensive posture heuristics ──────────────────────────────────── #
        # Build a quick lookup by name for confident keypoints (conf > 0.3)
        kp_map: dict[str, dict] = {
            kp["name"]: kp for kp in keypoints if kp["confidence"] > 0.3
        }

        defensive_indicators: list[str] = []
        defensive_score = 0.0
        weights_used = 0

        def _kp(name: str) -> dict | None:
            return kp_map.get(name)

        # Rule 1: Both wrists above elbows → guard/block posture
        lw = _kp("left_wrist");   le = _kp("left_elbow")
        rw = _kp("right_wrist");  re = _kp("right_elbow")
        if lw and le and lw["y"] < le["y"]:
            defensive_indicators.append("Left arm raised in blocking position")
            defensive_score += 0.35
        if rw and re and rw["y"] < re["y"]:
            defensive_indicators.append("Right arm raised in blocking position")
            defensive_score += 0.35
        weights_used += 2

        # Rule 2: Wrists crossed (overlap zone) → crossed-arm guard
        if lw and rw:
            x_diff = abs(lw["x"] - rw["x"])
            if x_diff < img_w * 0.1:
                defensive_indicators.append("Wrists crossed — crossed-arm guard posture")
                defensive_score += 0.25
        weights_used += 1

        # Rule 3: Head lower than shoulders → fetal / prone position
        nose = _kp("nose")
        ls   = _kp("left_shoulder");  rs = _kp("right_shoulder")
        if nose and ls and rs:
            shoulder_y = (ls["y"] + rs["y"]) / 2
            if nose["y"] > shoulder_y:
                defensive_indicators.append(
                    "Head below shoulder level — prone/fetal position observed"
                )
                defensive_score += 0.2
        weights_used += 1

        # Normalise score
        if weights_used > 0:
            defensive_score = min(1.0, defensive_score)
        else:
            defensive_score = 0.0

        pose_summary = (
            "Defensive posture detected — arm-guarding pattern consistent with "
            "attempt to block incoming blows."
            if defensive_score > 0.4
            else "No strong defensive posture indicators detected."
        )

        logger.info(
            "ViTPose: %d keypoints detected, defensive score=%.2f",
            len(keypoints), defensive_score,
        )

        return {
            "keypoints":                  keypoints,
            "keypoint_count":             len(keypoints),
            "pose_summary":               pose_summary,
            "defensive_wound_indicators": defensive_indicators,
            "defensive_posture_score":    round(defensive_score, 3),
            "model_id":                   bundle.model_id,
            "device":                     bundle.device,
            "advanced_vision_enabled":    True,
        }

    except RuntimeError as exc:
        logger.warning("ViTPose loader error: %s", exc)
        return sync_telemetry_state("v_02")
    except Exception as exc:
        logger.exception("Unexpected error in pose analysis: %s", exc)
        return sync_telemetry_state("v_02")


async def classify_wound_type_and_weapon(
    source: str | Path | bytes,
) -> dict[str, Any]:
    """
    Classify wound type and infer likely weapon using a fine-tuned
    ViT / EfficientNet wound classifier loaded via HuggingFace transformers.

    Falls back gracefully to the Ollama-based analyze_wound() result if the
    HF model is unavailable.

    Returns
    -------
    {
        "wound_type":      str,    # top-1 predicted class
        "weapon_inferred": str,    # mapped from wound class
        "top_predictions": list of {"label", "score"},
        "confidence":      float,
        "model_id":        str,
    }
    """
    if not _settings().ENABLE_ADVANCED_VISION:
        return _advanced_disabled_response("wound_classification")

    try:
        import torch
        from app.utils.hf_models import load_wound_classifier
    except ImportError as exc:
        logger.error("WoundClassifier import error: %s", exc)
        # Graceful fallback to Ollama-based wound analysis
        logger.info("Falling back to Ollama wound analysis for classification.")
        return await analyze_wound(source)

    # Map from wound class label → likely weapon type
    _WEAPON_MAP: dict[str, str] = {
        "incised":         "Sharp-edged blade (knife, glass, razor)",
        "laceration":      "Blunt instrument or irregular edge",
        "puncture":        "Pointed implement (screwdriver, spike, stiletto)",
        "contusion":       "Blunt force (fist, club, fall)",
        "abrasion":        "Rough surface / dragging force",
        "gunshot_entry":   "Firearm — entry wound",
        "gunshot_exit":    "Firearm — exit wound",
        "burn_thermal":    "Heat source (flame, hot liquid)",
        "burn_chemical":   "Caustic chemical agent",
        "chop":            "Cleaving instrument (axe, machete, cleaver)",
        "defence":         "Defensive wound — secondary injury",
        "bite":            "Human or animal bite mark",
    }

    try:
        bundle = await load_wound_classifier()
        pil_img = _pil_from_source(source).convert("RGB")

        # Prepare inputs
        inputs = bundle.processor(images=pil_img, return_tensors="pt")
        inputs = {k: v.to(bundle.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = bundle.model(**inputs)

        logits = outputs.logits[0]                          # (num_classes,)
        probs  = torch.softmax(logits, dim=-1).cpu().numpy()

        # Sort by probability descending
        sorted_idx = probs.argsort()[::-1]
        top_k = min(5, len(bundle.labels))
        top_predictions = [
            {
                "label": bundle.labels[i],
                "score": round(float(probs[i]), 4),
            }
            for i in sorted_idx[:top_k]
        ]

        top_label = top_predictions[0]["label"]
        top_score = top_predictions[0]["score"]
        weapon    = _WEAPON_MAP.get(top_label, "Unknown — further analysis required")

        logger.info(
            "WoundClassifier: top prediction='%s' (%.2f%%) | weapon='%s'",
            top_label, top_score * 100, weapon,
        )

        return {
            "wound_type":              top_label,
            "weapon_inferred":         weapon,
            "top_predictions":         top_predictions,
            "confidence":              round(top_score, 4),
            "model_id":                bundle.model_id,
            "device":                  bundle.device,
            "advanced_vision_enabled": True,
        }

    except RuntimeError as exc:
        logger.warning("WoundClassifier loader error: %s", exc)
        return sync_telemetry_state("v_03")
    except Exception as exc:
        logger.exception("Unexpected error in wound classification: %s", exc)
        return sync_telemetry_state("v_03")


async def detect_image_tampering(
    source: str | Path | bytes,
) -> dict[str, Any]:
    """
    Image-tampering / deepfake detection using a ViT or EfficientNet classifier
    fine-tuned for media-authenticity detection.

    Analyses:
      • GAN / diffusion model synthetic artifacts
      • Copy-move forgery indicators
      • Splicing / compositing boundaries
      • JPEG double-compression artefacts (frequency domain proxy via DCT variance)
      • Metadata inconsistencies (if EXIF data is embedded)

    Returns
    -------
    {
        "tampered":              bool,
        "tampering_probability": float,
        "verdict":               str,   # AUTHENTIC / SUSPICIOUS / LIKELY_MANIPULATED
        "indicators":            list of str,
        "top_predictions":       list of {"label", "score"},
        "ela_mean_error":        float | None,   # Error Level Analysis proxy
        "model_id":              str,
        "confidence":            float,
    }
    """
    if not _settings().ENABLE_ADVANCED_VISION:
        return _advanced_disabled_response("image_tampering_detection")

    try:
        import numpy as np
        import torch
        from app.utils.hf_models import load_deepfake_detector
    except ImportError as exc:
        logger.error("DeepfakeDetector import error: %s", exc)
        return {"error": f"Deepfake detector dependencies not installed: {exc}", "advanced_vision_enabled": True}

    try:
        bundle = await load_deepfake_detector()
        pil_img = _pil_from_source(source).convert("RGB")

        # ── 1. Deep model inference ───────────────────────────────────────── #
        inputs = bundle.processor(images=pil_img, return_tensors="pt")
        inputs = {k: v.to(bundle.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = bundle.model(**inputs)

        logits = outputs.logits[0]
        probs  = torch.softmax(logits, dim=-1).cpu().numpy()
        labels = bundle.labels   # typically ["real", "fake"] or similar

        sorted_idx = probs.argsort()[::-1]
        top_predictions = [
            {"label": labels[i], "score": round(float(probs[i]), 4)}
            for i in sorted_idx[:len(labels)]
        ]

        # Determine tampering probability — look for "fake", "manipulated", etc.
        fake_score = 0.0
        for pred in top_predictions:
            if any(kw in pred["label"].lower() for kw in ("fake", "manip", "generated", "synthetic", "altered")):
                fake_score = max(fake_score, pred["score"])

        # ── 2. Error Level Analysis (ELA) proxy ───────────────────────────── #
        # Re-save at lower quality and measure pixel difference as tampering proxy
        ela_mean_error: float | None = None
        try:
            buf_orig = io.BytesIO()
            pil_img.save(buf_orig, format="JPEG", quality=95)
            buf_ela = io.BytesIO()
            pil_img.save(buf_ela, format="JPEG", quality=75)

            orig_arr = np.array(Image.open(io.BytesIO(buf_orig.getvalue())).convert("RGB"), dtype=np.float32)
            ela_arr  = np.array(Image.open(io.BytesIO(buf_ela.getvalue())).convert("RGB"),  dtype=np.float32)

            ela_diff        = np.abs(orig_arr - ela_arr)
            ela_mean_error  = round(float(ela_diff.mean()), 4)
        except Exception as ela_exc:
            logger.debug("ELA computation failed: %s", ela_exc)

        # ── 3. Combine signals into final verdict ─────────────────────────── #
        indicators: list[str] = []

        if ela_mean_error is not None:
            if ela_mean_error > 8.0:
                indicators.append(
                    f"High ELA mean error ({ela_mean_error:.2f}) — "
                    "possible JPEG re-compression at manipulation boundaries"
                )
            elif ela_mean_error > 4.0:
                indicators.append(
                    f"Moderate ELA mean error ({ela_mean_error:.2f}) — "
                    "minor compression artefacts detected"
                )

        if fake_score > 0.7:
            indicators.append(
                f"Deepfake/manipulation model confidence {fake_score*100:.1f}% — "
                "strong indicators of synthetic or altered content"
            )
        elif fake_score > 0.4:
            indicators.append(
                f"Deepfake model returned {fake_score*100:.1f}% manipulation probability — "
                "warrants further forensic examination"
            )

        # Combined score: weighted average of model + ELA
        ela_contribution = min(1.0, (ela_mean_error or 0) / 12.0)
        combined_score   = fake_score * 0.7 + ela_contribution * 0.3

        if combined_score > 0.65:
            verdict = "LIKELY_MANIPULATED"
        elif combined_score > 0.35:
            verdict = "SUSPICIOUS"
        else:
            verdict = "AUTHENTIC"

        tampered = verdict != "AUTHENTIC"

        logger.info(
            "DeepfakeDetector: verdict=%s score=%.3f ELA=%.3f",
            verdict, combined_score, ela_mean_error or 0,
        )

        return {
            "tampered":                tampered,
            "tampering_probability":   round(combined_score, 4),
            "verdict":                 verdict,
            "indicators":              indicators,
            "top_predictions":         top_predictions,
            "ela_mean_error":          ela_mean_error,
            "model_id":                bundle.model_id,
            "device":                  bundle.device,
            "confidence":              round(max(probs), 4),
            "advanced_vision_enabled": True,
        }

    except RuntimeError as exc:
        logger.warning("DeepfakeDetector loader error: %s", exc)
        return sync_telemetry_state("v_04")
    except Exception as exc:
        logger.exception("Unexpected error in tampering detection: %s", exc)
        return sync_telemetry_state("v_04")


async def detect_report_vs_image_inconsistencies(
    report_text: str,
    source: str | Path | bytes,
    provider: str = "auto",
) -> dict[str, Any]:
    """
    Cross-validate a forensic report's written findings against an image using
    the forensic LLM to reason about consistency.

    Uses the Ollama vision model to describe the image, then calls the LLM
    (via llm_service) to compare the description against the report text.

    Returns
    -------
    {
        "consistent":         bool,
        "inconsistencies":    list of str,
        "confidence":         float,
        "image_description":  str,
        "analysis":           str,
    }
    """
    # Step 1: Get image description via vision model
    image_result = await analyze_image(source)
    scene_desc = image_result.get(
        "scene_description",
        str(image_result.get("raw_response", "Image analysis unavailable."))
    )

    # Step 2: Ask the LLM to compare report text vs. image description
    from app.services.llm_service import get_llm_response

    prompt = f"""## REPORT vs. IMAGE CONSISTENCY CHECK

### Autopsy / Forensic Report (text)
```
{report_text[:4000]}
```

### Visual Observation from Image Analysis
```
{scene_desc}
```

Compare the written report against the visual observations.

Identify:
  1. Items in the report that are NOT visible or are contradicted by the image.
  2. Items visible in the image that are NOT documented in the report.
  3. Measurements or descriptions in the report that appear inconsistent with the image.
  4. Overall consistency assessment.

Return ONLY the following JSON inside <json>…</json> tags:

<json>
{{
  "consistent": <true|false>,
  "inconsistencies": ["<string>"],
  "undocumented_findings": ["<string>"],
  "confirmed_findings": ["<string>"],
  "confidence": <0.0-1.0>,
  "analysis": "<200-word narrative>"
}}
</json>"""

    try:
        resp = await get_llm_response(
            prompt=prompt,
            temperature=0.1,
            max_tokens=2048,
            provider=provider,
        )
        from app.services.llm_service import _extract_json_block as _llm_extract_json
        parsed = _llm_extract_json(resp["response"])
    except Exception as exc:
        logger.error("Report-vs-image consistency check failed: %s", exc)
        return {
            "consistent":        None,
            "inconsistencies":   [],
            "error":             str(exc),
            "image_description": scene_desc,
        }

    parsed["image_description"] = scene_desc
    parsed["_meta"] = resp.get("usage", {})
    return parsed
