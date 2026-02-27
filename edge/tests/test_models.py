"""
Tests for data model serialisation (Day 4 property test).
Round-trip: AetherEvent → dict → JSON → dict → AetherEvent
"""
import json

import pytest

from aether.models.schemas import (
    AetherEvent,
    EventType,
    Severity,
    SensorSource,
    EscalationInfo,
)


def _make_event(**overrides) -> AetherEvent:
    defaults = dict(
        event_type=EventType.FALL,
        severity=Severity.HIGH,
        confidence=0.85,
        home_id="home-001",
        data={"fused_confidence": 0.85, "imu_impact_force": 5.2},
        sources=[
            SensorSource(sensor_id="wearable-001", sensor_type="imu", confidence=0.9),
        ],
        resident_id="resident-001",
    )
    defaults.update(overrides)
    return AetherEvent(**defaults)


class TestAetherEventSerialization:
    """Property: to_dict → from_dict round-trip preserves all fields."""

    def test_round_trip_basic(self):
        original = _make_event()
        restored = AetherEvent.from_dict(original.to_dict())
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.severity == original.severity
        assert restored.confidence == original.confidence
        assert restored.home_id == original.home_id
        assert restored.data == original.data
        assert restored.resident_id == original.resident_id

    def test_round_trip_json(self):
        original = _make_event()
        json_str = original.to_json()
        data = json.loads(json_str)
        restored = AetherEvent.from_dict(data)
        assert restored.event_type == original.event_type
        assert abs(restored.confidence - original.confidence) < 1e-6

    def test_round_trip_with_escalation(self):
        original = _make_event(
            escalation=EscalationInfo(
                tier=2,
                notified=["user-a", "user-b"],
                acknowledged_by="user-a",
                acknowledged_at=1700000000.0,
            )
        )
        restored = AetherEvent.from_dict(original.to_dict())
        assert restored.escalation is not None
        assert restored.escalation.tier == 2
        assert restored.escalation.acknowledged_by == "user-a"
        assert len(restored.escalation.notified) == 2

    def test_sources_preserved(self):
        original = _make_event(
            sources=[
                SensorSource("wearable-001", "imu", 0.9),
                SensorSource("sentinel-001", "acoustic", 0.75),
                SensorSource("cam-001", "pose", 0.80),
            ]
        )
        restored = AetherEvent.from_dict(original.to_dict())
        assert len(restored.sources) == 3
        assert restored.sources[0].sensor_id == "wearable-001"
        assert restored.sources[2].sensor_type == "pose"

    def test_all_event_types_serializable(self):
        for et in EventType:
            event = _make_event(event_type=et)
            restored = AetherEvent.from_dict(json.loads(event.to_json()))
            assert restored.event_type == et

    def test_all_severity_levels_serializable(self):
        for sev in Severity:
            event = _make_event(severity=sev)
            restored = AetherEvent.from_dict(json.loads(event.to_json()))
            assert restored.severity == sev

    def test_optional_fields_none(self):
        event = _make_event(resident_id=None, escalation=None, evidence_packet_url=None, ttl=None)
        d = event.to_dict()
        assert "resident_id" not in d
        assert "escalation" not in d
        restored = AetherEvent.from_dict(d)
        assert restored.resident_id is None
        assert restored.escalation is None
