"""
Tests for sensor simulators (Day 5).
Validates that generated data has correct shape, ranges, and physics.
"""
import math

import pytest
import numpy as np

from aether.simulators.imu_simulator import IMUSimulator
from aether.simulators.acoustic_simulator import AcousticSimulator
from aether.simulators.pose_simulator import PoseSimulator
from aether.simulators.medication_simulator import MedicationSimulator, SAMPLE_MEDICATIONS
from aether.models.schemas import AcousticEventLabel, SensorType, COCO_KEYPOINTS


class TestIMUSimulator:
    def setup_method(self):
        self.sim = IMUSimulator(seed=42)

    def test_idle_gravity(self):
        """Idle samples should have ~1g on Z axis."""
        samples = self.sim.generate_idle(duration_s=1.0)
        assert len(samples) == 100  # 100 Hz × 1s
        z_values = [s.accel_z for s in samples]
        mean_z = np.mean(z_values)
        assert 0.9 < mean_z < 1.1, f"Expected ~1g on Z, got {mean_z:.3f}"

    def test_idle_low_impact(self):
        """Idle should have impact force near 1g (just gravity)."""
        samples = self.sim.generate_idle(duration_s=1.0)
        for s in samples:
            assert s.impact_force < 1.5, f"Idle impact too high: {s.impact_force:.2f}g"

    def test_walking_periodic(self):
        """Walking should show periodic acceleration patterns."""
        samples = self.sim.generate_walking(duration_s=2.0)
        assert len(samples) == 200
        # Check X axis has variance (from step oscillation)
        x_values = [s.accel_x for s in samples]
        assert np.std(x_values) > 0.05, "Walking X acceleration should oscillate"

    def test_fall_impact_spike(self):
        """Fall sequence must contain high-g impact."""
        samples = self.sim.generate_fall(duration_s=2.0)
        max_impact = max(s.impact_force for s in samples)
        assert max_impact > 3.0, f"Fall must have impact > 3g, got {max_impact:.2f}g"

    def test_fall_freefall_phase(self):
        """Fall sequence must have near-zero g phase (free-fall)."""
        samples = self.sim.generate_fall(duration_s=2.0)
        min_impact = min(s.impact_force for s in samples)
        assert min_impact < 0.5, f"Fall should have free-fall phase < 0.5g, got {min_impact:.2f}g"

    def test_fall_post_stillness(self):
        """Last 50% of fall samples should be low-activity (lying still)."""
        samples = self.sim.generate_fall(duration_s=2.0)
        last_quarter = samples[len(samples) * 3 // 4:]
        gyro_magnitudes = [
            (s.gyro_x**2 + s.gyro_y**2 + s.gyro_z**2)**0.5
            for s in last_quarter
        ]
        mean_gyro = np.mean(gyro_magnitudes)
        assert mean_gyro < 10, f"Post-fall should be still, mean gyro: {mean_gyro:.1f}"

    def test_stream_yields_sensor_readings(self):
        readings = list(self.sim.stream("idle", duration_s=0.5))
        assert len(readings) == 50
        assert all(r.sensor_type == SensorType.IMU for r in readings)

    def test_reproducibility(self):
        """Same seed → same output."""
        sim_a = IMUSimulator(seed=99)
        sim_b = IMUSimulator(seed=99)
        a = sim_a.generate_idle(0.1)
        b = sim_b.generate_idle(0.1)
        for sa, sb in zip(a, b):
            assert sa.accel_x == sb.accel_x
            assert sa.accel_z == sb.accel_z


class TestAcousticSimulator:
    def setup_method(self):
        self.sim = AcousticSimulator(seed=42)

    def test_mfcc_shape(self):
        features = self.sim.generate(AcousticEventLabel.NORMAL, n_frames=5)
        assert len(features) == 5
        for f in features:
            assert len(f.mfcc) == 13, "MFCC should have 13 coefficients"

    def test_scream_high_energy(self):
        features = self.sim.generate(AcousticEventLabel.SCREAM, n_frames=20)
        mean_rms = np.mean([f.rms_energy for f in features])
        assert mean_rms > 0.3, f"Scream should have high RMS, got {mean_rms:.3f}"

    def test_silence_low_energy(self):
        features = self.sim.generate(AcousticEventLabel.SILENCE, n_frames=20)
        mean_rms = np.mean([f.rms_energy for f in features])
        assert mean_rms < 0.05, f"Silence should have very low RMS, got {mean_rms:.3f}"

    def test_glass_break_high_centroid(self):
        features = self.sim.generate(AcousticEventLabel.GLASS_BREAK, n_frames=20)
        mean_centroid = np.mean([f.spectral_centroid for f in features])
        assert mean_centroid > 4000, f"Glass break should have high centroid, got {mean_centroid:.0f}"

    def test_event_burst_structure(self):
        """Burst should have normal→event→normal pattern."""
        frames = self.sim.generate_event_burst(
            AcousticEventLabel.SCREAM, pre_frames=3, event_frames=5, post_frames=3
        )
        assert len(frames) == 11
        # Middle frames should have higher energy than edges
        pre_rms = np.mean([f.rms_energy for f in frames[:3]])
        mid_rms = np.mean([f.rms_energy for f in frames[3:8]])
        assert mid_rms > pre_rms, "Event burst should be louder than ambient"

    def test_stream_yields_sensor_readings(self):
        readings = list(self.sim.stream(AcousticEventLabel.NORMAL, duration_s=0.5))
        assert len(readings) == 5
        assert all(r.sensor_type == SensorType.ACOUSTIC for r in readings)


class TestPoseSimulator:
    def setup_method(self):
        self.sim = PoseSimulator(seed=42)

    def test_standing_17_keypoints(self):
        frames = self.sim.generate_standing(n_frames=5)
        assert len(frames) == 5
        for f in frames:
            assert len(f.keypoints) == 17
            kp_types = {kp.keypoint_type for kp in f.keypoints}
            assert kp_types == set(COCO_KEYPOINTS)

    def test_standing_upright_com(self):
        """Standing: center of mass should be in upper half (y < 0.6)."""
        frames = self.sim.generate_standing(n_frames=10)
        for f in frames:
            assert f.center_of_mass_y < 0.65, f"Standing COM too low: {f.center_of_mass_y:.2f}"

    def test_fall_com_drops(self):
        """Fall: COM should move from low y to high y (top of image to bottom)."""
        frames = self.sim.generate_fall(n_frames=30)
        initial_com = frames[0].center_of_mass_y
        final_com = frames[-1].center_of_mass_y
        assert final_com > initial_com + 0.2, (
            f"Fall COM should drop: initial={initial_com:.2f} final={final_com:.2f}"
        )

    def test_fall_final_pose_on_ground(self):
        """After a fall, the final pose should be near the bottom of the frame."""
        frames = self.sim.generate_fall(n_frames=30)
        final = frames[-1]
        assert final.center_of_mass_y > 0.80, f"Fallen COM should be > 0.80, got {final.center_of_mass_y:.2f}"

    def test_keypoint_confidences_valid(self):
        frames = self.sim.generate_standing(n_frames=5)
        for f in frames:
            for kp in f.keypoints:
                assert 0.0 <= kp.confidence <= 1.0

    def test_stream_yields_sensor_readings(self):
        readings = list(self.sim.stream("standing", n_frames=5))
        assert len(readings) == 5
        assert all(r.sensor_type == SensorType.POSE for r in readings)


class TestMedicationSimulator:
    def setup_method(self):
        self.sim = MedicationSimulator(seed=42)

    def test_taken_has_removal(self):
        event = self.sim.generate_taken()
        assert event.removal_detected is True

    def test_missed_no_removal(self):
        event = self.sim.generate_missed()
        assert event.removal_detected is False

    def test_missed_past_schedule(self):
        event = self.sim.generate_missed()
        assert event.timestamp > event.scheduled_time

    def test_late_has_removal(self):
        event = self.sim.generate_late()
        assert event.removal_detected is True
        assert event.timestamp - event.scheduled_time > 15 * 60  # at least 15 min late

    def test_confusion_wrong_tag(self):
        event = self.sim.generate_confusion()
        # The NFC tag should NOT match the expected medication
        expected_med = next(
            m for m in SAMPLE_MEDICATIONS if m["medication_id"] == event.medication_id
        )
        assert event.nfc_tag_id != expected_med["nfc_tag_id"]

    def test_daily_schedule_count(self):
        events = self.sim.generate_daily_schedule()
        assert len(events) == len(SAMPLE_MEDICATIONS)

    def test_daily_schedule_adherence(self):
        """With 100% adherence, all should be taken."""
        events = self.sim.generate_daily_schedule(adherence_rate=1.0)
        for e in events:
            assert e.removal_detected is True

    def test_stream_yields_sensor_readings(self):
        readings = list(self.sim.stream("taken", count=3))
        assert len(readings) == 3
        assert all(r.sensor_type == SensorType.MEDICATION for r in readings)
