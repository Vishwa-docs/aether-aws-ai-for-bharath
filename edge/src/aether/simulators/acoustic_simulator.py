"""
Acoustic Event Simulator — Day 5

Generates synthetic MFCC and spectral features for various acoustic events:
  • normal (ambient room sound)
  • scream
  • glass_break
  • impact
  • cough
  • doorbell
  • silence
  • choking
  • snoring / sleep_apnea
  • respiratory_distress / wheezing
  • verbal_distress

No raw audio is produced — only feature vectors, matching the privacy-first design.
"""
from __future__ import annotations

import time
import math
import numpy as np
from typing import Iterator

from aether.models.schemas import (
    AcousticFeatures,
    AcousticEventLabel,
    SensorReading,
    SensorType,
)


# ── Feature profiles per acoustic event type ──────────────────
# Each profile gives (mean, std) for the 5 scalar features + MFCC shape.

_PROFILES: dict[AcousticEventLabel, dict] = {
    AcousticEventLabel.NORMAL: {
        "mfcc_mean": 0.0, "mfcc_std": 2.0,
        "centroid": (2000, 200), "rolloff": (4000, 300),
        "zcr": (0.05, 0.01), "rms": (0.02, 0.005),
    },
    AcousticEventLabel.SCREAM: {
        "mfcc_mean": 5.0, "mfcc_std": 4.0,
        "centroid": (4500, 500), "rolloff": (7000, 600),
        "zcr": (0.15, 0.03), "rms": (0.6, 0.1),
    },
    AcousticEventLabel.GLASS_BREAK: {
        "mfcc_mean": 3.0, "mfcc_std": 5.0,
        "centroid": (6000, 800), "rolloff": (8500, 700),
        "zcr": (0.25, 0.05), "rms": (0.7, 0.15),
    },
    AcousticEventLabel.IMPACT: {
        "mfcc_mean": -2.0, "mfcc_std": 3.0,
        "centroid": (1500, 300), "rolloff": (3000, 400),
        "zcr": (0.08, 0.02), "rms": (0.8, 0.12),
    },
    AcousticEventLabel.COUGH: {
        "mfcc_mean": 1.0, "mfcc_std": 3.5,
        "centroid": (3000, 400), "rolloff": (5500, 500),
        "zcr": (0.12, 0.03), "rms": (0.35, 0.08),
    },
    AcousticEventLabel.DOORBELL: {
        "mfcc_mean": 2.0, "mfcc_std": 2.5,
        "centroid": (3500, 300), "rolloff": (6000, 400),
        "zcr": (0.10, 0.02), "rms": (0.4, 0.06),
    },
    AcousticEventLabel.SILENCE: {
        "mfcc_mean": 0.0, "mfcc_std": 0.5,
        "centroid": (500, 100), "rolloff": (1000, 200),
        "zcr": (0.01, 0.003), "rms": (0.005, 0.002),
    },
    AcousticEventLabel.CHOKING: {
        "mfcc_mean": 4.0, "mfcc_std": 5.5,
        "centroid": (3800, 600), "rolloff": (6500, 700),
        "zcr": (0.20, 0.05), "rms": (0.55, 0.12),
    },
    AcousticEventLabel.SNORING: {
        "mfcc_mean": -1.0, "mfcc_std": 2.5,
        "centroid": (800, 150), "rolloff": (2000, 300),
        "zcr": (0.04, 0.01), "rms": (0.15, 0.04),
    },
    AcousticEventLabel.SLEEP_APNEA: {
        "mfcc_mean": -0.5, "mfcc_std": 3.0,
        "centroid": (600, 200), "rolloff": (1500, 300),
        "zcr": (0.02, 0.005), "rms": (0.08, 0.03),
    },
    AcousticEventLabel.RESPIRATORY_DISTRESS: {
        "mfcc_mean": 2.5, "mfcc_std": 4.0,
        "centroid": (3200, 500), "rolloff": (5800, 600),
        "zcr": (0.14, 0.04), "rms": (0.45, 0.10),
    },
    AcousticEventLabel.WHEEZING: {
        "mfcc_mean": 1.5, "mfcc_std": 3.0,
        "centroid": (2800, 400), "rolloff": (5000, 500),
        "zcr": (0.11, 0.03), "rms": (0.25, 0.06),
    },
    AcousticEventLabel.VERBAL_DISTRESS: {
        "mfcc_mean": 4.5, "mfcc_std": 4.5,
        "centroid": (4200, 500), "rolloff": (6800, 600),
        "zcr": (0.16, 0.03), "rms": (0.50, 0.10),
    },
}


class AcousticSimulator:
    """Simulate MFCC / spectral feature data from an Acoustic Sentinel."""

    N_MFCC = 13  # Standard MFCC count

    def __init__(
        self,
        sentinel_id: str = "sentinel-001",
        room: str = "living_room",
        seed: int = 42,
    ):
        self.sentinel_id = sentinel_id
        self.room = room
        self.rng = np.random.default_rng(seed)

    # ── internals ─────────────────────────────────────────────

    def _generate_features(
        self,
        label: AcousticEventLabel,
        timestamp: float | None = None,
    ) -> AcousticFeatures:
        ts = timestamp or time.time()
        profile = _PROFILES[label]

        mfcc = self.rng.normal(
            profile["mfcc_mean"], profile["mfcc_std"], self.N_MFCC
        ).tolist()

        centroid = float(self.rng.normal(*profile["centroid"]))
        rolloff = float(self.rng.normal(*profile["rolloff"]))
        zcr = float(max(0, self.rng.normal(*profile["zcr"])))
        rms = float(max(0, self.rng.normal(*profile["rms"])))

        return AcousticFeatures(
            timestamp=ts,
            mfcc=mfcc,
            spectral_centroid=centroid,
            spectral_rolloff=rolloff,
            zero_crossing_rate=zcr,
            rms_energy=rms,
            sentinel_id=self.sentinel_id,
            room=self.room,
        )

    # ── Public API ────────────────────────────────────────────

    def generate(
        self,
        label: AcousticEventLabel = AcousticEventLabel.NORMAL,
        n_frames: int = 10,
        frame_interval_s: float = 0.1,
    ) -> list[AcousticFeatures]:
        """Generate *n_frames* feature snapshots for the given acoustic event."""
        t_start = time.time()
        return [
            self._generate_features(label, t_start + i * frame_interval_s)
            for i in range(n_frames)
        ]

    def generate_event_burst(
        self,
        label: AcousticEventLabel,
        pre_frames: int = 5,
        event_frames: int = 10,
        post_frames: int = 5,
        frame_interval_s: float = 0.1,
    ) -> list[AcousticFeatures]:
        """
        Create a realistic sequence: normal → event → normal.
        This models how an acoustic event is surrounded by ambient sound.
        """
        frames: list[AcousticFeatures] = []
        t = time.time()

        for i in range(pre_frames):
            frames.append(self._generate_features(AcousticEventLabel.NORMAL, t))
            t += frame_interval_s

        for i in range(event_frames):
            frames.append(self._generate_features(label, t))
            t += frame_interval_s

        for i in range(post_frames):
            frames.append(self._generate_features(AcousticEventLabel.NORMAL, t))
            t += frame_interval_s

        return frames

    def stream(
        self,
        label: AcousticEventLabel = AcousticEventLabel.NORMAL,
        duration_s: float = 5.0,
        frame_interval_s: float = 0.1,
    ) -> Iterator[SensorReading]:
        """Yield SensorReading wrappers for the fusion pipeline."""
        n_frames = int(duration_s / frame_interval_s)
        for feat in self.generate(label, n_frames, frame_interval_s):
            yield SensorReading(
                sensor_type=SensorType.ACOUSTIC,
                timestamp=feat.timestamp,
                sensor_id=self.sentinel_id,
                data=feat,
            )
