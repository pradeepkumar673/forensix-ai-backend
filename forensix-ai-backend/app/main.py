"""
app/main.py
-----------
ForensiX AI — FastAPI application factory.

Responsibilities:
  • Create and configure the FastAPI instance
  • Register global middleware  (CORS, request logging, process-time header)
  • Mount ALL API routers under /api/v1
  • Register global exception handlers (validation, HTTP, unexpected)
  • Expose system endpoints  (/health, /ping, /info, /api/v1/status)
  • Manage application lifespan (startup / shutdown)
"""

from __future__ import annotations

import logging
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# ────────────────────────────────────────────────────────────────────────────
# Shared response envelope models
# ────────────────────────────────────────────────────────────────────────────

class SuccessEnvelope(BaseModel):
    """Standard success response wrapper used across all routers."""
    status: str = "success"
    request_id: str
    timestamp: str
    data: Any = None
    message: str = ""


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorEnvelope(BaseModel):
    """Standard error response wrapper used for all error responses."""
    status: str = "error"
    request_id: str
    timestamp: str
    error_code: str
    message: str
    details: list[ErrorDetail] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _error_response(
    request_id: str,
    status_code: int,
    error_code: str,
    message: str,
    details: list[dict] | None = None,
) -> JSONResponse:
    body = ErrorEnvelope(
        request_id=request_id,
        timestamp=_now(),
        error_code=error_code,
        message=message,
        details=[ErrorDetail(**d) for d in (details or [])],
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


# ────────────────────────────────────────────────────────────────────────────
# Lifespan
# ────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("━━━ [startup]  %s v%s ━━━", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Debug mode   : %s", settings.DEBUG)
    logger.info("Ollama URL   : %s", settings.OLLAMA_BASE_URL)
    logger.info("CORS origins : %s", settings.CORS_ORIGINS)

    # ── Future startup hooks ───────────────────────────────────────────────
    # await init_db()
    # await warm_embedding_model()
    
    if settings.ENABLE_ADVANCED_VISION or settings.ENABLE_AUDIO_ANALYSIS:
        try:
            from app.utils.hf_models import warm_up_all_models
            logger.info("Warming up Hugging Face models...")
            warm_up_results = await warm_up_all_models()
            for model_name, status in warm_up_results.items():
                logger.info("Model warmup %s: %s", model_name, status)
        except Exception as exc:
            logger.error("Failed to warm up models: %s", exc)

    yield  # ← application runs here

    logger.info("━━━ [shutdown] %s shutting down ━━━", settings.APP_NAME)
    # await close_db()


# ────────────────────────────────────────────────────────────────────────────
# Application factory
# ────────────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        # Docs are available in debug mode only
        docs_url="/docs"        if settings.DEBUG else None,
        redoc_url="/redoc"      if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
        # Global response models shown in OpenAPI schema
        responses={
            400: {"model": ErrorEnvelope, "description": "Bad request"},
            422: {"model": ErrorEnvelope, "description": "Validation error"},
            500: {"model": ErrorEnvelope, "description": "Internal server error"},
        },
    )

    _add_middleware(app, settings)
    _add_exception_handlers(app)
    _add_system_routes(app, settings)
    _mount_routers(app)

    return app


# ────────────────────────────────────────────────────────────────────────────
# Middleware
# ────────────────────────────────────────────────────────────────────────────

def _add_middleware(app: FastAPI, settings) -> None:

    # 1. CORS — must be first so OPTIONS pre-flights are handled before auth
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # 2. Request-ID + process-time header
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.started_at = time.perf_counter()

        logger.info("→ %s %s  [%s]", request.method, request.url.path, request_id)

        response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - request.state.started_at) * 1000)
        response.headers["X-Request-Id"]    = request_id
        response.headers["X-Process-Time"]  = f"{elapsed_ms}ms"

        logger.info(
            "← %s %s  %d  %dms  [%s]",
            request.method, request.url.path,
            response.status_code, elapsed_ms, request_id,
        )
        return response


# ────────────────────────────────────────────────────────────────────────────
# Exception handlers
# ────────────────────────────────────────────────────────────────────────────

def _add_exception_handlers(app: FastAPI) -> None:

    # 422 Pydantic / FastAPI validation errors
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", "unknown")
        details = []
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err.get("loc", []))
            details.append({"field": field, "message": err["msg"]})
        return _error_response(
            request_id=request_id,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            message="Request body failed validation. Check the details field.",
            details=details,
        )

    # 4xx / 5xx FastAPI HTTP exceptions
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        request_id = getattr(request.state, "request_id", "unknown")
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            429: "TOO_MANY_REQUESTS",
            500: "INTERNAL_SERVER_ERROR",
            503: "SERVICE_UNAVAILABLE",
        }
        error_code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
        return _error_response(
            request_id=request_id,
            status_code=exc.status_code,
            error_code=error_code,
            message=str(exc.detail),
        )

    # Unexpected / unhandled exceptions — never leak stack traces to clients
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "Unhandled exception [%s]: %s\n%s",
            request_id, exc, traceback.format_exc(),
        )
        return _error_response(
            request_id=request_id,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred. Please try again or contact support.",
        )


# ────────────────────────────────────────────────────────────────────────────
# System / meta endpoints
# ────────────────────────────────────────────────────────────────────────────

def _add_system_routes(app: FastAPI, settings) -> None:

    @app.get(
        "/health",
        tags=["System"],
        summary="Liveness probe",
        response_description="Service health status",
    )
    async def health_check(request: Request):
        """
        Lightweight liveness probe for Docker / K8s health checks and
        load-balancer target-group checks.
        """
        return JSONResponse({
            "status": "ok",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "timestamp": _now(),
            "request_id": getattr(request.state, "request_id", "—"),
        })

    @app.get(
        "/ping",
        tags=["System"],
        summary="Minimal ping",
    )
    async def ping():
        """Returns pong — useful for network-level connectivity checks."""
        return {"ping": "pong"}

    @app.get(
        "/status/models",
        tags=["System"],
        summary="Model status check",
        response_model=dict[str, Any],
    )
    async def model_status_check():
        """Check which models are loaded and available."""
        from app.utils.hf_models import _MODEL_CACHE
        return {
            "status": "ok",
            "llm_provider": "featherless" if settings.ENABLE_FEATHERLESS else "ollama",
            "vision_enabled": settings.ENABLE_ADVANCED_VISION,
            "audio_enabled": settings.ENABLE_AUDIO_ANALYSIS,
            "loaded_hf_models": list(_MODEL_CACHE.keys()) if _MODEL_CACHE else []
        }

    @app.get(
        "/info",
        tags=["System"],
        summary="Application metadata",
    )
    async def app_info():
        """Returns application metadata and environment details."""
        return {
            "name":        settings.APP_NAME,
            "version":     settings.APP_VERSION,
            "description": settings.APP_DESCRIPTION,
            "debug":       settings.DEBUG,
            "ollama_url":  settings.OLLAMA_BASE_URL,
            "docs":        "/docs" if settings.DEBUG else "disabled",
        }

    @app.get(
        "/api/v1/status",
        tags=["System"],
        summary="API v1 status — all router prefixes",
    )
    async def api_status():
        """Lists every mounted router prefix so the frontend can verify routing."""
        return {
            "api_version": "v1",
            "base_prefix": "/api/v1",
            "routers": {
                "upload":      "/api/v1/upload",
                "analysis":    "/api/v1/analyze",
                "correlation": "/api/v1/correlation",
                "risk":        "/api/v1/risk",
                "assistant":   "/api/v1/assistant",
                "report":      "/api/v1/report",
            },
            "timestamp": _now(),
        }


# ────────────────────────────────────────────────────────────────────────────
# Router registration
# ────────────────────────────────────────────────────────────────────────────

def _mount_routers(app: FastAPI) -> None:
    """
    Import and mount every feature router.

    All routers are versioned under /api/v1.
    Each router module owns its own sub-prefix  (e.g. router.prefix = "/upload"),
    so the final paths are  /api/v1/upload/report,  /api/v1/risk/score, etc.
    """

    # ── Upload ───────────────────────────────────────────────────────────────
    try:
        from app.routers import upload
        app.include_router(
            upload.router,
            prefix="/api/v1",
            tags=["Upload"],
        )
        logger.info("✓ Router mounted: upload  → /api/v1/upload/*")
    except Exception as exc:
        logger.warning("✗ Router upload failed to load: %s", exc)

    # ── Analysis ─────────────────────────────────────────────────────────────
    try:
        from app.routers import analysis
        app.include_router(
            analysis.router,
            prefix="/api/v1",
            tags=["Analysis"],
        )
        logger.info("✓ Router mounted: analysis → /api/v1/analyze/*")
    except Exception as exc:
        logger.warning("✗ Router analysis failed to load: %s", exc)

    # ── Correlation & Graph ───────────────────────────────────────────────────
    try:
        from app.routers import correlation
        app.include_router(
            correlation.router,
            prefix="/api/v1",
            tags=["Correlation"],
        )
        logger.info("✓ Router mounted: correlation → /api/v1/correlation/*")
    except Exception as exc:
        logger.warning("✗ Router correlation failed to load: %s", exc)

    # ── Risk ──────────────────────────────────────────────────────────────────
    try:
        from app.routers import risk
        app.include_router(
            risk.router,
            prefix="/api/v1",
            tags=["Risk Analysis"],
        )
        logger.info("✓ Router mounted: risk → /api/v1/risk/*")
    except Exception as exc:
        logger.warning("✗ Router risk failed to load: %s", exc)

    # ── Forensic Assistant ────────────────────────────────────────────────────
    try:
        from app.routers import assistant
        app.include_router(
            assistant.router,
            prefix="/api/v1",
            tags=["Forensic Assistant"],
        )
        logger.info("✓ Router mounted: assistant → /api/v1/assistant/*")
    except Exception as exc:
        logger.warning("✗ Router assistant failed to load: %s", exc)

    # ── Report generation ─────────────────────────────────────────────────────
    try:
        from app.routers import report          # see inline definition below if missing
        app.include_router(
            report.router,
            prefix="/api/v1",
            tags=["Report"],
        )
        logger.info("✓ Router mounted: report → /api/v1/report/*")
    except ImportError:
        # report router not yet created as a separate file → attach inline
        _attach_inline_report_router(app)
    except Exception as exc:
        logger.warning("✗ Router report failed to load: %s", exc)


# ────────────────────────────────────────────────────────────────────────────
# Inline report router  (active until app/routers/report.py is created)
# ────────────────────────────────────────────────────────────────────────────

def _attach_inline_report_router(app: FastAPI) -> None:
    """
    Minimal /api/v1/report router wired directly to report_service.
    Replace with app/routers/report.py when you want to expand it.
    """
    from fastapi import APIRouter
    from fastapi.responses import FileResponse
    from pathlib import Path

    report_router = APIRouter(prefix="/api/v1/report", tags=["Report"])

    @report_router.post(
        "/generate",
        summary="Generate a full forensic PDF report",
        response_description="PDF file download",
    )
    async def generate_report(request: Request, report_data: dict):
        """
        Generate a multi-section forensic PDF from combined analysis data.

        Accepts a JSON body with keys:
          - case_context  (dict)
          - risk_score    (dict)
          - anomalies     (dict)
          - contradictions (dict)
          - leads         (dict)
          - timeline_events (list)

        Returns the PDF as a file download.
        """
        try:
            from app.services.report_service import generate_case_report
            pdf_path = await generate_case_report(report_data)
            return FileResponse(
                path=pdf_path,
                filename=Path(pdf_path).name,
                media_type="application/pdf",
                headers={"X-Request-Id": getattr(request.state, "request_id", "—")},
            )
        except Exception as exc:
            logger.exception("Report generation failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Report generation failed: {str(exc)}",
            )

    @report_router.get(
        "/list",
        summary="List previously generated reports",
    )
    async def list_reports():
        """Returns file names of all PDFs in the outputs/ directory."""
        from pathlib import Path
        outputs = Path("outputs")
        if not outputs.exists():
            return {"reports": []}
        pdfs = sorted(
            [f.name for f in outputs.glob("*.pdf")],
            reverse=True,
        )
        return {"reports": pdfs, "count": len(pdfs)}

    @report_router.get(
        "/download/{filename}",
        summary="Download a previously generated report by filename",
    )
    async def download_report(filename: str, request: Request):
        """Download a specific PDF by filename from the outputs/ directory."""
        from pathlib import Path
        safe_name = Path(filename).name
        if safe_name != filename or not safe_name.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Invalid filename")
        outputs = Path("outputs").resolve()
        path = (outputs / safe_name).resolve()
        if not path.is_relative_to(outputs):
            raise HTTPException(status_code=400, detail="Invalid path")
        if not path.exists():
            raise HTTPException(404, f"Report '{filename}' not found.")
        return FileResponse(
            path=str(path),
            filename=safe_name,
            media_type="application/pdf"
        )

    app.include_router(report_router)
    logger.info("✓ Router mounted: report (inline) → /api/v1/report/*")


# ────────────────────────────────────────────────────────────────────────────
# App instance  (imported by uvicorn as  "app.main:app")
# ────────────────────────────────────────────────────────────────────────────

app = create_app()
