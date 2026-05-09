"""
app/schemas/analysis.py
-----------------------
Pydantic v2 schemas for every forensic analysis produced by the AI engine.

Sections:
  1. Shared primitives & enumerations
  2. Time-of-death estimation
  3. Autopsy report parsing
  4. Image / crime-scene photo analysis
  5. Toxicology analysis
  6. Wound & injury analysis
  7. DNA / fingerprint analysis
  8. Timeline reconstruction
  9. Risk scoring
 10. Entity & relationship graph
 11. Geospatial analysis
 12. Full forensic analysis aggregate response
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator  # top-level


# =========================================================================== #
# 1. Shared primitives & enumerations                                          #
# =========================================================================== #

class ConfidenceLevel(str, Enum):
    VERY_LOW  = "very_low"    # < 20 %
    LOW       = "low"         # 20–40 %
    MODERATE  = "moderate"    # 40–60 %
    HIGH      = "high"        # 60–80 %
    VERY_HIGH = "very_high"   # > 80 %


class Severity(str, Enum):
    NONE     = "none"
    MILD     = "mild"
    MODERATE = "moderate"
    SEVERE   = "severe"
    CRITICAL = "critical"


class BodyRegion(str, Enum):
    HEAD        = "head"
    NECK        = "neck"
    CHEST       = "chest"
    ABDOMEN     = "abdomen"
    BACK        = "back"
    PELVIS      = "pelvis"
    LEFT_ARM    = "left_arm"
    RIGHT_ARM   = "right_arm"
    LEFT_LEG    = "left_leg"
    RIGHT_LEG   = "right_leg"
    HANDS       = "hands"
    FEET        = "feet"
    WHOLE_BODY  = "whole_body"


class AIModelMeta(BaseModel):
    """Provenance metadata for the AI model that produced a result."""
    model_name:    str            = Field(..., description="Model identifier, e.g. 'llama3'")
    model_version: Optional[str] = None
    inference_ms:  Optional[int] = Field(None, description="Wall-clock inference time in ms")
    prompt_tokens: Optional[int] = None
    output_tokens: Optional[int] = None


class ConfidenceScore(BaseModel):
    """Numeric confidence with an enum label."""
    score: float = Field(..., ge=0.0, le=1.0, description="Confidence 0.0 – 1.0")
    level: ConfidenceLevel

    @classmethod
    def from_float(cls, score: float) -> "ConfidenceScore":
        if score < 0.20:
            level = ConfidenceLevel.VERY_LOW
        elif score < 0.40:
            level = ConfidenceLevel.LOW
        elif score < 0.60:
            level = ConfidenceLevel.MODERATE
        elif score < 0.80:
            level = ConfidenceLevel.HIGH
        else:
            level = ConfidenceLevel.VERY_HIGH
        return cls(score=round(score, 4), level=level)


class DateTimeRange(BaseModel):
    """An inclusive time window with optional confidence."""
    earliest:   datetime
    latest:     datetime
    midpoint:   Optional[datetime]    = None
    confidence: Optional[ConfidenceScore] = None
    notes:      Optional[str]         = None


class Finding(BaseModel):
    """A single discrete finding within any analysis type."""
    finding_id:  UUID        = Field(default_factory=uuid4)
    category:    str         = Field(..., description="E.g. 'injury', 'substance', 'anomaly'")
    description: str         = Field(..., max_length=2048)
    severity:    Severity    = Severity.NONE
    confidence:  ConfidenceScore
    evidence_refs: list[str] = Field(default_factory=list,
                                      description="File IDs or page references that support this finding")
    tags:        list[str]   = Field(default_factory=list)


# =========================================================================== #
# 2. Time-of-death estimation                                                  #
# =========================================================================== #

class TimeOfDeathMethod(str, Enum):
    RIGOR_MORTIS         = "rigor_mortis"
    LIVOR_MORTIS         = "livor_mortis"
    ALGOR_MORTIS         = "algor_mortis"
    DECOMPOSITION        = "decomposition"
    STOMACH_CONTENTS     = "stomach_contents"
    VITREOUS_POTASSIUM   = "vitreous_potassium"
    ENTOMOLOGY           = "entomology"
    WITNESS_STATEMENT    = "witness_statement"
    DIGITAL_FOOTPRINT    = "digital_footprint"
    COMBINED             = "combined"


class TimeOfDeathRequest(BaseModel):
    """
    Input payload for the /analysis/time-of-death endpoint.
    All physical observations are optional; the model uses whatever is supplied.
    """
    case_id:          UUID              = Field(..., description="Parent case UUID")
    evidence_file_ids: list[UUID]       = Field(default_factory=list,
                                                 description="Specific evidence files to analyse")

    # ── Rigor mortis ────────────────────────────────────────────────────── #
    rigor_stage: Optional[str] = Field(None,
        description="e.g. 'onset', 'complete', 'passing', 'absent'")

    # ── Livor mortis ────────────────────────────────────────────────────── #
    livor_colour:    Optional[str] = Field(None, description="e.g. 'pink', 'cherry-red', 'purple'")
    livor_fixed:     Optional[bool] = None
    livor_locations: list[str]      = Field(default_factory=list)

    # ── Algor mortis ────────────────────────────────────────────────────── #
    body_temp_celsius:    Optional[float] = Field(None, ge=-10.0, le=45.0)
    ambient_temp_celsius: Optional[float] = Field(None, ge=-50.0, le=60.0)
    discovery_datetime:   Optional[datetime] = None

    # ── Decomposition ───────────────────────────────────────────────────── #
    decomposition_stage: Optional[str] = Field(None,
        description="'fresh', 'bloat', 'active_decay', 'advanced_decay', 'skeletonisation'")
    entomology_notes: Optional[str] = None

    # ── Stomach contents ─────────────────────────────────────────────────── #
    stomach_contents_description: Optional[str] = None
    last_known_meal_datetime:     Optional[datetime] = None

    # ── Environmental context ────────────────────────────────────────────── #
    environment:      Optional[str] = Field(None,
        description="e.g. 'indoor_heated', 'outdoor_summer', 'submerged_water'")
    humidity_percent: Optional[float] = Field(None, ge=0.0, le=100.0)

    # ── Free-text context ────────────────────────────────────────────────── #
    additional_context: Optional[str] = Field(None, max_length=4096)


class TimeOfDeathEstimate(BaseModel):
    """
    Single method estimate — one record per method applied.
    """
    method:          TimeOfDeathMethod
    estimated_window: DateTimeRange
    method_specific_findings: dict[str, Any] = Field(default_factory=dict,
        description="Raw method-specific values, e.g. body_cooling_rate")
    confidence: ConfidenceScore
    limitations: list[str] = Field(default_factory=list,
        description="Factors that reduce reliability of this method")


class TimeOfDeathResponse(BaseModel):
    """Aggregated time-of-death result across all applicable methods."""
    analysis_id:  UUID     = Field(default_factory=uuid4)
    case_id:      UUID
    analysed_at:  datetime = Field(default_factory=datetime.utcnow)

    # ── Combined estimate ────────────────────────────────────────────────── #
    combined_window: DateTimeRange = Field(..., description="Intersection of all method windows")
    overall_confidence: ConfidenceScore
    primary_method: TimeOfDeathMethod = Field(..., description="Most reliable method in this case")

    # ── Per-method breakdown ─────────────────────────────────────────────── #
    method_estimates: list[TimeOfDeathEstimate] = Field(default_factory=list)

    # ── Narrative ───────────────────────────────────────────────────────── #
    narrative_summary: str  = Field(..., max_length=4096,
                                     description="Plain-language summary for the report")
    caveats:           list[str] = Field(default_factory=list)
    model_meta:        Optional[AIModelMeta] = None


# =========================================================================== #
# 3. Autopsy report parsing                                                    #
# =========================================================================== #

class AutopsyExternalExam(BaseModel):
    """External examination findings from the autopsy."""
    height_cm:        Optional[float] = None
    weight_kg:        Optional[float] = None
    body_condition:   Optional[str]   = None   # e.g. 'well-nourished'
    skin_colour:      Optional[str]   = None
    identifying_marks: list[str]      = Field(default_factory=list,
                                               description="Tattoos, scars, birthmarks, etc.")
    external_injuries: list[Finding]  = Field(default_factory=list)


class AutopsyInternalExam(BaseModel):
    """Internal examination / organ findings."""
    cause_of_death_primary:   Optional[str] = None
    cause_of_death_secondary: Optional[str] = None
    manner_of_death:          Optional[str] = Field(None,
        description="'natural', 'accident', 'suicide', 'homicide', 'undetermined'")

    cardiovascular_findings: list[str] = Field(default_factory=list)
    respiratory_findings:    list[str] = Field(default_factory=list)
    neurological_findings:   list[str] = Field(default_factory=list)
    gastrointestinal_findings: list[str] = Field(default_factory=list)
    musculoskeletal_findings:  list[str] = Field(default_factory=list)
    other_organ_findings:      list[str] = Field(default_factory=list)

    internal_injuries: list[Finding] = Field(default_factory=list)


class AutopsyReportResponse(BaseModel):
    """Structured extraction of an autopsy report document."""
    analysis_id:     UUID     = Field(default_factory=uuid4)
    case_id:         UUID
    source_file_id:  Optional[UUID] = None
    analysed_at:     datetime = Field(default_factory=datetime.utcnow)

    # ── Report metadata ──────────────────────────────────────────────────── #
    report_number:    Optional[str] = None
    pathologist_name: Optional[str] = None
    autopsy_date:     Optional[datetime] = None
    report_date:      Optional[datetime] = None
    facility:         Optional[str] = None

    # ── Findings ────────────────────────────────────────────────────────── #
    external_exam: Optional[AutopsyExternalExam] = None
    internal_exam: Optional[AutopsyInternalExam] = None

    # ── Toxicology (brief — full detail in ToxicologyAnalysisResponse) ──── #
    toxicology_summary: Optional[str] = None

    # ── Key conclusions ──────────────────────────────────────────────────── #
    cause_of_death:   Optional[str] = None
    manner_of_death:  Optional[str] = None
    contributing_conditions: list[str] = Field(default_factory=list)
    estimated_survival_interval: Optional[str] = Field(None,
        description="Time between fatal injury and death")

    # ── AI extraction quality ────────────────────────────────────────────── #
    extraction_confidence: ConfidenceScore
    unextracted_sections:  list[str] = Field(default_factory=list,
        description="Sections the AI could not parse reliably")
    raw_text_snippet:      Optional[str] = Field(None, max_length=1024,
        description="First 1024 chars of extracted raw text for QA purposes")
    model_meta: Optional[AIModelMeta] = None


# =========================================================================== #
# 4. Image / crime-scene analysis                                              #
# =========================================================================== #

class DetectedObject(BaseModel):
    """A single object or region of interest detected in an image."""
    label:       str
    confidence:  float = Field(..., ge=0.0, le=1.0)
    bounding_box: Optional[dict[str, float]] = Field(None,
        description="{'x': float, 'y': float, 'width': float, 'height': float} — normalised 0-1")
    forensic_significance: Optional[str] = None


class BloodSpatterPattern(BaseModel):
    """Blood spatter pattern analysis output."""
    pattern_type: str = Field(..., description="e.g. 'high_velocity', 'medium_velocity', 'drip'")
    origin_estimate: Optional[str] = None
    directionality:  Optional[str] = None
    coverage_percent: Optional[float] = Field(None, ge=0.0, le=100.0)
    confidence: ConfidenceScore


class ImageAnalysisResponse(BaseModel):
    """AI analysis of a crime-scene or evidence photograph."""
    analysis_id:    UUID     = Field(default_factory=uuid4)
    case_id:        UUID
    source_file_id: Optional[UUID] = None
    analysed_at:    datetime = Field(default_factory=datetime.utcnow)

    image_width:  Optional[int] = None
    image_height: Optional[int] = None
    image_format: Optional[str] = None

    # ── Detections ───────────────────────────────────────────────────────── #
    detected_objects:   list[DetectedObject]    = Field(default_factory=list)
    blood_spatter:      list[BloodSpatterPattern] = Field(default_factory=list)
    weapon_indicators:  list[str] = Field(default_factory=list)
    body_position:      Optional[str] = None
    environmental_cues: list[str] = Field(default_factory=list,
        description="Lighting, time-of-day, weather indicators visible in image")

    # ── Scene classification ─────────────────────────────────────────────── #
    scene_type:         Optional[str] = Field(None,
        description="e.g. 'indoor_residential', 'outdoor_urban', 'vehicle_interior'")
    staging_indicators: list[str] = Field(default_factory=list,
        description="Evidence suggesting the scene may have been staged")
    struggle_evidence:  bool = False

    # ── Narrative ───────────────────────────────────────────────────────── #
    narrative_description: str = Field(..., max_length=4096)
    overall_confidence:    ConfidenceScore
    model_meta:            Optional[AIModelMeta] = None


# =========================================================================== #
# 5. Toxicology analysis                                                       #
# =========================================================================== #

class SubstanceDetected(BaseModel):
    """A single substance found in the toxicological screen."""
    substance_name:   str
    substance_class:  str  = Field(...,
        description="e.g. 'opioid', 'benzodiazepine', 'alcohol', 'stimulant', 'poison'")
    concentration:    Optional[str]  = Field(None,
        description="Measured concentration with units, e.g. '0.23 mg/L'")
    lethal_threshold: Optional[str]  = None
    above_therapeutic_range: Optional[bool] = None
    above_lethal_range:      Optional[bool] = None
    specimen_source:  Optional[str]  = Field(None,
        description="e.g. 'blood', 'urine', 'vitreous_humor', 'hair'")
    significance:     Optional[str]  = None
    confidence:       ConfidenceScore


class ToxicologyAnalysisResponse(BaseModel):
    """Structured toxicology screen results."""
    analysis_id:    UUID     = Field(default_factory=uuid4)
    case_id:        UUID
    source_file_id: Optional[UUID] = None
    analysed_at:    datetime = Field(default_factory=datetime.utcnow)

    substances_detected: list[SubstanceDetected] = Field(default_factory=list)
    substances_screened: list[str] = Field(default_factory=list,
        description="All substance classes screened, including negatives")

    # ── Interpretation ───────────────────────────────────────────────────── #
    polypharmacy_concern:    bool          = False
    drug_interaction_flags:  list[str]     = Field(default_factory=list)
    cause_of_death_contribution: Optional[str] = None
    manner_implication:      Optional[str] = Field(None,
        description="How findings relate to manner of death")

    toxicology_summary: str = Field(..., max_length=4096)
    overall_confidence: ConfidenceScore
    model_meta:         Optional[AIModelMeta] = None


# =========================================================================== #
# 6. Wound & injury analysis                                                   #
# =========================================================================== #

class WoundType(str, Enum):
    INCISED      = "incised"
    LACERATION   = "laceration"
    STAB         = "stab"
    GUNSHOT      = "gunshot"
    BLUNT_FORCE  = "blunt_force"
    BURN         = "burn"
    LIGATURE     = "ligature"
    ASPHYXIATION = "asphyxiation"
    BITE         = "bite"
    DEFENSIVE    = "defensive"
    OTHER        = "other"


class Wound(BaseModel):
    """A single wound or injury."""
    wound_id:       UUID       = Field(default_factory=uuid4)
    wound_type:     WoundType
    body_region:    BodyRegion
    description:    str        = Field(..., max_length=1024)
    dimensions_mm:  Optional[str]   = Field(None, description="e.g. '15×3 mm'")
    depth_mm:       Optional[float] = None
    direction:      Optional[str]   = Field(None, description="e.g. 'left-to-right downward'")
    antemortem:     Optional[bool]  = Field(None,
        description="True = before death, False = perimortem or post-mortem")
    weapon_class_inferred: Optional[str] = Field(None,
        description="Inferred weapon type, e.g. 'serrated blade', '9mm handgun'")
    defensive_injury: bool = False
    confidence: ConfidenceScore


class WoundAnalysisResponse(BaseModel):
    """Complete wound & injury pattern analysis."""
    analysis_id:    UUID     = Field(default_factory=uuid4)
    case_id:        UUID
    analysed_at:    datetime = Field(default_factory=datetime.utcnow)

    wounds:              list[Wound] = Field(default_factory=list)
    total_wound_count:   int         = 0
    fatal_wounds:        list[UUID]  = Field(default_factory=list,
        description="wound_ids classified as potentially fatal")
    defensive_wounds:    list[UUID]  = Field(default_factory=list)

    # ── Pattern-level conclusions ─────────────────────────────────────────── #
    attack_pattern:       Optional[str] = Field(None,
        description="e.g. 'sustained blunt assault', 'single stab', 'close-range gunshot'")
    victim_position:      Optional[str] = Field(None,
        description="Estimated victim position during assault")
    assailant_position:   Optional[str] = None
    number_of_assailants: Optional[int] = None
    right_left_handed:    Optional[str] = None

    narrative_summary: str = Field(..., max_length=4096)
    overall_confidence: ConfidenceScore
    model_meta:         Optional[AIModelMeta] = None

    @model_validator(mode="after")
    def count_wounds(self) -> "WoundAnalysisResponse":
        self.total_wound_count = len(self.wounds)
        return self


# =========================================================================== #
# 7. DNA / fingerprint analysis                                                #
# =========================================================================== #

class DNAProfileMatch(BaseModel):
    """A single CODIS / database match result."""
    profile_id:     str
    match_source:   str  = Field(..., description="e.g. 'CODIS', 'local_db', 'victim_reference'")
    match_percent:  float = Field(..., ge=0.0, le=100.0)
    identity:       Optional[str]  = None
    confidence:     ConfidenceScore


class FingerprintMatch(BaseModel):
    """Fingerprint comparison result."""
    fingerprint_id: str
    match_source:   str
    ridge_count:    Optional[int]  = None
    minutiae_count: Optional[int]  = None
    match_score:    float          = Field(..., ge=0.0, le=100.0)
    identity:       Optional[str]  = None
    confidence:     ConfidenceScore


class BiometricAnalysisResponse(BaseModel):
    """DNA and fingerprint analysis results."""
    analysis_id: UUID     = Field(default_factory=uuid4)
    case_id:     UUID
    analysed_at: datetime = Field(default_factory=datetime.utcnow)

    # ── DNA ─────────────────────────────────────────────────────────────── #
    dna_profiles_found:  int                  = 0
    dna_matches:         list[DNAProfileMatch]= Field(default_factory=list)
    mixed_profile:       bool                 = False
    contributor_estimate: Optional[int]       = Field(None,
        description="Estimated number of DNA contributors")

    # ── Fingerprints ─────────────────────────────────────────────────────── #
    fingerprints_found:  int                    = 0
    fingerprint_matches: list[FingerprintMatch] = Field(default_factory=list)
    latent_print_quality: Optional[str]         = Field(None,
        description="'excellent', 'good', 'poor', 'insufficient'")

    summary:    str = Field(..., max_length=2048)
    confidence: ConfidenceScore
    model_meta: Optional[AIModelMeta] = None


# =========================================================================== #
# 8. Timeline reconstruction                                                   #
# =========================================================================== #

class TimelineEventType(str, Enum):
    LAST_SEEN_ALIVE  = "last_seen_alive"
    PHONE_ACTIVITY   = "phone_activity"
    FINANCIAL_TRANS  = "financial_transaction"
    CCTV_SIGHTING    = "cctv_sighting"
    MEDICAL_EVENT    = "medical_event"
    INJURY_INFLICTED = "injury_inflicted"
    DEATH            = "death"
    DISCOVERY        = "discovery"
    POLICE_ARRIVAL   = "police_arrival"
    AUTOPSY          = "autopsy"
    WITNESS_ACCOUNT  = "witness_account"
    SUSPECT_ACTIVITY = "suspect_activity"
    OTHER            = "other"


class TimelineEvent(BaseModel):
    """A single event in the reconstructed timeline."""
    event_id:    UUID            = Field(default_factory=uuid4)
    event_type:  TimelineEventType
    timestamp:   Optional[datetime] = None
    time_window: Optional[DateTimeRange] = None  # when exact time unknown
    description: str             = Field(..., max_length=2048)
    location:    Optional[str]   = None
    source:      Optional[str]   = Field(None,
        description="Evidence source supporting this event")
    actors:      list[str]       = Field(default_factory=list,
        description="People involved: victim, suspect names / IDs")
    confidence:  ConfidenceScore
    linked_event_ids: list[UUID] = Field(default_factory=list,
        description="IDs of causally or temporally related events")


class TimelineResponse(BaseModel):
    """Full reconstructed event timeline for a case."""
    analysis_id:  UUID     = Field(default_factory=uuid4)
    case_id:      UUID
    analysed_at:  datetime = Field(default_factory=datetime.utcnow)

    events:            list[TimelineEvent] = Field(default_factory=list)
    event_count:       int                 = 0
    earliest_event:    Optional[datetime]  = None
    latest_event:      Optional[datetime]  = None
    total_span_hours:  Optional[float]     = None

    gaps_identified:   list[str]  = Field(default_factory=list,
        description="Notable time gaps with no corroborating evidence")
    contradictions:    list[str]  = Field(default_factory=list,
        description="Conflicting accounts or evidence")
    narrative_summary: str        = Field(..., max_length=4096)
    overall_confidence: ConfidenceScore
    model_meta:        Optional[AIModelMeta] = None

    @model_validator(mode="after")
    def compute_span(self) -> "TimelineResponse":
        self.event_count = len(self.events)
        ts = [e.timestamp for e in self.events if e.timestamp]
        if ts:
            self.earliest_event   = min(ts)
            self.latest_event     = max(ts)
            delta                 = self.latest_event - self.earliest_event
            self.total_span_hours = round(delta.total_seconds() / 3600, 2)
        return self


# =========================================================================== #
# 9. Risk scoring                                                               #
# =========================================================================== #

class RiskFactor(BaseModel):
    """An individual factor contributing to the overall risk score."""
    factor_name:    str
    category:       str   = Field(...,
        description="e.g. 'violence_indicators', 'substance_abuse', 'victim_vulnerability'")
    weight:         float = Field(..., ge=0.0, le=1.0,
        description="Relative weight of this factor in the model")
    raw_score:      float = Field(..., ge=0.0, le=100.0)
    weighted_score: float = Field(..., ge=0.0, le=100.0)
    evidence_basis: list[str] = Field(default_factory=list)
    description:    Optional[str] = None


class RiskScoreRequest(BaseModel):
    """Input payload for the /analysis/risk-score endpoint."""
    case_id:            UUID
    evidence_file_ids:  list[UUID]       = Field(default_factory=list)
    include_categories: list[str]        = Field(default_factory=list,
        description="If empty, all risk categories are evaluated")
    context_notes:      Optional[str]    = Field(None, max_length=2048)


class RiskScoreResponse(BaseModel):
    """Composite risk score with per-factor breakdown."""
    analysis_id:  UUID     = Field(default_factory=uuid4)
    case_id:      UUID
    analysed_at:  datetime = Field(default_factory=datetime.utcnow)

    # ── Scores ──────────────────────────────────────────────────────────── #
    overall_risk_score: float = Field(..., ge=0.0, le=100.0,
        description="Composite risk score 0 (minimal) – 100 (extreme)")
    risk_level:         str   = Field(...,
        description="'minimal', 'low', 'moderate', 'high', 'critical'")

    # ── Category sub-scores ──────────────────────────────────────────────── #
    violence_score:        Optional[float] = Field(None, ge=0.0, le=100.0)
    recidivism_score:      Optional[float] = Field(None, ge=0.0, le=100.0)
    substance_abuse_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    victim_vulnerability_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    organised_crime_score: Optional[float] = Field(None, ge=0.0, le=100.0)

    # ── Factor breakdown ─────────────────────────────────────────────────── #
    risk_factors:      list[RiskFactor] = Field(default_factory=list)
    protective_factors: list[str]      = Field(default_factory=list,
        description="Factors that reduce overall risk")

    # ── Flags ───────────────────────────────────────────────────────────── #
    urgent_flags:       list[str]   = Field(default_factory=list,
        description="Immediate action items raised by the risk engine")
    recommended_actions: list[str]  = Field(default_factory=list)

    narrative_summary:  str         = Field(..., max_length=4096)
    overall_confidence: ConfidenceScore
    model_meta:         Optional[AIModelMeta] = None

    @field_validator("risk_level", mode="before")
    @classmethod
    def infer_risk_level(cls, v: str) -> str:
        return v  # can be derived in service layer from overall_risk_score


# =========================================================================== #
# 10. Entity & relationship graph                                               #
# =========================================================================== #

class EntityType(str, Enum):
    PERSON       = "person"
    LOCATION     = "location"
    ORGANISATION = "organisation"
    WEAPON       = "weapon"
    VEHICLE      = "vehicle"
    SUBSTANCE    = "substance"
    PHONE        = "phone"
    DOCUMENT     = "document"
    OTHER        = "other"


class GraphEntity(BaseModel):
    """A node in the entity relationship graph."""
    entity_id:   UUID       = Field(default_factory=uuid4)
    entity_type: EntityType
    label:       str        = Field(..., description="Display name")
    attributes:  dict[str, Any] = Field(default_factory=dict)
    risk_score:  Optional[float] = Field(None, ge=0.0, le=100.0)
    confidence:  ConfidenceScore


class GraphRelationship(BaseModel):
    """A directed edge between two graph entities."""
    relationship_id: UUID        = Field(default_factory=uuid4)
    source_id:       UUID        = Field(..., description="entity_id of the source node")
    target_id:       UUID        = Field(..., description="entity_id of the target node")
    relation_type:   str         = Field(...,
        description="e.g. 'KNOWS', 'LIVES_AT', 'OWNS', 'WITNESSED', 'SUSPECT_OF'")
    strength:        float       = Field(default=1.0, ge=0.0, le=1.0)
    evidence_refs:   list[str]   = Field(default_factory=list)
    temporal_context: Optional[str] = None
    confidence:      ConfidenceScore


class EntityGraphResponse(BaseModel):
    """Full entity-relationship graph for a case."""
    analysis_id:     UUID     = Field(default_factory=uuid4)
    case_id:         UUID
    analysed_at:     datetime = Field(default_factory=datetime.utcnow)

    entities:        list[GraphEntity]       = Field(default_factory=list)
    relationships:   list[GraphRelationship] = Field(default_factory=list)
    entity_count:    int = 0
    relationship_count: int = 0

    # ── Key actors ───────────────────────────────────────────────────────── #
    central_entities: list[UUID] = Field(default_factory=list,
        description="entity_ids with highest betweenness centrality")
    suspect_entities: list[UUID] = Field(default_factory=list)

    narrative_summary: str = Field(..., max_length=2048)
    model_meta:        Optional[AIModelMeta] = None

    @model_validator(mode="after")
    def sync_counts(self) -> "EntityGraphResponse":
        self.entity_count       = len(self.entities)
        self.relationship_count = len(self.relationships)
        return self


# =========================================================================== #
# 11. Geospatial analysis                                                       #
# =========================================================================== #

class GeospatialPoint(BaseModel):
    """A labelled geographic point of interest."""
    point_id:    UUID    = Field(default_factory=uuid4)
    label:       str
    latitude:    float   = Field(..., ge=-90, le=90)
    longitude:   float   = Field(..., ge=-180, le=180)
    point_type:  str     = Field(...,
        description="e.g. 'crime_scene', 'body_discovery', 'suspect_residence', 'cctv_camera'")
    timestamp:   Optional[datetime] = None
    description: Optional[str]      = None
    confidence:  ConfidenceScore


class GeospatialAnalysisResponse(BaseModel):
    """Geospatial mapping and pattern analysis."""
    analysis_id:  UUID     = Field(default_factory=uuid4)
    case_id:      UUID
    analysed_at:  datetime = Field(default_factory=datetime.utcnow)

    points:           list[GeospatialPoint] = Field(default_factory=list)
    cluster_summary:  Optional[str]         = Field(None,
        description="Description of geographic clusters identified")
    anchor_point:     Optional[GeospatialPoint] = Field(None,
        description="Estimated anchor point / home base (geographic profiling)")
    search_radius_km: Optional[float]       = None
    travel_routes:    list[str]             = Field(default_factory=list,
        description="Inferred travel routes between key locations")

    narrative_summary: str = Field(..., max_length=2048)
    model_meta:        Optional[AIModelMeta] = None


# =========================================================================== #
# 12. Full forensic analysis aggregate response                                #
# =========================================================================== #

class ForensicAnalysisResponse(BaseModel):
    """
    Master analysis record — aggregates all sub-analysis results for a case.

    Individual sub-analyses can be run independently; this schema holds
    references to each completed analysis and a top-level AI-generated
    summary covering all evidence.
    """
    analysis_id:  UUID     = Field(default_factory=uuid4)
    case_id:      UUID
    analysed_at:  datetime = Field(default_factory=datetime.utcnow)
    analyst_name: Optional[str] = None

    # ── Sub-analysis results (all optional — run as available) ───────────── #
    time_of_death:   Optional[TimeOfDeathResponse]      = None
    autopsy_report:  Optional[AutopsyReportResponse]    = None
    image_analyses:  list[ImageAnalysisResponse]        = Field(default_factory=list)
    toxicology:      Optional[ToxicologyAnalysisResponse] = None
    wound_analysis:  Optional[WoundAnalysisResponse]    = None
    biometrics:      Optional[BiometricAnalysisResponse]= None
    timeline:        Optional[TimelineResponse]         = None
    risk_score:      Optional[RiskScoreResponse]        = None
    entity_graph:    Optional[EntityGraphResponse]      = None
    geospatial:      Optional[GeospatialAnalysisResponse] = None

    # ── Top-level AI-synthesised findings ────────────────────────────────── #
    key_findings:        list[Finding] = Field(default_factory=list,
        description="Cross-analysis key findings, ranked by significance")
    cause_of_death:      Optional[str] = None
    manner_of_death:     Optional[str] = None
    primary_hypothesis:  Optional[str] = Field(None, max_length=4096,
        description="AI-generated primary investigative hypothesis")
    alternative_hypotheses: list[str]  = Field(default_factory=list)
    recommended_next_steps: list[str]  = Field(default_factory=list)

    # ── Quality & completeness ───────────────────────────────────────────── #
    analyses_completed: list[str] = Field(default_factory=list,
        description="Names of sub-analyses that have been run")
    analyses_pending:   list[str] = Field(default_factory=list,
        description="Sub-analyses not yet run")
    overall_confidence: ConfidenceScore
    evidence_gaps:      list[str] = Field(default_factory=list,
        description="Missing evidence that would materially strengthen conclusions")

    # ── Report ───────────────────────────────────────────────────────────── #
    executive_summary: str = Field(..., max_length=8192,
        description="Comprehensive narrative summary suitable for the case report")
    model_meta:        Optional[AIModelMeta] = None

    class Config:
        json_schema_extra = {
            "example": {
                "case_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "cause_of_death": "Blunt-force head trauma",
                "manner_of_death": "Homicide",
                "primary_hypothesis": "Victim struck multiple times with a blunt instrument ...",
                "overall_confidence": {"score": 0.78, "level": "high"},
                "analyses_completed": ["time_of_death", "autopsy_report", "wound_analysis"],
                "analyses_pending": ["biometrics", "geospatial"],
                "executive_summary": "Post-mortem examination reveals ...",
            }
        }


# ===========================================================================
# Advanced Analysis Models
# ===========================================================================

class AudioAnalysisResponse(BaseModel):
    """Matches analyze_audio_stress() — includes optional error-only payloads."""

    model_config = ConfigDict(extra="allow")

    primary_emotion: str = ""
    emotion_confidence: float = 0.0
    all_emotions: list[dict[str, Any]] = Field(default_factory=list)
    stress_indicators: list[dict[str, Any]] = Field(default_factory=list)
    overall_assessment: str = ""
    error: Optional[str] = None


class TranscriptionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    transcription: str = ""
    error: Optional[str] = None


class TamperingResponse(BaseModel):
    """Tampering / deepfake pipeline — many fields optional for graceful degradation."""

    model_config = ConfigDict(extra="allow")

    status: str = "ok"
    error: Optional[str] = None
    tampered: Optional[bool] = None
    tampering_probability: Optional[float] = None
    verdict: Optional[str] = None
    indicators: Optional[list[str]] = None
    advanced_vision_enabled: Optional[bool] = None


class SegmentationResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "ok"
    masks: list[Any] = Field(default_factory=list)
    error: Optional[str] = None
    mask_count: Optional[int] = None
    image_dims: Optional[dict[str, Any]] = None
    model_id: Optional[str] = None
    device: Optional[str] = None
    advanced_vision_enabled: Optional[bool] = None


class PoseResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "ok"
    keypoints: list[Any] = Field(default_factory=list)
    error: Optional[str] = None
    pose_summary: Optional[str] = None
    defensive_wound_indicators: Optional[list[str]] = None
    defensive_posture_score: Optional[float] = None
    model_id: Optional[str] = None
    device: Optional[str] = None
    image_dims: Optional[dict[str, Any]] = None
    advanced_vision_enabled: Optional[bool] = None


class InconsistencyResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = "ok"
    inconsistencies: list[str] = Field(default_factory=list)
    error: Optional[str] = None

