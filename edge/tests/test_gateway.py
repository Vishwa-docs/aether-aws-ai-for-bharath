"""
Tests for the Edge Gateway (Day 6).
  - Privacy filter: no raw media in output
  - Offline event queue: enqueue, sync ordering, cleanup
  - Event queue ordering: critical events come first
"""
import json
import os
import tempfile

import pytest

from aether.models.schemas import (
    AetherEvent,
    EventType,
    Severity,
    SensorSource,
)
from aether.gateway.privacy_filter import (
    PrivacyFilter,
    PrivacySettings,
    PrivacyLevel,
)
from aether.gateway.event_queue import OfflineEventQueue


def _make_event(
    severity: Severity = Severity.HIGH,
    event_type: EventType = EventType.FALL,
    confidence: float = 0.85,
    data: dict | None = None,
) -> AetherEvent:
    return AetherEvent(
        event_type=event_type,
        severity=severity,
        confidence=confidence,
        home_id="home-001",
        data=data or {
            "fused_confidence": confidence,
            "imu_impact_force": 5.2,
            "raw_audio": "secret_audio_data",
            "raw_video": "secret_video_data",
            "mfcc": [1, 2, 3],
            "keypoints": [[0.5, 0.5, 0.9]],
            "room": "living_room",
        },
        sources=[
            SensorSource("wearable-001", "imu", 0.9),
        ],
    )


# ─── Privacy Filter ──────────────────────────────────────────

class TestPrivacyFilter:
    def test_minimal_strips_sensor_data(self):
        filt = PrivacyFilter(PrivacySettings(level=PrivacyLevel.MINIMAL))
        event = _make_event()
        filtered = filt.filter_event(event)
        assert "raw_audio" not in filtered.data
        assert "raw_video" not in filtered.data
        assert "mfcc" not in filtered.data
        assert "keypoints" not in filtered.data
        # Should keep metadata
        assert "fused_confidence" in filtered.data
        assert "room" in filtered.data

    def test_standard_keeps_aggregated(self):
        filt = PrivacyFilter(PrivacySettings(level=PrivacyLevel.STANDARD))
        event = _make_event()
        filtered = filt.filter_event(event)
        assert "raw_audio" not in filtered.data
        assert "raw_video" not in filtered.data
        assert "imu_impact_force" in filtered.data
        assert "fused_confidence" in filtered.data

    def test_enhanced_blocks_raw_media(self):
        """Even at ENHANCED level, raw audio/video is blocked."""
        filt = PrivacyFilter(PrivacySettings(
            level=PrivacyLevel.ENHANCED,
            acoustic_consent=True,
            pose_consent=True,
            imu_consent=True,
        ))
        event = _make_event()
        filtered = filt.filter_event(event)
        assert "raw_audio" not in filtered.data
        assert "raw_video" not in filtered.data

    def test_enhanced_without_consent_strips_features(self):
        filt = PrivacyFilter(PrivacySettings(
            level=PrivacyLevel.ENHANCED,
            acoustic_consent=False,
            pose_consent=False,
        ))
        event = _make_event()
        filtered = filt.filter_event(event)
        assert "mfcc" not in filtered.data
        assert "keypoints" not in filtered.data

    def test_enhanced_with_consent_keeps_features(self):
        filt = PrivacyFilter(PrivacySettings(
            level=PrivacyLevel.ENHANCED,
            acoustic_consent=True,
            pose_consent=True,
        ))
        event = _make_event()
        filtered = filt.filter_event(event)
        assert "mfcc" in filtered.data
        assert "keypoints" in filtered.data

    def test_no_raw_media_property(self):
        """Property test: no privacy level should ever pass raw media through."""
        for level in PrivacyLevel:
            filt = PrivacyFilter(PrivacySettings(level=level))
            event = _make_event()
            filtered = filt.filter_event(event)
            assert not filt.is_raw_media_present(filtered.data), (
                f"Raw media leaked at level {level.value}"
            )

    def test_original_event_not_mutated(self):
        filt = PrivacyFilter(PrivacySettings(level=PrivacyLevel.MINIMAL))
        event = _make_event()
        original_data = dict(event.data)
        _ = filt.filter_event(event)
        assert event.data == original_data, "Original event should not be mutated"


# ─── Offline Event Queue ─────────────────────────────────────

class TestOfflineEventQueue:
    @pytest.fixture
    def queue(self, tmp_path):
        db_path = str(tmp_path / "test_events.db")
        q = OfflineEventQueue(db_path=db_path)
        yield q
        q.close()

    def test_enqueue_and_count(self, queue):
        event = _make_event()
        queue.enqueue(event)
        assert queue.count() == 1
        assert queue.count(synced=False) == 1
        assert queue.count(synced=True) == 0

    def test_get_unsynced(self, queue):
        event = _make_event()
        queue.enqueue(event)
        unsynced = queue.get_unsynced()
        assert len(unsynced) == 1
        assert unsynced[0].event_id == event.event_id

    def test_mark_synced(self, queue):
        event = _make_event()
        queue.enqueue(event)
        queue.mark_synced([event.event_id])
        assert queue.count(synced=False) == 0
        assert queue.count(synced=True) == 1

    def test_critical_events_come_first(self, queue):
        """Property: critical events are prioritised during sync."""
        low = _make_event(severity=Severity.LOW, confidence=0.3)
        medium = _make_event(severity=Severity.MEDIUM, confidence=0.5)
        critical = _make_event(severity=Severity.CRITICAL, confidence=0.95)
        high = _make_event(severity=Severity.HIGH, confidence=0.8)

        # Enqueue in reverse priority order
        queue.enqueue(low)
        queue.enqueue(medium)
        queue.enqueue(high)
        queue.enqueue(critical)

        unsynced = queue.get_unsynced()
        assert len(unsynced) == 4
        assert unsynced[0].severity == Severity.CRITICAL
        assert unsynced[1].severity == Severity.HIGH
        assert unsynced[2].severity == Severity.MEDIUM
        assert unsynced[3].severity == Severity.LOW

    def test_ordering_preserved_within_severity(self, queue):
        """Events of the same severity are returned in timestamp order."""
        import time
        e1 = _make_event(severity=Severity.HIGH, confidence=0.8)
        e1.timestamp = 1000.0
        e2 = _make_event(severity=Severity.HIGH, confidence=0.8)
        e2.timestamp = 2000.0
        e3 = _make_event(severity=Severity.HIGH, confidence=0.8)
        e3.timestamp = 3000.0

        queue.enqueue(e3)
        queue.enqueue(e1)
        queue.enqueue(e2)

        unsynced = queue.get_unsynced()
        timestamps = [e.timestamp for e in unsynced]
        assert timestamps == sorted(timestamps), "Same-severity events should be time-ordered"

    def test_limit(self, queue):
        for _ in range(10):
            queue.enqueue(_make_event())
        unsynced = queue.get_unsynced(limit=3)
        assert len(unsynced) == 3

    def test_cleanup(self, queue):
        event = _make_event()
        queue.enqueue(event)
        queue.mark_synced([event.event_id])
        # cleanup with 0 days should delete everything synced
        deleted = queue.cleanup(max_age_days=0)
        assert deleted == 1
        assert queue.count() == 0

    def test_round_trip_event_data(self, queue):
        """Enqueue → get_unsynced preserves full event data."""
        event = _make_event(data={"fused_confidence": 0.92, "room": "bedroom"})
        queue.enqueue(event)
        restored = queue.get_unsynced()[0]
        assert restored.data["fused_confidence"] == 0.92
        assert restored.data["room"] == "bedroom"
        assert restored.event_type == EventType.FALL
