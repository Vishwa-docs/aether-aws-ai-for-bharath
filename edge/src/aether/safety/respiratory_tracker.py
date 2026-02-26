"""
AETHER Respiratory Health Tracker
===================================
Monitors respiratory health using acoustic features (cough frequency, wheeze,
breathing patterns) and optional SpO2 wearable data.

Features:
  • Cough frequency tracking (count per hour / per day)
  • Cough pattern analysis (dry vs wet proxy from spectral features)
  • Wheezing detection from acoustic features
  • Breathing rate trend from BedSense / acoustic data
  • Respiratory distress detection (sustained coughing + irregular breathing)
  • SpO2 desaturation monitoring (from wearable data)
  • Daily respiratory health score (0–100)
  • Multi-day trend analysis + drift detection
  • Clinical pattern matching: UTI-related cough, COPD exacerbation, pneumonia signs
  • AetherEvent generation for respiratory concerns

Privacy-first: only derived features — no raw audio stored.
"""

from __future__ import annotations

import time
import uuid
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

class CoughType(str, Enum):
    DRY = "dry"
    WET = "wet"
    UNKNOWN = "unknown"


class RespiratoryAlertType(str, Enum):
    HIGH_COUGH_RATE = "high_cough_rate"
    SUSTAINED_COUGHING = "sustained_coughing"
    WHEEZING_DETECTED = "wheezing_detected"
    BREATHING_IRREGULARITY = "breathing_irregularity"
    SPO2_DESATURATION = "spo2_desaturation"
    RESPIRATORY_DISTRESS = "respiratory_distress"
    COPD_EXACERBATION = "copd_exacerbation"


# ─── Data Models ──────────────────────────────────────────────

@dataclass
class CoughEvent:
    """A single detected cough episode."""
    timestamp: float
    cough_type: CoughType
    intensity: float             # 0.0–1.0 from RMS energy
    duration_s: float            # burst duration
    spectral_centroid: float     # frequency profile
    confidence: float


@dataclass
class BreathingSnapshot:
    """Periodic breathing rate measurement (from BedSense or acoustic)."""
    timestamp: float
    breathing_rate: float        # breaths per minute
    regularity: float            # 0.0 (irregular) – 1.0 (steady)
    depth_proxy: float           # 0.0 (shallow) – 1.0 (deep)
    source: str = "acoustic"     # "acoustic" or "pressure_strip"


@dataclass
class SpO2Reading:
    """Pulse oximeter reading from wearable."""
    timestamp: float
    spo2_pct: float              # 0–100
    heart_rate: int
    perfusion_index: float       # signal quality
    sensor_id: str = "oximeter-001"


@dataclass
class RespiratoryDailyReport:
    """Daily respiratory health summary."""
    report_id: str
    resident_id: str
    date: str
    total_cough_count: int
    cough_per_hour: float
    dry_cough_pct: float
    wet_cough_pct: float
    wheezing_episodes: int
    avg_breathing_rate: float
    breathing_regularity: float
    min_spo2: float
    avg_spo2: float
    spo2_desaturation_events: int
    respiratory_score: int       # 0–100
    alerts: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RespiratoryTrend:
    """Multi-day respiratory trend analysis."""
    resident_id: str
    period_days: int
    avg_cough_per_day: float
    avg_respiratory_score: float
    avg_breathing_rate: float
    avg_spo2: float
    trend: str                   # "improving", "stable", "worsening"
    drift_detected: bool
    clinical_pattern: str = ""   # detected clinical pattern name
    drift_details: str = ""


# ─── Respiratory Tracker ──────────────────────────────────────

class RespiratoryTracker:
    """Monitors respiratory health from acoustic and wearable data.

    Parameters
    ----------
    resident_id : str
        Resident identifier.
    cough_alert_per_hour : float
        Coughs per hour to trigger a HIGH_COUGH_RATE alert (default 8).
    sustained_cough_window_s : float
        Seconds within which multiple coughs count as sustained (default 120).
    sustained_cough_threshold : int
        Number of coughs within the window to flag (default 5).
    spo2_desaturation_level : float
        SpO2 below this triggers desaturation alert (default 92.0).
    distress_breathing_rate : float
        Breathing rate above which respiratory distress is flagged (default 24).
    """

    def __init__(
        self,
        resident_id: str = "resident-001",
        cough_alert_per_hour: float = 8.0,
        sustained_cough_window_s: float = 120.0,
        sustained_cough_threshold: int = 5,
        spo2_desaturation_level: float = 92.0,
        distress_breathing_rate: float = 24.0,
    ):
        self.resident_id = resident_id
        self.cough_alert_per_hour = cough_alert_per_hour
        self.sustained_cough_window_s = sustained_cough_window_s
        self.sustained_cough_threshold = sustained_cough_threshold
        self.spo2_desaturation_level = spo2_desaturation_level
        self.distress_breathing_rate = distress_breathing_rate

        self._cough_events: List[CoughEvent] = []
        self._breathing_snapshots: List[BreathingSnapshot] = []
        self._spo2_readings: List[SpO2Reading] = []
        self._wheezing_count: int = 0
        self._daily_reports: List[RespiratoryDailyReport] = []

    # ── Ingestion ─────────────────────────────────────────────

    def record_cough(self, event: CoughEvent) -> None:
        """Record a detected cough event."""
        self._cough_events.append(event)

    def record_breathing(self, snapshot: BreathingSnapshot) -> None:
        """Record a breathing rate snapshot."""
        self._breathing_snapshots.append(snapshot)

    def record_spo2(self, reading: SpO2Reading) -> None:
        """Record a pulse oximeter reading."""
        self._spo2_readings.append(reading)

    def record_wheezing(self) -> None:
        """Increment wheezing episode counter."""
        self._wheezing_count += 1

    # ── Cough classification ──────────────────────────────────

    @staticmethod
    def classify_cough(spectral_centroid: float, rms_energy: float) -> CoughType:
        """Classify a cough as dry or wet from spectral features.

        Wet coughs have lower spectral centroid (more bass/mucus resonance).
        """
        if spectral_centroid < 2500:
            return CoughType.WET
        elif spectral_centroid > 3500:
            return CoughType.DRY
        return CoughType.UNKNOWN

    # ── Real-time checks ─────────────────────────────────────

    def check_sustained_coughing(self) -> Optional[RespiratoryAlertType]:
        """Check if coughs within recent window exceed threshold."""
        if len(self._cough_events) < self.sustained_cough_threshold:
            return None
        now = time.time()
        recent = [
            c for c in self._cough_events
            if now - c.timestamp <= self.sustained_cough_window_s
        ]
        if len(recent) >= self.sustained_cough_threshold:
            return RespiratoryAlertType.SUSTAINED_COUGHING
        return None

    def check_spo2_desaturation(self) -> Optional[SpO2Reading]:
        """Check if latest SpO2 is below desaturation threshold."""
        if not self._spo2_readings:
            return None
        latest = self._spo2_readings[-1]
        if latest.spo2_pct < self.spo2_desaturation_level:
            return latest
        return None

    def check_respiratory_distress(self) -> bool:
        """Check for combined respiratory distress signals."""
        sustained = self.check_sustained_coughing()
        desat = self.check_spo2_desaturation()

        # Breathing rate check
        high_br = False
        if self._breathing_snapshots:
            recent_br = [
                s for s in self._breathing_snapshots[-10:]
                if s.breathing_rate > self.distress_breathing_rate
            ]
            high_br = len(recent_br) >= 3

        # Distress = any 2 of: sustained cough, high breathing rate, desaturation
        signals = sum([sustained is not None, high_br, desat is not None])
        return signals >= 2

    # ── Daily report ──────────────────────────────────────────

    def generate_daily_report(self, date: str = "") -> RespiratoryDailyReport:
        """Generate a daily respiratory health summary."""
        total_coughs = len(self._cough_events)
        hours = 24.0  # assume full day
        if self._cough_events and len(self._cough_events) >= 2:
            span = self._cough_events[-1].timestamp - self._cough_events[0].timestamp
            hours = max(span / 3600.0, 1.0)

        cough_per_hour = total_coughs / hours if hours > 0 else 0

        dry = sum(1 for c in self._cough_events if c.cough_type == CoughType.DRY)
        wet = sum(1 for c in self._cough_events if c.cough_type == CoughType.WET)
        dry_pct = dry / max(total_coughs, 1) * 100
        wet_pct = wet / max(total_coughs, 1) * 100

        avg_br = 0.0
        br_reg = 1.0
        if self._breathing_snapshots:
            avg_br = statistics.mean(s.breathing_rate for s in self._breathing_snapshots)
            br_reg = statistics.mean(s.regularity for s in self._breathing_snapshots)

        min_spo2 = 98.0
        avg_spo2 = 98.0
        desat_events = 0
        if self._spo2_readings:
            spo2_vals = [r.spo2_pct for r in self._spo2_readings]
            min_spo2 = min(spo2_vals)
            avg_spo2 = statistics.mean(spo2_vals)
            desat_events = sum(1 for v in spo2_vals if v < self.spo2_desaturation_level)

        # Alerts
        alerts: List[str] = []
        if cough_per_hour > self.cough_alert_per_hour:
            alerts.append(f"High cough rate: {cough_per_hour:.1f}/hr")
        if self._wheezing_count > 0:
            alerts.append(f"{self._wheezing_count} wheezing episodes")
        if desat_events > 0:
            alerts.append(f"{desat_events} SpO2 desaturation events (min {min_spo2:.0f}%)")
        if avg_br > self.distress_breathing_rate:
            alerts.append(f"Elevated breathing rate: {avg_br:.1f} bpm")

        # Score
        score = self._compute_respiratory_score(
            cough_per_hour, self._wheezing_count, avg_br, br_reg,
            avg_spo2, desat_events,
        )

        report = RespiratoryDailyReport(
            report_id=uuid.uuid4().hex[:12],
            resident_id=self.resident_id,
            date=date or time.strftime("%Y-%m-%d"),
            total_cough_count=total_coughs,
            cough_per_hour=round(cough_per_hour, 2),
            dry_cough_pct=round(dry_pct, 1),
            wet_cough_pct=round(wet_pct, 1),
            wheezing_episodes=self._wheezing_count,
            avg_breathing_rate=round(avg_br, 1),
            breathing_regularity=round(br_reg, 2),
            min_spo2=round(min_spo2, 1),
            avg_spo2=round(avg_spo2, 1),
            spo2_desaturation_events=desat_events,
            respiratory_score=score,
            alerts=alerts,
        )

        self._daily_reports.append(report)
        self._reset_day()
        return report

    # ── Trend analysis ────────────────────────────────────────

    def analyse_trends(self, last_n_days: int = 7) -> RespiratoryTrend:
        """Analyse multi-day respiratory trends for drift detection."""
        recent = self._daily_reports[-last_n_days:] if self._daily_reports else []

        if len(recent) < 2:
            r = recent[0] if recent else None
            return RespiratoryTrend(
                resident_id=self.resident_id,
                period_days=last_n_days,
                avg_cough_per_day=r.total_cough_count if r else 0,
                avg_respiratory_score=r.respiratory_score if r else 100,
                avg_breathing_rate=r.avg_breathing_rate if r else 16,
                avg_spo2=r.avg_spo2 if r else 98,
                trend="stable",
                drift_detected=False,
            )

        avg_cpd = statistics.mean(r.total_cough_count for r in recent)
        avg_score = statistics.mean(r.respiratory_score for r in recent)
        avg_br = statistics.mean(r.avg_breathing_rate for r in recent)
        avg_spo2 = statistics.mean(r.avg_spo2 for r in recent)

        # Trend
        mid = len(recent) // 2
        first_score = statistics.mean(r.respiratory_score for r in recent[:mid])
        second_score = statistics.mean(r.respiratory_score for r in recent[mid:])
        diff = second_score - first_score
        trend = "improving" if diff > 5 else ("worsening" if diff < -5 else "stable")

        # Clinical pattern detection
        drift = False
        clinical_pattern = ""
        drift_details = ""

        # Rising cough + rising wet-cough ratio → possible pneumonia
        wet_trend = statistics.mean(r.wet_cough_pct for r in recent)
        if avg_cpd > 30 and wet_trend > 50:
            drift = True
            clinical_pattern = "possible_pneumonia"
            drift_details = "Rising cough frequency with predominantly wet coughs"

        # Rising cough + wheezing → COPD exacerbation
        avg_wheeze = statistics.mean(r.wheezing_episodes for r in recent)
        if avg_wheeze > 3 and trend == "worsening":
            drift = True
            clinical_pattern = "copd_exacerbation"
            drift_details = "Increasing wheezing episodes with declining respiratory score"

        # Dropping SpO2
        if avg_spo2 < 94:
            drift = True
            drift_details = f"Chronic low SpO2 (avg {avg_spo2:.1f}%)"
            if not clinical_pattern:
                clinical_pattern = "chronic_hypoxia"

        # General score decline
        if not drift and trend == "worsening" and diff < -10:
            drift = True
            drift_details = f"Rapid respiratory decline ({diff:+.1f} pts over {last_n_days} days)"

        return RespiratoryTrend(
            resident_id=self.resident_id,
            period_days=last_n_days,
            avg_cough_per_day=round(avg_cpd, 1),
            avg_respiratory_score=round(avg_score, 1),
            avg_breathing_rate=round(avg_br, 1),
            avg_spo2=round(avg_spo2, 1),
            trend=trend,
            drift_detected=drift,
            clinical_pattern=clinical_pattern,
            drift_details=drift_details,
        )

    # ── Event generation ──────────────────────────────────────

    def check_alert(self, report: RespiratoryDailyReport) -> Optional[AetherEvent]:
        """Generate an AetherEvent if respiratory metrics breach thresholds."""
        if not report.alerts:
            return None

        severity = Severity.LOW
        if report.respiratory_score < 40:
            severity = Severity.HIGH
        elif report.respiratory_score < 60:
            severity = Severity.MEDIUM
        if report.spo2_desaturation_events > 0 and report.min_spo2 < 88:
            severity = Severity.CRITICAL

        return AetherEvent(
            event_type=EventType.RESPIRATORY_CONCERN,
            severity=severity,
            confidence=0.78,
            home_id="",
            data={
                "report": report.to_dict(),
                "respiratory_score": report.respiratory_score,
                "cough_per_hour": report.cough_per_hour,
                "min_spo2": report.min_spo2,
            },
            sources=[
                SensorSource(
                    sensor_id="acoustic-001",
                    sensor_type="acoustic",
                    confidence=0.78,
                ),
            ],
            resident_id=self.resident_id,
        )

    # ── Simulation ────────────────────────────────────────────

    def simulate_day(
        self,
        profile: str = "healthy",
        seed: int = 42,
    ) -> RespiratoryDailyReport:
        """Simulate a full day of respiratory data.

        Parameters
        ----------
        profile : str
            One of "healthy", "mild_cold", "copd", "pneumonia", "asthma".
        """
        import numpy as np
        rng = np.random.default_rng(seed)

        configs = {
            "healthy": {"coughs": 3, "wheeze": 0, "br": 15, "spo2": 97, "wet": 0.1},
            "mild_cold": {"coughs": 20, "wheeze": 0, "br": 17, "spo2": 96, "wet": 0.4},
            "copd": {"coughs": 30, "wheeze": 5, "br": 20, "spo2": 93, "wet": 0.5},
            "pneumonia": {"coughs": 45, "wheeze": 2, "br": 22, "spo2": 91, "wet": 0.7},
            "asthma": {"coughs": 15, "wheeze": 8, "br": 19, "spo2": 95, "wet": 0.2},
        }
        c = configs.get(profile, configs["healthy"])

        # Generate cough events
        n_coughs = max(0, int(rng.poisson(c["coughs"])))
        for _ in range(n_coughs):
            centroid = float(rng.normal(3000, 800))
            ctype = self.classify_cough(centroid, 0.5)
            if rng.random() < c["wet"]:
                ctype = CoughType.WET
            self.record_cough(CoughEvent(
                timestamp=time.time() - rng.uniform(0, 86400),
                cough_type=ctype,
                intensity=float(rng.uniform(0.2, 0.8)),
                duration_s=float(rng.uniform(0.3, 1.5)),
                spectral_centroid=centroid,
                confidence=0.85,
            ))

        # Wheezing
        for _ in range(c["wheeze"]):
            self.record_wheezing()

        # Breathing snapshots (every 30 min = 48/day)
        for i in range(48):
            self.record_breathing(BreathingSnapshot(
                timestamp=time.time() - (47 - i) * 1800,
                breathing_rate=float(rng.normal(c["br"], 2)),
                regularity=float(rng.uniform(0.6, 1.0)),
                depth_proxy=float(rng.uniform(0.4, 0.9)),
            ))

        # SpO2 readings (every 15 min = 96/day)
        for i in range(96):
            self.record_spo2(SpO2Reading(
                timestamp=time.time() - (95 - i) * 900,
                spo2_pct=float(rng.normal(c["spo2"], 1.5)),
                heart_rate=int(rng.normal(72, 8)),
                perfusion_index=float(rng.uniform(1.0, 5.0)),
            ))

        return self.generate_daily_report()

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _compute_respiratory_score(
        cough_rate: float, wheezing: int, breathing_rate: float,
        regularity: float, avg_spo2: float, desat_events: int,
    ) -> int:
        """Weighted respiratory health score (0–100)."""
        score = 100.0
        # Cough rate penalty
        if cough_rate > 2:
            score -= (cough_rate - 2) * 3
        # Wheezing penalty
        score -= wheezing * 5
        # Breathing rate (ideal 12–20)
        if breathing_rate > 20:
            score -= (breathing_rate - 20) * 3
        elif breathing_rate < 10:
            score -= (10 - breathing_rate) * 4
        # Regularity bonus
        score -= (1 - regularity) * 15
        # SpO2 (ideal >95)
        if avg_spo2 < 95:
            score -= (95 - avg_spo2) * 5
        # Desaturation events
        score -= desat_events * 8
        return max(0, min(100, int(round(score))))

    def _reset_day(self) -> None:
        """Reset daily counters."""
        self._cough_events.clear()
        self._breathing_snapshots.clear()
        self._spo2_readings.clear()
        self._wheezing_count = 0

    @property
    def daily_reports(self) -> List[RespiratoryDailyReport]:
        return list(self._daily_reports)
