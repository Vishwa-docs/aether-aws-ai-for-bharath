"""
Pose Estimation Simulator — Day 5

Generates synthetic 17-point COCO skeleton keypoints.
Supports activity modes:
  • standing
  • sitting
  • walking
  • falling (standing → in-air → ground)

Only keypoint data is produced — no images — matching the privacy-first design.
"""
from __future__ import annotations

import time
import math
import numpy as np
from typing import Iterator

from aether.models.schemas import (
    PoseKeypoint,
    PoseEstimation,
    SensorReading,
    SensorType,
    COCO_KEYPOINTS,
)


# ── Canonical reference poses (normalized 0-1 image coords) ──

_STANDING_POSE = {
    "nose": (0.50, 0.10),
    "left_eye": (0.48, 0.08), "right_eye": (0.52, 0.08),
    "left_ear": (0.46, 0.09), "right_ear": (0.54, 0.09),
    "left_shoulder": (0.42, 0.20), "right_shoulder": (0.58, 0.20),
    "left_elbow": (0.38, 0.35), "right_elbow": (0.62, 0.35),
    "left_wrist": (0.36, 0.48), "right_wrist": (0.64, 0.48),
    "left_hip": (0.44, 0.52), "right_hip": (0.56, 0.52),
    "left_knee": (0.43, 0.72), "right_knee": (0.57, 0.72),
    "left_ankle": (0.42, 0.92), "right_ankle": (0.58, 0.92),
}

_SITTING_POSE = {
    "nose": (0.50, 0.20),
    "left_eye": (0.48, 0.18), "right_eye": (0.52, 0.18),
    "left_ear": (0.46, 0.19), "right_ear": (0.54, 0.19),
    "left_shoulder": (0.42, 0.30), "right_shoulder": (0.58, 0.30),
    "left_elbow": (0.38, 0.42), "right_elbow": (0.62, 0.42),
    "left_wrist": (0.40, 0.50), "right_wrist": (0.60, 0.50),
    "left_hip": (0.44, 0.52), "right_hip": (0.56, 0.52),
    "left_knee": (0.44, 0.60), "right_knee": (0.56, 0.60),
    "left_ankle": (0.50, 0.68), "right_ankle": (0.56, 0.68),
}

_FALLEN_POSE = {
    "nose": (0.30, 0.85),
    "left_eye": (0.28, 0.84), "right_eye": (0.32, 0.84),
    "left_ear": (0.26, 0.85), "right_ear": (0.34, 0.85),
    "left_shoulder": (0.35, 0.87), "right_shoulder": (0.45, 0.87),
    "left_elbow": (0.30, 0.88), "right_elbow": (0.50, 0.88),
    "left_wrist": (0.25, 0.90), "right_wrist": (0.55, 0.90),
    "left_hip": (0.55, 0.88), "right_hip": (0.65, 0.88),
    "left_knee": (0.60, 0.90), "right_knee": (0.70, 0.90),
    "left_ankle": (0.65, 0.92), "right_ankle": (0.75, 0.92),
}


class PoseSimulator:
    """Simulate 17-point skeleton pose estimation from a camera feed."""

    FPS = 10  # simulated camera frame rate
    FRAME_INTERVAL = 1.0 / FPS

    def __init__(
        self,
        camera_id: str = "cam-001",
        seed: int = 42,
    ):
        self.camera_id = camera_id
        self.rng = np.random.default_rng(seed)

    # ── helpers ───────────────────────────────────────────────

    def _pose_from_template(
        self,
        template: dict[str, tuple[float, float]],
        noise_std: float = 0.01,
        confidence_mean: float = 0.90,
        timestamp: float | None = None,
    ) -> PoseEstimation:
        ts = timestamp or time.time()
        keypoints: list[PoseKeypoint] = []
        for kp_name in COCO_KEYPOINTS:
            base_x, base_y = template[kp_name]
            x = float(base_x + self.rng.normal(0, noise_std))
            y = float(base_y + self.rng.normal(0, noise_std))
            conf = float(max(0, min(1, self.rng.normal(confidence_mean, 0.05))))
            keypoints.append(PoseKeypoint(x=x, y=y, confidence=conf, keypoint_type=kp_name))
        return PoseEstimation(timestamp=ts, keypoints=keypoints, camera_id=self.camera_id)

    def _interpolate_pose(
        self,
        pose_a: dict[str, tuple[float, float]],
        pose_b: dict[str, tuple[float, float]],
        t: float,  # 0→1
    ) -> dict[str, tuple[float, float]]:
        result = {}
        for kp in COCO_KEYPOINTS:
            ax, ay = pose_a[kp]
            bx, by = pose_b[kp]
            result[kp] = (ax + (bx - ax) * t, ay + (by - ay) * t)
        return result

    # ── Public API ────────────────────────────────────────────

    def generate_standing(self, n_frames: int = 30) -> list[PoseEstimation]:
        t_start = time.time()
        return [
            self._pose_from_template(_STANDING_POSE, timestamp=t_start + i * self.FRAME_INTERVAL)
            for i in range(n_frames)
        ]

    def generate_sitting(self, n_frames: int = 30) -> list[PoseEstimation]:
        t_start = time.time()
        return [
            self._pose_from_template(_SITTING_POSE, timestamp=t_start + i * self.FRAME_INTERVAL)
            for i in range(n_frames)
        ]

    def generate_fall(self, n_frames: int = 30) -> list[PoseEstimation]:
        """
        Simulate a fall: standing → transitioning → lying on floor.
        First third: standing, middle third: transition, final third: fallen.
        """
        t_start = time.time()
        frames: list[PoseEstimation] = []
        third = n_frames // 3

        for i in range(third):
            frames.append(
                self._pose_from_template(
                    _STANDING_POSE,
                    noise_std=0.015,  # slightly more jitter
                    timestamp=t_start + i * self.FRAME_INTERVAL,
                )
            )

        for i in range(third):
            t_lerp = i / max(third - 1, 1)
            blended = self._interpolate_pose(_STANDING_POSE, _FALLEN_POSE, t_lerp)
            # Confidence drops during transition
            conf = 0.90 - 0.2 * t_lerp
            frames.append(
                self._pose_from_template(
                    blended,
                    noise_std=0.03,
                    confidence_mean=conf,
                    timestamp=t_start + (third + i) * self.FRAME_INTERVAL,
                )
            )

        for i in range(n_frames - 2 * third):
            frames.append(
                self._pose_from_template(
                    _FALLEN_POSE,
                    noise_std=0.005,  # very still
                    confidence_mean=0.85,
                    timestamp=t_start + (2 * third + i) * self.FRAME_INTERVAL,
                )
            )

        return frames

    def generate_walking(self, n_frames: int = 30) -> list[PoseEstimation]:
        """Walking — slight periodic sway in keypoints."""
        t_start = time.time()
        frames: list[PoseEstimation] = []
        for i in range(n_frames):
            phase = i / self.FPS * 2 * math.pi * 2.0  # 2 Hz step
            sway = 0.02 * math.sin(phase)
            template = {}
            for kp_name, (bx, by) in _STANDING_POSE.items():
                template[kp_name] = (bx + sway, by + 0.005 * abs(math.sin(phase)))
            frames.append(
                self._pose_from_template(
                    template,
                    noise_std=0.01,
                    timestamp=t_start + i * self.FRAME_INTERVAL,
                )
            )
        return frames

    def stream(
        self,
        mode: str = "standing",
        n_frames: int = 30,
    ) -> Iterator[SensorReading]:
        """Yield SensorReading wrappers for the fusion pipeline."""
        generators = {
            "standing": self.generate_standing,
            "sitting": self.generate_sitting,
            "walking": self.generate_walking,
            "fall": self.generate_fall,
        }
        gen = generators.get(mode, self.generate_standing)
        for pose in gen(n_frames):
            yield SensorReading(
                sensor_type=SensorType.POSE,
                timestamp=pose.timestamp,
                sensor_id=self.camera_id,
                data=pose,
            )
