"""
IMU Sensor Simulator — Day 5

Generates realistic 6-axis accelerometer + gyroscope data at 100 Hz.
Supports multiple activity modes:
  • idle (sitting/lying)
  • walking
  • fall (impact + post-fall stillness)

The simulator uses a seeded RNG for reproducibility.
"""
from __future__ import annotations

import time
import math
import numpy as np
from typing import Iterator

from aether.models.schemas import IMUReading, SensorReading, SensorType


class IMUSimulator:
    """Simulate a wearable IMU (pendant / wristband)."""

    SAMPLING_RATE_HZ = 100
    SAMPLE_INTERVAL = 1.0 / SAMPLING_RATE_HZ

    def __init__(
        self,
        sensor_id: str = "wearable-001",
        seed: int = 42,
    ):
        self.sensor_id = sensor_id
        self.rng = np.random.default_rng(seed)
        self._time_offset = time.time()

    # ── Activity profiles ─────────────────────────────────────

    def _idle_sample(self, t: float) -> IMUReading:
        """Sitting or lying — gravity on Z, tiny noise."""
        noise = self.rng.normal(0, 0.02, 6)
        return IMUReading(
            timestamp=t,
            accel_x=noise[0],
            accel_y=noise[1],
            accel_z=1.0 + noise[2],  # gravity
            gyro_x=noise[3] * 5,
            gyro_y=noise[4] * 5,
            gyro_z=noise[5] * 5,
            sensor_id=self.sensor_id,
        )

    def _walking_sample(self, t: float) -> IMUReading:
        """Walking — periodic acceleration with ~2 Hz step frequency."""
        phase = (t * 2 * math.pi * 2.0)  # 2 Hz steps
        step_accel = 0.3 * math.sin(phase)
        noise = self.rng.normal(0, 0.05, 6)
        return IMUReading(
            timestamp=t,
            accel_x=step_accel + noise[0],
            accel_y=0.1 * math.cos(phase) + noise[1],
            accel_z=1.0 + 0.15 * abs(math.sin(phase)) + noise[2],
            gyro_x=10 * math.sin(phase) + noise[3] * 10,
            gyro_y=5 * math.cos(phase) + noise[4] * 10,
            gyro_z=noise[5] * 5,
            sensor_id=self.sensor_id,
        )

    def _fall_sequence(self, t_start: float, duration: float = 2.0) -> list[IMUReading]:
        """
        Generate a complete fall event:
          0.0-0.3s  — pre-fall instability
          0.3-0.5s  — free fall (near-zero g)
          0.5-0.7s  — impact (5-10g spike)
          0.7-2.0s  — post-fall stillness
        """
        samples: list[IMUReading] = []
        n_samples = int(duration * self.SAMPLING_RATE_HZ)

        for i in range(n_samples):
            t = t_start + i * self.SAMPLE_INTERVAL
            elapsed = i * self.SAMPLE_INTERVAL

            if elapsed < 0.3:
                # Pre-fall: instability / stumble
                noise = self.rng.normal(0, 0.15, 6)
                samples.append(IMUReading(
                    timestamp=t,
                    accel_x=0.5 * math.sin(elapsed * 20) + noise[0],
                    accel_y=0.3 * math.cos(elapsed * 15) + noise[1],
                    accel_z=0.8 + noise[2],
                    gyro_x=50 * math.sin(elapsed * 10) + noise[3] * 20,
                    gyro_y=30 * math.cos(elapsed * 10) + noise[4] * 20,
                    gyro_z=noise[5] * 10,
                    sensor_id=self.sensor_id,
                ))
            elif elapsed < 0.5:
                # Free fall: near-zero g
                noise = self.rng.normal(0, 0.05, 6)
                samples.append(IMUReading(
                    timestamp=t,
                    accel_x=noise[0],
                    accel_y=noise[1],
                    accel_z=0.05 + noise[2],  # near zero
                    gyro_x=100 + noise[3] * 30,
                    gyro_y=80 + noise[4] * 30,
                    gyro_z=noise[5] * 20,
                    sensor_id=self.sensor_id,
                ))
            elif elapsed < 0.7:
                # Impact: 5-10g spike
                impact_phase = (elapsed - 0.5) / 0.2  # 0→1
                peak = 5.0 + self.rng.uniform(0, 5)  # 5-10g
                impact_g = peak * math.sin(impact_phase * math.pi)
                noise = self.rng.normal(0, 0.3, 6)
                samples.append(IMUReading(
                    timestamp=t,
                    accel_x=impact_g * 0.3 + noise[0],
                    accel_y=impact_g * 0.2 + noise[1],
                    accel_z=impact_g + noise[2],
                    gyro_x=noise[3] * 50,
                    gyro_y=noise[4] * 50,
                    gyro_z=noise[5] * 30,
                    sensor_id=self.sensor_id,
                ))
            else:
                # Post-fall: very still (lying on ground)
                noise = self.rng.normal(0, 0.01, 6)
                # Gravity shifted (lying sideways)
                samples.append(IMUReading(
                    timestamp=t,
                    accel_x=0.7 + noise[0],
                    accel_y=noise[1],
                    accel_z=0.7 + noise[2],
                    gyro_x=noise[3] * 2,
                    gyro_y=noise[4] * 2,
                    gyro_z=noise[5] * 2,
                    sensor_id=self.sensor_id,
                ))
        return samples

    # ── Public API ────────────────────────────────────────────

    def generate_idle(self, duration_s: float = 5.0) -> list[IMUReading]:
        """Generate idle (sitting) IMU data."""
        t_start = time.time()
        n = int(duration_s * self.SAMPLING_RATE_HZ)
        return [self._idle_sample(t_start + i * self.SAMPLE_INTERVAL) for i in range(n)]

    def generate_walking(self, duration_s: float = 5.0) -> list[IMUReading]:
        """Generate walking IMU data."""
        t_start = time.time()
        n = int(duration_s * self.SAMPLING_RATE_HZ)
        return [self._walking_sample(t_start + i * self.SAMPLE_INTERVAL) for i in range(n)]

    def generate_fall(self, duration_s: float = 2.0) -> list[IMUReading]:
        """Generate a complete fall event (instability → free-fall → impact → stillness)."""
        return self._fall_sequence(time.time(), duration_s)

    def stream(self, mode: str = "idle", duration_s: float = 10.0) -> Iterator[SensorReading]:
        """Yield SensorReading wrappers suitable for the fusion pipeline."""
        generators = {
            "idle": self.generate_idle,
            "walking": self.generate_walking,
            "fall": self.generate_fall,
        }
        gen = generators.get(mode, self.generate_idle)
        for reading in gen(duration_s):
            yield SensorReading(
                sensor_type=SensorType.IMU,
                timestamp=reading.timestamp,
                sensor_id=self.sensor_id,
                data=reading,
            )
