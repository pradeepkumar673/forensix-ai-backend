"""
app/utils/hf_models.py
----------------------
Lazy-loading helpers for every HuggingFace model used in the Forensix AI
advanced computer-vision pipeline.

Design principles
-----------------
* **Lazy initialisation** — no model is loaded at import time.  Each loader
  is called only on first use, then the result is cached in a module-level
  dict so subsequent calls are free.
* **Async-friendly** — network-bound work (HF Hub download checks) is
  dispatched to a thread-pool via ``asyncio.to_thread`` so FastAPI request
  handlers never block the event loop.
* **Device-aware** — every loader honours ``Settings.resolved_device``,
  which auto-selects CUDA when available and falls back to CPU.
* **Feature-gated** — all loaders raise ``RuntimeError`` immediately when
  ``Settings.ENABLE_ADVANCED_VISION`` is ``False``, giving callers a clear,
  actionable error rather than a silent no-op.
* **Typed return values** — each loader returns a named ``ModelBundle``
  dataclass so callers receive structured objects with named fields instead
  of anonymous tuples.

Usage example
-------------
```python
from app.utils.hf_models import load_medsam2, load_vitpose

bundle = await load_medsam2()
masks  = bundle.predictor.predict(image_array)

pose_bundle = await load_vitpose()
keypoints   = pose_bundle.model(pixel_values=tensor)
```
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal model registry — module-level singletons
# Keys mirror the loader function names; values are ModelBundle instances.
# ---------------------------------------------------------------------------
_MODEL_CACHE: dict[str, Any] = {}


# ===========================================================================
# Shared helpers
# ===========================================================================

def _get_settings():
    """Deferred import to avoid circular imports at module load time."""
    from app.core.config import get_settings
    return get_settings()


def _require_advanced_vision() -> None:
    """
    Raise ``RuntimeError`` when the advanced-vision feature flag is disabled.

    Call this as the first line of every model loader so callers get a clear
    diagnostic instead of a confusing import or CUDA error.
    """
    settings = _get_settings()
    if not settings.ENABLE_ADVANCED_VISION:
        raise RuntimeError(
            "Advanced vision models are disabled. "
            "Set ENABLE_ADVANCED_VISION=true in your .env file to enable them."
        )


def _device() -> str:
    """Return the resolved torch device string ('cuda' or 'cpu')."""
    return _get_settings().resolved_device


def _hf_cache() -> str:
    """Return the HuggingFace cache directory as a plain string."""
    return str(_get_settings().hf_cache_path)


def _set_hf_env() -> None:
    """
    Ensure HuggingFace environment variables point to the configured cache
    directory.  Called once inside every loader before any HF import so the
    variables are set even if ``get_settings()`` side-effect ran earlier.
    """
    cache = _hf_cache()
    os.environ.setdefault("HF_HOME", cache)
    os.environ.setdefault("TRANSFORMERS_CACHE", cache)
    os.environ.setdefault("HF_DATASETS_CACHE", cache)


def is_model_loaded(key: str) -> bool:
    """Return ``True`` if a model bundle is already cached under *key*."""
    return key in _MODEL_CACHE


def unload_model(key: str) -> bool:
    """
    Remove a cached model bundle and free GPU/CPU memory.

    Parameters
    ----------
    key:
        The model cache key (same string used internally by each loader, e.g.
        ``"medsam2"``, ``"vitpose"``, ``"wound_classifier"``).

    Returns
    -------
    bool
        ``True`` if the model was present and has been removed, ``False`` if
        the key was not in the cache.
    """
    if key not in _MODEL_CACHE:
        return False
    bundle = _MODEL_CACHE.pop(key)
    # Best-effort: move tensors off GPU before GC
    for attr in ("model", "processor", "tokenizer", "predictor"):
        obj = getattr(bundle, attr, None)
        if obj is not None and hasattr(obj, "cpu"):
            try:
                obj.cpu()
            except Exception:
                pass
    del bundle
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    logger.info("Unloaded model '%s' from cache.", key)
    return True


def loaded_models() -> list[str]:
    """Return a list of keys for all currently cached model bundles."""
    return list(_MODEL_CACHE.keys())


# ===========================================================================
# ModelBundle dataclasses
# ===========================================================================

@dataclass
class MedSAM2Bundle:
    """
    Holds the SAM2 / MedSAM2 predictor and its image-processor.

    Attributes
    ----------
    predictor:
        ``SAM2ImagePredictor`` instance (from ``sam2`` package) ready to call
        ``.set_image(np_array)`` then ``.predict(...)``.
    processor:
        ``Sam2Processor`` (HuggingFace transformers wrapper) for pixel-value
        preparation.  May be ``None`` if using the native SAM2 API directly.
    device:
        Device string on which the model is loaded ('cuda' or 'cpu').
    model_id:
        HuggingFace repo-id that was used to load the weights.
    """
    predictor: Any
    processor: Any
    device: str
    model_id: str


@dataclass
class ViTPoseBundle:
    """
    Holds the ViTPose model and its feature extractor / processor.

    Attributes
    ----------
    model:
        ``ViTPoseForPoseEstimation`` or equivalent transformers model in
        ``eval()`` mode.
    processor:
        ``ViTPoseImageProcessor`` used to prepare input tensors.
    device:
        Device string ('cuda' or 'cpu').
    model_id:
        HuggingFace repo-id.
    """
    model: Any
    processor: Any
    device: str
    model_id: str


@dataclass
class WoundClassifierBundle:
    """
    Holds a ViT / EfficientNet wound-type classifier and its feature extractor.

    Attributes
    ----------
    model:
        ``AutoModelForImageClassification`` in ``eval()`` mode.
    processor:
        ``AutoImageProcessor`` used to preprocess PIL images.
    labels:
        Ordered list of class label strings (wound types).
    device:
        Device string ('cuda' or 'cpu').
    model_id:
        HuggingFace repo-id.
    """
    model: Any
    processor: Any
    labels: list[str]
    device: str
    model_id: str


@dataclass
class MedNERBundle:
    """
    Holds a BioClinicalBERT / PubMedBERT NER pipeline.

    Attributes
    ----------
    pipeline:
        HuggingFace ``transformers.pipeline`` object (task='ner') configured
        for aggregation_strategy='simple' so overlapping sub-word tokens are
        merged into clean entity spans.
    model:
        Underlying ``AutoModelForTokenClassification``.
    tokenizer:
        Underlying ``AutoTokenizer``.
    device:
        Device string ('cuda' or 'cpu').
    model_id:
        HuggingFace repo-id.
    """
    pipeline: Any
    model: Any
    tokenizer: Any
    device: str
    model_id: str


@dataclass
class DeepfakeBundle:
    """
    Holds a deepfake / media-manipulation detection model.

    Attributes
    ----------
    model:
        ``AutoModelForImageClassification`` (ViT / EfficientNet) in ``eval()``
        mode.
    processor:
        ``AutoImageProcessor`` for input preparation.
    labels:
        Ordered list of class label strings (e.g. ['real', 'fake']).
    device:
        Device string ('cuda' or 'cpu').
    model_id:
        HuggingFace repo-id.
    """
    model: Any
    processor: Any
    labels: list[str]
    device: str
    model_id: str


@dataclass
class AudioBundle:
    """
    Holds a Wav2Vec2 / WavLM emotion & stress model plus its feature extractor.

    Attributes
    ----------
    emotion_model:
        ``Wav2Vec2ForSequenceClassification`` for speech emotion recognition.
    emotion_processor:
        ``Wav2Vec2FeatureExtractor`` for the emotion model.
    emotion_labels:
        Ordered list of emotion class strings.
    stress_model:
        Secondary model for stress / arousal prediction (may be ``None`` if
        the stress repo-id is not set).
    stress_processor:
        Feature extractor for the stress model.
    stress_labels:
        Ordered list of stress class strings.
    device:
        Device string ('cuda' or 'cpu').
    sample_rate:
        Expected audio sampling rate in Hz (typically 16000).
    """
    emotion_model: Any
    emotion_processor: Any
    emotion_labels: list[str]
    stress_model: Any
    stress_processor: Any
    stress_labels: list[str]
    device: str
    sample_rate: int = 16_000


# ===========================================================================
# 1. MedSAM2 — wound / injury segmentation
# ===========================================================================

def _load_medsam2_sync() -> MedSAM2Bundle:
    """
    Synchronous implementation of MedSAM2 loading.

    Attempts to load via the HuggingFace transformers ``Sam2Model`` /
    ``Sam2Processor`` path (transformers ≥ 4.45).  If those classes are not
    yet available in the installed version, falls back to the native ``sam2``
    package's ``build_sam2`` + ``SAM2ImagePredictor`` API.
    """
    _require_advanced_vision()
    _set_hf_env()

    cache_key = "medsam2"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    settings = _get_settings()
    model_id = settings.HF_MEDSAM2_MODEL
    device   = _device()

    logger.info("Loading MedSAM2 model '%s' on device '%s' …", model_id, device)

    processor = None
    predictor = None

    # ── Attempt 1: transformers Sam2 API (≥ 4.45) ─────────────────────────
    try:
        from transformers import Sam2Model, Sam2Processor  # type: ignore[attr-defined]

        processor = Sam2Processor.from_pretrained(
            model_id,
            cache_dir=_hf_cache(),
        )
        sam2_model = Sam2Model.from_pretrained(
            model_id,
            cache_dir=_hf_cache(),
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device).eval()

        # Wrap in a lightweight predictor-like facade
        class _HFSam2Predictor:
            """Thin wrapper around Sam2Model for a predictor-compatible API."""
            def __init__(self, mdl, proc, dev):
                self._model     = mdl
                self._processor = proc
                self._device    = dev
                self._image_embeddings = None

            def set_image(self, image: np.ndarray) -> None:
                """Pre-compute image embeddings for subsequent predict calls."""
                from PIL import Image as _PILImage
                pil = _PILImage.fromarray(image)
                inputs = self._processor(images=pil, return_tensors="pt").to(self._device)
                with torch.no_grad():
                    self._image_embeddings = self._model.get_image_embeddings(
                        inputs["pixel_values"]
                    )

            def predict(
                self,
                point_coords=None,
                point_labels=None,
                box=None,
                multimask_output: bool = True,
            ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
                """
                Predict segmentation masks.

                Returns
                -------
                masks       : (N, H, W) boolean array
                scores      : (N,) float array
                logits      : (N, 256, 256) float array
                """
                if self._image_embeddings is None:
                    raise RuntimeError("Call set_image() before predict().")

                inputs: dict[str, Any] = {"image_embeddings": self._image_embeddings}
                if box is not None:
                    inputs["input_boxes"] = torch.tensor(
                        [[box]], dtype=torch.float32, device=self._device
                    )
                if point_coords is not None:
                    inputs["input_points"] = torch.tensor(
                        [point_coords], dtype=torch.float32, device=self._device
                    )
                    inputs["input_labels"] = torch.tensor(
                        [point_labels], dtype=torch.long, device=self._device
                    )

                with torch.no_grad():
                    outputs = self._model(**inputs, multimask_output=multimask_output)

                masks  = (outputs.pred_masks.squeeze().cpu().numpy() > 0)
                scores = outputs.iou_scores.squeeze().cpu().numpy()
                logits = outputs.pred_masks.squeeze().cpu().float().numpy()
                return masks, scores, logits

        predictor = _HFSam2Predictor(sam2_model, processor, device)
        logger.info("MedSAM2 loaded via transformers Sam2 API.")

    except (ImportError, AttributeError):
        logger.warning(
            "transformers Sam2 API not available — falling back to native sam2 package."
        )

    # ── Attempt 2: native sam2 package ────────────────────────────────────
    if predictor is None:
        try:
            from sam2.build_sam import build_sam2_hf          # type: ignore[import]
            from sam2.sam2_image_predictor import SAM2ImagePredictor  # type: ignore[import]

            sam2_model = build_sam2_hf(model_id, device=device)
            predictor  = SAM2ImagePredictor(sam2_model)
            logger.info("MedSAM2 loaded via native sam2 package.")

        except ImportError as exc:
            raise ImportError(
                "Neither transformers Sam2 API nor the 'sam2' package is available. "
                "Install segment-anything-2 or upgrade transformers ≥ 4.45."
            ) from exc

    bundle = MedSAM2Bundle(
        predictor=predictor,
        processor=processor,
        device=device,
        model_id=model_id,
    )
    _MODEL_CACHE[cache_key] = bundle
    logger.info("MedSAM2 ready (device=%s, model=%s).", device, model_id)
    return bundle


async def load_medsam2() -> MedSAM2Bundle:
    """
    Async entry point — load (or return cached) MedSAM2 model bundle.

    The actual weight loading is dispatched to a thread-pool executor so the
    FastAPI event loop is never blocked during the potentially multi-second
    download / deserialisation.

    Returns
    -------
    MedSAM2Bundle
        Named bundle containing ``predictor``, ``processor``, ``device``,
        and ``model_id``.

    Raises
    ------
    RuntimeError
        If ``ENABLE_ADVANCED_VISION`` is ``False``.
    ImportError
        If neither the transformers Sam2 API nor the ``sam2`` package is
        installed.
    """
    if "medsam2" in _MODEL_CACHE:
        return _MODEL_CACHE["medsam2"]
    return await asyncio.to_thread(_load_medsam2_sync)


# ===========================================================================
# 2. ViTPose — human pose estimation
# ===========================================================================

def _load_vitpose_sync() -> ViTPoseBundle:
    """Synchronous implementation of ViTPose loading."""
    _require_advanced_vision()
    _set_hf_env()

    cache_key = "vitpose"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    settings = _get_settings()
    model_id = settings.HF_VITPOSE_MODEL
    device   = _device()

    logger.info("Loading ViTPose model '%s' on device '%s' …", model_id, device)

    try:
        from transformers import (  # type: ignore[attr-defined]
            AutoProcessor,
            VitPoseForPoseEstimation,
        )

        processor = AutoProcessor.from_pretrained(
            model_id,
            cache_dir=_hf_cache(),
        )
        model = VitPoseForPoseEstimation.from_pretrained(
            model_id,
            cache_dir=_hf_cache(),
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device).eval()

    except (ImportError, AttributeError):
        # Fallback: load as a generic ViT image model via AutoModel
        logger.warning(
            "VitPoseForPoseEstimation not found in transformers — "
            "loading as AutoModel (keypoint head may not be available)."
        )
        from transformers import AutoModel, AutoProcessor  # type: ignore[assignment]

        processor = AutoProcessor.from_pretrained(
            model_id, cache_dir=_hf_cache()
        )
        model = AutoModel.from_pretrained(
            model_id,
            cache_dir=_hf_cache(),
            torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ).to(device).eval()

    bundle = ViTPoseBundle(
        model=model,
        processor=processor,
        device=device,
        model_id=model_id,
    )
    _MODEL_CACHE[cache_key] = bundle
    logger.info("ViTPose ready (device=%s, model=%s).", device, model_id)
    return bundle


async def load_vitpose() -> ViTPoseBundle:
    """
    Async entry point — load (or return cached) ViTPose model bundle.

    ViTPose estimates 2-D human body keypoints from a cropped person image.
    In a forensic context this is used to determine body posture, fall
    direction, and injury-consistent positioning.

    Returns
    -------
    ViTPoseBundle
        Named bundle containing ``model``, ``processor``, ``device``,
        and ``model_id``.

    Raises
    ------
    RuntimeError
        If ``ENABLE_ADVANCED_VISION`` is ``False``.

    Example
    -------
    ```python
    from PIL import Image
    bundle = await load_vitpose()
    image  = Image.open("scene.jpg")
    inputs = bundle.processor(images=image, return_tensors="pt")
    inputs = {k: v.to(bundle.device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = bundle.model(**inputs)
    ```
    """
    if "vitpose" in _MODEL_CACHE:
        return _MODEL_CACHE["vitpose"]
    return await asyncio.to_thread(_load_vitpose_sync)


# ===========================================================================
# 3. Wound classifier — ViT / EfficientNet
# ===========================================================================

def _load_wound_classifier_sync() -> WoundClassifierBundle:
    """Synchronous implementation of wound-type classifier loading."""
    _require_advanced_vision()
    _set_hf_env()

    cache_key = "wound_classifier"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    settings = _get_settings()
    model_id = settings.HF_WOUND_CLASSIFIER_MODEL
    device   = _device()

    logger.info("Loading wound classifier '%s' on device '%s' …", model_id, device)

    from transformers import AutoImageProcessor, AutoModelForImageClassification

    processor = AutoImageProcessor.from_pretrained(
        model_id,
        cache_dir=_hf_cache(),
    )
    model = AutoModelForImageClassification.from_pretrained(
        model_id,
        cache_dir=_hf_cache(),
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ignore_mismatched_sizes=True,
    ).to(device).eval()

    # Extract ordered label list from model config
    labels: list[str] = []
    if hasattr(model.config, "id2label"):
        labels = [model.config.id2label[i] for i in sorted(model.config.id2label)]
    else:
        logger.warning("Model '%s' has no id2label config; labels will be empty.", model_id)

    bundle = WoundClassifierBundle(
        model=model,
        processor=processor,
        labels=labels,
        device=device,
        model_id=model_id,
    )
    _MODEL_CACHE[cache_key] = bundle
    logger.info(
        "Wound classifier ready (device=%s, classes=%d, model=%s).",
        device, len(labels), model_id,
    )
    return bundle


async def load_wound_classifier() -> WoundClassifierBundle:
    """
    Async entry point — load (or return cached) wound-type classifier bundle.

    The classifier assigns a wound image to one of several forensically
    relevant categories (e.g. abrasion, laceration, contusion, gunshot,
    stab, burn) to assist pathology triage and case correlation.

    Returns
    -------
    WoundClassifierBundle
        Named bundle containing ``model``, ``processor``, ``labels``,
        ``device``, and ``model_id``.

    Raises
    ------
    RuntimeError
        If ``ENABLE_ADVANCED_VISION`` is ``False``.

    Example
    -------
    ```python
    from PIL import Image
    bundle  = await load_wound_classifier()
    image   = Image.open("wound.jpg").convert("RGB")
    inputs  = bundle.processor(images=image, return_tensors="pt")
    inputs  = {k: v.to(bundle.device) for k, v in inputs.items()}
    with torch.no_grad():
        logits = bundle.model(**inputs).logits
    probs   = torch.softmax(logits, dim=-1).squeeze().tolist()
    results = sorted(zip(bundle.labels, probs), key=lambda x: x[1], reverse=True)
    ```
    """
    if "wound_classifier" in _MODEL_CACHE:
        return _MODEL_CACHE["wound_classifier"]
    return await asyncio.to_thread(_load_wound_classifier_sync)


# ===========================================================================
# 4. Medical NER — BioClinicalBERT / PubMedBERT
# ===========================================================================

def _load_med_ner_sync() -> MedNERBundle:
    """Synchronous implementation of Medical NER pipeline loading."""
    _require_advanced_vision()
    _set_hf_env()

    cache_key = "med_ner"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    settings      = _get_settings()
    model_id      = settings.HF_MED_NER_MODEL
    tokenizer_id  = settings.med_ner_tokenizer_id
    device        = _device()

    logger.info("Loading Medical NER model '%s' on device '%s' …", model_id, device)

    from transformers import (
        AutoModelForTokenClassification,
        AutoTokenizer,
        pipeline,
    )

    tokenizer = AutoTokenizer.from_pretrained(
        tokenizer_id,
        cache_dir=_hf_cache(),
        use_fast=True,
    )
    model = AutoModelForTokenClassification.from_pretrained(
        model_id,
        cache_dir=_hf_cache(),
    ).to(device).eval()

    # pipeline() device argument:  -1 = CPU, 0 = cuda:0, 1 = cuda:1, …
    pipeline_device = 0 if device == "cuda" else -1

    ner_pipeline = pipeline(
        task="ner",
        model=model,
        tokenizer=tokenizer,
        aggregation_strategy="simple",   # merges B-/I- sub-tokens cleanly
        device=pipeline_device,
    )

    bundle = MedNERBundle(
        pipeline=ner_pipeline,
        model=model,
        tokenizer=tokenizer,
        device=device,
        model_id=model_id,
    )
    _MODEL_CACHE[cache_key] = bundle
    logger.info("Medical NER ready (device=%s, model=%s).", device, model_id)
    return bundle


async def load_med_ner() -> MedNERBundle:
    """
    Async entry point — load (or return cached) Medical NER bundle.

    The pipeline recognises clinical entities such as diagnoses, medications,
    dosages, anatomical locations, and procedures from free-text forensic
    reports, autopsy notes, and witness statements.

    Returns
    -------
    MedNERBundle
        Named bundle containing ``pipeline``, ``model``, ``tokenizer``,
        ``device``, and ``model_id``.

    Raises
    ------
    RuntimeError
        If ``ENABLE_ADVANCED_VISION`` is ``False``.

    Example
    -------
    ```python
    bundle   = await load_med_ner()
    entities = bundle.pipeline("Patient presented with blunt-force trauma to the cranium.")
    # [{'entity_group': 'PROBLEM', 'word': 'blunt-force trauma', 'score': 0.97, ...}]
    ```
    """
    if "med_ner" in _MODEL_CACHE:
        return _MODEL_CACHE["med_ner"]
    return await asyncio.to_thread(_load_med_ner_sync)


# ===========================================================================
# 5. Deepfake detector — ViT / EfficientNet
# ===========================================================================

def _load_deepfake_sync() -> DeepfakeBundle:
    """Synchronous implementation of deepfake detector loading."""
    _require_advanced_vision()
    _set_hf_env()

    cache_key = "deepfake"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    settings = _get_settings()
    model_id = settings.HF_DEEPFAKE_MODEL
    device   = _device()

    logger.info("Loading deepfake detector '%s' on device '%s' …", model_id, device)

    from transformers import AutoImageProcessor, AutoModelForImageClassification

    processor = AutoImageProcessor.from_pretrained(
        model_id,
        cache_dir=_hf_cache(),
    )
    model = AutoModelForImageClassification.from_pretrained(
        model_id,
        cache_dir=_hf_cache(),
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        ignore_mismatched_sizes=True,
    ).to(device).eval()

    labels: list[str] = []
    if hasattr(model.config, "id2label"):
        labels = [model.config.id2label[i] for i in sorted(model.config.id2label)]
    else:
        labels = ["real", "fake"]
        logger.warning(
            "Model '%s' has no id2label config; defaulting to ['real', 'fake'].",
            model_id,
        )

    bundle = DeepfakeBundle(
        model=model,
        processor=processor,
        labels=labels,
        device=device,
        model_id=model_id,
    )
    _MODEL_CACHE[cache_key] = bundle
    logger.info(
        "Deepfake detector ready (device=%s, classes=%s, model=%s).",
        device, labels, model_id,
    )
    return bundle


async def load_deepfake_detector() -> DeepfakeBundle:
    """
    Async entry point — load (or return cached) deepfake detector bundle.

    Classifies images / video frames as authentic or manipulated.  In a
    forensic context this supports evidence-integrity verification for
    digital photographs and CCTV stills submitted as evidence.

    Returns
    -------
    DeepfakeBundle
        Named bundle containing ``model``, ``processor``, ``labels``,
        ``device``, and ``model_id``.

    Raises
    ------
    RuntimeError
        If ``ENABLE_ADVANCED_VISION`` is ``False``.

    Example
    -------
    ```python
    from PIL import Image
    bundle  = await load_deepfake_detector()
    image   = Image.open("evidence_photo.jpg").convert("RGB")
    inputs  = bundle.processor(images=image, return_tensors="pt")
    inputs  = {k: v.to(bundle.device) for k, v in inputs.items()}
    with torch.no_grad():
        logits = bundle.model(**inputs).logits
    probs   = torch.softmax(logits, dim=-1).squeeze().tolist()
    verdict = dict(zip(bundle.labels, probs))
    # {'real': 0.08, 'fake': 0.92}
    ```
    """
    if "deepfake" in _MODEL_CACHE:
        return _MODEL_CACHE["deepfake"]
    return await asyncio.to_thread(_load_deepfake_sync)


# ===========================================================================
# 6. Audio — Wav2Vec2 emotion / stress  +  preprocessing helpers
# ===========================================================================

def _load_audio_sync() -> AudioBundle:
    """Synchronous implementation of audio model loading."""
    _require_advanced_vision()
    _set_hf_env()

    cache_key = "audio"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    settings     = _get_settings()
    emotion_id   = settings.HF_AUDIO_EMOTION_MODEL
    stress_id    = settings.HF_AUDIO_STRESS_MODEL
    device       = _device()
    sample_rate  = 16_000

    logger.info(
        "Loading audio models — emotion='%s', stress='%s' on device '%s' …",
        emotion_id, stress_id, device,
    )

    from transformers import (
        Wav2Vec2FeatureExtractor,
        Wav2Vec2ForSequenceClassification,
    )

    # ── Emotion model ─────────────────────────────────────────────────────
    emotion_processor = Wav2Vec2FeatureExtractor.from_pretrained(
        emotion_id,
        cache_dir=_hf_cache(),
    )
    emotion_model = Wav2Vec2ForSequenceClassification.from_pretrained(
        emotion_id,
        cache_dir=_hf_cache(),
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
    ).to(device).eval()
    emotion_labels: list[str] = (
        [emotion_model.config.id2label[i] for i in sorted(emotion_model.config.id2label)]
        if hasattr(emotion_model.config, "id2label")
        else []
    )

    # ── Stress / arousal model (optional — skip if repo-id is blank) ──────
    stress_model     = None
    stress_processor = None
    stress_labels: list[str] = []

    if stress_id:
        try:
            stress_processor = Wav2Vec2FeatureExtractor.from_pretrained(
                stress_id,
                cache_dir=_hf_cache(),
            )
            stress_model = Wav2Vec2ForSequenceClassification.from_pretrained(
                stress_id,
                cache_dir=_hf_cache(),
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
            ).to(device).eval()
            stress_labels = (
                [stress_model.config.id2label[i] for i in sorted(stress_model.config.id2label)]
                if hasattr(stress_model.config, "id2label")
                else []
            )
            logger.info("Audio stress model loaded: '%s'.", stress_id)
        except Exception as exc:
            logger.warning(
                "Could not load stress model '%s': %s — stress analysis disabled.",
                stress_id, exc,
            )

    bundle = AudioBundle(
        emotion_model=emotion_model,
        emotion_processor=emotion_processor,
        emotion_labels=emotion_labels,
        stress_model=stress_model,
        stress_processor=stress_processor,
        stress_labels=stress_labels,
        device=device,
        sample_rate=sample_rate,
    )
    _MODEL_CACHE[cache_key] = bundle
    logger.info(
        "Audio models ready (device=%s, emotion_classes=%d).",
        device, len(emotion_labels),
    )
    return bundle


async def load_audio_models() -> AudioBundle:
    """
    Async entry point — load (or return cached) audio analysis bundle.

    Loads two Wav2Vec2-based classifiers:
    * **emotion model** — classifies speech into discrete emotion categories
      (anger, fear, sadness, neutral, etc.).
    * **stress model**  — estimates arousal / stress level, useful for
      detecting deception indicators or distress in recorded statements.

    Returns
    -------
    AudioBundle
        Named bundle with ``emotion_model``, ``emotion_processor``,
        ``emotion_labels``, ``stress_model``, ``stress_processor``,
        ``stress_labels``, ``device``, and ``sample_rate``.

    Raises
    ------
    RuntimeError
        If ``ENABLE_ADVANCED_VISION`` is ``False``.
    """
    if "audio" in _MODEL_CACHE:
        return _MODEL_CACHE["audio"]
    return await asyncio.to_thread(_load_audio_sync)


# ===========================================================================
# Audio preprocessing utilities
# ===========================================================================

def preprocess_audio_file(
    file_path: str | Path,
    target_sr: int = 16_000,
    max_duration_seconds: float = 30.0,
    normalize: bool = True,
) -> np.ndarray:
    """
    Load an audio file from disk and prepare it for Wav2Vec2 inference.

    Processing steps applied in order:
    1. Decode audio via ``librosa`` (handles MP3, WAV, FLAC, OGG, etc.).
    2. Resample to *target_sr* (Wav2Vec2 models expect 16 kHz mono).
    3. Convert stereo → mono by averaging channels.
    4. Trim silence from both ends (top-dB threshold = 20 dB).
    5. Truncate to *max_duration_seconds* to cap memory use.
    6. Peak-normalise to [-1, 1] when *normalize* is ``True``.

    Parameters
    ----------
    file_path:
        Path to the audio file on disk.
    target_sr:
        Target sample rate in Hz.  Default is 16 000 (Wav2Vec2 standard).
    max_duration_seconds:
        Maximum number of seconds to keep.  Longer recordings are truncated
        from the end.  Set to ``float('inf')`` to disable.
    normalize:
        Peak-normalise the waveform to [-1, 1] before returning.

    Returns
    -------
    np.ndarray
        1-D float32 waveform of shape ``(num_samples,)`` at *target_sr*.

    Raises
    ------
    FileNotFoundError
        If *file_path* does not exist.
    RuntimeError
        If librosa cannot decode the file.
    """
    import librosa  # deferred import — only needed when audio processing is used

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    try:
        waveform, sr = librosa.load(str(path), sr=target_sr, mono=True)
    except Exception as exc:
        raise RuntimeError(f"librosa failed to decode '{path}': {exc}") from exc

    # Trim leading / trailing silence
    waveform, _ = librosa.effects.trim(waveform, top_db=20)

    # Truncate to max duration
    max_samples = int(max_duration_seconds * target_sr)
    if len(waveform) > max_samples:
        waveform = waveform[:max_samples]

    # Peak normalise
    if normalize:
        peak = np.abs(waveform).max()
        if peak > 0:
            waveform = waveform / peak

    return waveform.astype(np.float32)


def preprocess_audio_bytes(
    audio_bytes: bytes,
    source_format: str = "wav",
    target_sr: int = 16_000,
    max_duration_seconds: float = 30.0,
    normalize: bool = True,
) -> np.ndarray:
    """
    Decode raw audio bytes and prepare them for Wav2Vec2 inference.

    Identical processing pipeline to :func:`preprocess_audio_file` but
    accepts in-memory bytes (e.g. from a multipart upload) rather than a
    file path.

    Parameters
    ----------
    audio_bytes:
        Raw audio data as bytes.
    source_format:
        Audio container format hint passed to ``soundfile`` (e.g. ``"wav"``,
        ``"flac"``).  ``"mp3"`` is handled via librosa / audioread.
    target_sr:
        Target sample rate in Hz.
    max_duration_seconds:
        Maximum number of seconds to keep.
    normalize:
        Peak-normalise the waveform to [-1, 1] before returning.

    Returns
    -------
    np.ndarray
        1-D float32 waveform of shape ``(num_samples,)``.
    """
    import io
    import librosa  # deferred import

    buffer = io.BytesIO(audio_bytes)
    try:
        waveform, sr = librosa.load(buffer, sr=target_sr, mono=True)
    except Exception as exc:
        raise RuntimeError(f"librosa failed to decode audio bytes: {exc}") from exc

    waveform, _ = librosa.effects.trim(waveform, top_db=20)

    max_samples = int(max_duration_seconds * target_sr)
    if len(waveform) > max_samples:
        waveform = waveform[:max_samples]

    if normalize:
        peak = np.abs(waveform).max()
        if peak > 0:
            waveform = waveform / peak

    return waveform.astype(np.float32)


def prepare_audio_tensor(
    waveform: np.ndarray,
    processor: Any,
    device: str,
    sample_rate: int = 16_000,
) -> dict[str, torch.Tensor]:
    """
    Convert a raw waveform array into a model-ready input tensor dict.

    Parameters
    ----------
    waveform:
        1-D float32 numpy array produced by :func:`preprocess_audio_file` or
        :func:`preprocess_audio_bytes`.
    processor:
        ``Wav2Vec2FeatureExtractor`` instance from an ``AudioBundle``.
    device:
        Target device string ('cuda' or 'cpu').
    sample_rate:
        Sampling rate of *waveform* (must match what the model expects).

    Returns
    -------
    dict[str, torch.Tensor]
        Input dict suitable for ``model(**inputs)``.  Contains at minimum the
        ``input_values`` key.
    """
    inputs = processor(
        waveform,
        sampling_rate=sample_rate,
        return_tensors="pt",
        padding=True,
    )
    return {k: v.to(device) for k, v in inputs.items()}


# ===========================================================================
# Convenience: warm-up all models at application startup
# ===========================================================================

async def warm_up_all_models() -> dict[str, str]:
    """
    Pre-load every HuggingFace model concurrently at application startup.

    Call this inside the FastAPI lifespan context (``app/main.py``) when
    ``ENABLE_ADVANCED_VISION=true`` to pay the one-time weight-loading cost
    before the first request arrives, rather than on first use.

    Returns
    -------
    dict[str, str]
        Mapping of model name → "ok" or error message, useful for the
        ``/health`` endpoint to report model readiness.

    Example
    -------
    ```python
    # In app/main.py lifespan:
    if settings.ENABLE_ADVANCED_VISION:
        status = await warm_up_all_models()
        logger.info("HF model warm-up: %s", status)
    ```
    """
    loaders = {
        "medsam2":          load_medsam2,
        "vitpose":          load_vitpose,
        "wound_classifier": load_wound_classifier,
        "med_ner":          load_med_ner,
        "deepfake":         load_deepfake_detector,
        "audio":            load_audio_models,
    }

    results: dict[str, str] = {}

    async def _safe_load(name: str, loader) -> None:
        try:
            await loader()
            results[name] = "ok"
            logger.info("✓ Model warm-up complete: %s", name)
        except Exception as exc:
            results[name] = f"error: {exc}"
            logger.error("✗ Model warm-up failed: %s — %s", name, exc)

    await asyncio.gather(*[_safe_load(n, fn) for n, fn in loaders.items()])
    return results
