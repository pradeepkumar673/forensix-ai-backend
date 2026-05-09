"""
app/services/audio_service.py
-----------------------------
Forensic audio analysis service.

Provides transcription via Whisper and stress/emotion analysis via Wav2Vec2.
"""

from __future__ import annotations

import logging
from typing import Any
from pathlib import Path
import asyncio

import torch

from app.core.config import get_settings
from app.utils.hf_models import (
    load_audio_models,
    preprocess_audio_bytes,
    prepare_audio_tensor,
)

logger = logging.getLogger(__name__)

async def analyze_audio_stress(audio_bytes: bytes) -> dict[str, Any]:
    """
    Perform emotion and stress analysis on an audio clip using Wav2Vec2 models.
    """
    settings = get_settings()
    if not settings.ENABLE_AUDIO_ANALYSIS:
        return {
            "status": "error",
            "error": "Audio analysis is disabled in configuration.",
        }

    try:
        bundle = await load_audio_models()
        waveform = preprocess_audio_bytes(
            audio_bytes,
            target_sr=bundle.sample_rate,
            max_duration_seconds=60.0
        )
        
        # 1. Emotion inference
        emotion_inputs = prepare_audio_tensor(waveform, bundle.emotion_processor, bundle.device, bundle.sample_rate)
        with torch.no_grad():
            emo_logits = bundle.emotion_model(**emotion_inputs).logits
        emo_probs = torch.softmax(emo_logits, dim=-1).squeeze().tolist()
        
        if not isinstance(emo_probs, list):
            emo_probs = [emo_probs]
            
        emo_results = sorted(zip(bundle.emotion_labels, emo_probs), key=lambda x: x[1], reverse=True)
        
        # 2. Stress inference (if available)
        stress_results = []
        if bundle.stress_model is not None:
            stress_inputs = prepare_audio_tensor(waveform, bundle.stress_processor, bundle.device, bundle.sample_rate)
            with torch.no_grad():
                stress_logits = bundle.stress_model(**stress_inputs).logits
            stress_probs = torch.softmax(stress_logits, dim=-1).squeeze().tolist()
            if not isinstance(stress_probs, list):
                stress_probs = [stress_probs]
            stress_results = sorted(zip(bundle.stress_labels, stress_probs), key=lambda x: x[1], reverse=True)

        return {
            "status": "ok",
            "primary_emotion": emo_results[0][0],
            "emotion_confidence": emo_results[0][1],
            "all_emotions": [{"label": e[0], "score": e[1]} for e in emo_results[:3]],
            "stress_indicators": [{"label": s[0], "score": s[1]} for s in stress_results[:3]] if stress_results else [],
            "overall_assessment": "Analysis complete.",
        }
    except Exception as exc:
        logger.error("Audio stress analysis failed: %s", exc)
        return {"status": "error", "error": str(exc)}

async def transcribe_audio(audio_bytes: bytes) -> dict[str, Any]:
    """
    Transcribe audio using Whisper-small via Transformers pipeline.
    """
    settings = get_settings()
    if not settings.ENABLE_AUDIO_ANALYSIS:
        return {
            "status": "error",
            "error": "Audio analysis is disabled in configuration.",
        }

    try:
        from transformers import pipeline
        # Lazy load pipeline
        device = 0 if settings.resolved_device == "cuda" else -1
        pipe = await asyncio.to_thread(
            pipeline, 
            "automatic-speech-recognition", 
            model="openai/whisper-small", 
            device=device
        )
        
        # Convert bytes to waveform
        waveform = preprocess_audio_bytes(
            audio_bytes,
            target_sr=16000,
            max_duration_seconds=300.0 # 5 mins max
        )
        
        result = await asyncio.to_thread(pipe, waveform)
        return {
            "status": "ok",
            "transcription": result.get("text", "").strip(),
        }
    except Exception as exc:
        logger.error("Audio transcription failed: %s", exc)
        return {"status": "error", "error": str(exc)}
