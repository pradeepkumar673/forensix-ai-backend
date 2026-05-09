"""
app/core/config.py
------------------
Central configuration for the Forensix AI API.
All settings are read from environment variables or a .env file,
with sensible defaults so the app runs out of the box.

New in this revision
--------------------
* HUGGINGFACE_CACHE_DIR  — local directory where HF Hub caches downloaded models
* DEVICE                 — inference device: "cuda" | "cpu" | "auto"
* ENABLE_ADVANCED_VISION — feature flag that gates the HuggingFace CV pipeline
* Per-model HF repo-id overrides for every advanced-vision capability
"""

from __future__ import annotations

import torch
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ------------------------------------------------------------------ #
    # Application metadata                                                 #
    # ------------------------------------------------------------------ #
    APP_NAME: str = Field(
        default="Forensix AI API",
        description="Display name of the service",
    )
    APP_VERSION: str = Field(
        default="0.2.0",
        description="Semantic version string",
    )
    APP_DESCRIPTION: str = Field(
        default=(
            "Backend API for the Forensix AI analysis platform — "
            "combining Ollama LLM inference with advanced HuggingFace "
            "forensic computer-vision models."
        ),
        description="Short description shown in the OpenAPI docs",
    )
    DEBUG: bool = Field(default=False, description="Enable debug / hot-reload mode")

    # ------------------------------------------------------------------ #
    # Server                                                               #
    # ------------------------------------------------------------------ #
    HOST: str = Field(default="0.0.0.0", description="Bind address for Uvicorn")
    PORT: int = Field(default=8000, description="Bind port for Uvicorn")

    # ------------------------------------------------------------------ #
    # CORS — list every origin that your React dev/prod server may use    #
    # ------------------------------------------------------------------ #
    CORS_ORIGINS: list[str] = Field(
        default=[
            "http://localhost:3000",   # React dev server (CRA / Vite default)
            "http://localhost:5173",   # Vite alternative port
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        description="Allowed CORS origins (add your production domain here)",
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True)
    CORS_ALLOW_METHODS: list[str] = Field(default=["*"])
    CORS_ALLOW_HEADERS: list[str] = Field(default=["*"])

    # ------------------------------------------------------------------ #
    # Ollama / LLM  (existing — unchanged)                                #
    # ------------------------------------------------------------------ #
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434",
        description="Base URL of the local Ollama server",
    )
    OLLAMA_MODEL: str = Field(
        default="llama3",
        description="Default Ollama model used for text inference",
    )
    OLLAMA_VISION_MODEL: str = Field(
        default="llava-llama3",
        description="Default Ollama model used for vision inference",
    )

    # ------------------------------------------------------------------ #
    # Featherless AI                                                       #
    # ------------------------------------------------------------------ #
    ENABLE_FEATHERLESS: bool = Field(
        default=True,
        description="Enable Featherless AI as an alternative LLM provider",
    )
    FEATHERLESS_API_KEY: str = Field(
        default="",
        description="Featherless AI API Key",
    )
    FEATHERLESS_BASE_URL: str = Field(
        default="https://api.featherless.ai/v1",
        description="Featherless AI base URL",
    )
    FEATHERLESS_MODEL: str = Field(
        default="meta-llama/Meta-Llama-3-70B-Instruct",
        description="Default Featherless model",
    )


    # ------------------------------------------------------------------ #
    # Vector store / embeddings  (existing — unchanged)                   #
    # ------------------------------------------------------------------ #
    CHROMA_PERSIST_DIR: str = Field(
        default="./data/chroma",
        description="Directory where ChromaDB persists its data",
    )
    EMBEDDING_MODEL: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence-Transformers model used for embeddings",
    )

    # ------------------------------------------------------------------ #
    # File uploads  (existing — unchanged)                                #
    # ------------------------------------------------------------------ #
    UPLOAD_DIR: str = Field(
        default="./data/uploads",
        description="Temporary directory for uploaded evidence files",
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=50,
        description="Maximum allowed upload size in megabytes",
    )

    # ================================================================== #
    # ██  HUGGING FACE — global settings  ██                             #
    # ================================================================== #

    # ------------------------------------------------------------------
    # Model cache directory
    # ------------------------------------------------------------------
    # Where HuggingFace Hub stores downloaded model weights & configs.
    # Defaults to ./data/hf_cache so all artefacts stay inside the
    # project tree and won't pollute the user's home directory.
    # Override via env:  HUGGINGFACE_CACHE_DIR=/mnt/models/hf
    # ------------------------------------------------------------------
    HUGGINGFACE_CACHE_DIR: str = Field(
        default="./data/hf_cache",
        description=(
            "Local directory used by huggingface_hub as the model/weight cache. "
            "Set HF_HOME or TRANSFORMERS_CACHE to the same path if needed."
        ),
    )

    # ------------------------------------------------------------------
    # Inference device
    # ------------------------------------------------------------------
    # "auto"  → GPU (CUDA) if available, otherwise CPU  (recommended)
    # "cuda"  → Force GPU — will raise at load time if unavailable
    # "cpu"   → Force CPU — slower but always safe
    # Override via env:  DEVICE=cuda
    # ------------------------------------------------------------------
    DEVICE: Literal["auto", "cuda", "cpu"] = Field(
        default="auto",
        description=(
            "PyTorch inference device. "
            "'auto' selects CUDA when available, falls back to CPU."
        ),
    )

    # ------------------------------------------------------------------
    # Advanced vision feature flag
    # ------------------------------------------------------------------
    # Set to False to disable all HuggingFace CV model loading at startup.
    # Useful when running in lightweight environments (CI, low-RAM servers)
    # where heavy GPU models should not be initialised.
    # Override via env:  ENABLE_ADVANCED_VISION=true
    # ------------------------------------------------------------------
    ENABLE_ADVANCED_VISION: bool = Field(
        default=False,
        description=(
            "Master switch for the HuggingFace advanced computer-vision pipeline. "
            "When False, vision service endpoints return 503 gracefully."
        ),
    )

    ENABLE_AUDIO_ANALYSIS: bool = Field(
        default=False,
        description="Master switch for HuggingFace audio (Wav2Vec2) processing models.",
    )


    # ================================================================== #
    # ██  HUGGING FACE — per-model repo-id overrides  ██                #
    # These ship with sane public defaults; override in .env if you      #
    # host fine-tuned variants on a private HF Hub or local path.        #
    # ================================================================== #

    # ------------------------------------------------------------------
    # MedSAM2 — medical / forensic image segmentation
    # ------------------------------------------------------------------
    # Upstream SAM2 checkpoint served via the official Meta repo;
    # MedSAM2 fine-tuned weights may be swapped in via env var.
    HF_MEDSAM2_MODEL: str = Field(
        default="facebook/sam2-hiera-large",
        description="HuggingFace repo-id for MedSAM2 / SAM2 segmentation model",
    )

    # ------------------------------------------------------------------
    # ViTPose — human pose estimation
    # ------------------------------------------------------------------
    HF_VITPOSE_MODEL: str = Field(
        default="usyd-community/vitpose-base-simple",
        description="HuggingFace repo-id for ViTPose pose estimation model",
    )

    # ------------------------------------------------------------------
    # Wound classification — ViT / CNN fine-tuned on wound imagery
    # ------------------------------------------------------------------
    HF_WOUND_CLASSIFIER_MODEL: str = Field(
        default="Annas-AI-Labs/wound_classification",
        description="HuggingFace repo-id for wound-type image classification model",
    )

    # ------------------------------------------------------------------
    # Medical NER — BioClinicalBERT / PubMedBERT
    # ------------------------------------------------------------------
    HF_MED_NER_MODEL: str = Field(
        default="samrawal/bert-base-uncased_clinical-ner",
        description=(
            "HuggingFace repo-id for the medical Named-Entity Recognition model "
            "(BioClinicalBERT or PubMedBERT fine-tuned on clinical text)"
        ),
    )
    HF_MED_NER_TOKENIZER: str = Field(
        default="",  # empty → use same id as HF_MED_NER_MODEL
        description=(
            "Tokenizer repo-id for the medical NER model. "
            "Leave empty to use the same repo as HF_MED_NER_MODEL."
        ),
    )

    # ------------------------------------------------------------------
    # Deepfake detection — MesoNet / Xception-based classifier
    # ------------------------------------------------------------------
    HF_DEEPFAKE_MODEL: str = Field(
        default="Wvolf/ViT_Deepfake_Detection",
        description=(
            "HuggingFace repo-id for the deepfake/media-manipulation detection model "
            "(MesoNet, Xception, or ViT-based)"
        ),
    )

    # ------------------------------------------------------------------
    # Audio analysis — Wav2Vec2 emotion & stress detection
    # ------------------------------------------------------------------
    HF_AUDIO_EMOTION_MODEL: str = Field(
        default="ehcalabres/wav2vec2-lg-xlsr-en-speech-emotion-recognition",
        description="HuggingFace repo-id for Wav2Vec2 speech-emotion recognition model",
    )
    HF_AUDIO_STRESS_MODEL: str = Field(
        default="3loi/SER-Odyssey-Baseline-WavLM-Categorical-Attributes",
        description=(
            "HuggingFace repo-id for audio stress / arousal detection model "
            "(used as a secondary indicator in forensic audio analysis)"
        ),
    )

    # ================================================================== #
    # ██  HUGGING FACE — inference hyper-parameters  ██                 #
    # ================================================================== #

    # Maximum image dimension (pixels) before downscaling for CV models.
    # Keeps VRAM usage predictable; SAM2 & ViTPose work best at ≤1024.
    CV_MAX_IMAGE_DIM: int = Field(
        default=1024,
        description="Maximum image side-length (px) fed to HF vision models",
    )

    # Batch size for NER / text processing
    NER_BATCH_SIZE: int = Field(
        default=8,
        description="Token-batch size used when running Medical NER over long text",
    )

    # Confidence threshold below which vision predictions are flagged as uncertain
    CV_CONFIDENCE_THRESHOLD: float = Field(
        default=0.45,
        description=(
            "Minimum confidence score (0–1) for HF model predictions to be "
            "included in the forensic report without an 'uncertain' flag"
        ),
    )

    # ------------------------------------------------------------------ #
    # Pydantic-settings: read from .env file when present                 #
    # ------------------------------------------------------------------ #
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,   # ENV_VAR names must match exactly
        extra="ignore",        # silently drop unknown env vars
    )

    # ------------------------------------------------------------------ #
    # Computed / derived properties                                        #
    # ------------------------------------------------------------------ #

    @property
    def resolved_device(self) -> str:
        """
        Return the concrete torch device string ("cuda" or "cpu").

        When DEVICE is "auto", checks torch.cuda.is_available() at runtime
        so the setting is evaluated lazily — safe to call before torch init.
        """
        if self.DEVICE == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return self.DEVICE

    @property
    def hf_cache_path(self) -> Path:
        """
        Return HUGGINGFACE_CACHE_DIR as an absolute Path, creating it if absent.
        """
        p = Path(self.HUGGINGFACE_CACHE_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def med_ner_tokenizer_id(self) -> str:
        """
        Return the tokenizer repo-id for MedNER, defaulting to the model id
        when HF_MED_NER_TOKENIZER is left blank.
        """
        return self.HF_MED_NER_TOKENIZER or self.HF_MED_NER_MODEL

    # ------------------------------------------------------------------ #
    # Validators                                                           #
    # ------------------------------------------------------------------ #

    @field_validator("CV_CONFIDENCE_THRESHOLD")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("CV_CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        return v

    @field_validator("MAX_UPLOAD_SIZE_MB")
    @classmethod
    def _validate_upload_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError("MAX_UPLOAD_SIZE_MB must be at least 1")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return a cached singleton Settings instance.

    Using lru_cache means the .env file is parsed only once per process,
    not on every request.  Call `get_settings.cache_clear()` in tests to
    force a fresh load.

    Side-effect: sets the HF_HOME environment variable so that
    huggingface_hub, transformers, and tokenizers all use the configured
    cache directory without extra code in each service module.
    """
    import os
    settings = Settings()

    # Propagate cache dir to all HuggingFace libraries via environment
    cache_str = str(settings.hf_cache_path)
    os.environ.setdefault("HF_HOME", cache_str)
    os.environ.setdefault("TRANSFORMERS_CACHE", cache_str)
    os.environ.setdefault("HF_DATASETS_CACHE", cache_str)

    return settings
