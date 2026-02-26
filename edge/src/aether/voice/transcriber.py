"""
AETHER Edge Voice Pipeline – Speech-to-Text Transcriber
========================================================
Provides speech recognition via AWS Transcribe (batch & streaming) with
a local keyword-matcher fallback for demo / offline operation.

Designed for en-IN (Indian English) as the primary locale.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, List, Optional

logger = logging.getLogger("aether.voice.transcriber")

SIMULATOR_MODE = os.getenv("SIMULATOR_MODE", "true").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TranscriptionResult:
    """Returned by transcription methods."""

    text: str
    confidence: float  # 0.0 – 1.0
    language_code: str = "en-IN"
    duration_ms: float = 0.0
    job_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Transcriber
# ---------------------------------------------------------------------------

class AetherTranscriber:
    """Speech-to-text engine backed by AWS Transcribe.

    In simulator / demo mode, falls back to a simple keyword matcher so the
    full voice pipeline can be exercised without cloud credentials.

    Parameters
    ----------
    region_name : str
        AWS region for the Transcribe & S3 clients.
    s3_bucket : str
        Bucket used for temporary audio uploads.
    s3_prefix : str
        Key prefix inside the bucket.
    simulator : bool | None
        When ``True`` (or ``SIMULATOR_MODE`` env var), use the local fallback.
    """

    def __init__(
        self,
        region_name: Optional[str] = None,
        s3_bucket: Optional[str] = None,
        s3_prefix: str = "voice/tmp/",
        simulator: Optional[bool] = None,
    ) -> None:
        self._region = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self._s3_bucket = s3_bucket or os.getenv("AETHER_EVIDENCE_BUCKET", "aether-evidence")
        self._s3_prefix = s3_prefix
        self._simulator = simulator if simulator is not None else SIMULATOR_MODE

        self._transcribe_client = None
        self._s3_client = None

        if not self._simulator:
            try:
                import boto3
                self._transcribe_client = boto3.client("transcribe", region_name=self._region)
                self._s3_client = boto3.client("s3", region_name=self._region)
                logger.info("AWS Transcribe client initialised (region=%s)", self._region)
            except Exception as exc:
                logger.warning("Could not create AWS clients – falling back to simulator: %s", exc)
                self._simulator = True

    # ------------------------------------------------------------------
    # Batch transcription (S3 round-trip)
    # ------------------------------------------------------------------

    def transcribe_audio(
        self,
        audio_bytes: bytes,
        language_code: str = "en-IN",
        media_format: str = "wav",
        sample_rate: int = 16000,
    ) -> TranscriptionResult:
        """Transcribe an audio buffer via AWS Transcribe (batch API).

        1. Upload PCM/WAV to S3.
        2. Start a transcription job.
        3. Poll until complete.
        4. Return the top transcript.
        """
        if self._simulator:
            return self.transcribe_local(audio_bytes)

        job_name = f"aether-{uuid.uuid4().hex[:12]}"
        s3_key = f"{self._s3_prefix}{job_name}.{media_format}"
        s3_uri = f"s3://{self._s3_bucket}/{s3_key}"

        t_start = time.time()

        # 1. Upload
        self._s3_client.put_object(
            Bucket=self._s3_bucket,
            Key=s3_key,
            Body=audio_bytes,
            ContentType=f"audio/{media_format}",
        )
        logger.info("Uploaded %d bytes to %s", len(audio_bytes), s3_uri)

        # 2. Start job
        self._transcribe_client.start_transcription_job(
            TranscriptionJobName=job_name,
            LanguageCode=language_code,
            MediaFormat=media_format,
            Media={"MediaFileUri": s3_uri},
            MediaSampleRateHertz=sample_rate,
            Settings={"ShowSpeakerLabels": False},
        )
        logger.info("Transcription job started: %s", job_name)

        # 3. Poll
        text, confidence = self._poll_job(job_name)

        duration_ms = (time.time() - t_start) * 1000
        logger.info(
            "Transcription complete: '%s' (confidence=%.2f, duration=%.0f ms)",
            text,
            confidence,
            duration_ms,
        )

        # Clean up temp S3 object (best-effort)
        try:
            self._s3_client.delete_object(Bucket=self._s3_bucket, Key=s3_key)
        except Exception:
            pass

        return TranscriptionResult(
            text=text,
            confidence=confidence,
            language_code=language_code,
            duration_ms=duration_ms,
            job_id=job_name,
        )

    def _poll_job(
        self,
        job_name: str,
        poll_interval: float = 1.0,
        max_wait: float = 60.0,
    ) -> tuple[str, float]:
        """Poll Transcribe until the job completes or times out."""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            resp = self._transcribe_client.get_transcription_job(
                TranscriptionJobName=job_name
            )
            status = resp["TranscriptionJob"]["TranscriptionJobStatus"]
            if status == "COMPLETED":
                uri = resp["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
                return self._fetch_transcript(uri)
            if status == "FAILED":
                reason = resp["TranscriptionJob"].get("FailureReason", "unknown")
                logger.error("Transcription job %s failed: %s", job_name, reason)
                return (f"[transcription failed: {reason}]", 0.0)
            time.sleep(poll_interval)
        logger.error("Transcription job %s timed out after %.0f s", job_name, max_wait)
        return ("[transcription timed out]", 0.0)

    def _fetch_transcript(self, transcript_uri: str) -> tuple[str, float]:
        """Download and parse the JSON transcript returned by AWS."""
        import urllib.request

        with urllib.request.urlopen(transcript_uri) as resp:
            data = json.loads(resp.read().decode())

        results = data.get("results", {})
        transcripts = results.get("transcripts", [])
        if not transcripts:
            return ("", 0.0)

        text = transcripts[0].get("transcript", "")
        items = results.get("items", [])
        if items:
            confidences = [
                float(it["alternatives"][0].get("confidence", 0))
                for it in items
                if it.get("alternatives")
            ]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        else:
            avg_conf = 0.0
        return (text, avg_conf)

    # ------------------------------------------------------------------
    # Streaming transcription
    # ------------------------------------------------------------------

    async def transcribe_streaming(
        self,
        audio_stream,
        language_code: str = "en-IN",
        sample_rate: int = 16000,
    ) -> AsyncIterator[str]:
        """Yield partial transcripts in real-time via Transcribe Streaming.

        Falls back to local keyword matching in simulator mode.
        """
        if self._simulator:
            # Consume stream chunks and run local matching
            chunks: list[bytes] = []
            async for chunk in audio_stream:
                chunks.append(chunk)
            result = self.transcribe_local(b"".join(chunks))
            yield result.text
            return

        # Real streaming via amazon-transcribe-streaming-sdk
        try:
            from amazon_transcribe.client import TranscribeStreamingClient  # type: ignore
            from amazon_transcribe.handlers import TranscriptResultStreamHandler  # type: ignore
            from amazon_transcribe.model import TranscriptEvent  # type: ignore
        except ImportError:
            logger.warning(
                "amazon-transcribe-streaming-sdk not installed – "
                "falling back to batch transcription"
            )
            chunks = []
            async for chunk in audio_stream:
                chunks.append(chunk)
            result = self.transcribe_audio(b"".join(chunks), language_code=language_code)
            yield result.text
            return

        client = TranscribeStreamingClient(region=self._region)
        stream = await client.start_stream_transcription(
            language_code=language_code,
            media_sample_rate_hz=sample_rate,
            media_encoding="pcm",
        )

        async def _feed():
            async for chunk in audio_stream:
                await stream.input_stream.send_audio_event(audio_chunk=chunk)
            await stream.input_stream.end_stream()

        import asyncio
        asyncio.ensure_future(_feed())

        async for event in stream.output_stream:
            if hasattr(event, "transcript") and event.transcript.results:
                for result in event.transcript.results:
                    if not result.is_partial:
                        for alt in result.alternatives:
                            yield alt.transcript

    # ------------------------------------------------------------------
    # Local fallback transcriber (demo / offline)
    # ------------------------------------------------------------------

    # Mapping of simple "keywords" that the energy-based recogniser can
    # pretend to detect, keyed by sequential demo invocation index.
    _DEMO_TRANSCRIPTS: List[str] = [
        "I'm fine, cancel the alert",
        "call my son please",
        "when should I take my medicine",
        "I feel a little dizzy",
        "help me I fell down",
        "yes I'm okay",
        "remind me to take my pills at 8 pm",
        "check in",
        "what is my blood pressure",
        "I'm alright everything is fine",
    ]

    _demo_index: int = 0

    def transcribe_local(self, audio_bytes: bytes) -> TranscriptionResult:
        """Keyword-matcher fallback for demo mode.

        Cycles through a list of pre-defined transcripts so the downstream
        intent classifier can be exercised without a real ASR engine.
        """
        transcript = self._DEMO_TRANSCRIPTS[self._demo_index % len(self._DEMO_TRANSCRIPTS)]
        self._demo_index += 1

        logger.info("Local transcription (demo): '%s'", transcript)
        return TranscriptionResult(
            text=transcript,
            confidence=0.85,
            language_code="en-IN",
            duration_ms=len(audio_bytes) / 32.0,  # rough estimate at 16 kHz mono
        )
