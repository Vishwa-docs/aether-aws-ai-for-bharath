"""
AETHER Sleep Tracker — BedSense + Acoustic Sleep Monitoring
=============================================================
Tracks sleep patterns using under-mattress pressure sensor data and
optional acoustic features (snoring, apnea events).

Features:
  • Sleep/wake detection from bed presence
  • Sleep stage estimation (light / deep / REM proxy)
  • Bed-exit counting (nighttime fall-risk indicator)
  • Toss-and-turn / restlessness scoring
  • Sleep fragmentation index (SFI)
  • Snoring frequency and duration tracking
  • Apnea event detection (silence gaps in breathing)
  • Nightly sleep quality score (0–100)
  • Multi-night trend analysis with drift detection
  • AetherEvent generation for sleep disruptions

Privacy-first: only derived features are stored — no raw audio.
"""

from __future__ import annotations

import time
import uuid
import math
import statistics
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

from aether.models.schemas import (
    AetherEvent,
    EventType,
    Severity,
    SensorSource,
)


# ─── Enums ────────────────────────────────────────────────────

class SleepStage(str, Enum):
    AWAKE = "awake"
    LIGHT = "light"
    DEEP = "deep"
    REM = "rem"


class SleepDisruptionType(str, Enum):
    BED_EXIT = "bed_exit"
    RESTLESSNESS = "restlessness"
    SNORING = "snoring"
    APNEA_EVENT = "apnea_event"
    PROLONGED_WAKEFULNESS = "prolonged_wakefulness"


# ─── Data Models ──────────────────────────────────────────────

@dataclass
class BedSenseReading:
    """Under-mattress pressure strip reading."""
    timestamp: float
    bed_occupied: bool
    pressure_level: float        # 0.0–1.0 (0 = empty, 1 = max pressure)
    movement_intensity: float    # 0.0–1.0 (toss/turn magnitude)
    heart_rate_proxy: float      # derived from ballistocardiography (BPM)
    breathing_rate_proxy: float  # breaths per minute from pressure oscillation
    sensor_id: str = "bedsense-001"


@dataclass
class SleepAcousticReading:
    """Derived acoustic features for sleep monitoring (NOT raw audio)."""
    timestamp: float
    snore_detected: bool
    snore_intensity: float       # 0.0–1.0
    apnea_pause_s: float         # seconds of breathing silence (>10s = event)
    cough_count: int
    breathing_regularity: float  # 0.0 (irregular) – 1.0 (steady)
    ambient_noise_db: float


@dataclass
class SleepEpoch:
    """30-second sleep epoch classification."""
    timestamp: float
    stage: SleepStage
    confidence: float
    movement_intensity: float
    heart_rate: float
    breathing_rate: float
    snoring: bool = False
    apnea_event: bool = False


@dataclass
class SleepSession:
    """Complete nightly sleep summary."""
    session_id: str
    resident_id: str
    date: str
    bed_time: float
    wake_time: float
    total_time_minutes: float
    sleep_onset_minutes: float   # time to fall asleep
    sleep_efficiency_pct: float  # time asleep / time in bed
    light_sleep_pct: float
    deep_sleep_pct: float
    rem_sleep_pct: float
    awake_pct: float
    bed_exits: int
    toss_turn_count: int
    snore_minutes: float
    apnea_events: int
    average_heart_rate: float
    average_breathing_rate: float
    sleep_quality_score: int     # 0–100
    fragmentation_index: float   # higher = more disrupted
    disruptions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SleepTrend:
    """Multi-night sleep trend analysis."""
    resident_id: str
    period_days: int
    avg_quality_score: float
    avg_total_sleep_min: float
    avg_deep_sleep_pct: float
    avg_bed_exits: float
    avg_apnea_events: float
    quality_trend: str           # "improving", "stable", "declining"
    drift_detected: bool
    drift_details: str = ""


# ─── Sleep Tracker ────────────────────────────────────────────

class SleepTracker:
    """Tracks sleep patterns from BedSense pressure data and acoustic features.

    Parameters
    ----------
    resident_id : str
        Resident identifier.
    deep_sleep_threshold : float
        Movement intensity below this → deep sleep (default 0.05).
    rem_movement_range : tuple
        Movement range for REM detection (micro-movements).
    apnea_threshold_s : float
        Breathing pause duration to flag as apnea event (default 10.0 s).
    bed_exit_absence_s : float
        Seconds of no bed presence to count as bed exit (default 30).
    """

    def __init__(
        self,
        resident_id: str = "resident-001",
        deep_sleep_threshold: float = 0.05,
        rem_movement_range: tuple = (0.02, 0.08),
        apnea_threshold_s: float = 10.0,
        bed_exit_absence_s: float = 30.0,
    ):
        self.resident_id = resident_id
        self.deep_sleep_threshold = deep_sleep_threshold
        self.rem_movement_range = rem_movement_range
        self.apnea_threshold_s = apnea_threshold_s
        self.bed_exit_absence_s = bed_exit_absence_s

        # Epoch + session buffers
        self._epochs: List[SleepEpoch] = []
        self._sessions: List[SleepSession] = []

        # Rolling state
        self._bed_occupied = False
        self._bed_enter_time: Optional[float] = None
        self._last_occupied_time: Optional[float] = None
        self._bed_exit_count = 0
        self._toss_turn_count = 0
        self._snore_epochs = 0
        self._apnea_events = 0

    # ── Epoch classification ──────────────────────────────────

    def classify_epoch(
        self,
        bed_reading: BedSenseReading,
        acoustic: Optional[SleepAcousticReading] = None,
    ) -> SleepEpoch:
        """Classify a 30-second epoch into a sleep stage."""
        movement = bed_reading.movement_intensity
        hr = bed_reading.heart_rate_proxy
        br = bed_reading.breathing_rate_proxy

        # Determine stage
        if not bed_reading.bed_occupied:
            stage = SleepStage.AWAKE
            confidence = 0.95
        elif movement > 0.3:
            stage = SleepStage.AWAKE
            confidence = 0.80
        elif movement < self.deep_sleep_threshold and br < 14:
            stage = SleepStage.DEEP
            confidence = 0.75
        elif self.rem_movement_range[0] <= movement <= self.rem_movement_range[1]:
            # REM: low overall movement but micro-movements, irregular breathing
            stage = SleepStage.REM
            confidence = 0.65
        else:
            stage = SleepStage.LIGHT
            confidence = 0.70

        snoring = False
        apnea = False
        if acoustic:
            snoring = acoustic.snore_detected
            apnea = acoustic.apnea_pause_s >= self.apnea_threshold_s

        epoch = SleepEpoch(
            timestamp=bed_reading.timestamp,
            stage=stage,
            confidence=confidence,
            movement_intensity=movement,
            heart_rate=hr,
            breathing_rate=br,
            snoring=snoring,
            apnea_event=apnea,
        )

        self._epochs.append(epoch)

        # Track disruptions
        if movement > 0.4:
            self._toss_turn_count += 1
        if snoring:
            self._snore_epochs += 1
        if apnea:
            self._apnea_events += 1

        # Bed exit detection
        if self._bed_occupied and not bed_reading.bed_occupied:
            self._last_occupied_time = bed_reading.timestamp
        if not self._bed_occupied and bed_reading.bed_occupied and self._last_occupied_time:
            absence = bed_reading.timestamp - self._last_occupied_time
            if absence >= self.bed_exit_absence_s:
                self._bed_exit_count += 1
        self._bed_occupied = bed_reading.bed_occupied
        if bed_reading.bed_occupied and self._bed_enter_time is None:
            self._bed_enter_time = bed_reading.timestamp

        return epoch

    # ── Session analysis ──────────────────────────────────────

    def generate_session(self, date: str = "") -> SleepSession:
        """Analyse accumulated epochs into a full sleep session summary."""
        if not self._epochs:
            return SleepSession(
                session_id=uuid.uuid4().hex[:12],
                resident_id=self.resident_id,
                date=date or time.strftime("%Y-%m-%d"),
                bed_time=0, wake_time=0, total_time_minutes=0,
                sleep_onset_minutes=0, sleep_efficiency_pct=0,
                light_sleep_pct=0, deep_sleep_pct=0, rem_sleep_pct=0,
                awake_pct=100, bed_exits=0, toss_turn_count=0,
                snore_minutes=0, apnea_events=0, average_heart_rate=0,
                average_breathing_rate=0, sleep_quality_score=0,
                fragmentation_index=1.0,
            )

        bed_time = self._epochs[0].timestamp
        wake_time = self._epochs[-1].timestamp
        total_min = (wake_time - bed_time) / 60.0

        # Stage distribution
        stages = [e.stage for e in self._epochs]
        total = len(stages)
        light_pct = stages.count(SleepStage.LIGHT) / total * 100
        deep_pct = stages.count(SleepStage.DEEP) / total * 100
        rem_pct = stages.count(SleepStage.REM) / total * 100
        awake_pct = stages.count(SleepStage.AWAKE) / total * 100

        # Sleep onset: time until first non-AWAKE epoch
        onset_min = 0.0
        for i, e in enumerate(self._epochs):
            if e.stage != SleepStage.AWAKE:
                onset_min = (e.timestamp - bed_time) / 60.0
                break

        sleep_efficiency = max(0, 100 - awake_pct)

        avg_hr = statistics.mean(e.heart_rate for e in self._epochs) if self._epochs else 0
        avg_br = statistics.mean(e.breathing_rate for e in self._epochs) if self._epochs else 0
        snore_min = self._snore_epochs * 0.5  # 30s epochs

        # Fragmentation index: transitions / total epochs
        transitions = sum(
            1 for i in range(1, len(stages)) if stages[i] != stages[i - 1]
        )
        frag_index = transitions / max(total, 1)

        # Quality score (0–100)
        quality = self._compute_quality_score(
            sleep_efficiency, deep_pct, rem_pct,
            self._bed_exit_count, self._apnea_events, frag_index, onset_min,
        )

        session = SleepSession(
            session_id=uuid.uuid4().hex[:12],
            resident_id=self.resident_id,
            date=date or time.strftime("%Y-%m-%d"),
            bed_time=bed_time,
            wake_time=wake_time,
            total_time_minutes=round(total_min, 1),
            sleep_onset_minutes=round(onset_min, 1),
            sleep_efficiency_pct=round(sleep_efficiency, 1),
            light_sleep_pct=round(light_pct, 1),
            deep_sleep_pct=round(deep_pct, 1),
            rem_sleep_pct=round(rem_pct, 1),
            awake_pct=round(awake_pct, 1),
            bed_exits=self._bed_exit_count,
            toss_turn_count=self._toss_turn_count,
            snore_minutes=round(snore_min, 1),
            apnea_events=self._apnea_events,
            average_heart_rate=round(avg_hr, 1),
            average_breathing_rate=round(avg_br, 1),
            sleep_quality_score=quality,
            fragmentation_index=round(frag_index, 3),
        )

        self._sessions.append(session)
        self._reset_night()
        return session

    # ── Trend analysis ────────────────────────────────────────

    def analyse_trends(self, last_n_days: int = 7) -> SleepTrend:
        """Analyse multi-night trends for drift detection."""
        recent = self._sessions[-last_n_days:] if self._sessions else []

        if len(recent) < 2:
            return SleepTrend(
                resident_id=self.resident_id,
                period_days=last_n_days,
                avg_quality_score=recent[0].sleep_quality_score if recent else 0,
                avg_total_sleep_min=recent[0].total_time_minutes if recent else 0,
                avg_deep_sleep_pct=recent[0].deep_sleep_pct if recent else 0,
                avg_bed_exits=recent[0].bed_exits if recent else 0,
                avg_apnea_events=recent[0].apnea_events if recent else 0,
                quality_trend="stable",
                drift_detected=False,
            )

        avg_quality = statistics.mean(s.sleep_quality_score for s in recent)
        avg_total = statistics.mean(s.total_time_minutes for s in recent)
        avg_deep = statistics.mean(s.deep_sleep_pct for s in recent)
        avg_exits = statistics.mean(s.bed_exits for s in recent)
        avg_apnea = statistics.mean(s.apnea_events for s in recent)

        # Trend: compare first half vs second half
        mid = len(recent) // 2
        first_half_q = statistics.mean(s.sleep_quality_score for s in recent[:mid])
        second_half_q = statistics.mean(s.sleep_quality_score for s in recent[mid:])

        diff = second_half_q - first_half_q
        if diff > 5:
            trend = "improving"
        elif diff < -5:
            trend = "declining"
        else:
            trend = "stable"

        # Drift detection
        drift = False
        drift_details = ""
        if avg_quality < 40:
            drift = True
            drift_details = f"Sleep quality critically low (avg {avg_quality:.0f}/100)"
        elif trend == "declining" and diff < -10:
            drift = True
            drift_details = f"Rapid sleep quality decline ({diff:+.1f} pts over {last_n_days} days)"
        elif avg_exits > 4:
            drift = True
            drift_details = f"Excessive bed exits (avg {avg_exits:.1f}/night) — fall risk"
        elif avg_apnea > 10:
            drift = True
            drift_details = f"High apnea frequency (avg {avg_apnea:.1f}/night)"

        return SleepTrend(
            resident_id=self.resident_id,
            period_days=last_n_days,
            avg_quality_score=round(avg_quality, 1),
            avg_total_sleep_min=round(avg_total, 1),
            avg_deep_sleep_pct=round(avg_deep, 1),
            avg_bed_exits=round(avg_exits, 1),
            avg_apnea_events=round(avg_apnea, 1),
            quality_trend=trend,
            drift_detected=drift,
            drift_details=drift_details,
        )

    # ── Event generation ──────────────────────────────────────

    def check_disruption_alert(self, session: SleepSession) -> Optional[AetherEvent]:
        """Generate an AetherEvent if sleep metrics breach thresholds."""
        reasons: List[str] = []
        severity = Severity.LOW

        if session.bed_exits >= 5:
            reasons.append(f"{session.bed_exits} bed exits (fall risk)")
            severity = Severity.HIGH
        elif session.bed_exits >= 3:
            reasons.append(f"{session.bed_exits} bed exits")
            severity = Severity.MEDIUM

        if session.apnea_events >= 15:
            reasons.append(f"{session.apnea_events} apnea events")
            severity = Severity.HIGH
        elif session.apnea_events >= 5:
            reasons.append(f"{session.apnea_events} apnea events")
            if severity.value not in ("critical", "high"):
                severity = Severity.MEDIUM

        if session.sleep_quality_score < 30:
            reasons.append(f"Very poor sleep quality ({session.sleep_quality_score}/100)")
            severity = Severity.HIGH
        elif session.sleep_quality_score < 50:
            reasons.append(f"Poor sleep quality ({session.sleep_quality_score}/100)")

        if session.sleep_efficiency_pct < 60:
            reasons.append(f"Low sleep efficiency ({session.sleep_efficiency_pct:.0f}%)")

        if not reasons:
            return None

        return AetherEvent(
            event_type=EventType.SLEEP_DISRUPTION,
            severity=severity,
            confidence=0.80,
            home_id="",
            data={
                "session": session.to_dict(),
                "reasons": reasons,
                "quality_score": session.sleep_quality_score,
                "bed_exits": session.bed_exits,
                "apnea_events": session.apnea_events,
            },
            sources=[
                SensorSource(
                    sensor_id="bedsense-001",
                    sensor_type="pressure_strip",
                    confidence=0.80,
                ),
            ],
            resident_id=self.resident_id,
        )

    # ── Simulate a full night ─────────────────────────────────

    def simulate_night(
        self,
        quality: str = "normal",
        duration_hours: float = 7.5,
        seed: int = 42,
    ) -> SleepSession:
        """Simulate a complete night of sleep data.

        Parameters
        ----------
        quality : str
            One of "good", "normal", "poor", "apnea", "restless".
        duration_hours : float
            Total time in bed.
        seed : int
            RNG seed for reproducibility.
        """
        import numpy as np
        rng = np.random.default_rng(seed)

        profiles = {
            "good": {"movement": 0.03, "bed_exits": 0, "apnea_rate": 0.0, "snore_rate": 0.05},
            "normal": {"movement": 0.08, "bed_exits": 1, "apnea_rate": 0.02, "snore_rate": 0.15},
            "poor": {"movement": 0.20, "bed_exits": 3, "apnea_rate": 0.05, "snore_rate": 0.3},
            "apnea": {"movement": 0.06, "bed_exits": 2, "apnea_rate": 0.15, "snore_rate": 0.5},
            "restless": {"movement": 0.30, "bed_exits": 5, "apnea_rate": 0.03, "snore_rate": 0.2},
        }
        p = profiles.get(quality, profiles["normal"])

        n_epochs = int(duration_hours * 120)  # 30s epochs
        t_start = time.time() - duration_hours * 3600

        for i in range(n_epochs):
            ts = t_start + i * 30
            # Circadian-like movement pattern
            phase = i / n_epochs
            circadian = 0.5 * (1 + math.cos(2 * math.pi * phase - math.pi))
            movement = max(0, rng.normal(p["movement"] * (0.5 + 0.5 * circadian), 0.03))

            occupied = True
            # Simulate bed exits
            if p["bed_exits"] > 0 and rng.random() < p["bed_exits"] / n_epochs * 3:
                occupied = False

            bed = BedSenseReading(
                timestamp=ts,
                bed_occupied=occupied,
                pressure_level=0.6 if occupied else 0.0,
                movement_intensity=float(movement),
                heart_rate_proxy=float(rng.normal(62, 4)),
                breathing_rate_proxy=float(rng.normal(14, 2)),
            )

            acoustic = SleepAcousticReading(
                timestamp=ts,
                snore_detected=bool(rng.random() < p["snore_rate"]),
                snore_intensity=float(rng.uniform(0.1, 0.6)) if rng.random() < p["snore_rate"] else 0.0,
                apnea_pause_s=float(rng.uniform(11, 25)) if rng.random() < p["apnea_rate"] else 0.0,
                cough_count=int(rng.poisson(0.1)),
                breathing_regularity=float(rng.uniform(0.7, 1.0)),
                ambient_noise_db=float(rng.normal(30, 5)),
            )

            self.classify_epoch(bed, acoustic)

        return self.generate_session()

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _compute_quality_score(
        efficiency: float, deep_pct: float, rem_pct: float,
        bed_exits: int, apnea_events: int, frag_index: float,
        onset_minutes: float,
    ) -> int:
        """Weighted quality score (0–100)."""
        score = 100.0
        # Efficiency penalty (ideal >85%)
        if efficiency < 85:
            score -= (85 - efficiency) * 0.8
        # Deep sleep bonus (ideal 15-25%)
        if deep_pct < 15:
            score -= (15 - deep_pct) * 0.5
        # REM (ideal 20-25%)
        if rem_pct < 15:
            score -= (15 - rem_pct) * 0.4
        # Bed exits
        score -= bed_exits * 5
        # Apnea events
        score -= apnea_events * 2
        # Fragmentation
        score -= frag_index * 30
        # Onset (ideal <15 min)
        if onset_minutes > 30:
            score -= (onset_minutes - 30) * 0.3
        return max(0, min(100, int(round(score))))

    def _reset_night(self) -> None:
        """Reset per-night counters for the next session."""
        self._epochs.clear()
        self._bed_exit_count = 0
        self._toss_turn_count = 0
        self._snore_epochs = 0
        self._apnea_events = 0
        self._bed_occupied = False
        self._bed_enter_time = None
        self._last_occupied_time = None

    @property
    def sessions(self) -> List[SleepSession]:
        return list(self._sessions)
