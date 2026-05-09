"""
app/routers/upload.py
---------------------
File upload endpoints for the Forensix AI backend.

Endpoints:
  POST /upload/report          → Autopsy / forensic PDF report
  POST /upload/images          → Crime scene / evidence images (bulk)
  POST /upload/digital-evidence → Digital artefacts (logs, dumps, archives)
  POST /upload/statements      → Witness / suspect statement documents

All files are saved under the /uploads directory, organised by category,
and the endpoint returns the saved file paths along with basic metadata.
"""

import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

# --------------------------------------------------------------------------- #
# Router                                                                        #
# --------------------------------------------------------------------------- #

router = APIRouter(
    prefix="/upload",
    tags=["Upload"],
)

# --------------------------------------------------------------------------- #
# Upload root and sub-directories                                               #
# --------------------------------------------------------------------------- #

UPLOAD_ROOT = Path("uploads")

CATEGORY_DIRS = {
    "report":           UPLOAD_ROOT / "reports",
    "images":           UPLOAD_ROOT / "images",
    "digital_evidence": UPLOAD_ROOT / "digital_evidence",
    "statements":       UPLOAD_ROOT / "statements",
}

# Allowed MIME types per category (guards against malicious uploads)
ALLOWED_TYPES: dict[str, set[str]] = {
    "report": {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    },
    "images": {
        "image/jpeg",
        "image/png",
        "image/tiff",
        "image/bmp",
        "image/webp",
        "image/gif",
    },
    "digital_evidence": {
        "application/zip",
        "application/x-tar",
        "application/gzip",
        "application/x-7z-compressed",
        "application/octet-stream",   # generic binary / memory dumps
        "text/plain",                 # log files
        "text/csv",
        "application/json",
        "application/xml",
        "text/xml",
    },
    "statements": {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "image/jpeg",   # scanned statements
        "image/png",
        "image/tiff",
    },
}

# Maximum file sizes per category (bytes)
MAX_FILE_SIZE: dict[str, int] = {
    "report":           50  * 1024 * 1024,   # 50 MB
    "images":           100 * 1024 * 1024,   # 100 MB per image
    "digital_evidence": 500 * 1024 * 1024,   # 500 MB
    "statements":       50  * 1024 * 1024,   # 50 MB
}

# --------------------------------------------------------------------------- #
# Helpers                                                                       #
# --------------------------------------------------------------------------- #

def _ensure_upload_dirs() -> None:
    """Create upload sub-directories if they don't exist yet."""
    for directory in CATEGORY_DIRS.values():
        directory.mkdir(parents=True, exist_ok=True)


def _unique_filename(original_name: str) -> str:
    """
    Return a collision-free filename by prepending a short UUID segment.

    Example: "autopsy_report.pdf" → "a3f1c2d4_autopsy_report.pdf"
    """
    stem   = Path(original_name).stem
    suffix = Path(original_name).suffix
    uid    = uuid.uuid4().hex[:8]
    return f"{uid}_{stem}{suffix}"


def _validate_file(
    file:     UploadFile,
    category: str,
    size:     int,
) -> None:
    """
    Raise HTTPException if the file fails content-type or size validation.
    """
    # Content-type check (browser-reported; not bullet-proof but useful)
    if file.content_type not in ALLOWED_TYPES[category]:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File '{file.filename}' has unsupported type '{file.content_type}'. "
                f"Allowed for {category}: {sorted(ALLOWED_TYPES[category])}"
            ),
        )

    # Size check
    limit = MAX_FILE_SIZE[category]
    if size > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File '{file.filename}' is {size / (1024*1024):.1f} MB. "
                f"Maximum allowed for {category} is {limit // (1024*1024)} MB."
            ),
        )


async def _save_file(file: UploadFile, category: str) -> dict:
    """
    Read, validate, and persist a single UploadFile to disk.

    Returns a metadata dict describing the saved file.
    """
    _ensure_upload_dirs()

    # Read the entire file into memory so we can check its size.
    # For very large uploads consider streaming directly to disk instead.
    contents = await file.read()
    size      = len(contents)

    _validate_file(file, category, size)

    dest_dir      = CATEGORY_DIRS[category]
    safe_name     = _unique_filename(file.filename or "unknown")
    dest_path     = dest_dir / safe_name

    # Write to disk
    dest_path.write_bytes(contents)

    return {
        "original_filename": file.filename,
        "saved_filename":    safe_name,
        "file_path":         str(dest_path),          # relative path
        "absolute_path":     str(dest_path.resolve()), # absolute path on server
        "content_type":      file.content_type,
        "size_bytes":        size,
        "size_mb":           round(size / (1024 * 1024), 3),
        "uploaded_at":       datetime.now(timezone.utc).isoformat(),
    }

# --------------------------------------------------------------------------- #
# POST /upload/report                                                           #
# --------------------------------------------------------------------------- #

@router.post(
    "/report",
    summary="Upload forensic / autopsy report",
    description=(
        "Upload a single forensic report (PDF, DOCX, or TXT). "
        "The file is saved to uploads/reports/ and the saved path is returned."
    ),
    status_code=status.HTTP_201_CREATED,
)
async def upload_report(
    file: UploadFile = File(..., description="Autopsy or forensic report file (PDF/DOCX/TXT)"),
) -> JSONResponse:
    """
    Accept one forensic report and persist it under uploads/reports/.

    The file is renamed with a UUID prefix to prevent collisions.
    """
    try:
        metadata = await _save_file(file, "report")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save report: {exc}",
        ) from exc

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "status":   "success",
            "message":  "Forensic report uploaded successfully.",
            "category": "report",
            "file":     metadata,
        },
    )

# --------------------------------------------------------------------------- #
# POST /upload/images                                                           #
# --------------------------------------------------------------------------- #

@router.post(
    "/images",
    summary="Upload crime scene / evidence images",
    description=(
        "Upload one or more images (JPEG, PNG, TIFF, BMP, WEBP). "
        "All files are saved to uploads/images/ and their paths are returned."
    ),
    status_code=status.HTTP_201_CREATED,
)
async def upload_images(
    files: List[UploadFile] = File(..., description="One or more image files"),
) -> JSONResponse:
    """
    Accept multiple evidence images and persist them under uploads/images/.

    Each image is saved with a unique filename to avoid collisions.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image files were provided.",
        )

    saved: list[dict] = []
    errors: list[dict] = []

    for file in files:
        try:
            metadata = await _save_file(file, "images")
            saved.append(metadata)
        except HTTPException as exc:
            # Collect per-file errors instead of aborting the whole batch
            errors.append({"filename": file.filename, "error": exc.detail})
        except Exception as exc:
            errors.append({"filename": file.filename, "error": str(exc)})

    if not saved and errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "All image uploads failed.", "errors": errors},
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "status":        "success" if not errors else "partial",
            "message":       f"{len(saved)} image(s) uploaded successfully.",
            "category":      "images",
            "files":         saved,
            "failed_count":  len(errors),
            "errors":        errors,
        },
    )

# --------------------------------------------------------------------------- #
# POST /upload/digital-evidence                                                 #
# --------------------------------------------------------------------------- #

@router.post(
    "/digital-evidence",
    summary="Upload digital evidence artefacts",
    description=(
        "Upload digital evidence such as ZIP archives, memory dumps, log files, "
        "JSON exports, or CSV datasets. Saved to uploads/digital_evidence/."
    ),
    status_code=status.HTTP_201_CREATED,
)
async def upload_digital_evidence(
    files: List[UploadFile] = File(..., description="Digital evidence files (ZIP, log, dump, CSV, JSON, etc.)"),
) -> JSONResponse:
    """
    Accept one or more digital evidence files and persist them under
    uploads/digital_evidence/.

    Supports: ZIP, TAR, GZ, 7Z, binary dumps, plain-text logs, CSV, JSON, XML.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No digital evidence files were provided.",
        )

    saved: list[dict] = []
    errors: list[dict] = []

    for file in files:
        try:
            metadata = await _save_file(file, "digital_evidence")
            saved.append(metadata)
        except HTTPException as exc:
            errors.append({"filename": file.filename, "error": exc.detail})
        except Exception as exc:
            errors.append({"filename": file.filename, "error": str(exc)})

    if not saved and errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "All digital evidence uploads failed.", "errors": errors},
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "status":       "success" if not errors else "partial",
            "message":      f"{len(saved)} digital evidence file(s) uploaded successfully.",
            "category":     "digital_evidence",
            "files":        saved,
            "failed_count": len(errors),
            "errors":       errors,
        },
    )

# --------------------------------------------------------------------------- #
# POST /upload/statements                                                       #
# --------------------------------------------------------------------------- #

@router.post(
    "/statements",
    summary="Upload witness / suspect statements",
    description=(
        "Upload one or more witness or suspect statements (PDF, DOCX, TXT, or "
        "scanned image). Saved to uploads/statements/."
    ),
    status_code=status.HTTP_201_CREATED,
)
async def upload_statements(
    files: List[UploadFile] = File(..., description="Statement documents (PDF/DOCX/TXT/Image)"),
) -> JSONResponse:
    """
    Accept one or more statement files and persist them under uploads/statements/.

    Scanned statement images (JPEG / PNG / TIFF) are also accepted and can be
    passed to the vision service for OCR in a subsequent analysis step.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No statement files were provided.",
        )

    saved: list[dict] = []
    errors: list[dict] = []

    for file in files:
        try:
            metadata = await _save_file(file, "statements")

            # Tag each statement with whether it appears to be a scanned image
            # so downstream services know whether to run OCR.
            metadata["is_scanned_image"] = (
                file.content_type is not None
                and file.content_type.startswith("image/")
            )

            saved.append(metadata)
        except HTTPException as exc:
            errors.append({"filename": file.filename, "error": exc.detail})
        except Exception as exc:
            errors.append({"filename": file.filename, "error": str(exc)})

    if not saved and errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "All statement uploads failed.", "errors": errors},
        )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content={
            "status":       "success" if not errors else "partial",
            "message":      f"{len(saved)} statement(s) uploaded successfully.",
            "category":     "statements",
            "files":        saved,
            "failed_count": len(errors),
            "errors":       errors,
        },
    )
