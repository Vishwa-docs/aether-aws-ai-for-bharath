"""
AETHER Edge Voice Pipeline – Text-to-Speech Synthesizer
========================================================
Wraps AWS Polly for high-quality neural TTS with an Indian English voice
(``Kajal`` by default).  Includes pre-built responses for common care
alerts and a simulated playback path for demo mode.

Runs on Raspberry Pi 5 / Jetson Orin Nano – audio playback is routed to
the local speaker via PyAudio (or simulated in demo mode).
"""

from __future__ import annotations

import io
import logging
import os
import struct
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger("aether.voice.synthesizer")

SIMULATOR_MODE = os.getenv("SIMULATOR_MODE", "true").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class SynthesisResult:
    """Returned by synthesis methods."""

    audio_bytes: bytes
    format: str = "pcm"       # "pcm" | "mp3" | "ogg_vorbis"
    sample_rate: int = 16000
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Pre-built alert responses
# ---------------------------------------------------------------------------

ALERT_RESPONSES: Dict[str, str] = {
    "fall_detected": (
        "I noticed a possible fall. Are you okay? "
        "Please say 'I'm fine' or 'help me' so I know how to help."
    ),
    "medication_reminder": (
        "It's time to take your medication. "
        "Please confirm once you've taken it."
    ),
    "medication_missed": (
        "It looks like you may have missed your medication. "
        "Would you like me to remind you again in 15 minutes?"
    ),
    "vital_alert": (
        "I've detected an unusual reading in your vitals. "
        "How are you feeling right now?"
    ),
    "emergency": (
        "I'm contacting emergency services and your designated caregiver now. "
        "Please stay calm and try not to move."
    ),
    "daily_checkin_greeting": (
        "Good morning! Let's do a quick check-in. How are you feeling today?"
    ),
    "cancel_confirmed": (
        "Okay, the alert has been cancelled. I'm glad you're alright."
    ),
    "goodbye": (
        "Take care! I'm always here if you need anything."
    ),
}


# ---------------------------------------------------------------------------
# Synthesizer
# ---------------------------------------------------------------------------

class AetherSynthesizer:
    """Text-to-speech engine backed by AWS Polly.

    Parameters
    ----------
    region_name : str
        AWS region for the Polly client.
    default_voice_id : str
        Default Polly voice.  ``Kajal`` supports Indian English neural TTS.
    default_engine : str
        ``"neural"`` (recommended) or ``"standard"``.
    default_language_code : str
        BCP-47 language code.
    simulator : bool | None
        Use simulated audio instead of real Polly calls.
    """

    def __init__(
        self,
        region_name: Optional[str] = None,
        default_voice_id: str = "Kajal",
        default_engine: str = "neural",
        default_language_code: str = "en-IN",
        simulator: Optional[bool] = None,
    ) -> None:
        self._region = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self._default_voice = default_voice_id
        self._default_engine = default_engine
        self._default_language = default_language_code
        self._simulator = simulator if simulator is not None else SIMULATOR_MODE

        self._polly_client = None
        if not self._simulator:
            try:
                import boto3
                self._polly_client = boto3.client("polly", region_name=self._region)
                logger.info("AWS Polly client initialised (region=%s)", self._region)
            except Exception as exc:
                logger.warning("Could not create Polly client – falling back to simulator: %s", exc)
                self._simulator = True

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        engine: Optional[str] = None,
        language_code: Optional[str] = None,
        output_format: str = "pcm",
        sample_rate: int = 16000,
    ) -> SynthesisResult:
        """Synthesize plain text to audio.

        Parameters
        ----------
        text :
            The text to speak.
        voice_id :
            Polly voice ID. Defaults to ``Kajal``.
        engine :
            ``"neural"`` or ``"standard"``.
        language_code :
            BCP-47 code.
        output_format :
            ``"pcm"``, ``"mp3"``, or ``"ogg_vorbis"``.
        sample_rate :
            Sample rate (Hz) for PCM output.

        Returns
        -------
        SynthesisResult
        """
        voice_id = voice_id or self._default_voice
        engine = engine or self._default_engine
        language_code = language_code or self._default_language

        if self._simulator:
            return self._simulate_synthesis(text, output_format, sample_rate)

        t_start = time.time()
        resp = self._polly_client.synthesize_speech(
            Engine=engine,
            LanguageCode=language_code,
            OutputFormat=output_format,
            SampleRate=str(sample_rate) if output_format == "pcm" else "22050",
            Text=text,
            TextType="text",
            VoiceId=voice_id,
        )

        audio_bytes = resp["AudioStream"].read()
        duration_ms = (time.time() - t_start) * 1000

        logger.info(
            "Polly synthesised %d bytes (%s, %s, %.0f ms)",
            len(audio_bytes),
            voice_id,
            output_format,
            duration_ms,
        )

        return SynthesisResult(
            audio_bytes=audio_bytes,
            format=output_format,
            sample_rate=sample_rate,
            duration_ms=duration_ms,
        )

    def synthesize_ssml(
        self,
        ssml: str,
        voice_id: Optional[str] = None,
        engine: Optional[str] = None,
        language_code: Optional[str] = None,
        output_format: str = "pcm",
        sample_rate: int = 16000,
    ) -> SynthesisResult:
        """Synthesize SSML-formatted text to audio."""
        voice_id = voice_id or self._default_voice
        engine = engine or self._default_engine
        language_code = language_code or self._default_language

        if self._simulator:
            # Strip SSML tags for simulation
            import re
            plain = re.sub(r"<[^>]+>", "", ssml)
            return self._simulate_synthesis(plain, output_format, sample_rate)

        t_start = time.time()
        resp = self._polly_client.synthesize_speech(
            Engine=engine,
            LanguageCode=language_code,
            OutputFormat=output_format,
            SampleRate=str(sample_rate) if output_format == "pcm" else "22050",
            Text=ssml,
            TextType="ssml",
            VoiceId=voice_id,
        )

        audio_bytes = resp["AudioStream"].read()
        duration_ms = (time.time() - t_start) * 1000

        logger.info(
            "Polly SSML synthesised %d bytes (%s, %.0f ms)",
            len(audio_bytes),
            voice_id,
            duration_ms,
        )

        return SynthesisResult(
            audio_bytes=audio_bytes,
            format=output_format,
            sample_rate=sample_rate,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play_audio(self, audio_bytes: bytes, sample_rate: int = 16000) -> None:
        """Play raw PCM audio through the local speaker.

        In simulator mode the audio is not actually played — only logged.
        """
        if self._simulator:
            duration_ms = len(audio_bytes) / (sample_rate * 2) * 1000  # 16-bit mono
            logger.info(
                "[SIM] Playing audio: %d bytes, ~%.0f ms (simulated)",
                len(audio_bytes),
                duration_ms,
            )
            return

        try:
            import pyaudio  # type: ignore

            pa = pyaudio.PyAudio()
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=sample_rate,
                output=True,
            )
            stream.write(audio_bytes)
            stream.stop_stream()
            stream.close()
            pa.terminate()
            logger.info("Audio playback complete (%d bytes)", len(audio_bytes))
        except ImportError:
            logger.warning("PyAudio not available – cannot play audio")
        except Exception as exc:
            logger.error("Audio playback failed: %s", exc)

    def speak(self, text: str, **synth_kwargs) -> SynthesisResult:
        """Convenience method: synthesize text and immediately play it.

        Returns the ``SynthesisResult`` for downstream use.
        """
        result = self.synthesize(text, **synth_kwargs)
        self.play_audio(result.audio_bytes, sample_rate=result.sample_rate)
        return result

    # ------------------------------------------------------------------
    # Alert helpers
    # ------------------------------------------------------------------

    def speak_alert(self, alert_key: str) -> SynthesisResult:
        """Speak a pre-built alert response by key.

        Parameters
        ----------
        alert_key :
            One of the keys in ``ALERT_RESPONSES``
            (e.g. ``"fall_detected"``, ``"medication_reminder"``).
        """
        text = ALERT_RESPONSES.get(alert_key, f"Alert: {alert_key}")
        return self.speak(text)

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------

    def _simulate_synthesis(
        self,
        text: str,
        output_format: str,
        sample_rate: int,
    ) -> SynthesisResult:
        """Generate dummy PCM audio for demo mode.

        Produces a short, low-volume sine-tone whose length is proportional
        to the input text so downstream components receive realistic-ish data.
        """
        import math

        # ~80 ms of audio per word
        n_words = max(len(text.split()), 1)
        duration_s = n_words * 0.08
        n_samples = int(sample_rate * duration_s)

        # 440 Hz sine at ~10% amplitude
        samples = []
        for i in range(n_samples):
            val = int(3276 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            samples.append(val)

        audio_bytes = struct.pack(f"<{n_samples}h", *samples)
        duration_ms = duration_s * 1000.0

        logger.info(
            "[SIM] Synthesised %d bytes for '%s…' (%.0f ms)",
            len(audio_bytes),
            text[:40],
            duration_ms,
        )

        return SynthesisResult(
            audio_bytes=audio_bytes,
            format=output_format,
            sample_rate=sample_rate,
            duration_ms=duration_ms,
        )
