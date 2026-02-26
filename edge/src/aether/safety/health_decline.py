"""
Health Decline Detection Engine

Tracks health metrics over time to detect gradual decline:
  • Personalised baseline establishment (7-day rolling window)
  • Drift detection via z-score comparison against baseline
  • Severity classification: normal, concerning, declining, critical
  • Trend analysis: improving, stable, declining
  • Gait degradation tracking (stride length, sway, asymmetry)
  • Generate decline alerts with affected domains

Designed to run on-edge with no cloud dependency.
"""
from __future__ import annotations

import logging
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
    SensorType,
)

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────

class DriftSeverity(str, Enum):
    NORMAL = "normal"
    CONCERNING = "concerning"
    DECLINING = "declining"
    CRITICAL = "critical"


class Trend(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


# ── Metric names tracked by the engine ────────────────────────

TRACKED_METRICS = [
    "mobility_score",
    "sleep_quality",
    "hydration_level",
    "meal_regularity",
    "medication_adherence",
    "social_interaction",
    "cognitive_score",
    "mood_score",
    "respiratory_health",
]


# ── Data classes ──────────────────────────────────────────────

@dataclass
class MetricSnapshot:
    """A single metric observation."""
    metric: str
    value: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class BaselineStats:
    """Rolling-window baseline statistics for a single metric."""
    metric: str
    mean: float
    std: float
    sample_count: int
    window_start: float
    window_end: float


@dataclass
class DriftResult:
    """Result of comparing a current value against its baseline."""
    metric: str
    current_value: float
    baseline_mean: float
    baseline_std: float
    z_score: float
    severity: DriftSeverity
    trend: Trend
    timestamp: float = field(default_factory=time.time)


@dataclass
class GaitSnapshot:
    """A single gait-analysis observation."""
    timestamp: float
    stride_length_cm: float
    sway_degrees: float
    asymmetry_pct: float  # 0 = symmetric, 100 = fully asymmetric

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


@dataclass
class GaitDegradationResult:
    """Result of comparing current gait against baseline."""
    current: GaitSnapshot
    baseline_stride: float
    baseline_sway: float
    baseline_asymmetry: float
    stride_z: float
    sway_z: float
    asymmetry_z: float
    severity: DriftSeverity
    timestamp: float = field(default_factory=time.time)


@dataclass
class DeclineAlert:
    """An alert generated when health decline is detected."""
    alert_id: str
    resident_id: str
    severity: DriftSeverity
    affected_domains: list[str]
    drift_results: list[DriftResult]
    summary: str
    timestamp: float = field(default_factory=time.time)


# ── Z-score → severity mapping ───────────────────────────────

_SEVERITY_THRESHOLDS = [
    (3.0, DriftSeverity.CRITICAL),
    (2.0, DriftSeverity.DECLINING),
    (1.5, DriftSeverity.CONCERNING),
]


def _z_to_severity(z: float) -> DriftSeverity:
    """Map an absolute z-score to a severity level."""
    abs_z = abs(z)
    for threshold, sev in _SEVERITY_THRESHOLDS:
        if abs_z >= threshold:
            return sev
    return DriftSeverity.NORMAL


# ── Engine ────────────────────────────────────────────────────

class HealthDeclineDetector:
    """Track health metrics over time and detect gradual decline.

    Parameters
    ----------
    resident_id : str
        Resident being monitored.
    baseline_window_days : int
        Number of days for the rolling baseline window (default 7).
    """

    BASELINE_WINDOW_S: float  # set in __init__

    def __init__(
        self,
        resident_id: str = "resident-001",
        baseline_window_days: int = 7,
        seed: int = 42,
    ):
        self.resident_id = resident_id
        self.BASELINE_WINDOW_S = baseline_window_days * 86400
        self.rng = np.random.default_rng(seed)

        # Per-metric history (bounded deque)
        self._history: dict[str, deque[MetricSnapshot]] = {
            m: deque(maxlen=2000) for m in TRACKED_METRICS
        }

        # Gait history
        self._gait_history: deque[GaitSnapshot] = deque(maxlen=500)

    # ── Baseline computation ──────────────────────────────────

    def _compute_baseline(self, metric: str) -> Optional[BaselineStats]:
        """Compute mean/std from the rolling window for *metric*."""
        now = time.time()
        cutoff = now - self.BASELINE_WINDOW_S
        values = [s.value for s in self._history[metric] if s.timestamp >= cutoff]
        if len(values) < 3:
            return None
        return BaselineStats(
            metric=metric,
            mean=float(np.mean(values)),
            std=float(np.std(values)) or 0.01,  # avoid division by zero
            sample_count=len(values),
            window_start=cutoff,
            window_end=now,
        )

    # ── Trend estimation ──────────────────────────────────────

    def _estimate_trend(self, metric: str, window_n: int = 10) -> Trend:
        """Simple linear-regression slope on the last *window_n* observations."""
        history = list(self._history[metric])
        if len(history) < window_n:
            return Trend.STABLE
        recent = history[-window_n:]
        x = np.arange(len(recent), dtype=float)
        y = np.array([s.value for s in recent])
        slope = float(np.polyfit(x, y, 1)[0])
        if slope > 0.02:
            return Trend.IMPROVING
        if slope < -0.02:
            return Trend.DECLINING
        return Trend.STABLE

    # ── Public API ────────────────────────────────────────────

    def record(self, metric: str, value: float, timestamp: float | None = None) -> None:
        """Record a metric observation.

        Parameters
        ----------
        metric : str
            Must be one of ``TRACKED_METRICS``.
        value : float
            Observed value (typically 0.0–1.0 normalised).
        timestamp : float, optional
            Unix epoch; defaults to now.
        """
        if metric not in self._history:
            logger.warning("Unknown metric '%s' — ignored", metric)
            return
        ts = timestamp or time.time()
        self._history[metric].append(MetricSnapshot(metric=metric, value=value, timestamp=ts))

    def record_gait(self, snapshot: GaitSnapshot) -> None:
        """Record a gait-analysis observation."""
        self._gait_history.append(snapshot)

    def detect_drift(self, metric: str, current_value: float) -> Optional[DriftResult]:
        """Compare *current_value* against the rolling baseline for *metric*.

        Returns
        -------
        DriftResult or None
            ``None`` if insufficient baseline data.
        """
        baseline = self._compute_baseline(metric)
        if baseline is None:
            return None
        z = (current_value - baseline.mean) / baseline.std
        severity = _z_to_severity(z)
        trend = self._estimate_trend(metric)

        return DriftResult(
            metric=metric,
            current_value=current_value,
            baseline_mean=round(baseline.mean, 3),
            baseline_std=round(baseline.std, 3),
            z_score=round(z, 2),
            severity=severity,
            trend=trend,
        )

    def detect_gait_degradation(self, current: GaitSnapshot) -> Optional[GaitDegradationResult]:
        """Compare current gait snapshot against baseline.

        Returns
        -------
        GaitDegradationResult or None
            ``None`` if insufficient gait history.
        """
        if len(self._gait_history) < 5:
            return None
        strides = [g.stride_length_cm for g in self._gait_history]
        sways = [g.sway_degrees for g in self._gait_history]
        asyms = [g.asymmetry_pct for g in self._gait_history]

        mean_stride, std_stride = float(np.mean(strides)), max(float(np.std(strides)), 0.01)
        mean_sway, std_sway = float(np.mean(sways)), max(float(np.std(sways)), 0.01)
        mean_asym, std_asym = float(np.mean(asyms)), max(float(np.std(asyms)), 0.01)

        sz = (current.stride_length_cm - mean_stride) / std_stride
        swz = (current.sway_degrees - mean_sway) / std_sway
        az = (current.asymmetry_pct - mean_asym) / std_asym

        worst_z = max(abs(sz), abs(swz), abs(az))
        severity = _z_to_severity(worst_z)

        return GaitDegradationResult(
            current=current,
            baseline_stride=round(mean_stride, 1),
            baseline_sway=round(mean_sway, 1),
            baseline_asymmetry=round(mean_asym, 1),
            stride_z=round(sz, 2),
            sway_z=round(swz, 2),
            asymmetry_z=round(az, 2),
            severity=severity,
        )

    def run_full_assessment(self) -> DeclineAlert | None:
        """Run drift detection on all tracked metrics and generate an alert
        if any metric is at *concerning* or worse.

        Returns
        -------
        DeclineAlert or None
        """
        drift_results: list[DriftResult] = []
        affected: list[str] = []

        for metric in TRACKED_METRICS:
            history = list(self._history[metric])
            if not history:
                continue
            latest = history[-1].value
            result = self.detect_drift(metric, latest)
            if result and result.severity != DriftSeverity.NORMAL:
                drift_results.append(result)
                affected.append(metric)

        if not drift_results:
            return None

        worst = max(drift_results, key=lambda r: abs(r.z_score))
        severity = worst.severity

        summary_parts = [
            f"{r.metric}: z={r.z_score:+.1f} ({r.severity.value}, {r.trend.value})"
            for r in drift_results
        ]
        summary = f"Health decline detected in {len(affected)} domain(s): " + "; ".join(summary_parts)

        return DeclineAlert(
            alert_id=str(uuid.uuid4()),
            resident_id=self.resident_id,
            severity=severity,
            affected_domains=affected,
            drift_results=drift_results,
            summary=summary,
        )

    def to_aether_event(self, alert: DeclineAlert) -> AetherEvent:
        """Convert a DeclineAlert into a canonical AetherEvent."""
        severity_map = {
            DriftSeverity.CONCERNING: Severity.LOW,
            DriftSeverity.DECLINING: Severity.MEDIUM,
            DriftSeverity.CRITICAL: Severity.HIGH,
        }
        return AetherEvent(
            event_type=EventType.DECLINING_HEALTH,
            severity=severity_map.get(alert.severity, Severity.LOW),
            confidence=min(1.0, max(abs(r.z_score) for r in alert.drift_results) / 4),
            home_id="home-001",
            resident_id=alert.resident_id,
            data={
                "alert_id": alert.alert_id,
                "affected_domains": alert.affected_domains,
                "summary": alert.summary,
                "drift_details": [
                    {
                        "metric": r.metric,
                        "z_score": r.z_score,
                        "severity": r.severity.value,
                        "trend": r.trend.value,
                        "current": r.current_value,
                        "baseline_mean": r.baseline_mean,
                    }
                    for r in alert.drift_results
                ],
            },
            sources=[SensorSource(
                sensor_id="health-decline-engine",
                sensor_type="analytics",
                confidence=min(1.0, max(abs(r.z_score) for r in alert.drift_results) / 4),
            )],
        )

    # ── Simulation helpers ────────────────────────────────────

    def seed_baseline(self, days: int = 7, readings_per_day: int = 24) -> None:
        """Populate baseline history with simulated healthy data.

        All metrics are seeded with values centred around 0.7–0.9 (healthy).
        """
        now = time.time()
        for metric in TRACKED_METRICS:
            base = self.rng.uniform(0.7, 0.9)
            for d in range(days):
                for r in range(readings_per_day):
                    ts = now - (days - d) * 86400 + r * 3600
                    val = float(np.clip(self.rng.normal(base, 0.05), 0.0, 1.0))
                    self.record(metric, val, timestamp=ts)

    def simulate_decline(
        self,
        metric: str,
        drop_per_day: float = 0.05,
        days: int = 7,
        readings_per_day: int = 24,
    ) -> None:
        """Inject a gradual decline into *metric* over *days*.

        Parameters
        ----------
        metric : str
            Metric to degrade.
        drop_per_day : float
            Daily value drop (default 0.05).
        days : int
            Number of days of decline (default 7).
        readings_per_day : int
            Observations per day.
        """
        now = time.time()
        history = list(self._history[metric])
        base = history[-1].value if history else 0.8
        for d in range(days):
            for r in range(readings_per_day):
                ts = now + d * 86400 + r * 3600
                val = float(np.clip(base - d * drop_per_day + self.rng.normal(0, 0.02), 0.0, 1.0))
                self.record(metric, val, timestamp=ts)
