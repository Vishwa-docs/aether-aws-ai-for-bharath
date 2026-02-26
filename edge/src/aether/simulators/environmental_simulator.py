"""
Environmental Sensor Simulator

Generates synthetic readings for home-environment sensors:
  • Temperature (room-by-room, with overheat/freezing anomalies)
  • Humidity (with mold risk detection >70%)
  • Air Quality Index (AQI with PM2.5)
  • Smoke detector (binary with simulated kitchen events)
  • CO (carbon monoxide) levels
  • Light levels (for circadian rhythm tracking)
  • Noise levels (ambient dB for sleep quality)

No real hardware is required — all data is simulated via seeded RNG.
"""
from __future__ import annotations

import math
import time
import numpy as np
from typing import Iterator

from aether.models.schemas import (
    EnvironmentalReading,
    SensorReading,
    SensorType,
)


# ── Normal-range profiles per room ────────────────────────────
# (mean, std) for each metric under normal conditions.

_ROOM_PROFILES: dict[str, dict] = {
    "living_room": {
        "temperature_c": (22.0, 1.0),
        "humidity_pct": (45.0, 5.0),
        "aqi": (35.0, 8.0),
        "pm25": (8.0, 3.0),
        "co_ppm": (0.5, 0.2),
        "light_lux": (300.0, 50.0),
        "noise_db": (35.0, 5.0),
    },
    "bedroom": {
        "temperature_c": (20.0, 0.8),
        "humidity_pct": (42.0, 4.0),
        "aqi": (25.0, 5.0),
        "pm25": (5.0, 2.0),
        "co_ppm": (0.3, 0.1),
        "light_lux": (50.0, 30.0),
        "noise_db": (28.0, 3.0),
    },
    "kitchen": {
        "temperature_c": (23.0, 1.5),
        "humidity_pct": (50.0, 8.0),
        "aqi": (45.0, 12.0),
        "pm25": (12.0, 5.0),
        "co_ppm": (1.0, 0.5),
        "light_lux": (400.0, 60.0),
        "noise_db": (40.0, 8.0),
    },
    "bathroom": {
        "temperature_c": (24.0, 1.2),
        "humidity_pct": (60.0, 10.0),
        "aqi": (30.0, 6.0),
        "pm25": (6.0, 2.5),
        "co_ppm": (0.2, 0.1),
        "light_lux": (200.0, 40.0),
        "noise_db": (32.0, 4.0),
    },
}

# ── Anomaly profiles ─────────────────────────────────────────

_ANOMALY_PROFILES: dict[str, dict] = {
    "overheat": {"temperature_c": (38.0, 2.0)},
    "freezing": {"temperature_c": (5.0, 2.0)},
    "mold_risk": {"humidity_pct": (78.0, 4.0)},
    "poor_air": {"aqi": (160.0, 20.0), "pm25": (55.0, 10.0)},
    "smoke": {"smoke_detected": True, "aqi": (200.0, 30.0), "pm25": (80.0, 15.0)},
    "co_leak": {"co_ppm": (35.0, 10.0)},
    "loud_noise": {"noise_db": (75.0, 8.0)},
}


class EnvironmentalSimulator:
    """Simulate environmental sensor readings for an AETHER-equipped home."""

    def __init__(
        self,
        sensor_id: str = "env-001",
        room: str = "living_room",
        seed: int = 42,
    ):
        self.sensor_id = sensor_id
        self.room = room
        self.rng = np.random.default_rng(seed)

    # ── Internals ─────────────────────────────────────────────

    def _profile(self) -> dict:
        return _ROOM_PROFILES.get(self.room, _ROOM_PROFILES["living_room"])

    def _sample(self, key: str, override: dict | None = None) -> float:
        """Draw a single Gaussian sample for *key*, optionally overridden."""
        if override and key in override:
            spec = override[key]
            if isinstance(spec, tuple):
                return float(self.rng.normal(*spec))
            return float(spec)
        mean, std = self._profile()[key]
        return float(self.rng.normal(mean, std))

    # ── Public API ────────────────────────────────────────────

    def generate_reading(
        self,
        timestamp: float | None = None,
        override: dict | None = None,
    ) -> EnvironmentalReading:
        """Generate a single environmental snapshot.

        Parameters
        ----------
        timestamp : float, optional
            Unix epoch; defaults to now.
        override : dict, optional
            Per-metric overrides ``{metric: (mean, std)}`` or
            ``{metric: scalar}``.
        """
        ts = timestamp or time.time()
        smoke = False
        if override and "smoke_detected" in override:
            smoke = bool(override["smoke_detected"])

        return EnvironmentalReading(
            timestamp=ts,
            room=self.room,
            temperature_c=round(self._sample("temperature_c", override), 1),
            humidity_pct=round(max(0, min(100, self._sample("humidity_pct", override))), 1),
            aqi=round(max(0, self._sample("aqi", override)), 1),
            pm25=round(max(0, self._sample("pm25", override)), 1),
            co_ppm=round(max(0, self._sample("co_ppm", override)), 2),
            smoke_detected=smoke,
            light_lux=round(max(0, self._sample("light_lux", override)), 0),
            noise_db=round(max(0, self._sample("noise_db", override)), 1),
            sensor_id=self.sensor_id,
        )

    def generate_anomaly(self, anomaly_type: str) -> EnvironmentalReading:
        """Generate a reading with a known anomaly injected.

        Supported types: ``overheat``, ``freezing``, ``mold_risk``,
        ``poor_air``, ``smoke``, ``co_leak``, ``loud_noise``.
        """
        profile = _ANOMALY_PROFILES.get(anomaly_type, {})
        return self.generate_reading(override=profile)

    def generate_day_cycle(
        self,
        hours: int = 24,
        interval_min: int = 15,
    ) -> list[EnvironmentalReading]:
        """Generate a full day of readings with circadian light/noise variation.

        Parameters
        ----------
        hours : int
            Number of hours to simulate (default 24).
        interval_min : int
            Minutes between readings (default 15).

        Returns
        -------
        list[EnvironmentalReading]
            One reading per interval with realistic day/night variation.
        """
        readings: list[EnvironmentalReading] = []
        t_start = time.time()
        n_readings = (hours * 60) // interval_min

        for i in range(n_readings):
            ts = t_start + i * interval_min * 60
            hour_of_day = (i * interval_min / 60) % 24

            # Circadian light curve: peaks at midday (~500 lux), near 0 at night
            light_factor = max(0.0, math.sin(math.pi * (hour_of_day - 6) / 12))
            light_base = 20 + 480 * light_factor  # 20-500 lux

            # Noise: quieter at night
            noise_factor = 0.5 + 0.5 * max(0.0, math.sin(math.pi * (hour_of_day - 6) / 14))
            noise_base = 22 + 25 * noise_factor

            # Temperature: slight dip overnight
            temp_factor = 0.5 + 0.5 * math.sin(math.pi * (hour_of_day - 4) / 14)
            temp_base = 19 + 4 * temp_factor

            override: dict = {
                "light_lux": (light_base, 20.0),
                "noise_db": (noise_base, 3.0),
                "temperature_c": (temp_base, 0.5),
            }
            readings.append(self.generate_reading(timestamp=ts, override=override))

        return readings

    def stream(
        self,
        duration_s: float = 60.0,
        interval_s: float = 5.0,
    ) -> Iterator[SensorReading]:
        """Yield SensorReading wrappers for the fusion pipeline."""
        n = int(duration_s / interval_s)
        t_start = time.time()
        for i in range(n):
            reading = self.generate_reading(timestamp=t_start + i * interval_s)
            yield SensorReading(
                sensor_type=SensorType.ENVIRONMENTAL,
                timestamp=reading.timestamp,
                sensor_id=self.sensor_id,
                data=reading,
            )
