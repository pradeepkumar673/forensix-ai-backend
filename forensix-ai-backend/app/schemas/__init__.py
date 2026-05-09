"""
app/schemas/__init__.py
-----------------------
Convenience re-exports so callers can import directly from `app.schemas`.

Example:
    from app.schemas import CaseUpload, ForensicAnalysisResponse
"""

# ── Case schemas ─────────────────────────────────────────────────────────── #
from app.schemas.case import (
    CaseStatus,
    CasePriority,
    CaseType,
    EvidenceType,
    GeoCoordinate,
    EvidenceFileMeta,
    CaseUpload,
    AnalysisSummary,
    CaseResponse,
    CaseListItem,
    CaseListResponse,
    CaseStatusUpdate,
)

# ── Analysis schemas ─────────────────────────────────────────────────────── #
from app.schemas.analysis import (
    # Primitives
    ConfidenceLevel,
    Severity,
    BodyRegion,
    AIModelMeta,
    ConfidenceScore,
    DateTimeRange,
    Finding,
    # Time of death
    TimeOfDeathMethod,
    TimeOfDeathRequest,
    TimeOfDeathEstimate,
    TimeOfDeathResponse,
    # Autopsy
    AutopsyExternalExam,
    AutopsyInternalExam,
    AutopsyReportResponse,
    # Image analysis
    DetectedObject,
    BloodSpatterPattern,
    ImageAnalysisResponse,
    # Toxicology
    SubstanceDetected,
    ToxicologyAnalysisResponse,
    # Wounds
    WoundType,
    Wound,
    WoundAnalysisResponse,
    # Biometrics
    DNAProfileMatch,
    FingerprintMatch,
    BiometricAnalysisResponse,
    # Timeline
    TimelineEventType,
    TimelineEvent,
    TimelineResponse,
    # Risk
    RiskFactor,
    RiskScoreRequest,
    RiskScoreResponse,
    # Graph
    EntityType,
    GraphEntity,
    GraphRelationship,
    EntityGraphResponse,
    # Geospatial
    GeospatialPoint,
    GeospatialAnalysisResponse,
    # Master aggregate
    ForensicAnalysisResponse,
)

__all__ = [
    # case
    "CaseStatus", "CasePriority", "CaseType", "EvidenceType", "GeoCoordinate",
    "EvidenceFileMeta", "CaseUpload", "AnalysisSummary", "CaseResponse",
    "CaseListItem", "CaseListResponse", "CaseStatusUpdate",
    # analysis — primitives
    "ConfidenceLevel", "Severity", "BodyRegion", "AIModelMeta",
    "ConfidenceScore", "DateTimeRange", "Finding",
    # analysis — sub-types
    "TimeOfDeathMethod", "TimeOfDeathRequest", "TimeOfDeathEstimate", "TimeOfDeathResponse",
    "AutopsyExternalExam", "AutopsyInternalExam", "AutopsyReportResponse",
    "DetectedObject", "BloodSpatterPattern", "ImageAnalysisResponse",
    "SubstanceDetected", "ToxicologyAnalysisResponse",
    "WoundType", "Wound", "WoundAnalysisResponse",
    "DNAProfileMatch", "FingerprintMatch", "BiometricAnalysisResponse",
    "TimelineEventType", "TimelineEvent", "TimelineResponse",
    "RiskFactor", "RiskScoreRequest", "RiskScoreResponse",
    "EntityType", "GraphEntity", "GraphRelationship", "EntityGraphResponse",
    "GeospatialPoint", "GeospatialAnalysisResponse",
    "ForensicAnalysisResponse",
]
