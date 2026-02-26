"""
Multi-Sensor Fusion Engine — Day 7

Combines IMU, pose estimation, and acoustic signals to detect events
(primarily falls) with confidence-based scoring.

Confidence thresholds:
  ≥ 0.90  →  Immediate escalation (CRITICAL)
  0.70-0.89  →  Voice check-in "Are you okay?" (HIGH)
  0.50-0.69  →  Log event, monitor (MEDIUM)
  < 0.50  →  Discard as noise

Sensor weights for fall detection:
  IMU:       0.40  (impact force, orientation change)
  Pose:      0.40  (vertical displacement, fallen posture)
  Acoustic:  0.20  (impact sound, scream)
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from aether.models.schemas import (
    AetherEvent,
    EventType,
    Severity,
    SensorSource,
    SensorType,
    IMUReading,
    AcousticFeatures,
    PoseEstimation,
    AcousticEventLabel,
)

logger = logging.getLogger(__name__)


# ── Thresholds ────────────────────────────────────────────────

CONFIDENCE_CRITICAL = 0.90
CONFIDENCE_HIGH = 0.70
CONFIDENCE_MEDIUM = 0.50

IMU_IMPACT_THRESHOLD_G = 3.0      # g-force indicating impact
IMU_FREEFALL_THRESHOLD_G = 0.3    # near-zero g indicating free-fall
POSE_FALL_Y_THRESHOLD = 0.80       # COM Y > this → likely on ground
ACOUSTIC_IMPACT_RMS_THRESHOLD = 0.5  # loud impact sound

# Weights
W_IMU = 0.40
W_POSE = 0.40
W_ACOUSTIC = 0.20


# ── Signal buffers ────────────────────────────────────────────

@dataclass
class IMUSignal:
    """Processed IMU signal for fusion."""
    timestamp: float
    impact_force: float
    has_freefall: bool
    orientation_changed: bool
    confidence: float
    sensor_id: str


@dataclass
class PoseSignal:
    """Processed pose signal for fusion."""
    timestamp: float
    center_of_mass_y: float
    fall_pattern_detected: bool
    confidence: float
    sensor_id: str


@dataclass
class AcousticSignal:
    """Processed acoustic signal for fusion."""
    timestamp: float
    impact_detected: bool
    scream_detected: bool
    rms_energy: float
    confidence: float
    sensor_id: str


# ── Fusion Result ─────────────────────────────────────────────

@dataclass
class FusionResult:
    """Outcome of multi-sensor fusion."""
    event_type: EventType
    confidence: float
    severity: Severity
    imu_signal: Optional[IMUSignal] = None
    pose_signal: Optional[PoseSignal] = None
    acoustic_signal: Optional[AcousticSignal] = None
    timestamp: float = field(default_factory=time.time)


# ── Main Fusion Engine ────────────────────────────────────────

class FusionEngine:
    """
    Stateful multi-sensor fusion engine.

    Feed it sensor readings via process_imu / process_pose / process_acoustic.
    The engine maintains short sliding windows and triggers fusion when
    correlated signals appear within a time window.
    """

    CORRELATION_WINDOW_S = 2.0  # signals within 2s are correlated

    def __init__(self, home_id: str = "home-001"):
        self.home_id = home_id

        # Sliding windows of recent signals
        self._imu_buffer: deque[IMUSignal] = deque(maxlen=50)
        self._pose_buffer: deque[PoseSignal] = deque(maxlen=50)
        self._acoustic_buffer: deque[AcousticSignal] = deque(maxlen=50)

        # Duplicate suppression: set of (event_type, rounded_timestamp)
        self._recent_events: deque[tuple[str, float]] = deque(maxlen=100)
        self._min_event_interval_s = 5.0  # don't fire same event within 5s

    # ── Signal processors ─────────────────────────────────────

    def process_imu(self, readings: list[IMUReading]) -> Optional[IMUSignal]:
        """Analyse a batch of IMU readings and extract a high-level signal."""
        if not readings:
            return None

        max_impact = max(r.impact_force for r in readings)
        has_freefall = any(r.impact_force < IMU_FREEFALL_THRESHOLD_G for r in readings)

        # Orientation change: check if gravity axis shifted significantly
        first = readings[0]
        last = readings[-1]
        gravity_shift = abs(first.accel_z - last.accel_z)
        orientation_changed = gravity_shift > 0.5

        # Confidence: how "fall-like" is this signal?
        imu_conf = 0.0
        if max_impact > IMU_IMPACT_THRESHOLD_G:
            imu_conf = min(1.0, max_impact / 10.0)  # scale up to 10g
        if has_freefall:
            imu_conf = max(imu_conf, 0.6)
        if orientation_changed:
            imu_conf = min(1.0, imu_conf + 0.2)

        signal = IMUSignal(
            timestamp=readings[-1].timestamp,
            impact_force=max_impact,
            has_freefall=has_freefall,
            orientation_changed=orientation_changed,
            confidence=imu_conf,
            sensor_id=readings[0].sensor_id,
        )
        self._imu_buffer.append(signal)
        return signal

    def process_pose(self, estimations: list[PoseEstimation]) -> Optional[PoseSignal]:
        """Analyse a sequence of pose estimations."""
        if not estimations:
            return None

        # Track vertical center of mass movement
        coms = [e.center_of_mass_y for e in estimations]
        final_com = coms[-1]
        initial_com = coms[0] if coms else 0.5

        # Fall pattern: COM moved significantly downward (toward y=1.0 = bottom)
        com_drop = final_com - initial_com
        fall_pattern = final_com > POSE_FALL_Y_THRESHOLD and com_drop > 0.2

        # Confidence from how extreme the drop is
        pose_conf = 0.0
        if fall_pattern:
            pose_conf = min(1.0, com_drop * 2.0)
            # Boost if final pose is very low
            if final_com > 0.85:
                pose_conf = min(1.0, pose_conf + 0.2)

        signal = PoseSignal(
            timestamp=estimations[-1].timestamp,
            center_of_mass_y=final_com,
            fall_pattern_detected=fall_pattern,
            confidence=pose_conf,
            sensor_id=estimations[0].camera_id,
        )
        self._pose_buffer.append(signal)
        return signal

    def process_acoustic(self, features_list: list[AcousticFeatures]) -> Optional[AcousticSignal]:
        """Analyse acoustic features for impact or distress sounds."""
        if not features_list:
            return None

        max_rms = max(f.rms_energy for f in features_list)
        # Simple classifier: high RMS + low spectral centroid → impact
        # High RMS + high centroid → scream
        avg_centroid = sum(f.spectral_centroid for f in features_list) / len(features_list)

        impact_detected = max_rms > ACOUSTIC_IMPACT_RMS_THRESHOLD and avg_centroid < 3000
        scream_detected = max_rms > ACOUSTIC_IMPACT_RMS_THRESHOLD and avg_centroid > 4000

        acoustic_conf = 0.0
        if impact_detected or scream_detected:
            acoustic_conf = min(1.0, max_rms)

        signal = AcousticSignal(
            timestamp=features_list[-1].timestamp,
            impact_detected=impact_detected,
            scream_detected=scream_detected,
            rms_energy=max_rms,
            confidence=acoustic_conf,
            sensor_id=features_list[0].sentinel_id,
        )
        self._acoustic_buffer.append(signal)
        return signal

    # ── Fusion ────────────────────────────────────────────────

    def fuse_fall_signals(
        self,
        imu_signal: Optional[IMUSignal] = None,
        pose_signal: Optional[PoseSignal] = None,
        acoustic_signal: Optional[AcousticSignal] = None,
    ) -> Optional[FusionResult]:
        """
        Combine multi-sensor signals into a single fall confidence score.
        Returns None if confidence is below the MEDIUM threshold.
        """
        confidence = 0.0
        sources_used = 0

        # IMU contribution
        if imu_signal and imu_signal.impact_force > IMU_IMPACT_THRESHOLD_G:
            confidence += W_IMU * imu_signal.confidence
            sources_used += 1

        # Pose contribution
        if pose_signal and pose_signal.fall_pattern_detected:
            confidence += W_POSE * pose_signal.confidence
            sources_used += 1

        # Acoustic contribution
        if acoustic_signal and (acoustic_signal.impact_detected or acoustic_signal.scream_detected):
            confidence += W_ACOUSTIC * acoustic_signal.confidence
            sources_used += 1

        # Boost for multi-sensor corroboration
        if sources_used >= 2:
            confidence = min(1.0, confidence * 1.1)
        if sources_used >= 3:
            confidence = min(1.0, confidence * 1.15)

        # Below threshold → no event
        if confidence < CONFIDENCE_MEDIUM:
            return None

        # Determine severity
        if confidence >= CONFIDENCE_CRITICAL:
            severity = Severity.CRITICAL
            event_type = EventType.FALL_WITH_IMMOBILITY
        elif confidence >= CONFIDENCE_HIGH:
            severity = Severity.HIGH
            event_type = EventType.FALL
        else:
            severity = Severity.MEDIUM
            event_type = EventType.FALL

        return FusionResult(
            event_type=event_type,
            confidence=confidence,
            severity=severity,
            imu_signal=imu_signal,
            pose_signal=pose_signal,
            acoustic_signal=acoustic_signal,
        )

    def detect_acoustic_event(
        self,
        features_list: list[AcousticFeatures],
    ) -> Optional[FusionResult]:
        """
        Standalone acoustic event detection (scream, glass break, etc.)
        without requiring IMU/pose correlation.
        """
        signal = self.process_acoustic(features_list)
        if not signal:
            return None

        if signal.scream_detected:
            return FusionResult(
                event_type=EventType.ACOUSTIC_DISTRESS,
                confidence=signal.confidence,
                severity=Severity.HIGH if signal.confidence >= 0.85 else Severity.MEDIUM,
                acoustic_signal=signal,
            )

        if signal.impact_detected:
            return FusionResult(
                event_type=EventType.IMPACT_SOUND,
                confidence=signal.confidence,
                severity=Severity.MEDIUM,
                acoustic_signal=signal,
            )

        return None

    # ── High-level pipeline ───────────────────────────────────

    def run_fall_detection(
        self,
        imu_readings: list[IMUReading],
        pose_estimations: list[PoseEstimation],
        acoustic_features: list[AcousticFeatures],
    ) -> Optional[AetherEvent]:
        """
        Full pipeline: process all sensor data → fuse → create event.
        Returns an AetherEvent if a fall is detected, or None.
        """
        # 1. Process individual signals
        imu_signal = self.process_imu(imu_readings)
        pose_signal = self.process_pose(pose_estimations)
        acoustic_signal = self.process_acoustic(acoustic_features)

        # 2. Fuse signals
        result = self.fuse_fall_signals(imu_signal, pose_signal, acoustic_signal)
        if not result:
            return None

        # 3. Duplicate suppression
        event_key = (result.event_type.value, round(result.timestamp, 0))
        for prev_key in self._recent_events:
            if (
                prev_key[0] == event_key[0]
                and abs(prev_key[1] - event_key[1]) < self._min_event_interval_s
            ):
                logger.debug("Suppressed duplicate %s event", result.event_type.value)
                return None
        self._recent_events.append(event_key)

        # 4. Build AetherEvent
        sources: list[SensorSource] = []
        event_data: dict = {
            "fused_confidence": result.confidence,
        }

        if result.imu_signal:
            sources.append(SensorSource(
                sensor_id=result.imu_signal.sensor_id,
                sensor_type=SensorType.IMU.value,
                confidence=result.imu_signal.confidence,
            ))
            event_data["imu_impact_force"] = result.imu_signal.impact_force
            event_data["imu_confidence"] = result.imu_signal.confidence

        if result.pose_signal:
            sources.append(SensorSource(
                sensor_id=result.pose_signal.sensor_id,
                sensor_type=SensorType.POSE.value,
                confidence=result.pose_signal.confidence,
            ))
            event_data["pose_fall_detected"] = result.pose_signal.fall_pattern_detected
            event_data["pose_confidence"] = result.pose_signal.confidence

        if result.acoustic_signal:
            sources.append(SensorSource(
                sensor_id=result.acoustic_signal.sensor_id,
                sensor_type=SensorType.ACOUSTIC.value,
                confidence=result.acoustic_signal.confidence,
            ))
            event_data["acoustic_impact"] = result.acoustic_signal.impact_detected
            event_data["acoustic_confidence"] = result.acoustic_signal.confidence

        return AetherEvent(
            event_type=result.event_type,
            severity=result.severity,
            confidence=result.confidence,
            home_id=self.home_id,
            data=event_data,
            sources=sources,
        )

    # ── Correlation helpers ───────────────────────────────────

    def get_correlated_signals(
        self, timestamp: float
    ) -> tuple[Optional[IMUSignal], Optional[PoseSignal], Optional[AcousticSignal]]:
        """Find the most recent signals within the correlation window."""
        window_start = timestamp - self.CORRELATION_WINDOW_S

        imu = None
        for sig in reversed(self._imu_buffer):
            if sig.timestamp >= window_start:
                imu = sig
                break

        pose = None
        for sig in reversed(self._pose_buffer):
            if sig.timestamp >= window_start:
                pose = sig
                break

        acoustic = None
        for sig in reversed(self._acoustic_buffer):
            if sig.timestamp >= window_start:
                acoustic = sig
                break

        return imu, pose, acoustic
