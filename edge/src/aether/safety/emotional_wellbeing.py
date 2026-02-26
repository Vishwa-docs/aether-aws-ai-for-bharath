"""
Emotional Wellbeing Tracker

Monitors emotional and mental health through multiple signals:
  • Mood scoring from check-in responses (1–10 scale)
  • Loneliness detection (social interaction frequency, call patterns)
  • Anxiety indicators (sleep disruption, pacing, verbal cues)
  • Depression screening proxy (reduced activity, meal skipping, isolation)
  • Positive event tracking (visitors, outings, phone calls)
  • Weekly wellbeing reports
  • Intervention recommendations

All analysis runs on-edge with simulated data — no clinical assessment.
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
)

logger = logging.getLogger(__name__)


# ── Enums ─────────────────────────────────────────────────────

class WellbeingLevel(str, Enum):
    THRIVING = "thriving"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class WellbeingTrend(str, Enum):
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


# ── Data classes ──────────────────────────────────────────────

@dataclass
class MoodObservation:
    """A single mood check-in observation."""
    timestamp: float
    mood_score: float           # 1.0 – 10.0
    verbal_cues: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class SocialInteraction:
    """A recorded social interaction event."""
    timestamp: float
    interaction_type: str       # "visit", "phone_call", "outing", "video_call"
    duration_min: float
    with_whom: str = ""         # "family", "friend", "carer", "unknown"


@dataclass
class ActivityObservation:
    """An activity-level observation for depression/anxiety screening."""
    timestamp: float
    steps: int = 0
    meals_eaten: int = 0
    sleep_hours: float = 0.0
    sleep_disruptions: int = 0
    pacing_detected: bool = False
    left_home: bool = False


@dataclass
class WeeklyWellbeingReport:
    """Weekly emotional wellbeing summary."""
    report_id: str
    resident_id: str
    timestamp: float
    week_label: str
    wellbeing_level: WellbeingLevel
    trend: WellbeingTrend
    avg_mood: float
    mood_variability: float
    loneliness_score: float      # 0.0 (not lonely) – 1.0 (severely lonely)
    anxiety_score: float         # 0.0 – 1.0
    depression_proxy_score: float  # 0.0 – 1.0
    social_interactions: int
    positive_events: int
    recommendations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ── Thresholds ────────────────────────────────────────────────

MOOD_CONCERN_THRESHOLD = 4.0          # mood ≤ 4 = concern
LONELINESS_INTERACTION_DAILY = 1.0    # minimum 1 interaction/day
ANXIETY_SLEEP_DISRUPTION_THRESHOLD = 2
DEPRESSION_ACTIVITY_THRESHOLD = 1000  # steps
DEPRESSION_MEAL_THRESHOLD = 2         # meals/day


# ── Intervention recommendations ─────────────────────────────

_INTERVENTIONS = {
    "low_mood": "Low mood detected — consider a friendly check-in call or visit.",
    "loneliness": "Social isolation risk — encourage family calls or community activity.",
    "anxiety": "Anxiety indicators present — ensure calming environment and routine consistency.",
    "depression_proxy": "Reduced activity/appetite may indicate low mood — alert care team.",
    "sleep_disruption": "Sleep disruption detected — review sleep environment (light, noise, temperature).",
    "positive_reinforcement": "Continue encouraging social engagement — positive trend observed.",
    "professional_referral": "Persistent low wellbeing — consider professional mental health assessment.",
}


# ── Engine ────────────────────────────────────────────────────

class EmotionalWellbeingTracker:
    """Track emotional wellbeing and detect mental-health concerns.

    Parameters
    ----------
    resident_id : str
        Resident being monitored.
    """

    def __init__(
        self,
        resident_id: str = "resident-001",
        seed: int = 42,
    ):
        self.resident_id = resident_id
        self.rng = np.random.default_rng(seed)

        self._moods: deque[MoodObservation] = deque(maxlen=2000)
        self._interactions: deque[SocialInteraction] = deque(maxlen=2000)
        self._activities: deque[ActivityObservation] = deque(maxlen=2000)

    # ── Recording ─────────────────────────────────────────────

    def record_mood(self, obs: MoodObservation) -> None:
        """Record a mood check-in observation."""
        self._moods.append(obs)

    def record_interaction(self, interaction: SocialInteraction) -> None:
        """Record a social interaction event."""
        self._interactions.append(interaction)

    def record_activity(self, obs: ActivityObservation) -> None:
        """Record a daily activity observation."""
        self._activities.append(obs)

    # ── Loneliness scoring ────────────────────────────────────

    def _compute_loneliness_score(self, window_days: int = 7) -> float:
        """Compute loneliness score based on social interaction frequency.

        Returns 0.0 (not lonely) – 1.0 (severely lonely).
        """
        now = time.time()
        cutoff = now - window_days * 86400
        recent = [i for i in self._interactions if i.timestamp >= cutoff]
        daily_rate = len(recent) / max(window_days, 1)
        if daily_rate >= LONELINESS_INTERACTION_DAILY * 2:
            return 0.0
        if daily_rate >= LONELINESS_INTERACTION_DAILY:
            return round(0.3 * (1 - daily_rate / (LONELINESS_INTERACTION_DAILY * 2)), 2)
        if daily_rate > 0:
            return round(0.5 + 0.3 * (1 - daily_rate / LONELINESS_INTERACTION_DAILY), 2)
        return 1.0

    # ── Anxiety scoring ───────────────────────────────────────

    def _compute_anxiety_score(self, window_days: int = 7) -> float:
        """Compute anxiety score from sleep disruptions and pacing."""
        now = time.time()
        cutoff = now - window_days * 86400
        recent = [a for a in self._activities if a.timestamp >= cutoff]
        if not recent:
            return 0.0

        avg_disruptions = float(np.mean([a.sleep_disruptions for a in recent]))
        pacing_rate = sum(1 for a in recent if a.pacing_detected) / len(recent)

        disruption_component = min(1.0, avg_disruptions / (ANXIETY_SLEEP_DISRUPTION_THRESHOLD * 2))
        pacing_component = pacing_rate

        return round(min(1.0, disruption_component * 0.6 + pacing_component * 0.4), 2)

    # ── Depression proxy scoring ──────────────────────────────

    def _compute_depression_proxy(self, window_days: int = 7) -> float:
        """Compute depression proxy score from activity, meals, isolation."""
        now = time.time()
        cutoff = now - window_days * 86400
        recent = [a for a in self._activities if a.timestamp >= cutoff]
        if not recent:
            return 0.0

        avg_steps = float(np.mean([a.steps for a in recent]))
        avg_meals = float(np.mean([a.meals_eaten for a in recent]))
        left_home_rate = sum(1 for a in recent if a.left_home) / len(recent)

        activity_component = max(0, 1, - avg_steps / DEPRESSION_ACTIVITY_THRESHOLD)
        meal_component = max(0, 1.0 - avg_meals / DEPRESSION_MEAL_THRESHOLD)
        isolation_component = 1.0 - left_home_rate

        score = (activity_component * 0.35 + meal_component * 0.35 + isolation_component * 0.30)
        return round(min(1.0, max(0.0, score)), 2)

    # ── Positive events ───────────────────────────────────────

    def _count_positive_events(self, window_days: int = 7) -> int:
        """Count positive social events in the window."""
        now = time.time()
        cutoff = now - window_days * 86400
        return len([
            i for i in self._interactions
            if i.timestamp >= cutoff and i.interaction_type in ("visit", "outing")
        ])

    # ── Trend estimation ──────────────────────────────────────

    def _estimate_trend(self, window_n: int = 14) -> WellbeingTrend:
        """Compute mood trend over the last *window_n* observations."""
        recent = list(self._moods)[-window_n:]
        if len(recent) < window_n:
            return WellbeingTrend.STABLE
        y = np.array([o.mood_score for o in recent])
        x = np.arange(len(y), dtype=float)
        slope = float(np.polyfit(x, y, 1)[0])
        if slope > 0.1:
            return WellbeingTrend.IMPROVING
        if slope < -0.1:
            return WellbeingTrend.DECLINING
        return WellbeingTrend.STABLE

    # ── Report generation ─────────────────────────────────────

    def generate_weekly_report(self, week_label: str | None = None) -> WeeklyWellbeingReport:
        """Generate a weekly emotional wellbeing report.

        Parameters
        ----------
        week_label : str, optional
            Week label (default: current ISO week).
        """
        now = time.time()
        label = week_label or time.strftime("%Y-W%W")
        window_days = 7
        cutoff = now - window_days * 86400

        # Mood
        recent_moods = [m for m in self._moods if m.timestamp >= cutoff]
        if recent_moods:
            avg_mood = float(np.mean([m.mood_score for m in recent_moods]))
            mood_var = float(np.std([m.mood_score for m in recent_moods]))
        else:
            avg_mood = 7.0
            mood_var = 0.0

        # Scores
        loneliness = self._compute_loneliness_score(window_days)
        anxiety = self._compute_anxiety_score(window_days)
        depression = self._compute_depression_proxy(window_days)
        positive = self._count_positive_events(window_days)
        trend = self._estimate_trend()

        social_count = len([i for i in self._interactions if i.timestamp >= cutoff])

        # Determine level
        concern_score = (
            (10 - avg_mood) / 10 * 0.30
            + loneliness * 0.25
            + anxiety * 0.20
            + depression * 0.25
        )

        if concern_score >= 0.70:
            level = WellbeingLevel.CRITICAL
        elif concern_score >= 0.50:
            level = WellbeingLevel.POOR
        elif concern_score >= 0.30:
            level = WellbeingLevel.FAIR
        elif concern_score >= 0.15:
            level = WellbeingLevel.GOOD
        else:
            level = WellbeingLevel.THRIVING

        # Recommendations
        recs: list[str] = []
        notes: list[str] = []

        if avg_mood <= MOOD_CONCERN_THRESHOLD:
            recs.append(_INTERVENTIONS["low_mood"])
            notes.append(f"Average mood this week: {avg_mood:.1f}/10.")
        if loneliness > 0.5:
            recs.append(_INTERVENTIONS["loneliness"])
            notes.append(f"Loneliness score: {loneliness:.2f}.")
        if anxiety > 0.5:
            recs.append(_INTERVENTIONS["anxiety"])
            notes.append(f"Anxiety score: {anxiety:.2f}.")
        if depression > 0.5:
            recs.append(_INTERVENTIONS["depression_proxy"])
            notes.append(f"Depression proxy score: {depression:.2f}.")
        if level in (WellbeingLevel.POOR, WellbeingLevel.CRITICAL):
            recs.append(_INTERVENTIONS["professional_referral"])
        if trend == WellbeingTrend.IMPROVING:
            recs.append(_INTERVENTIONS["positive_reinforcement"])

        return WeeklyWellbeingReport(
            report_id=str(uuid.uuid4()),
            resident_id=self.resident_id,
            timestamp=now,
            week_label=label,
            wellbeing_level=level,
            trend=trend,
            avg_mood=round(avg_mood, 1),
            mood_variability=round(mood_var, 2),
            loneliness_score=loneliness,
            anxiety_score=anxiety,
            depression_proxy_score=depression,
            social_interactions=social_count,
            positive_events=positive,
            recommendations=recs,
            notes=notes,
        )

    def to_aether_event(self, report: WeeklyWellbeingReport) -> AetherEvent | None:
        """Convert a wellbeing report to an AetherEvent if concern exists."""
        if report.wellbeing_level in (WellbeingLevel.THRIVING, WellbeingLevel.GOOD):
            return None

        severity_map = {
            WellbeingLevel.FAIR: Severity.LOW,
            WellbeingLevel.POOR: Severity.MEDIUM,
            WellbeingLevel.CRITICAL: Severity.HIGH,
        }
        concern_score = (
            (10 - report.avg_mood) / 10 * 0.30
            + report.loneliness_score * 0.25
            + report.anxiety_score * 0.20
            + report.depression_proxy_score * 0.25
        )
        return AetherEvent(
            event_type=EventType.EMOTIONAL_CONCERN,
            severity=severity_map.get(report.wellbeing_level, Severity.LOW),
            confidence=round(min(1.0, concern_score), 2),
            home_id="home-001",
            resident_id=report.resident_id,
            data={
                "report_id": report.report_id,
                "week": report.week_label,
                "level": report.wellbeing_level.value,
                "trend": report.trend.value,
                "avg_mood": report.avg_mood,
                "loneliness": report.loneliness_score,
                "anxiety": report.anxiety_score,
                "depression_proxy": report.depression_proxy_score,
                "social_interactions": report.social_interactions,
                "recommendations": report.recommendations,
                "notes": report.notes,
            },
            sources=[SensorSource(
                sensor_id="emotional-wellbeing-tracker",
                sensor_type="analytics",
                confidence=round(min(1.0, concern_score), 2),
            )],
        )

    # ── Simulation helpers ────────────────────────────────────

    def seed_healthy_history(self, days: int = 30) -> None:
        """Populate history with simulated healthy emotional data."""
        now = time.time()
        for d in range(days):
            ts_base = now - (days - d) * 86400

            # Mood (twice daily)
            for offset_h in [9, 18]:
                self.record_mood(MoodObservation(
                    timestamp=ts_base + offset_h * 3600,
                    mood_score=float(np.clip(self.rng.normal(7.5, 1.0), 1, 10)),
                ))

            # Social interactions (~1-2 per day)
            n_interactions = int(self.rng.integers(1, 3))
            for _ in range(n_interactions):
                self.record_interaction(SocialInteraction(
                    timestamp=ts_base + float(self.rng.uniform(8, 20)) * 3600,
                    interaction_type=str(self.rng.choice(["phone_call", "visit", "outing", "video_call"])),
                    duration_min=float(self.rng.uniform(10, 60)),
                    with_whom=str(self.rng.choice(["family", "friend", "carer"])),
                ))

            # Activity
            self.record_activity(ActivityObservation(
                timestamp=ts_base + 20 * 3600,
                steps=int(self.rng.normal(3500, 800)),
                meals_eaten=int(self.rng.integers(2, 4)),
                sleep_hours=float(np.clip(self.rng.normal(7, 0.8), 4, 10)),
                sleep_disruptions=int(max(0, self.rng.poisson(0.5))),
                pacing_detected=bool(self.rng.random() < 0.05),
                left_home=bool(self.rng.random() < 0.6),
            ))

    def simulate_decline(self, days: int = 14) -> None:
        """Inject simulated emotional decline over *days*."""
        now = time.time()
        recent = list(self._moods)
        base_mood = recent[-1].mood_score if recent else 7.5

        for d in range(days):
            ts_base = now + d * 86400
            mood = float(np.clip(base_mood - d * 0.3 + self.rng.normal(0, 0.5), 1, 10))

            for offset_h in [9, 18]:
                self.record_mood(MoodObservation(
                    timestamp=ts_base + offset_h * 3600,
                    mood_score=mood,
                ))

            # Reduce social interaction
            if self.rng.random() > 0.3 + d * 0.04:
                self.record_interaction(SocialInteraction(
                    timestamp=ts_base + 14 * 3600,
                    interaction_type="phone_call",
                    duration_min=float(max(2, self.rng.normal(10 - d * 0.5, 3))),
                    with_whom="family",
                ))

            # Reduce activity
            self.record_activity(ActivityObservation(
                timestamp=ts_base + 20 * 3600,
                steps=int(max(200, self.rng.normal(3500 - d * 200, 500))),
                meals_eaten=int(np.clip(self.rng.normal(3 - d * 0.1, 0.5), 0, 3)),
                sleep_hours=float(np.clip(self.rng.normal(7 - d * 0.15, 1.0), 3, 10)),
                sleep_disruptions=int(max(0, self.rng.poisson(0.5 + d * 0.3))),
                pacing_detected=bool(self.rng.random() < 0.05 + d * 0.03),
                left_home=bool(self.rng.random() < max(0.1, 0.6 - d * 0.04)),
            ))
