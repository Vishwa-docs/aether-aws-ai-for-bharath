"""
Integration tests for the AETHER voice pipeline (Day 14).
Tests wake-word detection, VAD, transcription, intent classification,
synthesis, and the full VoiceAgent — all in simulator / fallback mode
(no AWS credentials required).
"""
import math
import struct
import unittest

from aether.voice.wake_word import WakeWordDetector, WakeWordEvent
from aether.voice.vad import VoiceActivityDetector
from aether.voice.intent_classifier import Intent, IntentClassifier, IntentResult
from aether.voice.transcriber import AetherTranscriber, TranscriptionResult
from aether.voice.synthesizer import AetherSynthesizer, SynthesisResult, ALERT_RESPONSES
from aether.voice.voice_agent import VoiceAgent, VoiceResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pcm_frame(amplitude: int, n_samples: int = 512) -> tuple:
    """Return a tuple of 16-bit signed PCM samples at a fixed frequency."""
    return tuple(
        int(amplitude * math.sin(2 * math.pi * 300 * i / 16000))
        for i in range(n_samples)
    )


def _make_pcm_bytes(amplitude: int, duration_ms: int = 30, sample_rate: int = 16000) -> bytes:
    """Return raw 16-bit LE PCM bytes of a sine tone."""
    n_samples = int(sample_rate * duration_ms / 1000)
    samples = [
        int(amplitude * math.sin(2 * math.pi * 300 * i / sample_rate))
        for i in range(n_samples)
    ]
    return struct.pack(f"<{n_samples}h", *samples)


def _make_silence_bytes(duration_ms: int = 30, sample_rate: int = 16000) -> bytes:
    """Return raw 16-bit LE PCM bytes of silence."""
    n_samples = int(sample_rate * duration_ms / 1000)
    return b"\x00" * (n_samples * 2)


# ===========================================================================
# WakeWordDetector
# ===========================================================================

class TestWakeWordDetector(unittest.TestCase):
    """Test the WakeWordDetector in simulator (energy-fallback) mode."""

    def setUp(self):
        self.detector = WakeWordDetector(simulator=True, energy_threshold=1500.0)

    def test_silent_frame_no_detection(self):
        """A silent frame should NOT trigger a wake-word detection."""
        frame = _make_pcm_frame(amplitude=0)
        result = self.detector.process_frame(frame)
        self.assertEqual(result, -1)

    def test_quiet_frame_no_detection(self):
        """A low-energy frame should NOT trigger detection."""
        frame = _make_pcm_frame(amplitude=500)
        result = self.detector.process_frame(frame)
        self.assertEqual(result, -1)

    def test_loud_frame_triggers_detection(self):
        """A high-energy frame should trigger a detection (index >= 0)."""
        frame = _make_pcm_frame(amplitude=10000)
        result = self.detector.process_frame(frame)
        self.assertGreaterEqual(result, 0, "High-energy frame should trigger wake word")

    def test_detection_rotates_keyword_index(self):
        """Successive detections should alternate keyword indices."""
        frame = _make_pcm_frame(amplitude=10000)
        idx1 = self.detector.process_frame(frame)
        idx2 = self.detector.process_frame(frame)
        self.assertGreaterEqual(idx1, 0)
        self.assertGreaterEqual(idx2, 0)
        # With 2 default keywords, they should alternate
        self.assertNotEqual(idx1, idx2)

    def test_default_keywords(self):
        self.assertEqual(len(self.detector._keywords), 2)
        self.assertIn("hey sentinel", self.detector._keywords)
        self.assertIn("hey aether", self.detector._keywords)

    def test_custom_keywords(self):
        det = WakeWordDetector(
            simulator=True,
            keywords=["asha", "namaste"],
        )
        self.assertEqual(det._keywords, ["asha", "namaste"])

    def test_stop_is_safe(self):
        """stop() should be callable even if start() was never called."""
        self.detector.stop()  # should not raise


# ===========================================================================
# VoiceActivityDetector
# ===========================================================================

class TestVoiceActivityDetector(unittest.TestCase):
    """Test the energy-based VAD."""

    def setUp(self):
        self.vad = VoiceActivityDetector(
            energy_threshold=500.0,
            min_speech_ms=250,
            min_silence_ms=700,
        )

    def test_silence_is_not_speech(self):
        frame = _make_silence_bytes(duration_ms=30)
        self.assertFalse(self.vad.is_speech(frame))

    def test_loud_is_speech(self):
        frame = _make_pcm_bytes(amplitude=5000, duration_ms=30)
        self.assertTrue(self.vad.is_speech(frame))

    def test_threshold_boundary(self):
        """Amplitude right at threshold edge should behave deterministically."""
        # Very quiet — should be silence
        quiet = _make_pcm_bytes(amplitude=100, duration_ms=30)
        self.assertFalse(self.vad.is_speech(quiet))

    def test_empty_frame_is_silence(self):
        """Empty bytes should be treated as silence."""
        self.assertFalse(self.vad.is_speech(b""))

    def test_one_byte_is_silence(self):
        """A single byte is too short for a sample; should be silence."""
        self.assertFalse(self.vad.is_speech(b"\x00"))

    def test_detect_utterance_with_speech(self):
        """A stream of loud→silent frames should produce an utterance result."""
        # Build a stream: 20 speech frames + 30 silence frames
        speech = _make_pcm_bytes(amplitude=5000, duration_ms=30)
        silence = _make_silence_bytes(duration_ms=30)
        stream = iter([speech] * 20 + [silence] * 30)

        result = self.vad.detect_utterance(stream, timeout_s=5.0)
        self.assertIsNotNone(result, "Should detect an utterance from speech + silence")
        self.assertGreater(len(result.audio_bytes), 0)
        self.assertGreater(result.duration_ms, 0)

    def test_detect_utterance_timeout_on_silence(self):
        """A stream of pure silence should time out and return None."""
        silence = _make_silence_bytes(duration_ms=30)
        # Use a very short timeout so the test doesn't hang
        result = self.vad.detect_utterance(iter([silence] * 10), timeout_s=0.001)
        self.assertIsNone(result)


# ===========================================================================
# IntentClassifier
# ===========================================================================

class TestIntentClassifier(unittest.TestCase):
    """Test rule-based intent classification."""

    def setUp(self):
        self.clf = IntentClassifier(use_bedrock=False, simulator=True)

    # -- Emergency --
    def test_emergency_help(self):
        r = self.clf.classify("help me I fell down")
        self.assertEqual(r.intent, Intent.EMERGENCY)
        self.assertGreater(r.confidence, 0.5)

    def test_emergency_chest_pain(self):
        r = self.clf.classify("I have chest pain")
        self.assertEqual(r.intent, Intent.EMERGENCY)

    def test_emergency_cant_breathe(self):
        r = self.clf.classify("I can't breathe")
        self.assertEqual(r.intent, Intent.EMERGENCY)

    # -- Cancel alert --
    def test_cancel_alert(self):
        r = self.clf.classify("cancel the alert please")
        self.assertEqual(r.intent, Intent.CANCEL_ALERT)

    def test_cancel_im_fine(self):
        r = self.clf.classify("I'm fine it was a false alarm")
        self.assertEqual(r.intent, Intent.CANCEL_ALERT)

    # -- Confirm OK --
    def test_confirm_ok_yes(self):
        r = self.clf.classify("yes I'm alright")
        self.assertEqual(r.intent, Intent.CONFIRM_OK)

    def test_confirm_ok_all_good(self):
        r = self.clf.classify("all good here")
        self.assertEqual(r.intent, Intent.CONFIRM_OK)

    # -- Call contact --
    def test_call_contact_son(self):
        r = self.clf.classify("call my son please")
        self.assertEqual(r.intent, Intent.CALL_CONTACT)
        self.assertEqual(r.entities.get("contact_name"), "son")

    def test_call_contact_doctor(self):
        r = self.clf.classify("call doctor immediately")
        self.assertEqual(r.intent, Intent.CALL_CONTACT)

    # -- Medication query --
    def test_medication_query(self):
        r = self.clf.classify("when should I take my medicine")
        self.assertEqual(r.intent, Intent.MEDICATION_QUERY)

    def test_medication_dosage(self):
        r = self.clf.classify("what is my next dose")
        self.assertEqual(r.intent, Intent.MEDICATION_QUERY)

    # -- Health query --
    def test_health_query_bp(self):
        r = self.clf.classify("what is my blood pressure")
        self.assertEqual(r.intent, Intent.HEALTH_QUERY)

    def test_health_query_sugar(self):
        r = self.clf.classify("check my sugar level")
        self.assertEqual(r.intent, Intent.HEALTH_QUERY)

    # -- Daily check-in --
    def test_daily_checkin(self):
        r = self.clf.classify("let's do a check in")
        self.assertEqual(r.intent, Intent.DAILY_CHECKIN)

    # -- Set reminder --
    def test_set_reminder(self):
        r = self.clf.classify("set alarm for 8 pm please")
        self.assertEqual(r.intent, Intent.SET_REMINDER)
        self.assertEqual(r.entities.get("time"), "8 pm")

    # -- General / fallback --
    def test_general_gibberish(self):
        r = self.clf.classify("the weather is lovely today")
        self.assertEqual(r.intent, Intent.GENERAL)

    def test_empty_input(self):
        r = self.clf.classify("")
        self.assertEqual(r.intent, Intent.GENERAL)
        self.assertEqual(r.confidence, 0.0)

    def test_whitespace_only(self):
        r = self.clf.classify("   ")
        self.assertEqual(r.intent, Intent.GENERAL)
        self.assertEqual(r.confidence, 0.0)

    def test_none_like_empty(self):
        """Classifier should handle empty-string gracefully."""
        r = self.clf.classify("")
        self.assertIsInstance(r, IntentResult)

    def test_multiple_keyword_boost(self):
        """Multiple keyword hits should boost confidence slightly."""
        single = self.clf.classify("help")
        multi = self.clf.classify("help me emergency I fell")
        self.assertGreaterEqual(multi.confidence, single.confidence)

    def test_raw_text_preserved(self):
        text = "Call my daughter"
        r = self.clf.classify(text)
        self.assertEqual(r.raw_text, text)

    def test_entities_dict_always_present(self):
        r = self.clf.classify("hello world")
        self.assertIsInstance(r.entities, dict)


# ===========================================================================
# AetherTranscriber (local / demo mode)
# ===========================================================================

class TestAetherTranscriber(unittest.TestCase):
    """Test the transcriber in simulator mode (keyword matching fallback)."""

    def setUp(self):
        self.transcriber = AetherTranscriber(simulator=True)

    def test_returns_transcription_result(self):
        audio = _make_pcm_bytes(amplitude=3000, duration_ms=500)
        result = self.transcriber.transcribe_audio(audio)
        self.assertIsInstance(result, TranscriptionResult)
        self.assertGreater(len(result.text), 0)

    def test_confidence_non_zero(self):
        audio = _make_pcm_bytes(amplitude=3000, duration_ms=500)
        result = self.transcriber.transcribe_audio(audio)
        self.assertGreater(result.confidence, 0.0)

    def test_language_code_default(self):
        audio = _make_pcm_bytes(amplitude=3000, duration_ms=500)
        result = self.transcriber.transcribe_audio(audio)
        self.assertEqual(result.language_code, "en-IN")

    def test_cycles_through_demo_transcripts(self):
        """Successive calls should return different demo transcripts."""
        audio = _make_pcm_bytes(amplitude=3000, duration_ms=100)
        t1 = self.transcriber.transcribe_audio(audio)
        t2 = self.transcriber.transcribe_audio(audio)
        self.assertNotEqual(t1.text, t2.text)

    def test_transcribe_local_directly(self):
        result = self.transcriber.transcribe_local(b"\x00" * 1000)
        self.assertIsInstance(result, TranscriptionResult)
        self.assertGreater(len(result.text), 0)

    def test_duration_ms_estimated(self):
        audio = b"\x00" * 3200  # 100 ms at 16 kHz mono
        result = self.transcriber.transcribe_local(audio)
        self.assertGreater(result.duration_ms, 0)


# ===========================================================================
# AetherSynthesizer (simulator mode)
# ===========================================================================

class TestAetherSynthesizer(unittest.TestCase):
    """Test the synthesizer in simulator mode."""

    def setUp(self):
        self.synth = AetherSynthesizer(simulator=True)

    def test_synthesize_returns_result(self):
        result = self.synth.synthesize("Hello, how are you?")
        self.assertIsInstance(result, SynthesisResult)
        self.assertGreater(len(result.audio_bytes), 0)

    def test_audio_length_proportional_to_text(self):
        short = self.synth.synthesize("Hi")
        long = self.synth.synthesize("Good morning, how are you feeling today?")
        self.assertGreater(len(long.audio_bytes), len(short.audio_bytes))

    def test_pcm_format_default(self):
        result = self.synth.synthesize("Test")
        self.assertEqual(result.format, "pcm")

    def test_sample_rate_default(self):
        result = self.synth.synthesize("Test")
        self.assertEqual(result.sample_rate, 16000)

    def test_duration_ms_positive(self):
        result = self.synth.synthesize("Testing duration")
        self.assertGreater(result.duration_ms, 0)

    def test_speak_runs_without_error(self):
        """speak() in simulator mode should not raise."""
        result = self.synth.speak("Test speech")
        self.assertIsInstance(result, SynthesisResult)

    def test_speak_alert_known_key(self):
        result = self.synth.speak_alert("fall_detected")
        self.assertIsInstance(result, SynthesisResult)
        self.assertGreater(len(result.audio_bytes), 0)

    def test_speak_alert_unknown_key(self):
        """Unknown alert key should still produce audio."""
        result = self.synth.speak_alert("nonexistent_alert")
        self.assertIsInstance(result, SynthesisResult)
        self.assertGreater(len(result.audio_bytes), 0)

    def test_synthesize_ssml(self):
        ssml = '<speak>Hello <break time="300ms"/> How are you?</speak>'
        result = self.synth.synthesize_ssml(ssml)
        self.assertIsInstance(result, SynthesisResult)
        self.assertGreater(len(result.audio_bytes), 0)

    def test_play_audio_simulator(self):
        """play_audio in simulator mode should not raise."""
        audio = b"\x00" * 3200
        self.synth.play_audio(audio)  # should just log


# ===========================================================================
# VoiceAgent (simulator mode)
# ===========================================================================

class TestVoiceAgent(unittest.TestCase):
    """Test VoiceAgent initialization and pipeline in simulator mode."""

    def setUp(self):
        self.agent = VoiceAgent(config={"simulator": True})

    def test_initialization(self):
        self.assertIsNotNone(self.agent)
        self.assertTrue(self.agent._simulator)

    def test_process_voice_command_returns_response(self):
        """process_voice_command should return a VoiceResponse."""
        audio = _make_pcm_bytes(amplitude=3000, duration_ms=500)
        response = self.agent.process_voice_command(audio, resident_id="R001")
        self.assertIsInstance(response, VoiceResponse)
        self.assertGreater(len(response.transcript), 0)
        self.assertIsInstance(response.intent, IntentResult)
        self.assertGreater(len(response.response_text), 0)

    def test_process_voice_command_has_audio(self):
        audio = _make_pcm_bytes(amplitude=3000, duration_ms=500)
        response = self.agent.process_voice_command(audio)
        self.assertGreater(len(response.audio_bytes), 0)

    def test_process_voice_command_metadata(self):
        audio = _make_pcm_bytes(amplitude=3000, duration_ms=500)
        response = self.agent.process_voice_command(audio, resident_id="R001")
        self.assertIn("processing_time_ms", response.metadata)
        self.assertIn("transcription_confidence", response.metadata)
        self.assertIn("intent_confidence", response.metadata)
        self.assertEqual(response.metadata["resident_id"], "R001")

    def test_event_callback(self):
        """Event callbacks should be fired during pipeline execution."""
        events = []

        def capture(event_type, payload):
            events.append((event_type, payload))

        self.agent.on_event(capture)
        audio = _make_pcm_bytes(amplitude=3000, duration_ms=500)
        self.agent.process_voice_command(audio)

        event_types = [e[0] for e in events]
        self.assertIn("utterance", event_types)
        self.assertIn("intent", event_types)

    def test_handle_intent_emergency(self):
        result = IntentResult(
            intent=Intent.EMERGENCY,
            confidence=0.95,
            raw_text="help me",
        )
        text = self.agent.handle_intent(result, "R001")
        self.assertGreater(len(text), 0)

    def test_handle_intent_cancel_alert(self):
        result = IntentResult(
            intent=Intent.CANCEL_ALERT,
            confidence=0.90,
            raw_text="cancel",
        )
        text = self.agent.handle_intent(result, "R001")
        self.assertIn("cancel", text.lower())

    def test_handle_intent_general(self):
        result = IntentResult(
            intent=Intent.GENERAL,
            confidence=0.4,
            raw_text="blah blah",
        )
        text = self.agent.handle_intent(result, "R001")
        self.assertGreater(len(text), 0)

    def test_stop_is_safe(self):
        """stop() should be callable without prior start()."""
        self.agent.stop()


if __name__ == "__main__":
    unittest.main()
