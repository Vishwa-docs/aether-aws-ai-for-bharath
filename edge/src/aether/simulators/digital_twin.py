"""
Digital Twin Simulator — Day 14

Generates realistic synthetic sensor data for N homes over D days.
Can generate 90 days of data for 4 homes in ~15 minutes.
Used for testing, training, and demo purposes.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from aether.models.schemas import (
    AcousticEventLabel,
    EventType,
    Severity,
    SensorType,
)
from aether.simulators.imu_simulator import IMUSimulator
from aether.simulators.acoustic_simulator import AcousticSimulator
from aether.simulators.pose_simulator import PoseSimulator
from aether.simulators.medication_simulator import MedicationSimulator, SAMPLE_MEDICATIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ResidentProfile:
    """Profile of a single elderly resident."""
    resident_id: str
    name: str
    age: int
    conditions: list[str]        # e.g. ["arthritis", "diabetes", "hypertension"]
    medications: list[dict]      # [{name, dose, schedule}]
    risk_level: str              # low, medium, high
    mobility: str                # good, limited, poor
    fall_probability: float      # daily probability of a fall
    medication_adherence: float  # 0-1, probability of taking meds on time


@dataclass
class HomeConfig:
    """Configuration for a single simulated home."""
    home_id: str
    residents: list[ResidentProfile]
    rooms: list[str]
    sensors: dict  # {room: [sensor_types]}


# ---------------------------------------------------------------------------
# Pre-configured Indian homes
# ---------------------------------------------------------------------------

_DEFAULT_ROOMS = [
    "bedroom", "living_room", "kitchen", "bathroom", "dining_room", "hallway",
]

_DEFAULT_SENSORS = {
    "bedroom": ["imu", "acoustic", "pose", "environmental"],
    "living_room": ["imu", "acoustic", "pose", "environmental"],
    "kitchen": ["acoustic", "environmental"],
    "bathroom": ["imu", "acoustic"],
    "dining_room": ["acoustic"],
    "hallway": ["pose"],
}


def _default_homes() -> list[HomeConfig]:
    """Return 4 pre-configured Indian homes with realistic profiles."""
    return [
        HomeConfig(
            home_id="home-mumbai-001",
            residents=[
                ResidentProfile(
                    resident_id="R001",
                    name="Kamala Devi",
                    age=78,
                    conditions=["arthritis", "hypertension"],
                    medications=[
                        {"name": "Amlodipine 5mg", "dose": "5mg", "schedule": "08:00"},
                        {"name": "Diclofenac 50mg", "dose": "50mg", "schedule": "08:00,20:00"},
                    ],
                    risk_level="medium",
                    mobility="limited",
                    fall_probability=0.03,
                    medication_adherence=0.85,
                ),
            ],
            rooms=_DEFAULT_ROOMS,
            sensors=_DEFAULT_SENSORS,
        ),
        HomeConfig(
            home_id="home-delhi-002",
            residents=[
                ResidentProfile(
                    resident_id="R002",
                    name="Rajesh Kumar",
                    age=82,
                    conditions=["diabetes", "mild_dementia", "osteoporosis"],
                    medications=[
                        {"name": "Metformin 500mg", "dose": "500mg", "schedule": "07:30,19:30"},
                        {"name": "Donepezil 5mg", "dose": "5mg", "schedule": "21:00"},
                        {"name": "Calcium + Vit D", "dose": "1 tab", "schedule": "08:00"},
                    ],
                    risk_level="high",
                    mobility="limited",
                    fall_probability=0.06,
                    medication_adherence=0.70,
                ),
            ],
            rooms=_DEFAULT_ROOMS,
            sensors=_DEFAULT_SENSORS,
        ),
        HomeConfig(
            home_id="home-bangalore-003",
            residents=[
                ResidentProfile(
                    resident_id="R003",
                    name="Lakshmi Iyer",
                    age=73,
                    conditions=["hypertension"],
                    medications=[
                        {"name": "Losartan 50mg", "dose": "50mg", "schedule": "09:00"},
                    ],
                    risk_level="low",
                    mobility="good",
                    fall_probability=0.01,
                    medication_adherence=0.95,
                ),
            ],
            rooms=_DEFAULT_ROOMS,
            sensors=_DEFAULT_SENSORS,
        ),
        HomeConfig(
            home_id="home-chennai-004",
            residents=[
                ResidentProfile(
                    resident_id="R004",
                    name="Venkatesh Rao",
                    age=85,
                    conditions=["COPD", "heart_failure", "arthritis"],
                    medications=[
                        {"name": "Salbutamol Inhaler", "dose": "2 puffs", "schedule": "07:00,15:00,23:00"},
                        {"name": "Furosemide 40mg", "dose": "40mg", "schedule": "08:00"},
                        {"name": "Enalapril 5mg", "dose": "5mg", "schedule": "08:00,20:00"},
                        {"name": "Aspirin 75mg", "dose": "75mg", "schedule": "09:00"},
                    ],
                    risk_level="high",
                    mobility="poor",
                    fall_probability=0.08,
                    medication_adherence=0.75,
                ),
            ],
            rooms=_DEFAULT_ROOMS,
            sensors=_DEFAULT_SENSORS,
        ),
    ]


# ---------------------------------------------------------------------------
# Event templates
# ---------------------------------------------------------------------------

_ROUTINE_ACTIVITIES = {
    "morning": [
        {"activity": "wake_up", "hour_range": (5.5, 7.0), "room": "bedroom"},
        {"activity": "bathroom_visit", "hour_range": (5.5, 7.5), "room": "bathroom"},
        {"activity": "morning_prayer", "hour_range": (6.0, 7.5), "room": "living_room"},
        {"activity": "breakfast", "hour_range": (7.5, 9.0), "room": "kitchen"},
        {"activity": "morning_tea", "hour_range": (7.0, 8.5), "room": "kitchen"},
    ],
    "daytime": [
        {"activity": "light_walk", "hour_range": (9.0, 11.0), "room": "hallway"},
        {"activity": "tv_watching", "hour_range": (10.0, 12.0), "room": "living_room"},
        {"activity": "lunch", "hour_range": (12.0, 13.5), "room": "dining_room"},
        {"activity": "afternoon_nap", "hour_range": (14.0, 16.0), "room": "bedroom"},
        {"activity": "evening_tea", "hour_range": (16.0, 17.0), "room": "kitchen"},
        {"activity": "hydration", "hour_range": (10.0, 16.0), "room": "kitchen"},
    ],
    "evening": [
        {"activity": "dinner", "hour_range": (19.0, 20.5), "room": "dining_room"},
        {"activity": "tv_watching", "hour_range": (20.0, 22.0), "room": "living_room"},
        {"activity": "night_routine", "hour_range": (21.0, 22.5), "room": "bathroom"},
    ],
    "night": [
        {"activity": "sleep", "hour_range": (22.0, 6.0), "room": "bedroom"},
        {"activity": "bathroom_visit", "hour_range": (0.0, 5.0), "room": "bathroom"},
    ],
}

_CHECK_IN_MOODS = ["good", "okay", "not great", "fine", "a bit tired", "happy"]
_CHECK_IN_PAIN = [0, 0, 0, 1, 2, 3, 5, 7]  # weighted toward no pain
_CHECK_IN_SLEEP = ["well", "okay", "poorly", "fine", "like a log", "terribly"]


# ---------------------------------------------------------------------------
# DigitalTwin
# ---------------------------------------------------------------------------

class DigitalTwin:
    """Simulate N homes over D days generating realistic events.

    Parameters
    ----------
    homes : list[HomeConfig] | None
        Home configurations.  Uses 4 default Indian homes if not provided.
    seed : int
        Random seed for reproducibility.
    """

    def __init__(
        self,
        homes: list[HomeConfig] | None = None,
        seed: int = 42,
    ) -> None:
        self.homes = homes or _default_homes()
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        # Simulators (shared across runs for efficiency)
        self._imu_sim = IMUSimulator(seed=seed)
        self._acoustic_sim = AcousticSimulator(seed=seed)
        self._pose_sim = PoseSimulator(seed=seed)
        self._med_sim = MedicationSimulator(seed=seed)

        # Health decline trackers per resident
        self._health_state: dict[str, dict[str, Any]] = {}
        for home in self.homes:
            for res in home.residents:
                self._health_state[res.resident_id] = {
                    "cumulative_decline": 0.0,
                    "days_simulated": 0,
                    "fall_count": 0,
                    "missed_meds": 0,
                }

    # ------------------------------------------------------------------
    # Day simulation
    # ------------------------------------------------------------------

    def simulate_day(
        self,
        home: HomeConfig,
        date: datetime,
    ) -> list[dict]:
        """Simulate a full day of activity for a home.

        Generates events following realistic circadian patterns:
        - Morning routine (5:30–9 AM): wake, prayer, medication, breakfast
        - Daytime (9 AM–6 PM): activities, meals, hydration, naps
        - Evening (6–10 PM): dinner, medication, leisure
        - Night (10 PM–6 AM): sleep monitoring, bathroom visits
        - Random events: falls, acoustic events, vitals
        """
        events: list[dict] = []
        day_of_week = date.weekday()  # 0 = Monday
        day_number = self._health_state.get(
            home.residents[0].resident_id if home.residents else "?", {}
        ).get("days_simulated", 0)

        for resident in home.residents:
            res_events = self._simulate_resident_day(
                home, resident, date, day_of_week, day_number,
            )
            events.extend(res_events)

            # Update health state
            state = self._health_state[resident.resident_id]
            state["days_simulated"] += 1

        # Sort by timestamp
        events.sort(key=lambda e: e.get("timestamp", 0))
        return events

    def _simulate_resident_day(
        self,
        home: HomeConfig,
        resident: ResidentProfile,
        date: datetime,
        day_of_week: int,
        day_number: int,
    ) -> list[dict]:
        """Generate all events for one resident for one day."""
        events: list[dict] = []
        state = self._health_state[resident.resident_id]

        # Gradual health decline for high-risk residents
        decline_factor = 1.0
        if resident.risk_level == "high" and day_number > 30:
            decline_factor = 1.0 + (day_number - 30) * 0.005
            state["cumulative_decline"] = (decline_factor - 1.0)

        # === Routine activities ===
        for period, activities in _ROUTINE_ACTIVITIES.items():
            for act in activities:
                # Weekend variation — slightly later wake-up
                hour_start, hour_end = act["hour_range"]
                if day_of_week >= 5 and act["activity"] == "wake_up":
                    hour_start += 0.5
                    hour_end += 0.5

                # Skip some optional activities randomly
                if act["activity"] in ("light_walk", "morning_prayer", "hydration"):
                    if self.rng.random() > 0.7:
                        continue

                # Reduced activity for poor mobility
                if act["activity"] == "light_walk" and resident.mobility == "poor":
                    if self.rng.random() > 0.3:
                        continue

                hour = self._random_hour(hour_start, hour_end)
                ts = self._make_timestamp(date, hour)
                events.append(self._make_event(
                    event_type="routine_activity",
                    timestamp=ts,
                    home_id=home.home_id,
                    resident_id=resident.resident_id,
                    data={
                        "activity": act["activity"],
                        "room": act["room"],
                        "period": period,
                    },
                    severity="low",
                ))

        # === Medication events ===
        events.extend(self._generate_medication_events(
            home, resident, date, decline_factor,
        ))

        # === Vital signs (3x daily) ===
        for vital_hour in [7.0, 14.0, 21.0]:
            hour = vital_hour + self.rng.normal(0, 0.25)
            ts = self._make_timestamp(date, hour)
            events.append(self._generate_vital_signs(
                home, resident, ts, decline_factor,
            ))

        # === Daily check-in (morning) ===
        checkin_hour = self._random_hour(8.0, 10.0)
        ts = self._make_timestamp(date, checkin_hour)
        events.append(self._generate_checkin(home, resident, ts, day_number))

        # === Falls (probabilistic) ===
        adjusted_fall_prob = resident.fall_probability * decline_factor
        # Higher fall probability at night (2x) and in bathroom (1.5x)
        for period_label, hour_range, multiplier in [
            ("night", (22.0, 30.0), 2.0),   # 30 = 6 AM next day
            ("bathroom_morning", (6.0, 8.0), 1.5),
            ("daytime", (8.0, 22.0), 1.0),
        ]:
            period_prob = adjusted_fall_prob * multiplier / 3.0  # split across periods
            if self.rng.random() < period_prob:
                fall_hour = self._random_hour(*hour_range)
                if fall_hour >= 24.0:
                    fall_hour -= 24.0
                ts = self._make_timestamp(date, fall_hour)
                fall_event = self._generate_fall_event(
                    home, resident, ts, period_label,
                )
                events.append(fall_event)
                state["fall_count"] += 1

        # === Random acoustic events ===
        if self.rng.random() < 0.15:
            labels = [
                AcousticEventLabel.COUGH,
                AcousticEventLabel.DOORBELL,
                AcousticEventLabel.PHONE_RING,
            ]
            label = labels[int(self.rng.integers(0, len(labels)))]
            hour = self._random_hour(8.0, 22.0)
            ts = self._make_timestamp(date, hour)
            room_idx = int(self.rng.integers(0, len(home.rooms)))
            events.append(self._make_event(
                event_type="acoustic_event",
                timestamp=ts,
                home_id=home.home_id,
                resident_id=resident.resident_id,
                data={
                    "label": label.value,
                    "room": home.rooms[room_idx],
                    "confidence": round(float(self.rng.uniform(0.6, 0.95)), 2),
                },
                severity="low",
            ))

        # === Glass break (rare) ===
        if self.rng.random() < 0.005:
            hour = self._random_hour(8.0, 22.0)
            ts = self._make_timestamp(date, hour)
            events.append(self._make_event(
                event_type=EventType.GLASS_BREAK.value,
                timestamp=ts,
                home_id=home.home_id,
                resident_id=resident.resident_id,
                data={
                    "room": ["kitchen", "living_room", "dining_room"][int(self.rng.integers(0, 3))],
                    "confidence": round(float(self.rng.uniform(0.7, 0.95)), 2),
                },
                severity="medium",
            ))

        return events

    # ------------------------------------------------------------------
    # Event generators
    # ------------------------------------------------------------------

    def _generate_medication_events(
        self,
        home: HomeConfig,
        resident: ResidentProfile,
        date: datetime,
        decline_factor: float,
    ) -> list[dict]:
        """Generate medication events based on schedule and adherence."""
        events: list[dict] = []
        adherence = resident.medication_adherence / decline_factor  # worse with decline
        adherence = max(0.3, min(1.0, adherence))

        for med in resident.medications:
            schedule_times = med.get("schedule", "08:00").split(",")
            for sched_str in schedule_times:
                parts = sched_str.strip().split(":")
                sched_hour = int(parts[0]) + int(parts[1]) / 60.0

                r = self.rng.random()
                if r < adherence * 0.8:
                    # On time
                    hour = sched_hour + self.rng.normal(0, 0.1)
                    ts = self._make_timestamp(date, hour)
                    events.append(self._make_event(
                        event_type=EventType.MEDICATION_TAKEN.value,
                        timestamp=ts,
                        home_id=home.home_id,
                        resident_id=resident.resident_id,
                        data={
                            "medication_name": med["name"],
                            "dose": med["dose"],
                            "scheduled_time": sched_str.strip(),
                            "status": "on_time",
                            "delay_minutes": round(abs(float(self.rng.normal(0, 5))), 1),
                        },
                        severity="low",
                    ))
                elif r < adherence:
                    # Late (15-60 min)
                    delay_min = float(self.rng.uniform(15, 60))
                    hour = sched_hour + delay_min / 60.0
                    ts = self._make_timestamp(date, hour)
                    events.append(self._make_event(
                        event_type=EventType.MEDICATION_TAKEN.value,
                        timestamp=ts,
                        home_id=home.home_id,
                        resident_id=resident.resident_id,
                        data={
                            "medication_name": med["name"],
                            "dose": med["dose"],
                            "scheduled_time": sched_str.strip(),
                            "status": "late",
                            "delay_minutes": round(delay_min, 1),
                        },
                        severity="medium",
                    ))
                else:
                    # Missed
                    ts = self._make_timestamp(date, sched_hour + 1.0)
                    events.append(self._make_event(
                        event_type=EventType.MEDICATION_MISSED.value,
                        timestamp=ts,
                        home_id=home.home_id,
                        resident_id=resident.resident_id,
                        data={
                            "medication_name": med["name"],
                            "dose": med["dose"],
                            "scheduled_time": sched_str.strip(),
                            "status": "missed",
                        },
                        severity="high",
                    ))
                    self._health_state[resident.resident_id]["missed_meds"] += 1

        return events

    def _generate_vital_signs(
        self,
        home: HomeConfig,
        resident: ResidentProfile,
        timestamp: float,
        decline_factor: float,
    ) -> dict:
        """Generate vital-sign readings with condition-aware baselines."""
        # Base vitals
        hr_base = 72 if resident.age < 80 else 78
        sys_base = 130 if "hypertension" in resident.conditions else 120
        dia_base = 82 if "hypertension" in resident.conditions else 78
        spo2_base = 94 if "COPD" in resident.conditions else 97
        temp_base = 36.6
        rr_base = 18 if "COPD" in resident.conditions else 16
        glucose_base = 140 if "diabetes" in resident.conditions else 95

        # Apply decline
        if decline_factor > 1.0:
            sys_base += int((decline_factor - 1.0) * 30)
            spo2_base -= (decline_factor - 1.0) * 3

        # Add natural variation
        heart_rate = int(hr_base + self.rng.normal(0, 5))
        systolic = int(sys_base + self.rng.normal(0, 8))
        diastolic = int(dia_base + self.rng.normal(0, 5))
        spo2 = round(float(min(100, max(85, spo2_base + self.rng.normal(0, 1)))), 1)
        temperature = round(float(temp_base + self.rng.normal(0, 0.3)), 1)
        resp_rate = int(rr_base + self.rng.normal(0, 2))
        glucose = int(glucose_base + self.rng.normal(0, 15)) if "diabetes" in resident.conditions else None

        severity = "low"
        if spo2 < 90 or systolic > 160 or heart_rate > 110 or heart_rate < 50:
            severity = "high"
        elif spo2 < 93 or systolic > 145 or heart_rate > 100:
            severity = "medium"

        data: dict[str, Any] = {
            "heart_rate": heart_rate,
            "blood_pressure": {"systolic": systolic, "diastolic": diastolic},
            "spo2": spo2,
            "temperature": temperature,
            "respiratory_rate": resp_rate,
        }
        if glucose is not None:
            data["glucose"] = glucose

        return self._make_event(
            event_type="vital_signs",
            timestamp=timestamp,
            home_id=home.home_id,
            resident_id=resident.resident_id,
            data=data,
            severity=severity,
        )

    def _generate_checkin(
        self,
        home: HomeConfig,
        resident: ResidentProfile,
        timestamp: float,
        day_number: int,
    ) -> dict:
        """Generate a daily check-in event."""
        state = self._health_state[resident.resident_id]

        # Mood correlates with health state
        if state["cumulative_decline"] > 0.1 or state["fall_count"] > 2:
            mood = ["not great", "a bit tired", "okay"][int(self.rng.integers(0, 3))]
        else:
            mood = _CHECK_IN_MOODS[int(self.rng.integers(0, len(_CHECK_IN_MOODS)))]

        pain_idx = int(self.rng.integers(0, len(_CHECK_IN_PAIN)))
        pain_level = _CHECK_IN_PAIN[pain_idx]
        if "arthritis" in resident.conditions:
            pain_level = min(10, pain_level + int(self.rng.integers(0, 3)))

        sleep = _CHECK_IN_SLEEP[int(self.rng.integers(0, len(_CHECK_IN_SLEEP)))]
        glasses = int(self.rng.integers(2, 9))
        meals = int(self.rng.integers(1, 4))

        wellness_score = self._estimate_wellness(mood, pain_level, sleep, glasses, meals)

        return self._make_event(
            event_type="daily_checkin",
            timestamp=timestamp,
            home_id=home.home_id,
            resident_id=resident.resident_id,
            data={
                "mood": mood,
                "pain_level": pain_level,
                "sleep_quality": sleep,
                "hydration_glasses": glasses,
                "meals_count": meals,
                "wellness_score": wellness_score,
                "medication_taken": self.rng.random() < resident.medication_adherence,
            },
            severity="low" if wellness_score >= 60 else "medium",
        )

    def _generate_fall_event(
        self,
        home: HomeConfig,
        resident: ResidentProfile,
        timestamp: float,
        period: str,
    ) -> dict:
        """Generate a fall event with sensor data references."""
        _fall_rooms = ["bedroom", "hallway", "living_room"]
        room = "bathroom" if "bathroom" in period else _fall_rooms[
            int(self.rng.integers(0, len(_fall_rooms)))
        ]
        immobile_duration = float(self.rng.uniform(0, 300))  # 0-5 min
        severity = "critical" if immobile_duration > 120 else "high"
        event_type = (
            EventType.FALL_WITH_IMMOBILITY.value
            if immobile_duration > 60
            else EventType.FALL.value
        )

        confidence = round(float(self.rng.uniform(0.7, 0.98)), 2)

        return self._make_event(
            event_type=event_type,
            timestamp=timestamp,
            home_id=home.home_id,
            resident_id=resident.resident_id,
            data={
                "room": room,
                "period": period,
                "immobile_duration_s": round(immobile_duration, 1),
                "confidence": confidence,
                "sensors": {
                    "imu": {"impact_force_g": round(float(self.rng.uniform(3, 10)), 1)},
                    "pose": {"com_drop": True},
                    "acoustic": {"impact_detected": self.rng.random() > 0.3},
                },
            },
            severity=severity,
            confidence=confidence,
        )

    @staticmethod
    def _estimate_wellness(
        mood: str,
        pain_level: int,
        sleep: str,
        glasses: int,
        meals: int,
    ) -> int:
        """Quick wellness score estimate for check-in events."""
        score = 50.0
        mood_map = {"good": 20, "happy": 20, "fine": 15, "okay": 10, "a bit tired": 5, "not great": 0}
        score += mood_map.get(mood, 10)
        score += max(0, (10 - pain_level)) * 1.5
        sleep_map = {"well": 10, "like a log": 10, "fine": 7, "okay": 5, "poorly": 0, "terribly": -5}
        score += sleep_map.get(sleep, 5)
        score += min(10, glasses * 1.25)
        score += min(5, meals * 1.5)
        return max(0, min(100, int(score)))

    # ------------------------------------------------------------------
    # Full simulation
    # ------------------------------------------------------------------

    def simulate(
        self,
        days: int = 90,
        output_dir: str | None = None,
        start_date: datetime | None = None,
    ) -> dict:
        """Run full simulation over ``days`` for all configured homes.

        Parameters
        ----------
        days :
            Number of days to simulate.
        output_dir :
            If set, save JSON files per home per day under this directory.
        start_date :
            Starting date for the simulation. Defaults to today minus ``days``.

        Returns
        -------
        dict
            Summary statistics including total events, per-home breakdowns,
            and the full list of all events (unless output_dir is used).
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=days)

        all_events: list[dict] = []
        per_home: dict[str, dict] = {}

        t_start = time.time()

        for home in self.homes:
            home_events: list[dict] = []
            per_home[home.home_id] = {
                "residents": [r.name for r in home.residents],
                "days_simulated": days,
                "events_per_day": [],
            }

            for day_offset in range(days):
                date = start_date + timedelta(days=day_offset)
                day_events = self.simulate_day(home, date)
                home_events.extend(day_events)
                per_home[home.home_id]["events_per_day"].append(len(day_events))

                # Optionally save per-day JSON
                if output_dir:
                    self._save_day(output_dir, home.home_id, date, day_events)

            per_home[home.home_id]["total_events"] = len(home_events)
            all_events.extend(home_events)

        elapsed = time.time() - t_start
        analytics = self.generate_analytics(all_events)

        summary: dict[str, Any] = {
            "simulation": {
                "homes": len(self.homes),
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": (start_date + timedelta(days=days - 1)).isoformat(),
                "total_events": len(all_events),
                "elapsed_seconds": round(elapsed, 2),
                "seed": self.seed,
            },
            "per_home": per_home,
            "analytics": analytics,
        }

        if output_dir:
            summary_path = Path(output_dir) / "simulation_summary.json"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            with open(summary_path, "w") as f:
                json.dump(summary, f, indent=2, default=str)
            logger.info("Simulation summary saved to %s", summary_path)
        else:
            summary["events"] = all_events

        logger.info(
            "Simulation complete: %d homes × %d days = %d events in %.1f s",
            len(self.homes), days, len(all_events), elapsed,
        )
        return summary

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def generate_analytics(self, events: list[dict]) -> dict:
        """Generate analytics from a list of simulated events."""
        if not events:
            return {"total_events": 0}

        event_types: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        events_by_home: dict[str, int] = {}
        falls: list[dict] = []
        missed_meds: list[dict] = []
        wellness_scores: list[int] = []

        for ev in events:
            et = ev.get("event_type", "unknown")
            event_types[et] = event_types.get(et, 0) + 1

            sev = ev.get("severity", "low")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

            hid = ev.get("home_id", "unknown")
            events_by_home[hid] = events_by_home.get(hid, 0) + 1

            if et in (EventType.FALL.value, EventType.FALL_WITH_IMMOBILITY.value):
                falls.append(ev)
            if et == EventType.MEDICATION_MISSED.value:
                missed_meds.append(ev)
            if et == "daily_checkin":
                ws = ev.get("data", {}).get("wellness_score")
                if ws is not None:
                    wellness_scores.append(ws)

        avg_wellness = (
            round(sum(wellness_scores) / len(wellness_scores), 1)
            if wellness_scores else None
        )

        return {
            "total_events": len(events),
            "event_type_counts": event_types,
            "severity_counts": severity_counts,
            "events_by_home": events_by_home,
            "total_falls": len(falls),
            "total_missed_medications": len(missed_meds),
            "average_wellness_score": avg_wellness,
            "health_state": {
                rid: dict(state)
                for rid, state in self._health_state.items()
            },
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _random_hour(self, start: float, end: float) -> float:
        """Pick a random hour between start and end (handles wrap-around)."""
        if end > start:
            return float(self.rng.uniform(start, end))
        # Wrap-around (e.g. 22.0-6.0 crosses midnight)
        total = (24.0 - start) + end
        offset = float(self.rng.uniform(0, total))
        hour = start + offset
        if hour >= 24.0:
            hour -= 24.0
        return hour

    @staticmethod
    def _make_timestamp(date: datetime, hour: float) -> float:
        """Convert a date + fractional hour to a UNIX timestamp (ms)."""
        h = int(hour)
        m = int((hour - h) * 60)
        s = int(((hour - h) * 60 - m) * 60)
        dt = date.replace(hour=min(h, 23), minute=min(m, 59), second=min(s, 59))
        return dt.timestamp() * 1000

    @staticmethod
    def _make_event(
        event_type: str,
        timestamp: float,
        home_id: str,
        resident_id: str,
        data: dict,
        severity: str = "low",
        confidence: float | None = None,
    ) -> dict:
        """Create a standardised event dictionary."""
        ev: dict[str, Any] = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": timestamp,
            "home_id": home_id,
            "resident_id": resident_id,
            "severity": severity,
            "data": data,
            "created_at": timestamp,
        }
        if confidence is not None:
            ev["confidence"] = confidence
        return ev

    def _save_day(
        self,
        output_dir: str,
        home_id: str,
        date: datetime,
        events: list[dict],
    ) -> None:
        """Save one day's events to a JSON file."""
        dir_path = Path(output_dir) / home_id
        dir_path.mkdir(parents=True, exist_ok=True)
        filename = f"{date.strftime('%Y-%m-%d')}.json"
        filepath = dir_path / filename
        with open(filepath, "w") as f:
            json.dump(events, f, indent=2, default=str)
