"""
Cognitive Decline & Dementia Detection Tracker

Monitors cognitive health through multiple signals:
  • Conversation coherence over time (from check-in dialogues)
  • Response time tracking (slowdown detection)
  • Repetition detection (asking the same questions)
  • Word-finding difficulty scoring
  • Time/place disorientation detection
  • Task completion rate tracking (medication, daily routines)
  • Mini-Cog style scoring (simulated)
  • MMSE approximation score
  • Cognitive health reports with trend

All analysis runs on-edge with simulated data — no clinical instruments required.
"""
from __future__ import annotations

import logging
import time
import uuid
from collections import Counter, deque
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

class CognitiveLevel(str, Enum):
    NORMAL = "normal"
    MILD_CONCERN = "mild_concern"
    MODERATE_CONCERN = "moderate_concern"
    SEVERE_CONCERN = "severe_concern"


class CognitiveTrend(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


# ── Data classes ──────────────────────────────────────────────

@dataclass
class ConversationObservation:
    """A single check-in conversation observation."""
    timestamp: float
    coherence_score: float       # 0.0–1.0
    response_time_s: float       # mean response latency
    repetition_count: int        # repeated phrases/questions detected
    word_finding_score: float    # 0.0 (severe difficulty) – 1.0 (fluent)
    disorientation_detected: bool
    transcript_snippet: str = ""


@dataclass
class TaskCompletionRecord:
    """Record of a daily-task completion or failure."""
    timestamp: float
    task_type: str               # e.g. "medication", "meal_prep", "morning_routine"
    completed: bool
    time_taken_s: float = 0.0


@dataclass
class MiniCogResult:
    """Simulated Mini-Cog equivalent (0–5 scale)."""
    timestamp: float
    word_recall_score: int        # 0–3 (3 words recalled)
    clock_drawing_score: int      # 0–2 (normal=2)
    total_score: int              # 0–5

    @property
    def concern_level(self) -> CognitiveLevel:
        if self.total_score >= 4:
            return CognitiveLevel.NORMAL
        if self.total_score == 3:
            return CognitiveLevel.MILD_CONCERN
        if self.total_score == 2:
            return CognitiveLevel.MODERATE_CONCERN
        return CognitiveLevel.SEVERE_CONCERN


@dataclass
class MMSEApproximation:
    """Approximated MMSE score derived from check-in data (0–30 scale)."""
    timestamp: float
    orientation_score: float     # 0–10
    attention_score: float       # 0–5
    recall_score: float          # 0–3
    language_score: float        # 0–9
    visuospatial_score: float    # 0–3
    total_score: float           # 0–30

    @property
    def concern_level(self) -> CognitiveLevel:
        if self.total_score >= 24:
            return CognitiveLevel.NORMAL
        if self.total_score >= 19:
            return CognitiveLevel.MILD_CONCERN
        if self.total_score >= 10:
            return CognitiveLevel.MODERATE_CONCERN
        return CognitiveLevel.SEVERE_CONCERN


@dataclass
class CognitiveHealthReport:
    """Comprehensive cognitive health report."""
    report_id: str
    resident_id: str
    timestamp: float
    overall_level: CognitiveLevel
    trend: CognitiveTrend
    coherence_avg: float
    response_time_avg: float
    repetition_rate: float
    word_finding_avg: float
    disorientation_rate: float
    task_completion_rate: float
    mini_cog: Optional[MiniCogResult] = None
    mmse: Optional[MMSEApproximation] = None
    notes: list[str] = field(default_factory=list)


# ── Thresholds ────────────────────────────────────────────────

COHERENCE_CONCERN_THRESHOLD = 0.55
RESPONSE_TIME_CONCERN_S = 8.0
REPETITION_CONCERN_COUNT = 3
WORD_FINDING_CONCERN = 0.50
DISORIENTATION_CONCERN_RATE = 0.20
TASK_COMPLETION_CONCERN_RATE = 0.70


# ── Engine ────────────────────────────────────────────────────

class CognitiveTracker:
    """Track cognitive health signals and detect decline over time.

    Parameters
    ----------
    resident_id : str
        Resident being monitored.
    history_days : int
        Number of days of history to retain (default 90).
    """

    def __init__(
        self,
        resident_id: str = "resident-001",
        history_days: int = 90,
        seed: int = 42,
    ):
        self.resident_id = resident_id
        self._history_window_s = history_days * 86400
        self.rng = np.random.default_rng(seed)

        self._observations: deque[ConversationObservation] = deque(maxlen=5000)
        self._task_records: deque[TaskCompletionRecord] = deque(maxlen=5000)
        self._phrase_counter: Counter[str] = Counter()
        self._mini_cog_history: deque[MiniCogResult] = deque(maxlen=200)
        self._mmse_history: deque[MMSEApproximation] = deque(maxlen=200)

    # ── Recording ─────────────────────────────────────────────

    def record_observation(self, obs: ConversationObservation) -> None:
        """Record a check-in conversation observation."""
        self._observations.append(obs)
        if obs.transcript_snippet:
            self._phrase_counter[obs.transcript_snippet] += 1

    def record_task(self, record: TaskCompletionRecord) -> None:
        """Record a daily-task completion or failure."""
        self._task_records.append(record)

    # ── Repetition detection ──────────────────────────────────

    def detect_repetitions(self, window_n: int = 20) -> dict[str, int]:
        """Return phrases repeated more than once in the last *window_n* observations."""
        recent = list(self._observations)[-window_n:]
        counter: Counter[str] = Counter()
        for obs in recent:
            if obs.transcript_snippet:
                counter[obs.transcript_snippet] += 1
        return {phrase: count for phrase, count in counter.items() if count > 1}

    # ── Mini-Cog simulation ───────────────────────────────────

    def simulate_mini_cog(self, base_score: int | None = None) -> MiniCogResult:
        """Generate a simulated Mini-Cog result.

        Parameters
        ----------
        base_score : int, optional
            Target total score (0–5).  If not provided, derived from
            recent coherence data.
        """
        if base_score is not None:
            total = int(np.clip(base_score, 0, 5))
        else:
            recent = list(self._observations)[-30:]
            if recent:
                avg_coherence = float(np.mean([o.coherence_score for o in recent]))
                total = int(np.clip(round(avg_coherence * 5), 0, 5))
            else:
                total = 5

        word_recall = min(3, max(0, total - int(self.rng.integers(0, 2))))
        clock = total - word_recall

        result = MiniCogResult(
            timestamp=time.time(),
            word_recall_score=word_recall,
            clock_drawing_score=min(2, clock),
            total_score=word_recall + min(2, clock),
        )
        self._mini_cog_history.append(result)
        return result

    # ── MMSE approximation ────────────────────────────────────

    def approximate_mmse(self) -> MMSEApproximation:
        """Approximate an MMSE score from accumulated check-in signals.

        The approximation maps coherence, response-time, word-finding,
        disorientation, and task-completion metrics onto the 0–30 MMSE
        sub-scales.
        """
        recent = list(self._observations)[-30:]
        if not recent:
            return MMSEApproximation(
                timestamp=time.time(),
                orientation_score=10, attention_score=5, recall_score=3,
                language_score=9, visuospatial_score=3, total_score=30,
            )

        avg_coherence = float(np.mean([o.coherence_score for o in recent]))
        avg_response = float(np.mean([o.response_time_s for o in recent]))
        avg_word = float(np.mean([o.word_finding_score for o in recent]))
        disorientation_rate = sum(1 for o in recent if o.disorientation_detected) / len(recent)

        orientation = round(10 * (1 - disorientation_rate))
        attention = round(5 * min(1.0, 5.0 / max(avg_response, 0.1)))
        recall = round(3 * avg_coherence)
        language = round(9 * avg_word)
        visuospatial = round(3 * avg_coherence)
        total = orientation + attention + recall + language + visuospatial

        result = MMSEApproximation(
            timestamp=time.time(),
            orientation_score=float(min(10, orientation)),
            attention_score=float(min(5, attention)),
            recall_score=float(min(3, recall)),
            language_score=float(min(9, language)),
            visuospatial_score=float(min(3, visuospatial)),
            total_score=float(min(30, total)),
        )
        self._mmse_history.append(result)
        return result

    # ── Trend estimation ──────────────────────────────────────

    def _estimate_trend(self, window_n: int = 14) -> CognitiveTrend:
        """Compute a linear trend over the last *window_n* observations."""
        recent = list(self._observations)[-window_n:]
        if len(recent) < window_n:
            return CognitiveTrend.STABLE
        y = np.array([o.coherence_score for o in recent])
        x = np.arange(len(y), dtype=float)
        slope = float(np.polyfit(x, y, 1)[0])
        if slope > 0.01:
            return CognitiveTrend.IMPROVING
        if slope < -0.01:
            return CognitiveTrend.DECLINING
        return CognitiveTrend.STABLE

    # ── Report generation ─────────────────────────────────────

    def generate_report(self) -> CognitiveHealthReport:
        """Generate a comprehensive cognitive health report.

        Returns
        -------
        CognitiveHealthReport
        """
        recent = list(self._observations)[-30:]
        notes: list[str] = []

        # Defaults for empty data
        if not recent:
            return CognitiveHealthReport(
                report_id=str(uuid.uuid4()),
                resident_id=self.resident_id,
                timestamp=time.time(),
                overall_level=CognitiveLevel.NORMAL,
                trend=CognitiveTrend.STABLE,
                coherence_avg=1.0, response_time_avg=0.0,
                repetition_rate=0.0, word_finding_avg=1.0,
                disorientation_rate=0.0, task_completion_rate=1.0,
            )

        coherence_avg = float(np.mean([o.coherence_score for o in recent]))
        response_avg = float(np.mean([o.response_time_s for o in recent]))
        repetition_rate = float(np.mean([o.repetition_count for o in recent]))
        word_finding_avg = float(np.mean([o.word_finding_score for o in recent]))
        disorientation_rate = sum(1 for o in recent if o.disorientation_detected) / len(recent)

        # Task completion
        recent_tasks = list(self._task_records)[-50:]
        task_rate = (
            sum(1 for t in recent_tasks if t.completed) / len(recent_tasks)
            if recent_tasks else 1.0
        )

        # Determine overall level
        concern_flags = 0
        if coherence_avg < COHERENCE_CONCERN_THRESHOLD:
            concern_flags += 2
            notes.append("Conversation coherence below threshold.")
        if response_avg > RESPONSE_TIME_CONCERN_S:
            concern_flags += 1
            notes.append(f"Mean response time elevated ({response_avg:.1f}s).")
        if repetition_rate > REPETITION_CONCERN_COUNT:
            concern_flags += 1
            notes.append("Elevated repetition detected in conversations.")
        if word_finding_avg < WORD_FINDING_CONCERN:
            concern_flags += 2
            notes.append("Word-finding difficulty detected.")
        if disorientation_rate > DISORIENTATION_CONCERN_RATE:
            concern_flags += 2
            notes.append(f"Disorientation detected in {disorientation_rate*100:.0f}% of interactions.")
        if task_rate < TASK_COMPLETION_CONCERN_RATE:
            concern_flags += 1
            notes.append(f"Task completion rate low ({task_rate*100:.0f}%).")

        if concern_flags >= 6:
            level = CognitiveLevel.SEVERE_CONCERN
        elif concern_flags >= 4:
            level = CognitiveLevel.MODERATE_CONCERN
        elif concern_flags >= 2:
            level = CognitiveLevel.MILD_CONCERN
        else:
            level = CognitiveLevel.NORMAL

        trend = self._estimate_trend()
        mini_cog = self._mini_cog_history[-1] if self._mini_cog_history else None
        mmse = self._mmse_history[-1] if self._mmse_history else None

        return CognitiveHealthReport(
            report_id=str(uuid.uuid4()),
            resident_id=self.resident_id,
            timestamp=time.time(),
            overall_level=level,
            trend=trend,
            coherence_avg=round(coherence_avg, 2),
            response_time_avg=round(response_avg, 2),
            repetition_rate=round(repetition_rate, 2),
            word_finding_avg=round(word_finding_avg, 2),
            disorientation_rate=round(disorientation_rate, 2),
            task_completion_rate=round(task_rate, 2),
            mini_cog=mini_cog,
            mmse=mmse,
            notes=notes,
        )

    def to_aether_event(self, report: CognitiveHealthReport) -> AetherEvent | None:
        """Convert a report to an AetherEvent if concern level is non-normal."""
        if report.overall_level == CognitiveLevel.NORMAL:
            return None

        severity_map = {
            CognitiveLevel.MILD_CONCERN: Severity.LOW,
            CognitiveLevel.MODERATE_CONCERN: Severity.MEDIUM,
            CognitiveLevel.SEVERE_CONCERN: Severity.HIGH,
        }
        return AetherEvent(
            event_type=EventType.COGNITIVE_DECLINE,
            severity=severity_map.get(report.overall_level, Severity.LOW),
            confidence=1.0 - report.coherence_avg,
            home_id="home-001",
            resident_id=report.resident_id,
            data={
                "report_id": report.report_id,
                "level": report.overall_level.value,
                "trend": report.trend.value,
                "coherence_avg": report.coherence_avg,
                "response_time_avg": report.response_time_avg,
                "word_finding_avg": report.word_finding_avg,
                "task_completion_rate": report.task_completion_rate,
                "notes": report.notes,
            },
            sources=[SensorSource(
                sensor_id="cognitive-tracker",
                sensor_type="analytics",
                confidence=1.0 - report.coherence_avg,
            )],
        )

    # ── Simulation helpers ────────────────────────────────────

    def seed_healthy_history(self, days: int = 30, observations_per_day: int = 2) -> None:
        """Populate history with simulated healthy cognitive data."""
        now = time.time()
        for d in range(days):
            for i in range(observations_per_day):
                ts = now - (days - d) * 86400 + i * 3600 * 8
                self.record_observation(ConversationObservation(
                    timestamp=ts,
                    coherence_score=float(np.clip(self.rng.normal(0.85, 0.05), 0, 1)),
                    response_time_s=float(max(0.5, self.rng.normal(3.0, 0.8))),
                    repetition_count=int(max(0, self.rng.poisson(0.3))),
                    word_finding_score=float(np.clip(self.rng.normal(0.88, 0.04), 0, 1)),
                    disorientation_detected=bool(self.rng.random() < 0.03),
                ))
                self.record_task(TaskCompletionRecord(
                    timestamp=ts,
                    task_type=str(self.rng.choice(["medication", "meal_prep", "morning_routine"])),
                    completed=bool(self.rng.random() < 0.95),
                    time_taken_s=float(self.rng.normal(300, 60)),
                ))

    def simulate_decline(
        self,
        days: int = 14,
        observations_per_day: int = 2,
        coherence_drop_per_day: float = 0.02,
    ) -> None:
        """Inject simulated cognitive decline over *days*."""
        now = time.time()
        recent = list(self._observations)
        base_coherence = recent[-1].coherence_score if recent else 0.85
        base_word = recent[-1].word_finding_score if recent else 0.88

        for d in range(days):
            for i in range(observations_per_day):
                ts = now + d * 86400 + i * 3600 * 8
                coh = float(np.clip(
                    base_coherence - d * coherence_drop_per_day + self.rng.normal(0, 0.02),
                    0, 1,
                ))
                wf = float(np.clip(
                    base_word - d * coherence_drop_per_day * 0.8 + self.rng.normal(0, 0.02),
                    0, 1,
                ))
                self.record_observation(ConversationObservation(
                    timestamp=ts,
                    coherence_score=coh,
                    response_time_s=float(max(0.5, 3.0 + d * 0.4 + self.rng.normal(0, 0.5))),
                    repetition_count=int(max(0, self.rng.poisson(0.3 + d * 0.2))),
                    word_finding_score=wf,
                    disorientation_detected=bool(self.rng.random() < 0.03 + d * 0.02),
                    transcript_snippet=str(self.rng.choice([
                        "What day is it?", "Did I take my medicine?",
                        "Where are my glasses?", "Is my daughter coming?",
                        "What time is lunch?",
                    ])),
                ))
