"""
Nutrition Monitoring Tracker

Tracks nutritional health through multiple signals:
  • Meal tracking (via kitchen activity, refrigerator sensor, routine)
  • Hydration tracking (water intake reminders, tracking glasses)
  • Calorie estimation (meal type classification)
  • Nutritional balance scoring
  • Weight trend tracking
  • Appetite changes detection
  • Daily nutrition reports
  • Meal recommendations based on conditions/medications

All analysis runs on-edge with simulated data — no real sensors required.
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

class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class NutritionLevel(str, Enum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


# ── Data classes ──────────────────────────────────────────────

@dataclass
class MealRecord:
    """A single meal observation."""
    timestamp: float
    meal_type: MealType
    detected: bool              # whether a meal was actually detected
    estimated_calories: float
    protein_score: float        # 0.0 – 1.0
    fruit_veg_score: float      # 0.0 – 1.0
    duration_min: float
    kitchen_activity: bool = True
    notes: str = ""


@dataclass
class HydrationRecord:
    """A single hydration observation."""
    timestamp: float
    glasses_consumed: int       # cumulative today
    target_glasses: int = 8
    reminder_sent: bool = False


@dataclass
class WeightRecord:
    """A weight measurement."""
    timestamp: float
    weight_kg: float


@dataclass
class DailyNutritionReport:
    """Daily summary of nutritional intake and health."""
    report_id: str
    resident_id: str
    timestamp: float
    date: str
    meals_detected: int
    meals_expected: int
    total_calories: float
    avg_protein_score: float
    avg_fruit_veg_score: float
    hydration_glasses: int
    hydration_target: int
    nutritional_balance: float   # 0.0–1.0
    nutrition_level: NutritionLevel
    weight_kg: Optional[float] = None
    weight_trend: Optional[str] = None  # "gaining", "stable", "losing"
    appetite_change: Optional[str] = None
    recommendations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ── Calorie estimates by meal type ────────────────────────────

_CALORIE_ESTIMATES: dict[MealType, tuple[float, float]] = {
    MealType.BREAKFAST: (300, 80),
    MealType.LUNCH: (500, 120),
    MealType.DINNER: (600, 150),
    MealType.SNACK: (150, 50),
}

# ── Recommendation templates ─────────────────────────────────

_RECOMMENDATIONS = {
    "low_protein": "Consider adding protein-rich foods (eggs, dal, paneer, fish).",
    "low_fruit_veg": "Increase fruit and vegetable intake — aim for 5 portions daily.",
    "low_hydration": "Drink more water — you are below today's target of {target} glasses.",
    "skipped_meal": "A {meal} was missed today — regular meals support energy and medication efficacy.",
    "low_calories": "Overall calorie intake is low — ensure adequate nutrition.",
    "weight_loss": "Gradual weight loss detected — consult your care team.",
    "appetite_decline": "Appetite appears to be declining — monitor and report to carer.",
    "diabetes": "For diabetes management, choose low-GI foods and maintain regular meal timing.",
    "hypertension": "Reduce sodium intake and increase potassium-rich foods for blood pressure management.",
}


# ── Engine ────────────────────────────────────────────────────

class NutritionTracker:
    """Track nutritional intake, hydration, and appetite over time.

    Parameters
    ----------
    resident_id : str
        Resident being monitored.
    conditions : list[str]
        Known medical conditions for tailored recommendations.
        Supported: ``diabetes``, ``hypertension``.
    """

    MEALS_PER_DAY = 3
    DAILY_CALORIE_MIN = 1200

    def __init__(
        self,
        resident_id: str = "resident-001",
        conditions: list[str] | None = None,
        seed: int = 42,
    ):
        self.resident_id = resident_id
        self.conditions = conditions or []
        self.rng = np.random.default_rng(seed)

        self._meals: deque[MealRecord] = deque(maxlen=2000)
        self._hydration: deque[HydrationRecord] = deque(maxlen=500)
        self._weights: deque[WeightRecord] = deque(maxlen=365)

    # ── Recording ─────────────────────────────────────────────

    def record_meal(self, record: MealRecord) -> None:
        """Record a meal observation."""
        self._meals.append(record)

    def record_hydration(self, record: HydrationRecord) -> None:
        """Record a hydration observation."""
        self._hydration.append(record)

    def record_weight(self, record: WeightRecord) -> None:
        """Record a weight measurement."""
        self._weights.append(record)

    # ── Calorie estimation ────────────────────────────────────

    def estimate_calories(self, meal_type: MealType) -> float:
        """Estimate calories for a meal type using Gaussian model."""
        mean, std = _CALORIE_ESTIMATES[meal_type]
        return float(max(50, self.rng.normal(mean, std)))

    # ── Weight trend ──────────────────────────────────────────

    def _compute_weight_trend(self, window_n: int = 14) -> Optional[str]:
        """Compute weight trend over the last *window_n* measurements."""
        weights = list(self._weights)
        if len(weights) < window_n:
            return None
        recent = weights[-window_n:]
        x = np.arange(len(recent), dtype=float)
        y = np.array([w.weight_kg for w in recent])
        slope = float(np.polyfit(x, y, 1)[0])
        if slope > 0.05:
            return "gaining"
        if slope < -0.05:
            return "losing"
        return "stable"

    # ── Appetite change detection ─────────────────────────────

    def _detect_appetite_change(self, window_days: int = 7) -> Optional[str]:
        """Detect appetite changes by comparing recent vs. baseline calorie intake."""
        meals = list(self._meals)
        if len(meals) < 14:
            return None
        now = time.time()
        cutoff = now - window_days * 86400
        recent_cals = [m.estimated_calories for m in meals if m.timestamp >= cutoff and m.detected]
        older_cals = [m.estimated_calories for m in meals if m.timestamp < cutoff and m.detected]
        if not recent_cals or not older_cals:
            return None
        recent_avg = float(np.mean(recent_cals))
        older_avg = float(np.mean(older_cals))
        ratio = recent_avg / max(older_avg, 1)
        if ratio < 0.75:
            return "declining"
        if ratio > 1.25:
            return "increasing"
        return "stable"

    # ── Report generation ─────────────────────────────────────

    def generate_daily_report(self, date_str: str | None = None) -> DailyNutritionReport:
        """Generate a daily nutrition report.

        Parameters
        ----------
        date_str : str, optional
            Date label (default: today).
        """
        now = time.time()
        today_start = now - 86400
        date_label = date_str or time.strftime("%Y-%m-%d")

        # Gather today's data
        today_meals = [m for m in self._meals if m.timestamp >= today_start]
        detected = [m for m in today_meals if m.detected]
        today_hydration = [h for h in self._hydration if h.timestamp >= today_start]

        meals_detected = len(detected)
        total_cals = sum(m.estimated_calories for m in detected) if detected else 0
        avg_protein = float(np.mean([m.protein_score for m in detected])) if detected else 0
        avg_fv = float(np.mean([m.fruit_veg_score for m in detected])) if detected else 0

        # Hydration
        hydration_glasses = today_hydration[-1].glasses_consumed if today_hydration else 0
        hydration_target = today_hydration[-1].target_glasses if today_hydration else 8

        # Nutritional balance (composite)
        calorie_score = min(1.0, total_cals / max(self.DAILY_CALORIE_MIN, 1))
        hydration_score = min(1.0, hydration_glasses / max(hydration_target, 1))
        balance = round((calorie_score + avg_protein + avg_fv + hydration_score) / 4, 2)

        # Determine level
        if balance >= 0.75:
            level = NutritionLevel.GOOD
        elif balance >= 0.50:
            level = NutritionLevel.FAIR
        elif balance >= 0.25:
            level = NutritionLevel.POOR
        else:
            level = NutritionLevel.CRITICAL

        # Weight
        latest_weight = self._weights[-1].weight_kg if self._weights else None
        weight_trend = self._compute_weight_trend()

        # Appetite
        appetite = self._detect_appetite_change()

        # Recommendations
        recs: list[str] = []
        notes: list[str] = []
        if avg_protein < 0.5:
            recs.append(_RECOMMENDATIONS["low_protein"])
        if avg_fv < 0.5:
            recs.append(_RECOMMENDATIONS["low_fruit_veg"])
        if hydration_glasses < hydration_target:
            recs.append(_RECOMMENDATIONS["low_hydration"].format(target=hydration_target))
        if meals_detected < self.MEALS_PER_DAY:
            missing = set(MealType) - {m.meal_type for m in detected}
            for mt in missing:
                if mt != MealType.SNACK:
                    recs.append(_RECOMMENDATIONS["skipped_meal"].format(meal=mt.value))
        if total_cals < self.DAILY_CALORIE_MIN and meals_detected > 0:
            recs.append(_RECOMMENDATIONS["low_calories"])
            notes.append(f"Total calories ({total_cals:.0f}) below minimum ({self.DAILY_CALORIE_MIN}).")
        if weight_trend == "losing":
            recs.append(_RECOMMENDATIONS["weight_loss"])
        if appetite == "declining":
            recs.append(_RECOMMENDATIONS["appetite_decline"])
        for cond in self.conditions:
            if cond in _RECOMMENDATIONS:
                recs.append(_RECOMMENDATIONS[cond])

        return DailyNutritionReport(
            report_id=str(uuid.uuid4()),
            resident_id=self.resident_id,
            timestamp=now,
            date=date_label,
            meals_detected=meals_detected,
            meals_expected=self.MEALS_PER_DAY,
            total_calories=round(total_cals, 0),
            avg_protein_score=round(avg_protein, 2),
            avg_fruit_veg_score=round(avg_fv, 2),
            hydration_glasses=hydration_glasses,
            hydration_target=hydration_target,
            nutritional_balance=balance,
            nutrition_level=level,
            weight_kg=latest_weight,
            weight_trend=weight_trend,
            appetite_change=appetite,
            recommendations=recs,
            notes=notes,
        )

    def to_aether_event(self, report: DailyNutritionReport) -> AetherEvent | None:
        """Convert a nutrition report to an AetherEvent if concern exists."""
        if report.nutrition_level == NutritionLevel.GOOD:
            return None

        severity_map = {
            NutritionLevel.FAIR: Severity.LOW,
            NutritionLevel.POOR: Severity.MEDIUM,
            NutritionLevel.CRITICAL: Severity.HIGH,
        }
        return AetherEvent(
            event_type=EventType.NUTRITION_CONCERN,
            severity=severity_map.get(report.nutrition_level, Severity.LOW),
            confidence=1.0 - report.nutritional_balance,
            home_id="home-001",
            resident_id=report.resident_id,
            data={
                "report_id": report.report_id,
                "date": report.date,
                "level": report.nutrition_level.value,
                "meals_detected": report.meals_detected,
                "total_calories": report.total_calories,
                "hydration": f"{report.hydration_glasses}/{report.hydration_target}",
                "balance": report.nutritional_balance,
                "recommendations": report.recommendations,
                "notes": report.notes,
            },
            sources=[SensorSource(
                sensor_id="nutrition-tracker",
                sensor_type="analytics",
                confidence=1.0 - report.nutritional_balance,
            )],
        )

    # ── Simulation helpers ────────────────────────────────────

    def seed_history(self, days: int = 14, meals_per_day: int = 3) -> None:
        """Populate history with simulated healthy nutrition data."""
        now = time.time()
        for d in range(days):
            glasses = 0
            for i, mt in enumerate([MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER]):
                ts = now - (days - d) * 86400 + i * 3600 * 5 + 7 * 3600
                cals = self.estimate_calories(mt)
                self.record_meal(MealRecord(
                    timestamp=ts,
                    meal_type=mt,
                    detected=True,
                    estimated_calories=round(cals, 0),
                    protein_score=float(np.clip(self.rng.normal(0.7, 0.1), 0, 1)),
                    fruit_veg_score=float(np.clip(self.rng.normal(0.65, 0.12), 0, 1)),
                    duration_min=float(max(5, self.rng.normal(20, 5))),
                ))
                glasses += int(self.rng.integers(1, 4))

            self.record_hydration(HydrationRecord(
                timestamp=now - (days - d) * 86400 + 18 * 3600,
                glasses_consumed=min(glasses, 10),
                target_glasses=8,
            ))

            self.record_weight(WeightRecord(
                timestamp=now - (days - d) * 86400,
                weight_kg=float(self.rng.normal(68, 0.3)),
            ))

    def simulate_poor_nutrition(self, days: int = 7) -> None:
        """Inject simulated poor nutrition over *days*."""
        now = time.time()
        for d in range(days):
            # Skip some meals
            meal_types = [MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER]
            for mt in meal_types:
                ts = now + d * 86400 + list(MealType).index(mt) * 3600 * 5
                detected = bool(self.rng.random() > 0.4)  # 40% skip rate
                cals = self.estimate_calories(mt) if detected else 0
                self.record_meal(MealRecord(
                    timestamp=ts,
                    meal_type=mt,
                    detected=detected,
                    estimated_calories=round(cals * 0.6, 0),
                    protein_score=float(np.clip(self.rng.normal(0.3, 0.1), 0, 1)),
                    fruit_veg_score=float(np.clip(self.rng.normal(0.25, 0.1), 0, 1)),
                    duration_min=float(max(3, self.rng.normal(10, 3))),
                ))

            self.record_hydration(HydrationRecord(
                timestamp=now + d * 86400 + 18 * 3600,
                glasses_consumed=int(self.rng.integers(1, 4)),
                target_glasses=8,
            ))
