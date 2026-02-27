#!/usr/bin/env python3
"""Quick validation of all AETHER edge modules."""

import sys

def main():
    print("=" * 60)
    print("AETHER Edge Module Validation")
    print("=" * 60)

    # 1. Import all modules
    print("\n--- Importing all modules ---")
    from aether.safety.health_decline import HealthDeclineDetector
    from aether.safety.cognitive_tracker import CognitiveTracker
    from aether.safety.nutrition_tracker import NutritionTracker
    from aether.safety.scam_detector import ScamDetector
    from aether.safety.emotional_wellbeing import EmotionalWellbeingTracker
    from aether.safety.guardrails import AetherGuardrails
    from aether.safety.sleep_tracker import SleepTracker
    from aether.safety.respiratory_tracker import RespiratoryTracker
    from aether.simulators.environmental_simulator import EnvironmentalSimulator
    from aether.simulators.smart_toilet_simulator import SmartToiletSimulator
    from aether.simulators.digital_twin import DigitalTwin
    from aether.simulators.acoustic_simulator import AcousticSimulator
    from aether.simulators.imu_simulator import IMUSimulator
    from aether.simulators.medication_simulator import MedicationSimulator
    from aether.simulators.pose_simulator import PoseSimulator
    from aether.simulators.wifi_csi_simulator import WiFiCSISimulator
    from aether.fusion.fusion_engine import FusionEngine
    from aether.gateway.edge_gateway import EdgeGateway
    from aether.gateway.escalation_timer import EdgeEscalationTimer
    from aether.voice.voice_agent import VoiceAgent
    from aether.voice.checkin_dialogue import CheckInDialogue
    from aether.voice.intent_classifier import IntentClassifier
    from aether.voice.transcriber import AetherTranscriber
    from aether.voice.synthesizer import AetherSynthesizer
    from aether.voice.vad import VoiceActivityDetector
    from aether.voice.wake_word import WakeWordDetector
    print("  All imports OK")

    # 2. Environmental Simulator
    print("\n--- Environmental Simulator ---")
    env_sim = EnvironmentalSimulator()
    reading = env_sim.generate_reading()
    print(f"  Temperature: {reading.temperature_c:.1f}C")
    print(f"  Humidity: {reading.humidity_pct:.0f}%")
    print(f"  AQI: {reading.aqi}")
    assert 10 <= reading.temperature_c <= 45, "Temperature out of range"
    print("  PASS")

    # 3. Smart Toilet Simulator
    print("\n--- Smart Toilet Simulator ---")
    toilet = SmartToiletSimulator()
    session = toilet.generate_reading()
    print(f"  Duration: {session.duration_s}s")
    print(f"  Session type: {session.session_type}")
    assert session.duration_s > 0
    print("  PASS")

    # 4. Cognitive Tracker
    print("\n--- Cognitive Tracker ---")
    cog = CognitiveTracker("R001")
    report = cog.generate_report()
    print(f"  Level: {report.overall_level.value}")
    print(f"  Trend: {report.trend.value}")
    print(f"  Coherence: {report.coherence_avg:.2f}")
    assert report.overall_level is not None
    print("  PASS")

    # 5. Scam Detector
    print("\n--- Scam Detector ---")
    scam = ScamDetector()
    scam.simulate_normal_activity()
    scam.simulate_scam_attempt()
    alert = scam.analyse_recent_activity()
    print(f"  Risk Level: {alert.risk_level.value}")
    print(f"  Risk Score: {alert.risk_score:.2f}")
    print(f"  Triggers: {len(alert.triggers)}")
    assert alert.risk_score > 0
    print("  PASS")

    # 6. Nutrition Tracker
    print("\n--- Nutrition Tracker ---")
    nutri = NutritionTracker("R001")
    nutri.seed_history()
    daily = nutri.generate_daily_report()
    print(f"  Level: {daily.nutrition_level.value}")
    print(f"  Meals: {daily.meals_detected}/{daily.meals_expected}")
    print(f"  Hydration: {daily.hydration_glasses}/{daily.hydration_target} glasses")
    print(f"  Calories: {daily.total_calories}")
    print("  PASS")

    # 7. Emotional Wellbeing
    print("\n--- Emotional Wellbeing ---")
    emo = EmotionalWellbeingTracker("R001")
    emo.seed_healthy_history()
    weekly = emo.generate_weekly_report()
    print(f"  Wellbeing: {weekly.wellbeing_level.value}")
    print(f"  Avg Mood: {weekly.avg_mood:.1f}")
    print(f"  Loneliness Score: {weekly.loneliness_score:.2f}")
    print(f"  Social Interactions: {weekly.social_interactions}")
    print("  PASS")

    # 8. Health Decline Detector
    print("\n--- Health Decline Detector ---")
    health = HealthDeclineDetector("R001")
    health.seed_baseline()
    alert = health.run_full_assessment()
    print(f"  Severity: {alert.severity.value}")
    print(f"  Domains affected: {alert.affected_domains}")
    print("  PASS")

    # 9. Digital Twin
    print("\n--- Digital Twin ---")
    twin = DigitalTwin()  # Uses default homes
    state = twin._health_state
    print(f"  Tracked residents: {len(state)}")
    assert len(state) > 0, "Should have tracked residents"
    print("  PASS")

    # 10. Fusion Engine
    print("\n--- Fusion Engine ---")
    fusion = FusionEngine()
    print(f"  Engine initialized: {fusion is not None}")
    print("  PASS")

    # 11. Voice Pipeline
    print("\n--- Voice Pipeline ---")
    vad = VoiceActivityDetector()
    wwd = WakeWordDetector()
    transcriber = AetherTranscriber()
    synth = AetherSynthesizer()
    classifier = IntentClassifier()

    # Test intent classification
    intent_result = classifier.classify("I need help, I fell down")
    print(f"  Intent: {intent_result.intent.value}, confidence: {intent_result.confidence:.2f}")
    assert intent_result.confidence > 0
    print("  PASS")

    # 12. Guardrails
    print("\n--- Guardrails ---")
    guardrails = AetherGuardrails()
    test_input = "The patient should take aspirin and rest."
    result = guardrails.validate_input(test_input)
    print(f"  Input validation: {result}")
    print("  PASS")

    # 13. Acoustic Simulator
    print("\n--- Acoustic Simulator ---")
    acoustic = AcousticSimulator()
    frames = acoustic.generate()
    print(f"  Generated {len(frames)} acoustic frames")
    print(f"  First frame room: {frames[0].room}")
    assert len(frames) > 0
    print("  PASS")

    # 14. IMU Simulator
    print("\n--- IMU Simulator ---")
    imu = IMUSimulator()
    readings = imu.generate_idle()
    print(f"  Generated {len(readings)} IMU readings")
    print(f"  First accel: x={readings[0].accel_x:.2f} y={readings[0].accel_y:.2f} z={readings[0].accel_z:.2f}")
    assert len(readings) > 0
    print("  PASS")

    # 15. Edge Gateway
    print("\n--- Edge Gateway ---")
    gw = EdgeGateway()
    print(f"  Gateway initialized: {gw is not None}")
    print("  PASS")

    # 16. Checkin Dialogue
    print("\n--- CheckIn Dialogue ---")
    checkin = CheckInDialogue()
    print(f"  Dialogue initialized")
    print("  PASS")

    # 17. Sleep Tracker
    print("\n--- Sleep Tracker ---")
    sleep = SleepTracker("R001")
    session = sleep.simulate_night("normal")
    print(f"  Quality score: {session.sleep_quality_score}")
    print(f"  Total time: {session.total_time_minutes:.0f} min")
    print(f"  Bed exits: {session.bed_exits}")
    assert 0 <= session.sleep_quality_score <= 100, "Quality score out of range"
    assert session.total_time_minutes > 0, "Should have positive sleep time"
    alert = sleep.check_disruption_alert(session)
    print(f"  Disruption alert: {alert.event_type if alert else 'none'}")
    print("  PASS")

    # 18. Respiratory Tracker
    print("\n--- Respiratory Tracker ---")
    resp = RespiratoryTracker("R001")
    report = resp.simulate_day("healthy")
    print(f"  Respiratory score: {report.respiratory_score}")
    print(f"  Cough count: {report.total_cough_count}")
    print(f"  SpO2 desaturations: {report.spo2_desaturation_events}")
    assert 0 <= report.respiratory_score <= 100
    alert = resp.check_alert(report)
    print(f"  Respiratory alert: {alert.event_type if alert else 'none'}")
    print("  PASS")

    # 19. Edge Escalation Timer
    print("\n--- Edge Escalation Timer ---")
    from aether.models.schemas import AetherEvent as _AE, EventType as _ET, Severity as _SV, SensorSource as _SS
    actions = []
    timer = EdgeEscalationTimer(on_action=lambda a: actions.append(a))
    # Create a synthetic event for escalation
    test_event = _AE(
        event_type=_ET.FALL,
        severity=_SV.CRITICAL,
        confidence=0.95,
        home_id="HOME-001",
        resident_id="R001",
        data={"test": True},
        sources=[_SS(sensor_id="imu-001", sensor_type="imu", confidence=0.95)],
    )
    esc_state = timer.start_escalation(test_event)
    print(f"  Escalation started: {esc_state.escalation_id}")
    print(f"  Current tier: {esc_state.current_tier.value}")
    assert len(esc_state.actions) >= 1, "Should have triggered tier 1 action"
    timer.cancel(esc_state.escalation_id, reason="test_complete")
    print(f"  Escalation cancelled")
    print("  PASS")

    # 20. WiFi CSI Simulator
    print("\n--- WiFi CSI Simulator ---")
    csi = WiFiCSISimulator()
    scenario = csi.generate_fall_scenario()
    print(f"  Scenario frames: {len(scenario)}")
    print(f"  First frame room: {scenario[0].room}")
    assert len(scenario) > 0
    detection = csi.analyse_window(scenario)
    print(f"  Fall detected: {detection.fall_detected}")
    print(f"  Confidence: {detection.confidence:.2f}")
    print(f"  Activity: {detection.activity.value}")
    print("  PASS")

    # 21. Medication Confusion Loop
    print("\n--- Medication Confusion Loop ---")
    med_sim = MedicationSimulator()
    loop = med_sim.generate_confusion_loop()
    print(f"  Loop cycles: {loop.open_close_cycles}")
    print(f"  Duration: {loop.duration_s:.1f}s")
    assert loop.open_close_cycles >= 2, "Should have at least 2 cycles"
    patterns = med_sim.analyse_confusion_patterns()
    print(f"  Confusion pattern: total loops = {patterns.total_loops}")
    print("  PASS")

    # 22. Proactive Companion & Multi-language
    print("\n--- Proactive Companion & Multi-language ---")
    voice = VoiceAgent()
    proactive_result = voice.start_proactive_conversation(resident_id="R001", reason="hydration_reminder")
    print(f"  Proactive response text: {proactive_result.response_text[:60]}...")
    assert proactive_result.metadata.get("proactive") is True, "Should be proactive"
    voice.set_language("hi-IN")
    print(f"  Language set to: {voice.current_language}")
    assert voice.current_language == "hi-IN"
    proactive_hi = voice.start_proactive_conversation(resident_id="R001", reason="medication_reminder")
    print(f"  Hindi prompt: {proactive_hi.response_text[:60]}...")
    voice.set_language("en-IN")
    print("  PASS")

    print("\n" + "=" * 60)
    print("ALL 22 MODULE TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    main()
