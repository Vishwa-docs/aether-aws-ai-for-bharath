"""
Smart Toilet Simulator

Simulates smart-toilet analysis using sound-based inference:
  • Bowel movement frequency tracking
  • Duration analysis
  • Strain detection (via audio patterns)
  • Urination frequency
  • Bristol stool scale estimation (simulated)
  • Hydration indicators

Produces health insights: dehydration risk, UTI risk, digestive issues.

No real hardware is required — all data is simulated via seeded RNG.
"""
from __future__ import annotations

import time
import numpy as np
from dataclasses import dataclass, field
from typing import Iterator

from aether.models.schemas import (
    SmartToiletReading,
    SensorReading,
    SensorType,
)


# ── Health insight thresholds ─────────────────────────────────

DEHYDRATION_HYDRATION_THRESHOLD = 0.35
UTI_FREQUENCY_THRESHOLD = 10          # urinations per day
CONSTIPATION_BRISTOL_LOW = 1          # Bristol 1-2 = constipation
DIARRHEA_BRISTOL_HIGH = 6             # Bristol 6-7 = diarrhea
STRAIN_DURATION_THRESHOLD_S = 300     # >5 min with strain = concerning


@dataclass
class ToiletHealthInsight:
    """Aggregated health insight derived from toilet usage data."""
    timestamp: float
    dehydration_risk: float     # 0.0 – 1.0
    uti_risk: float             # 0.0 – 1.0
    constipation_risk: float    # 0.0 – 1.0
    diarrhea_risk: float        # 0.0 – 1.0
    digestive_score: float      # 0.0 (poor) – 1.0 (healthy)
    avg_hydration: float
    total_sessions: int
    urination_count: int
    bowel_movement_count: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


# ── Simulation profiles ──────────────────────────────────────

_SESSION_PROFILES: dict[str, dict] = {
    "normal_urination": {
        "session_type": "urination",
        "duration_s": (25.0, 8.0),
        "strain": False,
        "bristol_scale": 0,
        "hydration": (0.7, 0.1),
    },
    "normal_bowel": {
        "session_type": "bowel_movement",
        "duration_s": (180.0, 60.0),
        "strain": False,
        "bristol_scale": (4, 1),  # Bristol 3-5 = normal
        "hydration": (0.6, 0.1),
    },
    "constipation": {
        "session_type": "bowel_movement",
        "duration_s": (420.0, 90.0),
        "strain": True,
        "bristol_scale": (1, 0.5),  # Bristol 1-2
        "hydration": (0.3, 0.1),
    },
    "diarrhea": {
        "session_type": "bowel_movement",
        "duration_s": (45.0, 15.0),
        "strain": False,
        "bristol_scale": (6, 0.5),
        "hydration": (0.3, 0.1),
    },
    "dehydrated_urination": {
        "session_type": "urination",
        "duration_s": (15.0, 5.0),
        "strain": False,
        "bristol_scale": 0,
        "hydration": (0.2, 0.05),
    },
    "uti_pattern": {
        "session_type": "urination",
        "duration_s": (10.0, 3.0),
        "strain": True,
        "bristol_scale": 0,
        "hydration": (0.4, 0.1),
    },
}


class SmartToiletSimulator:
    """Simulate smart toilet sound-based analysis readings."""

    def __init__(
        self,
        sensor_id: str = "toilet-001",
        seed: int = 42,
    ):
        self.sensor_id = sensor_id
        self.rng = np.random.default_rng(seed)
        self._daily_sessions: list[SmartToiletReading] = []

    # ── Internals ─────────────────────────────────────────────

    def _generate_session(
        self,
        profile_name: str = "normal_urination",
        timestamp: float | None = None,
    ) -> SmartToiletReading:
        """Generate a single toilet session reading from a named profile."""
        ts = timestamp or time.time()
        profile = _SESSION_PROFILES.get(profile_name, _SESSION_PROFILES["normal_urination"])

        duration_spec = profile["duration_s"]
        if isinstance(duration_spec, tuple):
            duration = max(5.0, float(self.rng.normal(*duration_spec)))
        else:
            duration = float(duration_spec)

        bristol = 0
        bristol_spec = profile["bristol_scale"]
        if isinstance(bristol_spec, tuple):
            bristol = int(np.clip(round(self.rng.normal(*bristol_spec)), 1, 7))
        else:
            bristol = int(bristol_spec)

        hydration_spec = profile["hydration"]
        if isinstance(hydration_spec, tuple):
            hydration = float(np.clip(self.rng.normal(*hydration_spec), 0.0, 1.0))
        else:
            hydration = float(hydration_spec)

        strain = bool(profile["strain"])
        # Add random chance of strain (~10 %) even in "normal" sessions
        if not strain and self.rng.random() < 0.10:
            strain = True

        reading = SmartToiletReading(
            timestamp=ts,
            session_type=profile["session_type"],
            duration_s=round(duration, 1),
            strain_detected=strain,
            bristol_scale=bristol,
            hydration_indicator=round(hydration, 2),
            frequency_today=len(self._daily_sessions) + 1,
            sensor_id=self.sensor_id,
        )
        self._daily_sessions.append(reading)
        return reading

    # ── Public API ────────────────────────────────────────────

    def generate_reading(
        self,
        profile: str = "normal_urination",
        timestamp: float | None = None,
    ) -> SmartToiletReading:
        """Generate a single toilet session reading.

        Parameters
        ----------
        profile : str
            One of ``normal_urination``, ``normal_bowel``, ``constipation``,
            ``diarrhea``, ``dehydrated_urination``, ``uti_pattern``.
        timestamp : float, optional
            Unix epoch; defaults to now.
        """
        return self._generate_session(profile, timestamp)

    def generate_daily_sessions(
        self,
        urination_count: int = 6,
        bowel_count: int = 1,
        anomaly: str | None = None,
    ) -> list[SmartToiletReading]:
        """Generate a full day of toilet sessions.

        Parameters
        ----------
        urination_count : int
            Number of urination events (default 6).
        bowel_count : int
            Number of bowel movements (default 1).
        anomaly : str, optional
            If set, inject anomaly profile for some sessions.
            Supported: ``constipation``, ``diarrhea``, ``dehydration``,
            ``uti``.
        """
        self._daily_sessions.clear()
        sessions: list[SmartToiletReading] = []
        t_start = time.time()

        # Spread sessions across ~16 waking hours
        total = urination_count + bowel_count
        interval_s = (16 * 3600) / max(total, 1)

        for i in range(urination_count):
            ts = t_start + i * interval_s
            if anomaly == "dehydration":
                profile = "dehydrated_urination"
            elif anomaly == "uti" and i % 2 == 0:
                profile = "uti_pattern"
            else:
                profile = "normal_urination"
            sessions.append(self._generate_session(profile, ts))

        for i in range(bowel_count):
            ts = t_start + (urination_count + i) * interval_s
            if anomaly == "constipation":
                profile = "constipation"
            elif anomaly == "diarrhea":
                profile = "diarrhea"
            else:
                profile = "normal_bowel"
            sessions.append(self._generate_session(profile, ts))

        return sessions

    def generate_health_insight(
        self,
        sessions: list[SmartToiletReading] | None = None,
    ) -> ToiletHealthInsight:
        """Analyse a list of sessions and produce health insights.

        Parameters
        ----------
        sessions : list, optional
            Sessions to analyse; defaults to today's accumulated sessions.
        """
        data = sessions or self._daily_sessions
        if not data:
            return ToiletHealthInsight(
                timestamp=time.time(),
                dehydration_risk=0.0, uti_risk=0.0,
                constipation_risk=0.0, diarrhea_risk=0.0,
                digestive_score=1.0, avg_hydration=1.0,
                total_sessions=0, urination_count=0,
                bowel_movement_count=0,
            )

        urinations = [s for s in data if s.session_type == "urination"]
        bowels = [s for s in data if s.session_type == "bowel_movement"]

        avg_hydration = float(np.mean([s.hydration_indicator for s in data]))
        notes: list[str] = []

        # Dehydration risk
        dehydration_risk = 0.0
        if avg_hydration < DEHYDRATION_HYDRATION_THRESHOLD:
            dehydration_risk = min(1.0, (DEHYDRATION_HYDRATION_THRESHOLD - avg_hydration) * 4)
            notes.append("Low hydration indicators detected — encourage fluid intake.")

        # UTI risk
        uti_risk = 0.0
        if len(urinations) >= UTI_FREQUENCY_THRESHOLD:
            uti_risk = min(1.0, (len(urinations) - UTI_FREQUENCY_THRESHOLD) / 5 + 0.4)
            notes.append(f"High urination frequency ({len(urinations)}/day) — possible UTI indicator.")
        strain_urinations = [s for s in urinations if s.strain_detected]
        if strain_urinations:
            uti_risk = min(1.0, uti_risk + 0.3)
            notes.append("Strain detected during urination — possible UTI indicator.")

        # Constipation risk
        constipation_risk = 0.0
        low_bristol = [s for s in bowels if s.bristol_scale <= CONSTIPATION_BRISTOL_LOW]
        if low_bristol:
            constipation_risk = min(1.0, len(low_bristol) / max(len(bowels), 1))
            notes.append("Hard stool detected (Bristol 1-2) — possible constipation.")
        strained_long = [s for s in bowels if s.strain_detected and s.duration_s > STRAIN_DURATION_THRESHOLD_S]
        if strained_long:
            constipation_risk = min(1.0, constipation_risk + 0.3)
            notes.append("Prolonged strain during bowel movement — possible constipation.")

        # Diarrhea risk
        diarrhea_risk = 0.0
        high_bristol = [s for s in bowels if s.bristol_scale >= DIARRHEA_BRISTOL_HIGH]
        if high_bristol:
            diarrhea_risk = min(1.0, len(high_bristol) / max(len(bowels), 1))
            notes.append("Loose stool detected (Bristol 6-7) — possible diarrhea.")

        # Overall digestive score (1.0 = healthy)
        digestive_score = max(0.0, 1.0 - max(constipation_risk, diarrhea_risk, dehydration_risk))

        return ToiletHealthInsight(
            timestamp=time.time(),
            dehydration_risk=round(dehydration_risk, 2),
            uti_risk=round(uti_risk, 2),
            constipation_risk=round(constipation_risk, 2),
            diarrhea_risk=round(diarrhea_risk, 2),
            digestive_score=round(digestive_score, 2),
            avg_hydration=round(avg_hydration, 2),
            total_sessions=len(data),
            urination_count=len(urinations),
            bowel_movement_count=len(bowels),
            notes=notes,
        )

    def stream(
        self,
        profile: str = "normal_urination",
        count: int = 4,
    ) -> Iterator[SensorReading]:
        """Yield SensorReading wrappers for the fusion pipeline."""
        for _ in range(count):
            reading = self._generate_session(profile)
            yield SensorReading(
                sensor_type=SensorType.TOILET,
                timestamp=reading.timestamp,
                sensor_id=self.sensor_id,
                data=reading,
            )
