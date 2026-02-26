"""
Scam & Financial Fraud Protection

Detects potential phone/messaging scam activity targeting elderly residents:
  • Phone call duration anomaly detection (unusually long calls)
  • Repeated unknown caller detection
  • Keyword detection in overheard audio (money, transfer, bank, etc.)
  • Time-of-day anomaly (late-night calls)
  • Pattern recognition (escalating pressure tactics)
  • Configurable sensitivity levels
  • WhatsApp/message scam patterns
  • Fraud risk alerts

All analysis is on-edge and privacy-preserving — only metadata and
keyword flags are stored, never raw audio content.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import numpy as np

from aether.models.schemas import (
    AetherEvent,
    EventType,
    Severity,
    SensorSource,
)

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────

class ScamRiskLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SensitivityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ── Data classes ──────────────────────────────────────────────

@dataclass
class CallRecord:
    """Metadata for a phone call (no audio content stored)."""
    timestamp: float
    caller_id: str               # phone number or "unknown"
    duration_s: float
    is_known_contact: bool
    keywords_detected: list[str] = field(default_factory=list)
    is_incoming: bool = True


@dataclass
class MessageRecord:
    """Metadata for a text/WhatsApp message."""
    timestamp: float
    sender_id: str
    is_known_contact: bool
    keywords_detected: list[str] = field(default_factory=list)
    contains_link: bool = False
    urgency_language: bool = False


@dataclass
class FraudRiskAlert:
    """Alert generated when scam activity is suspected."""
    alert_id: str
    resident_id: str
    risk_level: ScamRiskLevel
    risk_score: float            # 0.0 – 1.0
    triggers: list[str]
    call_records: list[CallRecord] = field(default_factory=list)
    message_records: list[MessageRecord] = field(default_factory=list)
    recommendation: str = ""
    timestamp: float = field(default_factory=time.time)


# ── Keyword libraries ────────────────────────────────────────

# English scam keywords
_SCAM_KEYWORDS_EN = [
    "money", "transfer", "bank", "password", "otp", "urgent",
    "account", "payment", "verify", "social security", "irs", "tax",
    "prize", "lottery", "winner", "gift card", "wire", "western union",
    "arrest", "warrant", "police", "legal action", "court",
    "grandson", "granddaughter", "accident", "hospital", "bail",
    "insurance", "refund", "expired", "suspended", "compromised",
]

# Hindi scam keywords
_SCAM_KEYWORDS_HI = [
    "paisa", "transfer", "bank", "otp", "jaldi", "turant",
    "khata", "bhugtan", "inam", "lottery", "jeet", "card",
    "giraftar", "police", "kanoon", "adalat",
    "pota", "poti", "hadsa", "aspatal", "zamanat",
]

# Combined pattern (case-insensitive)
_KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(_SCAM_KEYWORDS_EN + _SCAM_KEYWORDS_HI) + r")\b",
    re.IGNORECASE,
)

# Pressure tactic phrases
_PRESSURE_PHRASES = [
    r"act\s+now", r"don't\s+tell\s+anyone", r"keep\s+this\s+secret",
    r"limited\s+time", r"last\s+chance", r"immediately",
    r"right\s+away", r"don't\s+hang\s+up", r"stay\s+on\s+the\s+line",
    r"you\s+will\s+be\s+arrested", r"your\s+account\s+will\s+be\s+closed",
]

_PRESSURE_PATTERN = re.compile(
    r"(" + "|".join(_PRESSURE_PHRASES) + r")",
    re.IGNORECASE,
)

# ── Sensitivity thresholds ────────────────────────────────────

_SENSITIVITY_CONFIG: dict[SensitivityLevel, dict] = {
    SensitivityLevel.LOW: {
        "call_duration_threshold_s": 1800,    # 30 min
        "unknown_caller_threshold": 5,
        "late_night_start_hour": 23,
        "late_night_end_hour": 5,
        "keyword_threshold": 4,
    },
    SensitivityLevel.MEDIUM: {
        "call_duration_threshold_s": 900,     # 15 min
        "unknown_caller_threshold": 3,
        "late_night_start_hour": 22,
        "late_night_end_hour": 6,
        "keyword_threshold": 3,
    },
    SensitivityLevel.HIGH: {
        "call_duration_threshold_s": 600,     # 10 min
        "unknown_caller_threshold": 2,
        "late_night_start_hour": 21,
        "late_night_end_hour": 7,
        "keyword_threshold": 2,
    },
}


# ── Engine ────────────────────────────────────────────────────

class ScamDetector:
    """Detect potential scam and fraud activity targeting elderly residents.

    Parameters
    ----------
    resident_id : str
        Resident being monitored.
    sensitivity : SensitivityLevel
        Detection sensitivity (default MEDIUM).
    known_contacts : list[str]
        List of known/trusted phone numbers.
    """

    def __init__(
        self,
        resident_id: str = "resident-001",
        sensitivity: SensitivityLevel = SensitivityLevel.MEDIUM,
        known_contacts: list[str] | None = None,
        seed: int = 42,
    ):
        self.resident_id = resident_id
        self.sensitivity = sensitivity
        self.known_contacts = set(known_contacts or [])
        self.rng = np.random.default_rng(seed)

        self._calls: deque[CallRecord] = deque(maxlen=5000)
        self._messages: deque[MessageRecord] = deque(maxlen=5000)

        self._config = _SENSITIVITY_CONFIG[sensitivity]

    # ── Keyword scanning ──────────────────────────────────────

    @staticmethod
    def scan_keywords(text: str) -> list[str]:
        """Return scam-related keywords found in *text*."""
        return list({m.group(0).lower() for m in _KEYWORD_PATTERN.finditer(text)})

    @staticmethod
    def detect_pressure_tactics(text: str) -> list[str]:
        """Return pressure tactic phrases found in *text*."""
        return [m.group(0) for m in _PRESSURE_PATTERN.finditer(text)]

    # ── Recording ─────────────────────────────────────────────

    def record_call(self, call: CallRecord) -> None:
        """Record a phone call metadata entry."""
        self._calls.append(call)

    def record_message(self, msg: MessageRecord) -> None:
        """Record a text/WhatsApp message metadata entry."""
        self._messages.append(msg)

    # ── Risk analysis ─────────────────────────────────────────

    def _is_late_night(self, timestamp: float) -> bool:
        """Check if timestamp falls in the late-night window."""
        hour = time.localtime(timestamp).tm_hour
        start = self._config["late_night_start_hour"]
        end = self._config["late_night_end_hour"]
        if start > end:
            return hour >= start or hour < end
        return start <= hour < end

    def analyse_recent_activity(self, window_hours: int = 24) -> FraudRiskAlert:
        """Analyse recent call and message activity for fraud indicators.

        Parameters
        ----------
        window_hours : int
            Look-back window in hours (default 24).

        Returns
        -------
        FraudRiskAlert
        """
        now = time.time()
        cutoff = now - window_hours * 3600
        recent_calls = [c for c in self._calls if c.timestamp >= cutoff]
        recent_msgs = [m for m in self._messages if m.timestamp >= cutoff]

        triggers: list[str] = []
        risk_score = 0.0

        # 1. Long calls with unknown callers
        long_unknown = [
            c for c in recent_calls
            if not c.is_known_contact
            and c.duration_s > self._config["call_duration_threshold_s"]
        ]
        if long_unknown:
            risk_score += 0.25 * len(long_unknown)
            triggers.append(
                f"{len(long_unknown)} long call(s) from unknown number(s) "
                f"(>{self._config['call_duration_threshold_s']//60} min)"
            )

        # 2. Repeated unknown callers
        unknown_callers = [c.caller_id for c in recent_calls if not c.is_known_contact]
        unique_unknown = set(unknown_callers)
        if len(unknown_callers) >= self._config["unknown_caller_threshold"]:
            risk_score += 0.20
            triggers.append(
                f"{len(unknown_callers)} call(s) from {len(unique_unknown)} unknown number(s)"
            )

        # 3. Keywords detected in calls
        all_call_keywords: list[str] = []
        for c in recent_calls:
            all_call_keywords.extend(c.keywords_detected)
        if len(all_call_keywords) >= self._config["keyword_threshold"]:
            risk_score += 0.25
            triggers.append(
                f"Scam keywords detected in calls: {', '.join(set(all_call_keywords))}"
            )

        # 4. Late-night calls
        late_calls = [c for c in recent_calls if self._is_late_night(c.timestamp)]
        if late_calls:
            risk_score += 0.15
            triggers.append(f"{len(late_calls)} late-night call(s) detected")

        # 5. Message analysis
        suspicious_msgs = [
            m for m in recent_msgs
            if m.keywords_detected or m.contains_link or m.urgency_language
        ]
        if suspicious_msgs:
            risk_score += 0.15 * len(suspicious_msgs)
            triggers.append(f"{len(suspicious_msgs)} suspicious message(s) detected")

        risk_score = min(1.0, risk_score)

        # Map score to risk level
        if risk_score >= 0.75:
            level = ScamRiskLevel.CRITICAL
        elif risk_score >= 0.50:
            level = ScamRiskLevel.HIGH
        elif risk_score >= 0.25:
            level = ScamRiskLevel.MEDIUM
        elif risk_score > 0:
            level = ScamRiskLevel.LOW
        else:
            level = ScamRiskLevel.NONE

        # Recommendation
        if level in (ScamRiskLevel.CRITICAL, ScamRiskLevel.HIGH):
            recommendation = "Immediately notify family/carer. Consider blocking unknown numbers."
        elif level == ScamRiskLevel.MEDIUM:
            recommendation = "Monitor closely. Remind resident about common scam patterns."
        elif level == ScamRiskLevel.LOW:
            recommendation = "Low risk — continue routine monitoring."
        else:
            recommendation = "No action required."

        return FraudRiskAlert(
            alert_id=str(uuid.uuid4()),
            resident_id=self.resident_id,
            risk_level=level,
            risk_score=round(risk_score, 2),
            triggers=triggers,
            call_records=recent_calls,
            message_records=recent_msgs,
            recommendation=recommendation,
        )

    def to_aether_event(self, alert: FraudRiskAlert) -> AetherEvent | None:
        """Convert a fraud alert to an AetherEvent if risk is non-zero."""
        if alert.risk_level == ScamRiskLevel.NONE:
            return None

        severity_map = {
            ScamRiskLevel.LOW: Severity.LOW,
            ScamRiskLevel.MEDIUM: Severity.MEDIUM,
            ScamRiskLevel.HIGH: Severity.HIGH,
            ScamRiskLevel.CRITICAL: Severity.CRITICAL,
        }
        return AetherEvent(
            event_type=EventType.SCAM_ALERT,
            severity=severity_map.get(alert.risk_level, Severity.LOW),
            confidence=alert.risk_score,
            home_id="home-001",
            resident_id=alert.resident_id,
            data={
                "alert_id": alert.alert_id,
                "risk_level": alert.risk_level.value,
                "risk_score": alert.risk_score,
                "triggers": alert.triggers,
                "recommendation": alert.recommendation,
                "call_count": len(alert.call_records),
                "message_count": len(alert.message_records),
            },
            sources=[SensorSource(
                sensor_id="scam-detector",
                sensor_type="analytics",
                confidence=alert.risk_score,
            )],
        )

    # ── Simulation helpers ────────────────────────────────────

    def simulate_normal_activity(self, days: int = 7) -> None:
        """Populate history with normal, non-suspicious call/message activity."""
        now = time.time()
        known = ["family-001", "friend-002", "doctor-003"]
        for d in range(days):
            n_calls = int(self.rng.integers(1, 5))
            for _ in range(n_calls):
                ts = now - (days - d) * 86400 + float(self.rng.uniform(8, 20)) * 3600
                caller = str(self.rng.choice(known))
                self.record_call(CallRecord(
                    timestamp=ts,
                    caller_id=caller,
                    duration_s=float(self.rng.uniform(60, 600)),
                    is_known_contact=True,
                ))

    def simulate_scam_attempt(self) -> None:
        """Inject a simulated scam-call pattern."""
        now = time.time()
        scam_number = "unknown-scam-999"

        # First call — short probe
        self.record_call(CallRecord(
            timestamp=now - 7200,
            caller_id=scam_number,
            duration_s=45,
            is_known_contact=False,
        ))

        # Second call — longer, with keywords
        self.record_call(CallRecord(
            timestamp=now - 3600,
            caller_id=scam_number,
            duration_s=1200,
            is_known_contact=False,
            keywords_detected=["bank", "transfer", "urgent", "otp"],
        ))

        # Third call — late night, pressure
        self.record_call(CallRecord(
            timestamp=now - 1800,
            caller_id=scam_number,
            duration_s=900,
            is_known_contact=False,
            keywords_detected=["money", "password", "arrest"],
        ))

        # Suspicious WhatsApp message
        self.record_message(MessageRecord(
            timestamp=now - 900,
            sender_id=scam_number,
            is_known_contact=False,
            keywords_detected=["bank", "verify", "account"],
            contains_link=True,
            urgency_language=True,
        ))
