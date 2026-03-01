"""
AETHER Elderly Care System – Shared Data Models
================================================
Canonical dataclasses and helper utilities consumed by every Lambda in the
AETHER cloud layer.  All timestamps are ISO-8601 UTC strings.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    """All recognised event types emitted by the Edge Gateway."""

    FALL_DETECTED = "fall_detected"
    MEDICATION_TAKEN = "medication_taken"
    MEDICATION_MISSED = "medication_missed"
    MEDICATION_LATE = "medication_late"
    ACOUSTIC_SCREAM = "acoustic_scream"
    ACOUSTIC_GLASS_BREAK = "acoustic_glass_break"
    ACOUSTIC_IMPACT = "acoustic_impact"
    ACOUSTIC_SILENCE = "acoustic_silence"
    ROUTINE_ANOMALY = "routine_anomaly"
    VITAL_ALERT = "vital_alert"
    CHECK_IN_COMPLETED = "check_in_completed"


class Severity(str, Enum):
    """Severity levels – ordered from most to least critical."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class PrivacyLevel(str, Enum):
    """Privacy levels controlling data retention / access."""

    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    SENSITIVE = "SENSITIVE"
    RESTRICTED = "RESTRICTED"


class EscalationTier(int, Enum):
    """Escalation ladder tiers."""

    LOCAL_ALARM = 1
    CAREGIVER = 2
    NURSE = 3
    EMERGENCY = 4


# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------

_SEVERITY_PRIORITY: Dict[str, int] = {
    Severity.CRITICAL: 1,
    Severity.HIGH: 2,
    Severity.MEDIUM: 3,
    Severity.LOW: 4,
    Severity.INFO: 5,
}


def severity_to_priority(severity: str) -> int:
    """Convert a severity string to a numeric priority (1 = highest).

    Args:
        severity: One of the ``Severity`` enum values.

    Returns:
        Integer priority where 1 is the most urgent.
    """
    return _SEVERITY_PRIORITY.get(severity.upper(), 5)


# ---------------------------------------------------------------------------
# ID / timestamp helpers
# ---------------------------------------------------------------------------

def generate_event_id() -> str:
    """Generate a globally unique event identifier.

    Returns:
        A prefixed UUID-4 string, e.g. ``evt-<uuid4>``.
    """
    return f"evt-{uuid.uuid4().hex}"


def generate_triage_id() -> str:
    """Generate a globally unique triage card identifier."""
    return f"tri-{uuid.uuid4().hex}"


def generate_escalation_id() -> str:
    """Generate a globally unique escalation identifier."""
    return f"esc-{uuid.uuid4().hex}"


def get_current_timestamp() -> str:
    """Return the current UTC time as an ISO-8601 string.

    Returns:
        Timestamp like ``2026-03-01T12:34:56.789012Z``.
    """
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """Canonical representation of an AETHER sensor event.

    Attributes:
        event_id: Unique identifier (``evt-…``).
        home_id: ID of the home / dwelling.
        resident_id: ID of the resident associated with the event.
        event_type: One of :class:`EventType` values.
        severity: One of :class:`Severity` values.
        timestamp: ISO-8601 UTC timestamp.
        data: Arbitrary sensor payload.
        confidence: Model confidence score in ``[0, 1]``.
        source_sensors: List of sensor identifiers that contributed.
        privacy_level: Data sensitivity classification.
        evidence_packet_id: S3 key / reference to evidence bundle.
    """

    event_id: str
    home_id: str
    resident_id: str
    event_type: str
    severity: str
    timestamp: str
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    source_sensors: List[str] = field(default_factory=list)
    privacy_level: str = PrivacyLevel.PRIVATE
    evidence_packet_id: Optional[str] = None

    # -- convenience helpers -------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dictionary (DynamoDB-friendly)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Construct an ``Event`` from a raw dictionary.

        Unknown keys are silently ignored so the class is forward-compatible
        with payload extensions.
        """
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})

    @property
    def is_critical_or_high(self) -> bool:
        """Return ``True`` when the event's severity warrants triage."""
        return self.severity in (Severity.CRITICAL, Severity.HIGH)

    @property
    def priority(self) -> int:
        """Numeric priority derived from severity."""
        return severity_to_priority(self.severity)


@dataclass
class TriageCard:
    """AI-generated clinical triage card for high-severity events.

    Attributes:
        event_id: The source event identifier.
        triage_id: Unique triage card ID.
        risk_score: Numeric risk 0–100.
        assessment: Free-text clinical assessment.
        recommended_actions: Ordered action list.
        model_used: Bedrock model identifier.
        generated_at: ISO-8601 UTC timestamp of generation.
    """

    event_id: str
    triage_id: str = field(default_factory=generate_triage_id)
    risk_score: float = 0.0
    assessment: str = ""
    recommended_actions: List[str] = field(default_factory=list)
    model_used: str = ""
    generated_at: str = field(default_factory=get_current_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriageCard":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


@dataclass
class EscalationStep:
    """One step in the escalation history."""

    tier: int
    action: str
    timestamp: str = field(default_factory=get_current_timestamp)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EscalationState:
    """Tracks the current state of an active escalation workflow.

    Attributes:
        event_id: The originating event.
        escalation_id: Unique escalation identifier.
        current_tier: Current :class:`EscalationTier` value.
        started_at: When escalation began (ISO-8601).
        acknowledged_by: User ID that acknowledged, or ``None``.
        acknowledged_at: When it was acknowledged, or ``None``.
        resolved: Whether escalation is complete.
        escalation_history: Ordered list of :class:`EscalationStep`.
        home_id: Home associated with this escalation.
        resident_id: Resident associated with this escalation.
        severity: Original event severity.
    """

    event_id: str
    escalation_id: str = field(default_factory=generate_escalation_id)
    current_tier: int = EscalationTier.LOCAL_ALARM
    started_at: str = field(default_factory=get_current_timestamp)
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved: bool = False
    escalation_history: List[Dict[str, Any]] = field(default_factory=list)
    home_id: str = ""
    resident_id: str = ""
    severity: str = Severity.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EscalationState":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})

    def add_step(self, tier: int, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Append a step to the escalation history."""
        step = EscalationStep(tier=tier, action=action, details=details or {})
        self.escalation_history.append(step.to_dict())
        self.current_tier = tier


@dataclass
class TimelineEntry:
    """A single entry in the daily timeline roll-up.

    Attributes:
        home_id: Home identifier (partition key).
        date: Calendar date ``YYYY-MM-DD`` (sort key).
        total_events: Number of events in the day.
        events_by_type: Counts keyed by event type.
        events_by_severity: Counts keyed by severity.
        fall_count: Number of fall events.
        medication_adherence_pct: Percentage of medications taken on time.
        activity_score: Composite 0–100 daily activity score.
        narrative_summary: AI-generated plain-English summary.
        key_events: List of the most important event summaries.
        updated_at: Last aggregation run timestamp.
    """

    home_id: str
    date: str
    total_events: int = 0
    events_by_type: Dict[str, int] = field(default_factory=dict)
    events_by_severity: Dict[str, int] = field(default_factory=dict)
    fall_count: int = 0
    medication_adherence_pct: float = 100.0
    activity_score: float = 0.0
    narrative_summary: str = ""
    key_events: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: str = field(default_factory=get_current_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimelineEntry":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

VALID_EVENT_TYPES = {e.value for e in EventType}
VALID_SEVERITIES = {s.value for s in Severity}

REQUIRED_EVENT_FIELDS = {"home_id", "resident_id", "event_type", "severity", "timestamp"}


def validate_event_payload(payload: Dict[str, Any]) -> List[str]:
    """Validate a raw event payload and return a list of error strings.

    Returns:
        An empty list if the payload is valid.
    """
    errors: List[str] = []

    for field_name in REQUIRED_EVENT_FIELDS:
        if field_name not in payload or not payload[field_name]:
            errors.append(f"Missing required field: {field_name}")

    if payload.get("event_type") and payload["event_type"] not in VALID_EVENT_TYPES:
        errors.append(f"Invalid event_type: {payload['event_type']}")

    if payload.get("severity") and payload["severity"] not in VALID_SEVERITIES:
        errors.append(f"Invalid severity: {payload['severity']}")

    confidence = payload.get("confidence")
    if confidence is not None:
        try:
            c = float(confidence)
            if not 0.0 <= c <= 1.0:
                errors.append(f"confidence must be between 0 and 1, got {c}")
        except (TypeError, ValueError):
            errors.append(f"confidence must be numeric, got {confidence!r}")

    return errors


# ---------------------------------------------------------------------------
# Prescription OCR models
# ---------------------------------------------------------------------------

@dataclass
class PrescriptionRecord:
    """Parsed prescription from OCR processing.

    Attributes:
        document_id: Unique document identifier (``rx-…``).
        resident_id: Associated resident.
        home_id: Associated home.
        medications: List of parsed medication dicts (name, dosage, frequency, etc.).
        doctor: Prescribing doctor's name.
        date: Prescription date.
        source_url: S3 URL of the original document.
        confidence_score: Overall OCR + parsing confidence (0–1).
        field_confidences: Per-field confidence scores.
        page_count: Number of pages in the source document.
        raw_text: Extracted raw text (truncated).
        conflicts: List of detected medication conflicts.
        status: Processing status (``processed`` or ``review_needed``).
        created_at: When the record was created.
        correlation_id: Request correlation ID.
    """

    document_id: str
    resident_id: str = ""
    home_id: str = ""
    medications: List[Dict[str, Any]] = field(default_factory=list)
    doctor: str = ""
    date: str = ""
    source_url: str = ""
    confidence_score: float = 0.0
    field_confidences: Dict[str, float] = field(default_factory=dict)
    page_count: int = 1
    raw_text: str = ""
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "processed"
    created_at: str = field(default_factory=get_current_timestamp)
    correlation_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PrescriptionRecord":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


# ---------------------------------------------------------------------------
# Polypharmacy / Drug interaction models
# ---------------------------------------------------------------------------

@dataclass
class DrugInteraction:
    """A detected drug-drug interaction.

    Attributes:
        drug_a: First medication in the interaction pair.
        drug_b: Second medication in the interaction pair.
        severity: Interaction severity (minor, moderate, severe, contraindicated).
        description: Clinical description of the interaction.
        recommendation: Recommended action.
    """

    drug_a: str
    drug_b: str
    severity: str = "unknown"
    description: str = ""
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DrugInteraction":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


# ---------------------------------------------------------------------------
# Booking models (DEMO ONLY)
# ---------------------------------------------------------------------------

@dataclass
class Booking:
    """A simulated booking request (transport, food, appointment, shopping).

    Attributes:
        booking_id: Unique booking identifier (``bk-…``).
        resident_id: Resident who made the request.
        home_id: Associated home.
        booking_type: One of ``transport``, ``food_order``, ``appointment``, ``shopping``.
        status: Booking status (``confirmed``, ``cancelled``, ``completed``).
        request_text: Original natural-language request.
        parsed_intent: Structured intent parsed from the request.
        details: Type-specific booking details.
        confirmation_message: Generated confirmation message for the elder.
        demo_only: Always ``True`` – indicates no real transaction.
        created_at: When the booking was created.
        updated_at: Last update timestamp.
        correlation_id: Request correlation ID.
    """

    booking_id: str
    resident_id: str = ""
    home_id: str = ""
    booking_type: str = "transport"
    status: str = "confirmed"
    request_text: str = ""
    parsed_intent: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)
    confirmation_message: str = ""
    demo_only: bool = True
    created_at: str = field(default_factory=get_current_timestamp)
    updated_at: str = field(default_factory=get_current_timestamp)
    correlation_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Booking":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


# ---------------------------------------------------------------------------
# Health insights models
# ---------------------------------------------------------------------------

@dataclass
class HealthProfile:
    """Aggregated health profile with domain scores and trends.

    Attributes:
        resident_id: Resident identifier (partition key).
        home_id: Associated home.
        domain_scores: Health scores (0–100) per domain.
        trends: Trend analysis data.
        overall_score: Weighted overall health score.
        last_updated: Last computation timestamp.
        report_window: Time window for the report (e.g. ``7d``).
        event_count: Number of events analysed.
        narrative: AI-generated health narrative.
    """

    resident_id: str
    home_id: str = ""
    domain_scores: Dict[str, float] = field(default_factory=dict)
    trends: Dict[str, Any] = field(default_factory=dict)
    overall_score: float = 0.0
    last_updated: str = field(default_factory=get_current_timestamp)
    report_window: str = "7d"
    event_count: int = 0
    narrative: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthProfile":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


# ---------------------------------------------------------------------------
# Clinic / B2B operations models
# ---------------------------------------------------------------------------

@dataclass
class SiteHealth:
    """Health status for a monitored site.

    Attributes:
        site_id: Site identifier.
        tenant_id: Tenant owning this site.
        gateway_status: Gateway online/offline counts and uptime.
        sensor_counts: Sensor active/inactive/error counts.
        sla_metrics: SLA compliance metrics.
        overall_health_score: Composite health score (0–100).
        alert_density: Alerts per resident per day.
        last_updated: Last refresh timestamp.
    """

    site_id: str
    tenant_id: str = ""
    gateway_status: Dict[str, Any] = field(default_factory=lambda: {
        "total": 0, "online": 0, "offline": 0, "uptime_pct": 0.0,
    })
    sensor_counts: Dict[str, int] = field(default_factory=lambda: {
        "total": 0, "active": 0, "inactive": 0, "error": 0,
    })
    sla_metrics: Dict[str, Any] = field(default_factory=dict)
    overall_health_score: float = 0.0
    alert_density: float = 0.0
    last_updated: str = field(default_factory=get_current_timestamp)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteHealth":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


# ---------------------------------------------------------------------------
# Family portal models
# ---------------------------------------------------------------------------

@dataclass
class FamilyCalendarEvent:
    """An event in the shared family calendar.

    Attributes:
        event_id: Unique event identifier (``cal-…``).
        resident_id: Associated resident.
        event_type: Category (medication, appointment, transport, etc.).
        title: Human-readable title.
        event_datetime: When the event occurs (ISO-8601).
        participants: List of participant names / IDs.
        recurrence: Recurrence rule (e.g. ``daily``, ``weekly``, or ``None``).
        notes: Free-text notes.
        created_by: Who created the event.
        created_at: When the event was created.
        status: Event status (``active``, ``deleted``).
    """

    event_id: str
    resident_id: str = ""
    event_type: str = "other"
    title: str = ""
    event_datetime: str = ""
    participants: List[str] = field(default_factory=list)
    recurrence: Optional[str] = None
    notes: str = ""
    created_by: str = ""
    created_at: str = field(default_factory=get_current_timestamp)
    status: str = "active"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FamilyCalendarEvent":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


@dataclass
class CareHandoff:
    """Caregiver shift handoff record.

    Attributes:
        handoff_id: Unique handoff identifier (``ho-…``).
        resident_id: Associated resident.
        home_id: Associated home.
        from_caregiver: Outgoing caregiver ID / name.
        to_caregiver: Incoming caregiver ID / name.
        checklist: List of handoff checklist items with completion status.
        notes: Free-text handoff notes.
        shift_summary: Summary of the completed shift.
        pending_tasks: Tasks that need to be completed by the incoming caregiver.
        timestamp: When the handoff was created.
        status: Handoff status (``pending``, ``completed``).
    """

    handoff_id: str
    resident_id: str = ""
    home_id: str = ""
    from_caregiver: str = ""
    to_caregiver: str = ""
    checklist: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    shift_summary: str = ""
    pending_tasks: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=get_current_timestamp)
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CareHandoff":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})


@dataclass
class ConsentRecord:
    """Privacy and consent settings for a resident.

    Attributes:
        resident_id: Resident identifier.
        data_types: Dict mapping data type to allowed viewers and retention.
        data_sharing_enabled: Whether data sharing is globally enabled.
        export_allowed: Whether the resident's data can be exported.
        delete_on_request: Whether data is deleted upon request.
        last_reviewed: When consent was last reviewed.
        updated_at: Last update timestamp.
        updated_by: Who made the last update.
    """

    resident_id: str
    data_types: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    data_sharing_enabled: bool = True
    export_allowed: bool = True
    delete_on_request: bool = True
    last_reviewed: Optional[str] = None
    updated_at: str = field(default_factory=get_current_timestamp)
    updated_by: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsentRecord":
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known_fields})
