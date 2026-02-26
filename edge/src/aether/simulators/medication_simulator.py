"""
Medication Event Simulator — Day 5

Simulates NFC tag scans and pressure-sensor events from a MedDock.
Supports scenarios:
  • taken — medication removed and confirmed
  • missed — scheduled time passes with no activity
  • late — medication taken after scheduled window
  • confusion — wrong medication removed
  • confusion_loop — repeated open-close-open pattern (dose confusion)
  • camera_verification — pill camera + gulp sound confirmation
"""
from __future__ import annotations

import time
import uuid
import numpy as np
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

from aether.models.schemas import MedicationEvent, SensorReading, SensorType


# ── Pre-defined medication library for simulation ─────────────

SAMPLE_MEDICATIONS = [
    {"medication_id": "med-001", "medication_name": "Metformin 500mg", "nfc_tag_id": "nfc-a1"},
    {"medication_id": "med-002", "medication_name": "Lisinopril 10mg", "nfc_tag_id": "nfc-b2"},
    {"medication_id": "med-003", "medication_name": "Atorvastatin 20mg", "nfc_tag_id": "nfc-c3"},
    {"medication_id": "med-004", "medication_name": "Aspirin 75mg", "nfc_tag_id": "nfc-d4"},
]


# ── Confusion Loop Detection ─────────────────────────────────

@dataclass
class ConfusionLoopEvent:
    """Describes a dose confusion loop: repeated open-close-open pattern."""
    timestamp: float
    medication_id: str
    medication_name: str
    open_close_cycles: int       # number of open→close cycles
    duration_s: float            # total duration of confusion episode
    compartments_checked: int    # how many different compartments were opened
    resolved: bool               # whether the correct medication was eventually taken
    dock_id: str = "meddock-001"


@dataclass
class ConfusionLoopPattern:
    """Tracks recurring confusion loops over time."""
    resident_id: str
    total_loops: int
    loops_last_7_days: int
    loops_last_30_days: int
    most_confused_medication: str
    avg_cycles_per_loop: float
    escalating: bool             # true if frequency is increasing
    trend: str                   # "stable", "increasing", "decreasing"


@dataclass
class PillVerificationResult:
    """Camera + acoustic pill verification outcome."""
    timestamp: float
    medication_id: str
    medication_name: str
    pill_detected_by_camera: bool
    pill_count_camera: int
    gulp_sound_detected: bool
    confidence: float
    verified: bool               # all checks passed


class MedicationSimulator:
    """Simulate MedDock NFC scans and pressure-sensor events."""

    def __init__(
        self,
        dock_id: str = "meddock-001",
        seed: int = 42,
    ):
        self.dock_id = dock_id
        self.rng = np.random.default_rng(seed)
        self._confusion_loops: List[ConfusionLoopEvent] = []

    # ── Event generators ──────────────────────────────────────

    def generate_taken(
        self,
        medication: dict | None = None,
        delay_s: float = 0.0,
    ) -> MedicationEvent:
        """Medication removed and confirmed within schedule window."""
        med = medication or self.rng.choice(SAMPLE_MEDICATIONS)
        now = time.time()
        scheduled = now - delay_s  # in the past by delay_s
        return MedicationEvent(
            timestamp=now,
            medication_id=med["medication_id"],
            medication_name=med["medication_name"],
            nfc_tag_id=med["nfc_tag_id"],
            removal_detected=True,
            scheduled_time=scheduled,
            dock_id=self.dock_id,
        )

    def generate_missed(
        self,
        medication: dict | None = None,
    ) -> MedicationEvent:
        """Scheduled time passed with no NFC scan (no removal)."""
        med = medication or self.rng.choice(SAMPLE_MEDICATIONS)
        now = time.time()
        # Scheduled 30 min ago — window expired
        scheduled = now - 30 * 60
        return MedicationEvent(
            timestamp=now,
            medication_id=med["medication_id"],
            medication_name=med["medication_name"],
            nfc_tag_id=med["nfc_tag_id"],
            removal_detected=False,
            scheduled_time=scheduled,
            dock_id=self.dock_id,
        )

    def generate_late(
        self,
        medication: dict | None = None,
    ) -> MedicationEvent:
        """Medication taken but outside the normal window (15-45 min late)."""
        med = medication or self.rng.choice(SAMPLE_MEDICATIONS)
        now = time.time()
        delay_min = self.rng.uniform(15, 45)
        scheduled = now - delay_min * 60
        return MedicationEvent(
            timestamp=now,
            medication_id=med["medication_id"],
            medication_name=med["medication_name"],
            nfc_tag_id=med["nfc_tag_id"],
            removal_detected=True,
            scheduled_time=scheduled,
            dock_id=self.dock_id,
        )

    def generate_confusion(self) -> MedicationEvent:
        """Wrong medication removed — NFC tag doesn't match schedule."""
        # Pick two different meds
        meds = list(self.rng.choice(SAMPLE_MEDICATIONS, size=2, replace=False))
        expected = meds[0]
        actual = meds[1]
        now = time.time()
        return MedicationEvent(
            timestamp=now,
            medication_id=expected["medication_id"],
            medication_name=expected["medication_name"],
            nfc_tag_id=actual["nfc_tag_id"],  # wrong tag
            removal_detected=True,
            scheduled_time=now - 5 * 60,
            dock_id=self.dock_id,
        )

    def generate_confusion_loop(
        self,
        medication: dict | None = None,
        cycles: int | None = None,
    ) -> ConfusionLoopEvent:
        """Simulate a dose confusion loop: open-close-open-close pattern.

        This models an elder opening compartments, looking confused, closing,
        and re-opening — the 'dose confusion' pattern from the MedDock spec.
        """
        med = medication or self.rng.choice(SAMPLE_MEDICATIONS)
        n_cycles = cycles or int(self.rng.integers(2, 6))
        duration = float(self.rng.uniform(30, 180))  # 30–180 seconds
        compartments = int(self.rng.integers(1, min(n_cycles + 1, 5)))
        resolved = bool(self.rng.random() > 0.3)  # 70% eventually take it

        loop = ConfusionLoopEvent(
            timestamp=time.time(),
            medication_id=med["medication_id"],
            medication_name=med["medication_name"],
            open_close_cycles=n_cycles,
            duration_s=duration,
            compartments_checked=compartments,
            resolved=resolved,
            dock_id=self.dock_id,
        )
        self._confusion_loops.append(loop)
        return loop

    def generate_pill_verification(
        self,
        medication: dict | None = None,
        verified: bool = True,
    ) -> PillVerificationResult:
        """Simulate camera + gulp sound pill verification."""
        med = medication or self.rng.choice(SAMPLE_MEDICATIONS)
        return PillVerificationResult(
            timestamp=time.time(),
            medication_id=med["medication_id"],
            medication_name=med["medication_name"],
            pill_detected_by_camera=verified,
            pill_count_camera=1 if verified else 0,
            gulp_sound_detected=verified and bool(self.rng.random() > 0.1),
            confidence=float(self.rng.uniform(0.85, 0.98)) if verified else float(self.rng.uniform(0.2, 0.5)),
            verified=verified,
        )

    def analyse_confusion_patterns(
        self,
        resident_id: str = "resident-001",
    ) -> ConfusionLoopPattern:
        """Analyse confusion loop history for pattern detection."""
        loops = self._confusion_loops
        now = time.time()
        last_7d = [l for l in loops if now - l.timestamp <= 7 * 86400]
        last_30d = [l for l in loops if now - l.timestamp <= 30 * 86400]

        # Most confused medication
        med_counts: dict[str, int] = {}
        for l in loops:
            med_counts[l.medication_name] = med_counts.get(l.medication_name, 0) + 1
        most_confused = max(med_counts, key=med_counts.get) if med_counts else "N/A"

        avg_cycles = (
            sum(l.open_close_cycles for l in loops) / len(loops)
            if loops else 0
        )

        # Trend detection: compare last 7d vs previous 7d
        prev_7d = [
            l for l in loops
            if 7 * 86400 < now - l.timestamp <= 14 * 86400
        ]
        if len(last_7d) > len(prev_7d) + 1:
            trend = "increasing"
            escalating = True
        elif len(last_7d) < len(prev_7d) - 1:
            trend = "decreasing"
            escalating = False
        else:
            trend = "stable"
            escalating = False

        return ConfusionLoopPattern(
            resident_id=resident_id,
            total_loops=len(loops),
            loops_last_7_days=len(last_7d),
            loops_last_30_days=len(last_30d),
            most_confused_medication=most_confused,
            avg_cycles_per_loop=round(avg_cycles, 1),
            escalating=escalating,
            trend=trend,
        )

    # ── Daily schedule simulation ─────────────────────────────

    def generate_daily_schedule(
        self,
        adherence_rate: float = 0.85,
    ) -> list[MedicationEvent]:
        """
        Generate a full day's medication events.
        *adherence_rate* controls how many doses are 'taken' vs 'missed/late'.
        """
        events: list[MedicationEvent] = []
        for med in SAMPLE_MEDICATIONS:
            r = self.rng.random()
            if r < adherence_rate * 0.8:
                events.append(self.generate_taken(med))
            elif r < adherence_rate:
                events.append(self.generate_late(med))
            else:
                events.append(self.generate_missed(med))
        return events

    def stream(
        self,
        scenario: str = "taken",
        count: int = 4,
    ) -> Iterator[SensorReading]:
        """Yield SensorReading wrappers for the fusion pipeline."""
        generators = {
            "taken": self.generate_taken,
            "missed": self.generate_missed,
            "late": self.generate_late,
            "confusion": self.generate_confusion,
        }
        gen = generators.get(scenario, self.generate_taken)
        for _ in range(count):
            evt = gen() if scenario == "confusion" else gen()
            yield SensorReading(
                sensor_type=SensorType.MEDICATION,
                timestamp=evt.timestamp,
                sensor_id=self.dock_id,
                data=evt,
            )
