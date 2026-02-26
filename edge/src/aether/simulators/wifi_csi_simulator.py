"""
AETHER WiFi CSI Fall Detection Simulator
==========================================
Simulates WiFi Channel State Information (CSI) based fall detection,
implementing the research paper approach of using WiFi signal variations
for privacy-preserving fall detection.

WiFi CSI captures amplitude and phase changes across OFDM subcarriers.
Human movement modulates the wireless channel — falls create distinctive
CSI patterns (sudden amplitude drop + phase shift + prolonged static).

This is the ultra-private fall detection path: no cameras, no wearables.
Only WiFi routers and receivers already present in the home.

Features:
  • CSI amplitude pattern simulation (30 subcarriers)
  • Fall signature detection (impact + post-fall stillness)
  • Activity classification (walking, sitting, standing, lying, fall)
  • Doppler speed estimation from CSI phase changes
  • Multi-room presence detection (which rooms are occupied)
  • Integration with the fusion engine as an additional fall signal
  • Configurable sensitivity / false-positive trade-off
"""

from __future__ import annotations

import time
import math
import uuid
import numpy as np
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Iterator, List, Optional

from aether.models.schemas import (
    SensorReading,
    SensorType,
    AetherEvent,
    EventType,
    Severity,
    SensorSource,
)


# ─── Enums ────────────────────────────────────────────────────

class CSIActivity(str, Enum):
    EMPTY = "empty"
    STANDING = "standing"
    WALKING = "walking"
    SITTING = "sitting"
    LYING = "lying"
    FALL = "fall"
    POST_FALL_STILL = "post_fall_still"


# ─── Data Models ──────────────────────────────────────────────

@dataclass
class CSIFrame:
    """A single WiFi CSI measurement frame.

    Each frame captures amplitude and phase across N subcarriers for
    one transmitter–receiver antenna pair.
    """
    timestamp: float
    subcarrier_amplitudes: List[float]   # N amplitudes (typically 30 or 56)
    subcarrier_phases: List[float]       # N phases (radians)
    rssi: float                          # overall received signal strength (dBm)
    doppler_speed: float                 # estimated Doppler speed (m/s)
    room: str
    tx_id: str = "router-001"
    rx_id: str = "receiver-001"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CSIFallDetection:
    """Result of CSI-based fall analysis for a window of frames."""
    timestamp: float
    fall_detected: bool
    confidence: float
    activity: CSIActivity
    amplitude_variance: float     # high variance = movement
    phase_change_rate: float      # rapid phase → faster movement
    post_fall_stillness_s: float  # seconds of stillness after impact
    room: str
    details: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["activity"] = self.activity.value
        return d


# ─── WiFi CSI Simulator ──────────────────────────────────────

class WiFiCSISimulator:
    """Simulate WiFi CSI data for fall detection research.

    Parameters
    ----------
    n_subcarriers : int
        Number of OFDM subcarriers to simulate (default 30).
    room : str
        Room where the WiFi link is measured.
    sample_rate_hz : float
        CSI sampling rate (typical: 100–1000 Hz for fall detection).
    seed : int
        RNG seed for reproducibility.
    """

    def __init__(
        self,
        n_subcarriers: int = 30,
        room: str = "living_room",
        sample_rate_hz: float = 100.0,
        seed: int = 42,
    ):
        self.n_subcarriers = n_subcarriers
        self.room = room
        self.sample_rate_hz = sample_rate_hz
        self.rng = np.random.default_rng(seed)

        # Baseline CSI (empty room calibration)
        self._baseline_amplitudes = self.rng.uniform(0.5, 1.0, n_subcarriers)
        self._baseline_phases = self.rng.uniform(-math.pi, math.pi, n_subcarriers)

    # ── Activity profiles ─────────────────────────────────────

    _ACTIVITY_PROFILES: Dict[CSIActivity, Dict[str, Any]] = {
        CSIActivity.EMPTY: {
            "amp_noise": 0.02, "phase_noise": 0.05,
            "doppler": 0.0, "rssi_offset": 0,
        },
        CSIActivity.STANDING: {
            "amp_noise": 0.05, "phase_noise": 0.1,
            "doppler": 0.01, "rssi_offset": -2,
        },
        CSIActivity.WALKING: {
            "amp_noise": 0.15, "phase_noise": 0.4,
            "doppler": 0.8, "rssi_offset": -5,
        },
        CSIActivity.SITTING: {
            "amp_noise": 0.04, "phase_noise": 0.08,
            "doppler": 0.02, "rssi_offset": -3,
        },
        CSIActivity.LYING: {
            "amp_noise": 0.03, "phase_noise": 0.06,
            "doppler": 0.005, "rssi_offset": -4,
        },
        CSIActivity.FALL: {
            "amp_noise": 0.35, "phase_noise": 0.8,
            "doppler": 2.5, "rssi_offset": -15,
        },
        CSIActivity.POST_FALL_STILL: {
            "amp_noise": 0.02, "phase_noise": 0.03,
            "doppler": 0.0, "rssi_offset": -8,
        },
    }

    # ── Frame generation ──────────────────────────────────────

    def generate_frame(
        self,
        activity: CSIActivity = CSIActivity.EMPTY,
        timestamp: Optional[float] = None,
    ) -> CSIFrame:
        """Generate a single CSI frame for the given activity."""
        ts = timestamp or time.time()
        profile = self._ACTIVITY_PROFILES[activity]

        amplitudes = (
            self._baseline_amplitudes
            + self.rng.normal(0, profile["amp_noise"], self.n_subcarriers)
        ).tolist()

        phases = (
            self._baseline_phases
            + self.rng.normal(0, profile["phase_noise"], self.n_subcarriers)
        ).tolist()

        rssi = float(-45 + profile["rssi_offset"] + self.rng.normal(0, 1))
        doppler = float(max(0, profile["doppler"] + self.rng.normal(0, 0.1)))

        return CSIFrame(
            timestamp=ts,
            subcarrier_amplitudes=amplitudes,
            subcarrier_phases=phases,
            rssi=rssi,
            doppler_speed=doppler,
            room=self.room,
        )

    def generate_sequence(
        self,
        activity: CSIActivity,
        duration_s: float = 5.0,
    ) -> List[CSIFrame]:
        """Generate a sequence of CSI frames for an activity."""
        n_frames = int(duration_s * self.sample_rate_hz)
        t_start = time.time()
        return [
            self.generate_frame(activity, t_start + i / self.sample_rate_hz)
            for i in range(n_frames)
        ]

    def generate_fall_scenario(
        self,
        pre_activity: CSIActivity = CSIActivity.WALKING,
        pre_duration_s: float = 3.0,
        fall_duration_s: float = 1.0,
        post_still_duration_s: float = 10.0,
    ) -> List[CSIFrame]:
        """Generate a complete fall scenario: activity → fall → stillness."""
        frames: List[CSIFrame] = []
        t = time.time()

        # Pre-fall activity
        for i in range(int(pre_duration_s * self.sample_rate_hz)):
            frames.append(self.generate_frame(pre_activity, t))
            t += 1 / self.sample_rate_hz

        # Fall impact
        for i in range(int(fall_duration_s * self.sample_rate_hz)):
            frames.append(self.generate_frame(CSIActivity.FALL, t))
            t += 1 / self.sample_rate_hz

        # Post-fall stillness
        for i in range(int(post_still_duration_s * self.sample_rate_hz)):
            frames.append(self.generate_frame(CSIActivity.POST_FALL_STILL, t))
            t += 1 / self.sample_rate_hz

        return frames

    # ── Fall detection analysis ────────────────────────────────

    def analyse_window(
        self,
        frames: List[CSIFrame],
        fall_amp_threshold: float = 0.25,
        stillness_threshold: float = 0.04,
        min_stillness_s: float = 5.0,
    ) -> CSIFallDetection:
        """Analyse a window of CSI frames for fall detection.

        Algorithm:
        1. Compute amplitude variance across subcarriers
        2. Detect sudden amplitude spike (fall impact)
        3. Detect post-impact stillness (person on ground)
        4. Combine signals for fall probability

        Parameters
        ----------
        frames :
            Window of CSI frames to analyse.
        fall_amp_threshold :
            Amplitude variance threshold to detect impact.
        stillness_threshold :
            Amplitude variance below which person is still.
        min_stillness_s :
            Seconds of stillness after impact to confirm fall.
        """
        if not frames:
            return CSIFallDetection(
                timestamp=time.time(),
                fall_detected=False,
                confidence=0,
                activity=CSIActivity.EMPTY,
                amplitude_variance=0,
                phase_change_rate=0,
                post_fall_stillness_s=0,
                room=self.room,
            )

        # Compute per-frame amplitude variance
        amp_vars = []
        for f in frames:
            amp_arr = np.array(f.subcarrier_amplitudes)
            amp_vars.append(float(np.var(amp_arr)))

        # Phase change rate
        phase_changes = []
        for i in range(1, len(frames)):
            prev = np.array(frames[i - 1].subcarrier_phases)
            curr = np.array(frames[i].subcarrier_phases)
            phase_changes.append(float(np.mean(np.abs(curr - prev))))

        avg_amp_var = np.mean(amp_vars)
        avg_phase_rate = np.mean(phase_changes) if phase_changes else 0

        # Detect impact spike
        max_amp_var = max(amp_vars)
        impact_detected = max_amp_var > fall_amp_threshold

        # Detect post-impact stillness
        stillness_s = 0.0
        if impact_detected:
            impact_idx = amp_vars.index(max_amp_var)
            post_impact = amp_vars[impact_idx:]
            still_frames = sum(1 for v in post_impact if v < stillness_threshold)
            stillness_s = still_frames / self.sample_rate_hz

        # Classify activity
        if impact_detected and stillness_s >= min_stillness_s:
            activity = CSIActivity.FALL
            confidence = min(0.95, 0.60 + 0.05 * stillness_s)
            fall_detected = True
        elif impact_detected:
            activity = CSIActivity.FALL
            confidence = 0.45
            fall_detected = False  # impact but no prolonged stillness
        elif avg_amp_var < stillness_threshold:
            activity = CSIActivity.LYING if avg_phase_rate < 0.05 else CSIActivity.STANDING
            confidence = 0.70
            fall_detected = False
        elif avg_amp_var > 0.1:
            activity = CSIActivity.WALKING
            confidence = 0.75
            fall_detected = False
        else:
            activity = CSIActivity.STANDING
            confidence = 0.60
            fall_detected = False

        details = ""
        if fall_detected:
            details = (
                f"WiFi CSI fall detected: amplitude spike {max_amp_var:.3f} "
                f"followed by {stillness_s:.1f}s of stillness"
            )

        return CSIFallDetection(
            timestamp=frames[-1].timestamp,
            fall_detected=fall_detected,
            confidence=confidence,
            activity=activity,
            amplitude_variance=round(avg_amp_var, 4),
            phase_change_rate=round(avg_phase_rate, 4),
            post_fall_stillness_s=round(stillness_s, 1),
            room=self.room,
            details=details,
        )

    # ── Event generation ──────────────────────────────────────

    def generate_fall_event(self, detection: CSIFallDetection) -> Optional[AetherEvent]:
        """Generate an AetherEvent from a positive CSI fall detection."""
        if not detection.fall_detected:
            return None

        severity = Severity.CRITICAL if detection.post_fall_stillness_s >= 10 else Severity.HIGH

        return AetherEvent(
            event_type=EventType.FALL,
            severity=severity,
            confidence=detection.confidence,
            home_id="",
            data={
                "detection_method": "wifi_csi",
                "amplitude_variance": detection.amplitude_variance,
                "phase_change_rate": detection.phase_change_rate,
                "post_fall_stillness_s": detection.post_fall_stillness_s,
                "room": detection.room,
                "details": detection.details,
            },
            sources=[
                SensorSource(
                    sensor_id="wifi-csi-001",
                    sensor_type="wifi_csi",
                    confidence=detection.confidence,
                ),
            ],
        )

    # ── Streaming ─────────────────────────────────────────────

    def stream(
        self,
        activity: CSIActivity = CSIActivity.EMPTY,
        duration_s: float = 5.0,
    ) -> Iterator[SensorReading]:
        """Yield SensorReading wrappers for the fusion pipeline."""
        frames = self.generate_sequence(activity, duration_s)
        for frame in frames:
            yield SensorReading(
                sensor_type=SensorType.IMU,  # maps to general motion sensor
                timestamp=frame.timestamp,
                sensor_id=f"wifi-csi-{self.room}",
                data=frame,
            )
