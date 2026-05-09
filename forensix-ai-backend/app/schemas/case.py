"""
app/schemas/case.py
-------------------
Pydantic v2 schemas for forensic case management.

Covers:
  • Case creation (upload) requests
  • Case response / detail models
  • Evidence file metadata
  • Case status & classification enums
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


# =========================================================================== #
# Enumerations                                                                  #
# =========================================================================== #

class CaseStatus(str, Enum):
    """Lifecycle stage of a forensic case."""
    PENDING     = "pending"       # Uploaded, awaiting initial triage
    IN_PROGRESS = "in_progress"   # Actively being analysed
    REVIEWED    = "reviewed"      # Analysis complete, pending sign-off
    CLOSED      = "closed"        # Finalised and archived
    FLAGGED     = "flagged"       # Requires urgent attention


class CasePriority(str, Enum):
    """Operational priority assigned to the case."""
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class CaseType(str, Enum):
    """Broad classification of the forensic case."""
    HOMICIDE         = "homicide"
    SUICIDE          = "suicide"
    ACCIDENTAL_DEATH = "accidental_death"
    NATURAL_DEATH    = "natural_death"
    UNDETERMINED     = "undetermined"
    ASSAULT          = "assault"
    SEXUAL_ASSAULT   = "sexual_assault"
    MISSING_PERSON   = "missing_person"
    MASS_CASUALTY    = "mass_casualty"
    OTHER            = "other"


class EvidenceType(str, Enum):
    """Category of an individual evidence file."""
    AUTOPSY_REPORT   = "autopsy_report"
    CRIME_SCENE_PHOTO = "crime_scene_photo"
    TOXICOLOGY_REPORT = "toxicology_report"
    WITNESS_STATEMENT = "witness_statement"
    POLICE_REPORT    = "police_report"
    MEDICAL_RECORD   = "medical_record"
    LAB_RESULT       = "lab_result"
    BODY_SCAN        = "body_scan"        # CT / MRI DICOM
    FINGERPRINT      = "fingerprint"
    DNA_PROFILE      = "dna_profile"
    DIGITAL_EVIDENCE = "digital_evidence"
    OTHER            = "other"


class GeoCoordinate(BaseModel):
    """WGS-84 geographic coordinate."""
    latitude:  float = Field(..., ge=-90,  le=90,  description="Decimal latitude")
    longitude: float = Field(..., ge=-180, le=180, description="Decimal longitude")
    altitude_m: Optional[float] = Field(None, description="Altitude in metres (optional)")


# =========================================================================== #
# Evidence file schemas                                                         #
# =========================================================================== #

class EvidenceFileMeta(BaseModel):
    """
    Metadata describing a single uploaded evidence file.
    This is embedded inside CaseUpload and returned inside CaseResponse.
    """
    file_id:       UUID         = Field(default_factory=uuid4)
    original_name: str          = Field(..., min_length=1, max_length=512,
                                        description="Original filename from the client")
    evidence_type: EvidenceType = Field(..., description="Categorised evidence type")
    mime_type:     str          = Field(..., description="MIME type, e.g. application/pdf")
    size_bytes:    int          = Field(..., ge=0, description="File size in bytes")
    checksum_sha256: Optional[str] = Field(None, description="SHA-256 hex digest for integrity verification")
    notes:         Optional[str]   = Field(None, max_length=2048,
                                           description="Analyst notes specific to this file")
    uploaded_at:   datetime        = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "original_name": "autopsy_report_doe_john.pdf",
                "evidence_type": "autopsy_report",
                "mime_type": "application/pdf",
                "size_bytes": 2048000,
                "checksum_sha256": "e3b0c44298fc1c149afb4c8996fb92427ae41e4649b934ca495991b7852b855",
                "notes": "Preliminary post-mortem report by Dr. Patel",
            }
        }


# =========================================================================== #
# Case upload request                                                           #
# =========================================================================== #

class CaseUpload(BaseModel):
    """
    Payload sent by the client when opening a new forensic case.

    In a real endpoint the actual files are received as multipart/form-data;
    this schema carries the structured metadata that accompanies the upload.
    """

    # ── Identification ──────────────────────────────────────────────────── #
    case_number: str = Field(
        ...,
        min_length=3, max_length=64,
        pattern=r"^[A-Z0-9\-_/]+$",
        description="Official case reference number, e.g. 'CASE-2024-00123'",
    )
    case_type:    CaseType    = Field(..., description="Broad classification of the case")
    priority:     CasePriority = Field(default=CasePriority.MEDIUM)

    # ── Victim / subject ────────────────────────────────────────────────── #
    victim_name:    Optional[str] = Field(None, max_length=256,
                                          description="Full name of the deceased / subject")
    victim_age:     Optional[int] = Field(None, ge=0, le=150, description="Age in years")
    victim_sex:     Optional[str] = Field(None, pattern=r"^(male|female|unknown|other)$")
    victim_dob:     Optional[datetime] = Field(None, description="Date of birth (ISO-8601)")

    # ── Incident details ─────────────────────────────────────────────────── #
    incident_date:       Optional[datetime] = Field(None, description="Known or estimated date of incident")
    incident_location:   Optional[str]      = Field(None, max_length=512,
                                                     description="Human-readable location description")
    incident_coordinates: Optional[GeoCoordinate] = Field(None, description="GPS coordinates of the scene")

    # ── Discovery details ───────────────────────────────────────────────── #
    discovery_date:     Optional[datetime] = Field(None)
    discovery_location: Optional[str]      = Field(None, max_length=512)
    reported_by:        Optional[str]      = Field(None, max_length=256,
                                                    description="Name / badge of reporting officer")

    # ── Narrative ───────────────────────────────────────────────────────── #
    summary:      Optional[str] = Field(None, max_length=4096,
                                         description="Free-text initial summary of the case")
    tags:         list[str]     = Field(default_factory=list,
                                        description="Free-form labels for search / filtering")

    # ── Evidence manifest ───────────────────────────────────────────────── #
    evidence_files: list[EvidenceFileMeta] = Field(
        default_factory=list,
        description="Metadata for each file included in the multipart upload",
    )

    # ── Submitting analyst ──────────────────────────────────────────────── #
    submitted_by: Optional[str] = Field(None, max_length=256,
                                         description="Analyst or officer opening the case")
    department:   Optional[str] = Field(None, max_length=256)

    # ── Validators ──────────────────────────────────────────────────────── #
    @field_validator("case_number", mode="before")
    @classmethod
    def normalise_case_number(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("tags", mode="before")
    @classmethod
    def deduplicate_tags(cls, v: list[str]) -> list[str]:
        seen: set[str] = set()
        result = []
        for tag in v:
            tag = tag.strip().lower()
            if tag and tag not in seen:
                seen.add(tag)
                result.append(tag)
        return result

    @model_validator(mode="after")
    def discovery_after_incident(self) -> "CaseUpload":
        if self.incident_date and self.discovery_date:
            if self.discovery_date < self.incident_date:
                raise ValueError(
                    "discovery_date cannot be earlier than incident_date"
                )
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "case_number": "CASE-2024-00123",
                "case_type": "homicide",
                "priority": "high",
                "victim_name": "John Doe",
                "victim_age": 34,
                "victim_sex": "male",
                "incident_date": "2024-06-01T22:30:00Z",
                "incident_location": "12 Baker Street, London, UK",
                "incident_coordinates": {"latitude": 51.5236, "longitude": -0.1585},
                "summary": "Victim found unresponsive at residential address.",
                "tags": ["blunt-force", "indoor", "no-witnesses"],
                "submitted_by": "DS Harper",
                "department": "Metropolitan Police — Homicide Command",
            }
        }


# =========================================================================== #
# Case response                                                                 #
# =========================================================================== #

class AnalysisSummary(BaseModel):
    """
    Lightweight summary of completed analyses attached to a case.
    Full analysis payloads live in app/schemas/analysis.py.
    """
    analysis_id:   UUID     = Field(default_factory=uuid4)
    analysis_type: str      = Field(..., description="E.g. 'time_of_death', 'risk_score'")
    completed_at:  datetime = Field(default_factory=datetime.utcnow)
    confidence:    float    = Field(..., ge=0.0, le=1.0,
                                    description="Overall confidence of the analysis (0-1)")
    headline:      str      = Field(..., max_length=512,
                                    description="One-line human-readable result")


class CaseResponse(BaseModel):
    """
    Full case record returned by the API after creation or retrieval.
    Combines the original upload payload with server-assigned fields.
    """

    # ── Server-assigned identity ─────────────────────────────────────────── #
    case_id:    UUID     = Field(default_factory=uuid4, description="Unique internal case UUID")
    case_number: str     = Field(..., description="Canonical case reference number")
    status:     CaseStatus = Field(default=CaseStatus.PENDING)
    priority:   CasePriority

    # ── Classification ───────────────────────────────────────────────────── #
    case_type: CaseType

    # ── Victim / subject ────────────────────────────────────────────────── #
    victim_name:  Optional[str]     = None
    victim_age:   Optional[int]     = None
    victim_sex:   Optional[str]     = None
    victim_dob:   Optional[datetime] = None

    # ── Incident & discovery ─────────────────────────────────────────────── #
    incident_date:        Optional[datetime]    = None
    incident_location:    Optional[str]         = None
    incident_coordinates: Optional[GeoCoordinate] = None
    discovery_date:       Optional[datetime]    = None
    discovery_location:   Optional[str]         = None
    reported_by:          Optional[str]         = None

    # ── Narrative ───────────────────────────────────────────────────────── #
    summary: Optional[str] = None
    tags:    list[str]     = Field(default_factory=list)

    # ── Evidence ────────────────────────────────────────────────────────── #
    evidence_files: list[EvidenceFileMeta] = Field(default_factory=list)
    evidence_count: int = Field(default=0, description="Total number of evidence files")

    # ── Analyses ────────────────────────────────────────────────────────── #
    analyses:       list[AnalysisSummary] = Field(default_factory=list)
    analysis_count: int = Field(default=0, description="Number of completed analyses")

    # ── Assignment & audit ───────────────────────────────────────────────── #
    submitted_by:    Optional[str] = None
    assigned_to:     Optional[str] = Field(None, description="Lead analyst assigned to the case")
    department:      Optional[str] = None
    created_at:      datetime      = Field(default_factory=datetime.utcnow)
    updated_at:      datetime      = Field(default_factory=datetime.utcnow)
    closed_at:       Optional[datetime] = None

    # ── Risk flag ────────────────────────────────────────────────────────── #
    risk_score:   Optional[float] = Field(None, ge=0.0, le=100.0,
                                           description="Aggregated risk score 0-100")
    flagged:      bool            = Field(default=False)
    flag_reason:  Optional[str]   = None

    # ── Derived helpers ──────────────────────────────────────────────────── #
    @model_validator(mode="after")
    def sync_counts(self) -> "CaseResponse":
        self.evidence_count = len(self.evidence_files)
        self.analysis_count = len(self.analyses)
        return self

    class Config:
        from_attributes = True   # allows ORM model → schema conversion
        json_schema_extra = {
            "example": {
                "case_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "case_number": "CASE-2024-00123",
                "status": "in_progress",
                "priority": "high",
                "case_type": "homicide",
                "victim_name": "John Doe",
                "victim_age": 34,
                "victim_sex": "male",
                "incident_date": "2024-06-01T22:30:00Z",
                "incident_location": "12 Baker Street, London, UK",
                "summary": "Victim found unresponsive at residential address.",
                "evidence_count": 4,
                "analysis_count": 2,
                "risk_score": 82.5,
                "flagged": True,
                "flag_reason": "High-risk indicators detected in toxicology report",
                "created_at": "2024-06-02T09:00:00Z",
                "updated_at": "2024-06-02T14:37:00Z",
            }
        }


# =========================================================================== #
# Lightweight list / pagination schemas                                         #
# =========================================================================== #

class CaseListItem(BaseModel):
    """Compact representation used in paginated case lists."""
    case_id:      UUID
    case_number:  str
    case_type:    CaseType
    status:       CaseStatus
    priority:     CasePriority
    victim_name:  Optional[str]  = None
    risk_score:   Optional[float] = None
    flagged:      bool            = False
    evidence_count: int           = 0
    created_at:   datetime
    updated_at:   datetime


class CaseListResponse(BaseModel):
    """Paginated list of cases."""
    total:   int              = Field(..., description="Total number of matching cases")
    page:    int              = Field(default=1, ge=1)
    size:    int              = Field(default=20, ge=1, le=100)
    items:   list[CaseListItem]


class CaseStatusUpdate(BaseModel):
    """Minimal payload for PATCH /cases/{case_id}/status."""
    status:      CaseStatus
    assigned_to: Optional[str] = None
    note:        Optional[str] = Field(None, max_length=1024,
                                        description="Reason for the status change")
