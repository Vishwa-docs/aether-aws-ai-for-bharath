"""
AETHER Edge Voice Pipeline – Voice Activity Detection
======================================================
Energy-based VAD with a simple state machine that segments a continuous
audio stream into discrete utterances.  Designed for 16 kHz / 16-bit mono
PCM typically produced by the wake-word front end.

Runs entirely on-device – no cloud calls required.
"""

from __future__ import annotations

import logging
import math
import struct
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Iterator, Optional

logger = logging.getLogger("aether.voice.vad")


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class _VADState(Enum):
    IDLE = auto()
    SPEECH_STARTED = auto()
    SPEECH_ENDED = auto()


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class UtteranceResult:
    """Returned by :meth:`VoiceActivityDetector.detect_utterance`."""

    audio_bytes: bytes
    duration_ms: float
    speech_start_ts: float  # time.time()
    speech_end_ts: float


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class VoiceActivityDetector:
    """Energy-based Voice Activity Detector.

    Parameters
    ----------
    energy_threshold : float
        RMS energy level above which a frame is classified as speech.
    min_speech_ms : int
        Minimum duration of consecutive speech frames before transitioning
        to ``SPEECH_STARTED``.
    min_silence_ms : int
        Minimum duration of consecutive silence frames before transitioning
        to ``SPEECH_ENDED`` (i.e., end-of-utterance).
    max_utterance_s : float
        Hard cap on utterance length (seconds).
    frame_duration_ms : int
        Duration of a single analysis frame in milliseconds.
    sample_rate : int
        Expected audio sample rate.
    """

    def __init__(
        self,
        energy_threshold: float = 500.0,
        min_speech_ms: int = 250,
        min_silence_ms: int = 700,
        max_utterance_s: float = 30.0,
        frame_duration_ms: int = 30,
        sample_rate: int = 16000,
    ) -> None:
        self.energy_threshold = energy_threshold
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.max_utterance_s = max_utterance_s
        self.frame_duration_ms = frame_duration_ms
        self.sample_rate = sample_rate

        # Derived constants
        self._frame_samples = int(sample_rate * frame_duration_ms / 1000)
        self._frame_bytes = self._frame_samples * 2  # 16-bit = 2 bytes/sample

        self._state = _VADState.IDLE
        self._speech_frames = 0
        self._silence_frames = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_speech(self, audio_frame: bytes, sample_rate: int = 16000) -> bool:
        """Classify a single frame as speech or silence.

        Parameters
        ----------
        audio_frame :
            Raw 16-bit little-endian PCM bytes.
        sample_rate :
            Sample rate (used only for logging/diagnostics).

        Returns
        -------
        bool
            ``True`` if the frame energy exceeds ``energy_threshold``.
        """
        rms = self._rms_energy(audio_frame)
        return rms >= self.energy_threshold

    def detect_utterance(
        self,
        audio_stream: Iterator[bytes],
        timeout_s: float = 10.0,
    ) -> Optional[UtteranceResult]:
        """Listen on *audio_stream* for a complete utterance.

        The method blocks until:
        * Speech is detected and subsequently followed by sufficient silence, OR
        * The *timeout_s* elapses with no speech detected, OR
        * The utterance exceeds ``max_utterance_s``.

        Parameters
        ----------
        audio_stream :
            An iterator that yields raw PCM byte chunks.  Each chunk should
            be ``frame_duration_ms`` of 16 kHz / 16-bit mono audio (960 B
            for 30 ms).
        timeout_s :
            Maximum time to wait for speech *start*.

        Returns
        -------
        UtteranceResult | None
            The captured utterance, or ``None`` if the timeout expired.
        """
        self._reset()

        utterance_chunks: list[bytes] = []
        started_listening = time.time()
        speech_start_ts: float = 0.0

        for chunk in audio_stream:
            now = time.time()

            # --- timeout for speech start --------------------------------
            if self._state == _VADState.IDLE and (now - started_listening) > timeout_s:
                logger.debug("VAD timeout – no speech detected within %.1f s", timeout_s)
                return None

            # --- classify frame ------------------------------------------
            frame_is_speech = self.is_speech(chunk)

            if self._state == _VADState.IDLE:
                if frame_is_speech:
                    self._speech_frames += 1
                    self._silence_frames = 0
                    utterance_chunks.append(chunk)
                    if self._speech_frames * self.frame_duration_ms >= self.min_speech_ms:
                        self._state = _VADState.SPEECH_STARTED
                        speech_start_ts = now - (self._speech_frames * self.frame_duration_ms / 1000.0)
                        logger.info("VAD: speech started (ts=%.3f)", speech_start_ts)
                else:
                    self._speech_frames = 0

            elif self._state == _VADState.SPEECH_STARTED:
                utterance_chunks.append(chunk)

                if frame_is_speech:
                    self._silence_frames = 0
                else:
                    self._silence_frames += 1
                    if self._silence_frames * self.frame_duration_ms >= self.min_silence_ms:
                        self._state = _VADState.SPEECH_ENDED
                        logger.info("VAD: speech ended (silence gate)")

                # Hard cap
                elapsed = now - speech_start_ts if speech_start_ts else 0
                if elapsed >= self.max_utterance_s:
                    self._state = _VADState.SPEECH_ENDED
                    logger.warning("VAD: utterance capped at %.1f s", self.max_utterance_s)

            if self._state == _VADState.SPEECH_ENDED:
                break

        if not utterance_chunks or self._state != _VADState.SPEECH_ENDED:
            return None

        audio_bytes = b"".join(utterance_chunks)
        duration_ms = len(audio_bytes) / self._frame_bytes * self.frame_duration_ms

        result = UtteranceResult(
            audio_bytes=audio_bytes,
            duration_ms=duration_ms,
            speech_start_ts=speech_start_ts,
            speech_end_ts=time.time(),
        )
        logger.info(
            "VAD utterance captured: %.1f ms (%d bytes)",
            result.duration_ms,
            len(result.audio_bytes),
        )
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _rms_energy(pcm_bytes: bytes) -> float:
        """Compute RMS energy of 16-bit LE PCM bytes."""
        if len(pcm_bytes) < 2:
            return 0.0

        n_samples = len(pcm_bytes) // 2
        fmt = f"<{n_samples}h"
        try:
            samples = struct.unpack(fmt, pcm_bytes[: n_samples * 2])
        except struct.error:
            return 0.0

        if n_samples == 0:
            return 0.0

        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / n_samples)

    def _reset(self) -> None:
        self._state = _VADState.IDLE
        self._speech_frames = 0
        self._silence_frames = 0
