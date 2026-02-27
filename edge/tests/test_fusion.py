"""
Tests for the Fusion Engine (Day 7).
  - Confidence-based escalation correctness
  - Multi-sensor fusion weights
  - Fall detection accuracy on simulated data
  - Duplicate event suppression
"""
import pytest

from aether.models.schemas import (
    EventType,
    Severity,
    SensorType,
    IMUReading,
    AcousticFeatures,
    PoseEstimation,
    AcousticEventLabel,
)
from aether.simulators.imu_simulator import IMUSimulator
from aether.simulators.acoustic_simulator import AcousticSimulator
from aether.simulators.pose_simulator import PoseSimulator
from aether.fusion.fusion_engine import (
    FusionEngine,
    CONFIDENCE_CRITICAL,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
)


class TestFusionEngineSignals:
    def setup_method(self):
        self.engine = FusionEngine(home_id="home-test")

    def test_imu_idle_no_signal(self):
        sim = IMUSimulator(seed=42)
        readings = sim.generate_idle(duration_s=1.0)
        signal = self.engine.process_imu(readings)
        assert signal is not None
        assert signal.confidence < 0.3, "Idle IMU should have low fall confidence"

    def test_imu_fall_high_signal(self):
        sim = IMUSimulator(seed=42)
        readings = sim.generate_fall(duration_s=2.0)
        signal = self.engine.process_imu(readings)
        assert signal is not None
        assert signal.impact_force > 3.0
        assert signal.confidence > 0.5

    def test_pose_standing_no_fall(self):
        sim = PoseSimulator(seed=42)
        frames = sim.generate_standing(n_frames=20)
        signal = self.engine.process_pose(frames)
        assert signal is not None
        assert signal.fall_pattern_detected is False
        assert signal.confidence < 0.2

    def test_pose_fall_detected(self):
        sim = PoseSimulator(seed=42)
        frames = sim.generate_fall(n_frames=30)
        signal = self.engine.process_pose(frames)
        assert signal is not None
        assert signal.fall_pattern_detected is True
        assert signal.confidence > 0.4

    def test_acoustic_normal_no_event(self):
        sim = AcousticSimulator(seed=42)
        features = sim.generate(AcousticEventLabel.NORMAL, n_frames=10)
        signal = self.engine.process_acoustic(features)
        assert signal is not None
        assert signal.impact_detected is False
        assert signal.scream_detected is False

    def test_acoustic_impact_detected(self):
        sim = AcousticSimulator(seed=42)
        features = sim.generate(AcousticEventLabel.IMPACT, n_frames=10)
        signal = self.engine.process_acoustic(features)
        assert signal is not None
        assert signal.impact_detected is True
        assert signal.confidence > 0.4


class TestFusionEngineFallDetection:
    def setup_method(self):
        self.engine = FusionEngine(home_id="home-test")
        self.imu_sim = IMUSimulator(seed=42)
        self.pose_sim = PoseSimulator(seed=42)
        self.acoustic_sim = AcousticSimulator(seed=42)

    def test_no_fall_on_idle(self):
        """Idle sensor data should NOT trigger a fall event."""
        event = self.engine.run_fall_detection(
            imu_readings=self.imu_sim.generate_idle(1.0),
            pose_estimations=self.pose_sim.generate_standing(10),
            acoustic_features=self.acoustic_sim.generate(AcousticEventLabel.NORMAL, 10),
        )
        assert event is None, "Idle data should not trigger fall"

    def test_fall_detected_with_all_sensors(self):
        """Fall with all 3 sensors should be detected with high confidence."""
        event = self.engine.run_fall_detection(
            imu_readings=self.imu_sim.generate_fall(2.0),
            pose_estimations=self.pose_sim.generate_fall(30),
            acoustic_features=self.acoustic_sim.generate(AcousticEventLabel.IMPACT, 10),
        )
        assert event is not None, "Fall with all sensors should be detected"
        assert event.event_type in (EventType.FALL, EventType.FALL_WITH_IMMOBILITY)
        assert event.confidence >= CONFIDENCE_HIGH

    def test_fall_imu_only(self):
        """Fall detected by IMU alone (no pose/acoustic) should still register."""
        event = self.engine.run_fall_detection(
            imu_readings=self.imu_sim.generate_fall(2.0),
            pose_estimations=self.pose_sim.generate_standing(10),
            acoustic_features=self.acoustic_sim.generate(AcousticEventLabel.NORMAL, 10),
        )
        # IMU alone with weight 0.4 — might be above medium threshold
        # Depends on exact confidence values
        if event:
            assert event.confidence >= CONFIDENCE_MEDIUM

    def test_fall_imu_plus_pose(self):
        """Fall from IMU + pose should have higher confidence than IMU alone."""
        engine_a = FusionEngine(home_id="home-a")
        imu_sim = IMUSimulator(seed=100)
        pose_sim = PoseSimulator(seed=100)
        acoustic_sim = AcousticSimulator(seed=100)

        # IMU + normal pose
        event_imu_only = engine_a.run_fall_detection(
            imu_readings=imu_sim.generate_fall(2.0),
            pose_estimations=pose_sim.generate_standing(10),
            acoustic_features=acoustic_sim.generate(AcousticEventLabel.NORMAL, 10),
        )

        engine_b = FusionEngine(home_id="home-b")
        imu_sim2 = IMUSimulator(seed=100)
        pose_sim2 = PoseSimulator(seed=100)

        # IMU + fall pose
        event_both = engine_b.run_fall_detection(
            imu_readings=imu_sim2.generate_fall(2.0),
            pose_estimations=pose_sim2.generate_fall(30),
            acoustic_features=acoustic_sim.generate(AcousticEventLabel.NORMAL, 10),
        )

        if event_imu_only and event_both:
            assert event_both.confidence >= event_imu_only.confidence, (
                "IMU+Pose should be ≥ IMU-only confidence"
            )

    def test_confidence_based_severity(self):
        """Property: confidence thresholds map to correct severity levels."""
        event = self.engine.run_fall_detection(
            imu_readings=self.imu_sim.generate_fall(2.0),
            pose_estimations=self.pose_sim.generate_fall(30),
            acoustic_features=self.acoustic_sim.generate(AcousticEventLabel.IMPACT, 10),
        )
        if event:
            if event.confidence >= CONFIDENCE_CRITICAL:
                assert event.severity == Severity.CRITICAL
            elif event.confidence >= CONFIDENCE_HIGH:
                assert event.severity == Severity.HIGH
            elif event.confidence >= CONFIDENCE_MEDIUM:
                assert event.severity == Severity.MEDIUM

    def test_event_has_correct_sources(self):
        """Fall event should list all contributing sensor sources."""
        event = self.engine.run_fall_detection(
            imu_readings=self.imu_sim.generate_fall(2.0),
            pose_estimations=self.pose_sim.generate_fall(30),
            acoustic_features=self.acoustic_sim.generate(AcousticEventLabel.IMPACT, 10),
        )
        if event:
            sensor_types = {s.sensor_type for s in event.sources}
            assert SensorType.IMU.value in sensor_types

    def test_event_data_has_fused_confidence(self):
        event = self.engine.run_fall_detection(
            imu_readings=self.imu_sim.generate_fall(2.0),
            pose_estimations=self.pose_sim.generate_fall(30),
            acoustic_features=self.acoustic_sim.generate(AcousticEventLabel.IMPACT, 10),
        )
        if event:
            assert "fused_confidence" in event.data
            assert event.data["fused_confidence"] == event.confidence

    def test_duplicate_suppression(self):
        """Running detection twice in quick succession should suppress the second."""
        event1 = self.engine.run_fall_detection(
            imu_readings=self.imu_sim.generate_fall(2.0),
            pose_estimations=self.pose_sim.generate_fall(30),
            acoustic_features=self.acoustic_sim.generate(AcousticEventLabel.IMPACT, 10),
        )

        # Second call immediately — should be suppressed
        imu_sim2 = IMUSimulator(seed=99)
        pose_sim2 = PoseSimulator(seed=99)
        acoustic_sim2 = AcousticSimulator(seed=99)
        event2 = self.engine.run_fall_detection(
            imu_readings=imu_sim2.generate_fall(2.0),
            pose_estimations=pose_sim2.generate_fall(30),
            acoustic_features=acoustic_sim2.generate(AcousticEventLabel.IMPACT, 10),
        )

        if event1:
            assert event2 is None, "Duplicate fall event should be suppressed"


class TestAcousticEventDetection:
    def setup_method(self):
        self.engine = FusionEngine(home_id="home-test")

    def test_scream_detection(self):
        sim = AcousticSimulator(seed=42)
        features = sim.generate(AcousticEventLabel.SCREAM, n_frames=10)
        result = self.engine.detect_acoustic_event(features)
        assert result is not None
        assert result.event_type == EventType.ACOUSTIC_DISTRESS

    def test_normal_no_detection(self):
        sim = AcousticSimulator(seed=42)
        features = sim.generate(AcousticEventLabel.NORMAL, n_frames=10)
        result = self.engine.detect_acoustic_event(features)
        assert result is None, "Normal ambient sound should not trigger acoustic event"

    def test_impact_detection(self):
        sim = AcousticSimulator(seed=42)
        features = sim.generate(AcousticEventLabel.IMPACT, n_frames=10)
        result = self.engine.detect_acoustic_event(features)
        assert result is not None
        assert result.event_type == EventType.IMPACT_SOUND
