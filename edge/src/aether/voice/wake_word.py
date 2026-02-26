"""
AETHER Edge Voice Pipeline – Wake-Word Detection
=================================================
Detects configurable wake words ("hey sentinel", "hey aether") using the
Picovoice Porcupine engine when available, with an energy-based fallback
for demo / simulator environments.

Runs on Raspberry Pi 5 or Jetson Orin Nano.
"""

from __future__ import annotations

import logging
import os
import struct
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

logger = logging.getLogger("aether.voice.wake_word")

SIMULATOR_MODE = os.getenv("SIMULATOR_MODE", "true").lower() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class WakeWordEvent:
    """Emitted when a wake word is detected."""

    keyword_index: int
    keyword_label: str
    timestamp: float  # time.time()
    detection_latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Porcupine-backed detector
# ---------------------------------------------------------------------------

try:
    import pvporcupine  # type: ignore

    _PORCUPINE_AVAILABLE = True
except ImportError:
    _PORCUPINE_AVAILABLE = False

try:
    import pyaudio  # type: ignore

    _PYAUDIO_AVAILABLE = True
except ImportError:
    _PYAUDIO_AVAILABLE = False


class WakeWordDetector:
    """Listens for wake words via Porcupine or a simple energy-based fallback.

    Parameters
    ----------
    access_key : str | None
        Picovoice access key. Ignored in simulator mode.
    keyword_paths : list[str] | None
        Paths to ``.ppn`` keyword model files.  When *None* the built-in
        keywords ``"hey sentry"`` / ``"computer"`` are used as stand-ins
        (Porcupine ships a limited set of built-in keywords).
    sensitivities : list[float] | None
        Per-keyword sensitivity in [0, 1]. Defaults to 0.5 for each keyword.
    model_path : str | None
        Optional path to a custom Porcupine model file.
    keywords : list[str]
        Human-readable labels for the keywords (used in logs & events).
    energy_threshold : float
        RMS energy threshold for the fallback detector.
    simulator : bool | None
        Force simulator mode. Defaults to ``SIMULATOR_MODE`` env var.
    """

    DEFAULT_KEYWORDS = ["hey sentinel", "hey aether"]

    def __init__(
        self,
        access_key: Optional[str] = None,
        keyword_paths: Optional[List[str]] = None,
        sensitivities: Optional[List[float]] = None,
        model_path: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        energy_threshold: float = 1500.0,
        simulator: Optional[bool] = None,
    ) -> None:
        self._access_key = access_key or os.getenv("PORCUPINE_ACCESS_KEY", "")
        self._keyword_paths = keyword_paths
        self._keywords = keywords or self.DEFAULT_KEYWORDS
        self._sensitivities = sensitivities or [0.5] * len(self._keywords)
        self._model_path = model_path
        self._energy_threshold = energy_threshold
        self._simulator = simulator if simulator is not None else SIMULATOR_MODE

        self._porcupine = None  # lazily initialised
        self._audio_stream = None
        self._pyaudio_instance = None
        self._running = False

        # Metrics
        self._detections: List[WakeWordEvent] = []

        if self._simulator:
            logger.info(
                "WakeWordDetector running in SIMULATOR / energy-fallback mode"
            )
        elif _PORCUPINE_AVAILABLE:
            logger.info("Porcupine library available – using hardware-accelerated detection")
        else:
            logger.warning(
                "pvporcupine not installed – falling back to energy-based detection"
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_porcupine(self) -> None:
        """Create the Porcupine handle (real mode only)."""
        if self._simulator or not _PORCUPINE_AVAILABLE:
            return

        kw_kwargs: dict = {}
        if self._keyword_paths:
            kw_kwargs["keyword_paths"] = self._keyword_paths
        else:
            # Use built-in keywords as proxies
            builtin = pvporcupine.KEYWORDS
            chosen = []
            for kw in ("hey sentry", "computer"):
                if kw in builtin:
                    chosen.append(kw)
            kw_kwargs["keywords"] = chosen or list(builtin)[:2]
            self._sensitivities = [0.5] * len(kw_kwargs["keywords"])

        self._porcupine = pvporcupine.create(
            access_key=self._access_key,
            sensitivities=self._sensitivities,
            model_path=self._model_path,
            **kw_kwargs,
        )
        logger.info(
            "Porcupine initialised – frame_length=%d, sample_rate=%d",
            self._porcupine.frame_length,
            self._porcupine.sample_rate,
        )

    def start(self, audio_callback: Optional[Callable[[WakeWordEvent], None]] = None) -> None:
        """Begin listening on the default microphone.

        Parameters
        ----------
        audio_callback :
            Called with a ``WakeWordEvent`` each time a wake word fires.
        """
        self._init_porcupine()
        self._running = True
        frame_length = self._porcupine.frame_length if self._porcupine else 512
        sample_rate = self._porcupine.sample_rate if self._porcupine else 16000

        if _PYAUDIO_AVAILABLE:
            self._pyaudio_instance = pyaudio.PyAudio()
            self._audio_stream = self._pyaudio_instance.open(
                rate=sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=frame_length,
            )
            logger.info("Microphone stream opened (rate=%d, frame=%d)", sample_rate, frame_length)
        else:
            logger.warning("PyAudio not available – start() will not capture real audio")
            self._running = False
            return

        try:
            while self._running:
                raw = self._audio_stream.read(frame_length, exception_on_overflow=False)
                pcm = struct.unpack_from(f"{frame_length}h", raw)
                kw_index = self.process_frame(pcm)
                if kw_index >= 0:
                    event = self._make_event(kw_index)
                    if audio_callback:
                        audio_callback(event)
        except KeyboardInterrupt:
            logger.info("Wake-word listening interrupted by user")
        finally:
            self.stop()

    def stop(self) -> None:
        """Release all resources."""
        self._running = False

        if self._audio_stream is not None:
            try:
                self._audio_stream.stop_stream()
                self._audio_stream.close()
            except Exception:
                pass
            self._audio_stream = None

        if self._pyaudio_instance is not None:
            try:
                self._pyaudio_instance.terminate()
            except Exception:
                pass
            self._pyaudio_instance = None

        if self._porcupine is not None:
            try:
                self._porcupine.delete()
            except Exception:
                pass
            self._porcupine = None

        logger.info("WakeWordDetector stopped – total detections: %d", len(self._detections))

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def process_frame(self, pcm_frame: Sequence[int]) -> int:
        """Process a single audio frame.

        Parameters
        ----------
        pcm_frame :
            Tuple / list of 16-bit signed PCM samples, length must match
            Porcupine's ``frame_length`` (512 for 16 kHz).

        Returns
        -------
        int
            Keyword index (≥ 0) if a wake word was detected, otherwise -1.
        """
        t_start = time.perf_counter()

        if self._porcupine is not None and not self._simulator:
            result = self._porcupine.process(pcm_frame)
        else:
            result = self._energy_detect(pcm_frame)

        if result >= 0:
            latency_ms = (time.perf_counter() - t_start) * 1000.0
            event = self._make_event(result, latency_ms)
            self._detections.append(event)
            logger.info(
                "Wake word DETECTED: '%s' (index=%d, latency=%.2f ms, ts=%.3f)",
                event.keyword_label,
                event.keyword_index,
                event.detection_latency_ms,
                event.timestamp,
            )
            return result

        return -1

    # ------------------------------------------------------------------
    # Energy-based fallback
    # ------------------------------------------------------------------

    def _energy_detect(self, pcm_frame: Sequence[int]) -> int:
        """Simple RMS energy gate used when Porcupine is unavailable.

        This is *not* a real wake-word engine – it merely fires when the
        short-term energy exceeds ``energy_threshold``.  Useful for demos
        and integration tests.
        """
        if len(pcm_frame) == 0:
            return -1

        sum_sq = sum(s * s for s in pcm_frame)
        rms = (sum_sq / len(pcm_frame)) ** 0.5

        if rms >= self._energy_threshold:
            # Alternate between keyword indices for variety in demos
            idx = len(self._detections) % len(self._keywords)
            return idx
        return -1

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_event(self, keyword_index: int, latency_ms: float = 0.0) -> WakeWordEvent:
        label = (
            self._keywords[keyword_index]
            if keyword_index < len(self._keywords)
            else f"keyword_{keyword_index}"
        )
        return WakeWordEvent(
            keyword_index=keyword_index,
            keyword_label=label,
            timestamp=time.time(),
            detection_latency_ms=latency_ms,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def detections(self) -> List[WakeWordEvent]:
        """All wake-word events detected so far."""
        return list(self._detections)

    @property
    def is_running(self) -> bool:
        return self._running
