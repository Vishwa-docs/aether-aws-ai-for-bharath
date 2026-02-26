"""
Privacy Filter — Day 6

Applies data minimisation before any data leaves the home.
Ensures no raw audio/video is ever transmitted to cloud.

Privacy levels:
  MINIMAL  — event metadata only (type, timestamp, severity)
  STANDARD — metadata + aggregated features (activity level, ambient dB)
  ENHANCED — metadata + detailed features (MFCC, pose keypoints) — requires consent
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from aether.models.schemas import AetherEvent

logger = logging.getLogger(__name__)


class PrivacyLevel(str, Enum):
    MINIMAL = "minimal"
    STANDARD = "standard"
    ENHANCED = "enhanced"


@dataclass
class PrivacySettings:
    level: PrivacyLevel = PrivacyLevel.STANDARD
    acoustic_consent: bool = False
    pose_consent: bool = False
    imu_consent: bool = False
    raw_audio_recording: bool = False


class PrivacyFilter:
    """
    Gate-keeper that strips event payloads down to the configured privacy level
    before the event is transmitted to the cloud.
    """

    def __init__(self, settings: PrivacySettings | None = None):
        self.settings = settings or PrivacySettings()

    def filter_event(self, event: AetherEvent) -> AetherEvent:
        """
        Return a *new* AetherEvent with data stripped according to privacy settings.
        The original event is never mutated.
        """
        filtered_data = self._filter_data(event.data)
        return AetherEvent(
            event_id=event.event_id,
            home_id=event.home_id,
            timestamp=event.timestamp,
            event_type=event.event_type,
            severity=event.severity,
            confidence=event.confidence,
            resident_id=event.resident_id,
            data=filtered_data,
            sources=event.sources,
            escalation=event.escalation,
            evidence_packet_url=event.evidence_packet_url,
            created_at=event.created_at,
            updated_at=event.updated_at,
            ttl=event.ttl,
        )

    def _filter_data(self, data: dict[str, Any]) -> dict[str, Any]:
        level = self.settings.level

        if level == PrivacyLevel.MINIMAL:
            # Only keep non-sensor metadata
            return {
                k: v
                for k, v in data.items()
                if k in (
                    "fused_confidence",
                    "status",
                    "room",
                    "immobility_duration",
                    "voice_check_in_response",
                )
            }

        elif level == PrivacyLevel.STANDARD:
            # Keep aggregated / derived features, drop detailed vectors
            allowed = {
                "fused_confidence",
                "status",
                "room",
                "immobility_duration",
                "voice_check_in_response",
                "imu_impact_force",
                "acoustic_type",
                "removal_detected",
                "medication_name",
                "medication_id",
                "scheduled_time",
                "actual_time",
                "critical",
                "escalated",
            }
            return {k: v for k, v in data.items() if k in allowed}

        elif level == PrivacyLevel.ENHANCED:
            out: dict[str, Any] = {}
            for k, v in data.items():
                # Always block raw audio/video fields
                if k in ("raw_audio", "raw_video", "video_frame"):
                    logger.warning("Blocked raw media field: %s", k)
                    continue
                # Acoustic features need consent
                if k in ("mfcc", "features") and not self.settings.acoustic_consent:
                    continue
                # Pose keypoints need consent
                if k in ("keypoints", "pose_keypoints") and not self.settings.pose_consent:
                    continue
                # IMU details need consent
                if k in ("acceleration", "gyroscope") and not self.settings.imu_consent:
                    continue
                out[k] = v
            return out

        return data  # fallback — return as-is

    # ── Convenience checks ────────────────────────────────────

    def is_raw_media_present(self, data: dict[str, Any]) -> bool:
        """Property test helper — verify no raw media in output."""
        forbidden = {"raw_audio", "raw_video", "video_frame", "audio_samples"}
        return bool(forbidden & set(data.keys()))
