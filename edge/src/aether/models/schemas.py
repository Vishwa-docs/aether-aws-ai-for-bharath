"""
AETHER data models — Python mirrors of the TypeScript interfaces.

These dataclasses are used across the edge layer:
  • Sensor simulators produce SensorReading instances
  • The fusion engine consumes them and produces AetherEvent instances
  • The gateway serialises AetherEvent to JSON for MQTT / SQLite
"""
from __future__ import annotations

import json
import uuid
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


# ─── Enums ────────────────────────────────────────────────────

class EventType(str, Enum):
    FALL = "fall"
    FALL_WITH_IMMOBILITY = "fall_with_immobility"
    ACOUSTIC_DISTRESS = "acoustic_distress"
    GLASS_BREAK = "glass_break"
    PROLONGED_SILENCE = "prolonged_silence"
    IMPACT_SOUND = "impact_sound"
    MEDICATION_TAKEN = "medication_taken"
    MEDICATION_MISSED = "medication_missed"
    MEDICATION_CONFUSION = "medication_confusion"
    ROUTINE_DRIFT = "routine_drift"
    DECLINING_HEALTH = "declining_health"
    RESPIRATORY_CONCERN = "respiratory_concern"
    MISSED_DOORBELL = "missed_doorbell"
    SYSTEM_HEALTH = "system_health"
    ENVIRONMENTAL_ALERT = "environmental_alert"
    COGNITIVE_DECLINE = "cognitive_decline"
    NUTRITION_CONCERN = "nutrition_concern"
    SCAM_ALERT = "scam_alert"
    EMOTIONAL_CONCERN = "emotional_concern"
    BATHROOM_ANOMALY = "bathroom_anomaly"
    CHOKING = "choking"
    GAIT_DEGRADATION = "gait_degradation"
    SLEEP_DISRUPTION = "sleep_disruption"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SensorType(str, Enum):
    IMU = "imu"
    ACOUSTIC = "acoustic"
    POSE = "pose"
    MEDICATION = "medication"
    ENVIRONMENTAL = "environmental"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    AIR_QUALITY = "air_quality"
    SMOKE = "smoke"
    CO = "co"
    LIGHT = "light"
    NOISE = "noise"
    TOILET = "toilet"


class AcousticEventLabel(str, Enum):
    SCREAM = "scream"
    GLASS_BREAK = "glass_break"
    IMPACT = "impact"
    COUGH = "cough"
    DOORBELL = "doorbell"
    PHONE_RING = "phone_ring"
    SILENCE = "silence"
    NORMAL = "normal"
    CHOKING = "choking"
    SNORING = "snoring"
    SLEEP_APNEA = "sleep_apnea"
    RESPIRATORY_DISTRESS = "respiratory_distress"
    WHEEZING = "wheezing"
    VERBAL_DISTRESS = "verbal_distress"


# ─── Sensor Readings (produced by simulators) ────────────────

@dataclass
class IMUReading:
    """A single 6-axis IMU sample at 100 Hz."""
    timestamp: float
    accel_x: float  # g-force
    accel_y: float
    accel_z: float
    gyro_x: float   # degrees/sec
    gyro_y: float
    gyro_z: float
    sensor_id: str = "wearable-001"

    @property
    def impact_force(self) -> float:
        """Total acceleration magnitude (g)."""
        return (self.accel_x**2 + self.accel_y**2 + self.accel_z**2) ** 0.5

    def to_dict(self) -> dict:
        d = asdict(self)
        d["impact_force"] = self.impact_force
        return d


@dataclass
class AcousticFeatures:
    """Extracted audio features (NOT raw audio)."""
    timestamp: float
    mfcc: list[float]            # 13 coefficients
    spectral_centroid: float
    spectral_rolloff: float
    zero_crossing_rate: float
    rms_energy: float
    sentinel_id: str = "sentinel-001"
    room: str = "living_room"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PoseKeypoint:
    """Single keypoint from 17-point skeleton."""
    x: float
    y: float
    confidence: float
    keypoint_type: str


# The 17 COCO keypoints
COCO_KEYPOINTS = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]


@dataclass
class PoseEstimation:
    """17-point skeleton from a single frame."""
    timestamp: float
    keypoints: list[PoseKeypoint]
    camera_id: str = "cam-001"

    @property
    def center_of_mass_y(self) -> float:
        """Approximate vertical center of mass from hip keypoints."""
        hips = [kp for kp in self.keypoints if "hip" in kp.keypoint_type]
        if not hips:
            return 0.5
        return sum(kp.y for kp in hips) / len(hips)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "keypoints": [asdict(kp) for kp in self.keypoints],
            "camera_id": self.camera_id,
            "center_of_mass_y": self.center_of_mass_y,
        }


@dataclass
class MedicationEvent:
    """NFC tag scan / pressure sensor event from MedDock."""
    timestamp: float
    medication_id: str
    medication_name: str
    nfc_tag_id: str
    removal_detected: bool
    scheduled_time: float
    dock_id: str = "meddock-001"

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Environmental & Smart Toilet Readings ───────────────────

@dataclass
class EnvironmentalReading:
    """A single environmental sensor snapshot."""
    timestamp: float
    room: str
    temperature_c: float
    humidity_pct: float
    aqi: float
    pm25: float
    co_ppm: float
    smoke_detected: bool
    light_lux: float
    noise_db: float
    sensor_id: str = "env-001"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SmartToiletReading:
    """A single smart toilet analysis reading."""
    timestamp: float
    session_type: str           # "urination" or "bowel_movement"
    duration_s: float
    strain_detected: bool
    bristol_scale: int          # 1-7
    hydration_indicator: float  # 0.0 (dehydrated) → 1.0 (well-hydrated)
    frequency_today: int
    sensor_id: str = "toilet-001"

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Generic sensor wrapper ──────────────────────────────────

@dataclass
class SensorReading:
    """Uniform wrapper around any sensor data for the fusion pipeline."""
    sensor_type: SensorType
    timestamp: float
    sensor_id: str
    data: IMUReading | AcousticFeatures | PoseEstimation | MedicationEvent | EnvironmentalReading | SmartToiletReading

    def to_dict(self) -> dict:
        return {
            "sensor_type": self.sensor_type.value,
            "timestamp": self.timestamp,
            "sensor_id": self.sensor_id,
            "data": self.data.to_dict(),
        }


# ─── Core Event (outbound to cloud) ──────────────────────────

@dataclass
class SensorSource:
    sensor_id: str
    sensor_type: str
    confidence: float


@dataclass
class EscalationInfo:
    tier: int
    notified: list[str] = field(default_factory=list)
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[float] = None
    resolved_at: Optional[float] = None


@dataclass
class AetherEvent:
    """
    The canonical event object transmitted to AWS IoT Core / stored in DynamoDB.
    """
    event_type: EventType
    severity: Severity
    confidence: float
    home_id: str
    data: dict[str, Any]
    sources: list[SensorSource]
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=lambda: time.time() * 1000)
    resident_id: Optional[str] = None
    escalation: Optional[EscalationInfo] = None
    evidence_packet_url: Optional[str] = None
    created_at: float = field(default_factory=lambda: time.time() * 1000)
    updated_at: float = field(default_factory=lambda: time.time() * 1000)
    ttl: Optional[int] = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "event_id": self.event_id,
            "home_id": self.home_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "data": self.data,
            "sources": [asdict(s) for s in self.sources],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.resident_id is not None:
            d["resident_id"] = self.resident_id
        if self.escalation is not None:
            d["escalation"] = asdict(self.escalation)
        if self.evidence_packet_url is not None:
            d["evidence_packet_url"] = self.evidence_packet_url
        if self.ttl is not None:
            d["ttl"] = self.ttl
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, d: dict) -> "AetherEvent":
        sources = [SensorSource(**s) for s in d.get("sources", [])]
        esc = None
        if "escalation" in d and d["escalation"]:
            esc = EscalationInfo(**d["escalation"])
        return cls(
            event_id=d["event_id"],
            home_id=d["home_id"],
            timestamp=d["timestamp"],
            event_type=EventType(d["event_type"]),
            severity=Severity(d["severity"]),
            confidence=d["confidence"],
            data=d.get("data", {}),
            sources=sources,
            resident_id=d.get("resident_id"),
            escalation=esc,
            evidence_packet_url=d.get("evidence_packet_url"),
            created_at=d.get("created_at", 0),
            updated_at=d.get("updated_at", 0),
            ttl=d.get("ttl"),
        )
