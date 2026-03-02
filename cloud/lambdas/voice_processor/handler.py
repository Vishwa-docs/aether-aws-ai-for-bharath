"""
AETHER Voice Processor Lambda
===============================
Unified Lambda function behind API Gateway (proxy integration) for all
voice-related operations: speech-to-text, text-to-speech, and daily
check-in dialogue management.

Endpoints
---------
POST /api/voice/process     – Transcribe audio / classify intent / generate response
POST /api/voice/synthesize  – Text-to-speech via AWS Polly (neural)
POST /api/voice/checkin     – Multi-turn daily check-in dialogue flow
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.models import (
    EventType,
    Severity,
    generate_event_id,
    get_current_timestamp,
)
from shared.utils import (
    api_error,
    api_response,
    dynamo_get_item,
    dynamo_put_item,
    dynamo_update_item,
    events_table_name,
    evidence_bucket_name,
    generate_correlation_id,
    get_env,
    get_s3_client,
    get_bedrock_client,
    invoke_bedrock_model,
    json_dumps,
    log_with_context,
    residents_table_name,
    s3_get_presigned_url,
    s3_put_object,
    setup_logger,
    sns_publish_structured_alert,
    alerts_topic_arn,
    timeline_table_name,
)

import boto3
from botocore.config import Config

logger = setup_logger("voice_processor")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TRANSCRIBE_LANGUAGE_CODE = get_env("TRANSCRIBE_LANGUAGE_CODE", "en-IN")
POLLY_VOICE_ID = get_env("POLLY_VOICE_ID", "Kajal")
POLLY_ENGINE = get_env("POLLY_ENGINE", "neural")
BEDROCK_MODEL_ID = get_env("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
CHECKIN_SESSION_TTL_SECONDS = 3600  # 1 hour session expiry

# Check-in dialogue steps (ordered)
CHECKIN_STEPS = ["greeting", "mood", "pain", "sleep", "hydration", "meals", "summary"]

# Supported intents for voice command classification
SUPPORTED_INTENTS = [
    "cancel_alert",
    "confirm_ok",
    "call_contact",
    "medication_query",
    "health_query",
    "emergency",
    "daily_checkin",
    "general",
]

# ---------------------------------------------------------------------------
# Lazy boto3 clients (created once per Lambda container)
# ---------------------------------------------------------------------------

_BOTO_CONFIG = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=30,
)

_transcribe_client: Optional[Any] = None
_polly_client: Optional[Any] = None


def _get_transcribe_client() -> Any:
    global _transcribe_client
    if _transcribe_client is None:
        _transcribe_client = boto3.client("transcribe", config=_BOTO_CONFIG)
    return _transcribe_client


def _get_polly_client() -> Any:
    global _polly_client
    if _polly_client is None:
        _polly_client = boto3.client("polly", config=_BOTO_CONFIG)
    return _polly_client


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point for API Gateway proxy integration."""
    correlation_id = (
        (event.get("headers") or {}).get("X-Correlation-Id")
        or (event.get("headers") or {}).get("x-correlation-id")
        or generate_correlation_id()
    )

    # Handle CORS preflight
    http_method = event.get("httpMethod", "POST").upper()
    if http_method == "OPTIONS":
        return api_response(200, {"message": "OK"})

    path = event.get("path", "/")

    log_with_context(
        logger, "INFO",
        f"{http_method} {path}",
        correlation_id=correlation_id,
    )

    try:
        response = _route_request(http_method, path, event, correlation_id)
        return response
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Unhandled voice processor error: {exc}",
            correlation_id=correlation_id,
            traceback=traceback.format_exc(),
        )
        return api_error(500, "internal_error", "An unexpected error occurred.", correlation_id)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

_ROUTES: List[Tuple[str, str, Callable]] = []


def _route(method: str, pattern: str):
    """Decorator to register a route handler."""
    def decorator(fn: Callable) -> Callable:
        _ROUTES.append((method, pattern, fn))
        return fn
    return decorator


def _route_request(
    method: str,
    path: str,
    event: Dict[str, Any],
    correlation_id: str,
) -> Dict[str, Any]:
    """Match the request against registered routes and dispatch."""
    for route_method, pattern, handler_fn in _ROUTES:
        if method != route_method:
            continue
        match = re.match(pattern, path)
        if match:
            return handler_fn(event, match, correlation_id)

    return api_error(404, "not_found", f"No route matches {method} {path}", correlation_id)


# ---------------------------------------------------------------------------
# Request helpers
# ---------------------------------------------------------------------------

def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse the JSON request body."""
    body = event.get("body")
    if body is None:
        return {}
    if isinstance(body, dict):
        return body
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return {}


# ---------------------------------------------------------------------------
# POST /api/voice/process
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/voice/process/?$")
def _voice_process(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Process voice input: transcribe audio → classify intent → generate response.

    Request body:
        audio_base64 (str, optional): Base64-encoded audio (WAV/MP3/OGG).
        text (str, optional): Direct text input (skips transcription).
        audio_format (str): Media format – "wav", "mp3", or "ogg" (default "wav").
        resident_id (str, optional): Resident identifier for context.
        home_id (str, optional): Home identifier for context.

    Returns:
        transcript, intent, confidence, response_text, response_audio_url
    """
    body = _parse_body(event)

    audio_b64 = body.get("audio_base64")
    text_input = body.get("text")
    audio_format = body.get("audio_format", "wav")
    resident_id = body.get("resident_id", "unknown")
    home_id = body.get("home_id", "unknown")

    if not audio_b64 and not text_input:
        return api_error(400, "bad_request", "Provide either 'audio_base64' or 'text' field.", correlation_id)

    log_with_context(
        logger, "INFO",
        f"Voice process request: resident={resident_id}, has_audio={bool(audio_b64)}, has_text={bool(text_input)}",
        correlation_id=correlation_id,
    )

    # Step 1: Transcription (if audio provided)
    transcript = text_input or ""
    if audio_b64 and not text_input:
        transcript = _transcribe_audio(audio_b64, audio_format, correlation_id)

    if not transcript:
        return api_error(422, "transcription_failed", "Could not transcribe audio input.", correlation_id)

    # Step 2: Classify intent via Bedrock
    intent, confidence = _classify_intent(transcript, correlation_id)

    # Step 3: Generate contextual response via Bedrock
    response_text = _generate_response(transcript, intent, resident_id, correlation_id)

    # Step 4: Synthesize response audio and upload to S3
    response_audio_url = ""
    try:
        response_audio_url = _synthesize_and_upload(
            response_text,
            POLLY_VOICE_ID,
            TRANSCRIBE_LANGUAGE_CODE,
            correlation_id,
        )
    except Exception as synth_err:
        log_with_context(
            logger, "WARNING",
            f"Response audio synthesis failed (non-fatal): {synth_err}",
            correlation_id=correlation_id,
        )

    # Step 5: Handle emergency intent escalation
    if intent == "emergency":
        _handle_emergency_intent(transcript, resident_id, home_id, correlation_id)

    result = {
        "transcript": transcript,
        "intent": intent,
        "confidence": confidence,
        "response_text": response_text,
        "response_audio_url": response_audio_url,
    }

    log_with_context(
        logger, "INFO",
        f"Voice processed: intent={intent}, confidence={confidence:.2f}",
        correlation_id=correlation_id,
    )

    return api_response(200, result)


# ---------------------------------------------------------------------------
# POST /api/voice/synthesize
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/voice/synthesize/?$")
def _voice_synthesize(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Synthesize text to speech using AWS Polly (neural engine).

    Request body:
        text (str, required): Text to synthesize.
        voice_id (str): Polly voice ID (default: Kajal).
        language_code (str): Language code (default: en-IN).

    Returns:
        audio_url, duration_ms
    """
    body = _parse_body(event)

    text = body.get("text", "").strip()
    voice_id = body.get("voice_id", POLLY_VOICE_ID)
    language_code = body.get("language_code", TRANSCRIBE_LANGUAGE_CODE)

    if not text:
        return api_error(400, "bad_request", "The 'text' field is required.", correlation_id)

    if len(text) > 3000:
        return api_error(400, "bad_request", "Text exceeds maximum length of 3000 characters.", correlation_id)

    log_with_context(
        logger, "INFO",
        f"Synthesize request: voice={voice_id}, lang={language_code}, len={len(text)}",
        correlation_id=correlation_id,
    )

    try:
        audio_url, duration_ms = _synthesize_speech(text, voice_id, language_code, correlation_id)

        return api_response(200, {
            "audio_url": audio_url,
            "duration_ms": duration_ms,
        })
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Polly synthesis failed: {exc}",
            correlation_id=correlation_id,
            traceback=traceback.format_exc(),
        )
        return api_error(502, "synthesis_error", f"Speech synthesis failed: {exc}", correlation_id)


# ---------------------------------------------------------------------------
# POST /api/voice/checkin
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/voice/checkin/?$")
def _voice_checkin(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Manage a multi-turn daily check-in dialogue.

    Dialogue flow: greeting → mood → pain → sleep → hydration → meals → summary

    Request body:
        resident_id (str, required): Resident identifier.
        session_id (str, optional): Existing session ID to continue. Omit to start new.
        step (str, optional): Current dialogue step override.
        user_response (str, optional): Resident's response to the current question.

    Returns:
        session_id, step, question, is_complete, check_in_report (on final step)
    """
    body = _parse_body(event)

    resident_id = body.get("resident_id", "").strip()
    session_id = body.get("session_id", "").strip()
    step = body.get("step", "").strip()
    user_response = body.get("user_response", "").strip()

    if not resident_id:
        return api_error(400, "bad_request", "The 'resident_id' field is required.", correlation_id)

    log_with_context(
        logger, "INFO",
        f"Check-in request: resident={resident_id}, session={session_id or 'new'}, step={step or 'auto'}",
        correlation_id=correlation_id,
    )

    try:
        # Start new session or load existing
        if not session_id:
            session = _create_checkin_session(resident_id, correlation_id)
            session_id = session["session_id"]
        else:
            session = _load_checkin_session(session_id, correlation_id)
            if not session:
                return api_error(404, "session_not_found", f"Check-in session '{session_id}' not found or expired.", correlation_id)

        # Determine current step
        current_step = step or session.get("current_step", "greeting")

        # Record user response for previous step (if provided)
        if user_response and current_step != "greeting":
            _record_checkin_response(session_id, current_step, user_response, correlation_id)

        # Advance to next step if user_response was given (except greeting starts fresh)
        if user_response and current_step != "summary":
            current_step_idx = CHECKIN_STEPS.index(current_step) if current_step in CHECKIN_STEPS else 0
            next_idx = min(current_step_idx + 1, len(CHECKIN_STEPS) - 1)
            current_step = CHECKIN_STEPS[next_idx]

        # Check if dialogue is complete
        is_complete = current_step == "summary" and user_response != ""

        # Generate question or summary
        if is_complete:
            check_in_report = _generate_checkin_summary(session_id, resident_id, correlation_id)
            question = "Thank you for completing your daily check-in. Take care!"

            # Update session as complete
            _update_checkin_session(session_id, current_step, is_complete=True, correlation_id=correlation_id)

            # Store check-in event
            _store_checkin_event(resident_id, session_id, check_in_report, correlation_id)
        else:
            question = _generate_checkin_question(current_step, resident_id, session_id, correlation_id)
            check_in_report = None

            # Update session state
            _update_checkin_session(session_id, current_step, is_complete=False, correlation_id=correlation_id)

        result: Dict[str, Any] = {
            "session_id": session_id,
            "step": current_step,
            "question": question,
            "is_complete": is_complete,
        }
        if check_in_report:
            result["check_in_report"] = check_in_report

        return api_response(200, result)

    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Check-in error: {exc}",
            correlation_id=correlation_id,
            traceback=traceback.format_exc(),
        )
        return api_error(500, "checkin_error", f"Check-in processing failed: {exc}", correlation_id)


# ===================================================================
# INTERNAL HELPERS
# ===================================================================

# ---------------------------------------------------------------------------
# Transcription (AWS Transcribe)
# ---------------------------------------------------------------------------

def _transcribe_audio(audio_b64: str, audio_format: str, correlation_id: str) -> str:
    """Transcribe base64-encoded audio using AWS Transcribe (batch via S3).

    Uploads the audio to S3, starts a Transcribe job, polls until complete,
    and returns the transcript text.
    """
    log_with_context(logger, "INFO", "Starting audio transcription", correlation_id=correlation_id)

    # Decode audio
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception as decode_err:
        log_with_context(logger, "ERROR", f"Base64 decode failed: {decode_err}", correlation_id=correlation_id)
        return ""

    # Map format to media format & content type
    format_map = {
        "wav": ("wav", "audio/wav"),
        "mp3": ("mp3", "audio/mpeg"),
        "ogg": ("ogg", "audio/ogg"),
        "flac": ("flac", "audio/flac"),
        "webm": ("webm", "audio/webm"),
    }
    media_format, content_type = format_map.get(audio_format.lower(), ("wav", "audio/wav"))

    # Upload to S3 for Transcribe
    bucket = evidence_bucket_name()
    job_name = f"aether-voice-{uuid.uuid4().hex[:12]}"
    s3_key = f"voice/transcribe-input/{job_name}.{media_format}"

    s3_client = get_s3_client()
    s3_client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=audio_bytes,
        ContentType=content_type,
    )

    media_uri = f"s3://{bucket}/{s3_key}"

    log_with_context(
        logger, "INFO",
        f"Audio uploaded for transcription: {media_uri} ({len(audio_bytes)} bytes)",
        correlation_id=correlation_id,
    )

    # Start transcription job
    transcribe = _get_transcribe_client()
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={"MediaFileUri": media_uri},
        MediaFormat=media_format,
        LanguageCode=TRANSCRIBE_LANGUAGE_CODE,
        OutputBucketName=bucket,
        OutputKey=f"voice/transcribe-output/{job_name}.json",
        Settings={
            "ShowSpeakerLabels": False,
            "ChannelIdentification": False,
        },
    )

    # Poll for completion (max ~60 seconds)
    max_polls = 30
    poll_interval = 2
    transcript_text = ""

    for attempt in range(max_polls):
        time.sleep(poll_interval)
        status_resp = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        status = status_resp["TranscriptionJob"]["TranscriptionJobStatus"]

        if status == "COMPLETED":
            transcript_uri = status_resp["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
            # Read transcript output from S3
            output_key = f"voice/transcribe-output/{job_name}.json"
            try:
                output_obj = s3_client.get_object(Bucket=bucket, Key=output_key)
                output_data = json.loads(output_obj["Body"].read().decode("utf-8"))
                transcripts = output_data.get("results", {}).get("transcripts", [])
                if transcripts:
                    transcript_text = transcripts[0].get("transcript", "")
            except Exception as read_err:
                log_with_context(logger, "ERROR", f"Failed to read transcript output: {read_err}", correlation_id=correlation_id)
            break
        elif status == "FAILED":
            failure_reason = status_resp["TranscriptionJob"].get("FailureReason", "Unknown")
            log_with_context(logger, "ERROR", f"Transcription failed: {failure_reason}", correlation_id=correlation_id)
            break

    # Cleanup: delete the Transcribe job (best-effort)
    try:
        transcribe.delete_transcription_job(TranscriptionJobName=job_name)
    except Exception:
        pass

    log_with_context(
        logger, "INFO",
        f"Transcription result: '{transcript_text[:100]}...' ({len(transcript_text)} chars)",
        correlation_id=correlation_id,
    )

    return transcript_text


# ---------------------------------------------------------------------------
# Intent classification (Bedrock)
# ---------------------------------------------------------------------------

def _classify_intent(transcript: str, correlation_id: str) -> Tuple[str, float]:
    """Classify the user's intent from their transcript using Bedrock.

    Returns:
        A tuple of (intent_name, confidence_score).
    """
    intents_list = ", ".join(SUPPORTED_INTENTS)

    prompt = (
        "You are an intent classifier for an elderly care voice assistant called AETHER. "
        "Classify the following spoken text into exactly one intent.\n\n"
        f"Supported intents: {intents_list}\n\n"
        "Intent descriptions:\n"
        "- cancel_alert: User wants to dismiss or cancel a current alarm or alert\n"
        "- confirm_ok: User confirms they are okay or acknowledges a check\n"
        "- call_contact: User wants to call a family member, caregiver, or emergency contact\n"
        "- medication_query: User asks about medications, doses, or schedules\n"
        "- health_query: User asks about health metrics, vitals, or general health\n"
        "- emergency: User is reporting an emergency, fall, or urgent need for help\n"
        "- daily_checkin: User wants to start or continue a daily wellness check-in\n"
        "- general: General conversation or unrecognised intent\n\n"
        f"Spoken text: \"{transcript}\"\n\n"
        "Respond in valid JSON only with two fields:\n"
        "{ \"intent\": \"<intent_name>\", \"confidence\": <0.0 to 1.0> }\n"
        "Do not include any other text."
    )

    log_with_context(logger, "DEBUG", "Classifying intent via Bedrock", correlation_id=correlation_id)

    try:
        raw_response = invoke_bedrock_model(prompt, model_id=BEDROCK_MODEL_ID, max_tokens=100, temperature=0.1)

        # Parse JSON from response
        cleaned = raw_response.strip()
        # Handle markdown code blocks in response
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        intent = parsed.get("intent", "general")
        confidence = float(parsed.get("confidence", 0.5))

        # Validate intent
        if intent not in SUPPORTED_INTENTS:
            log_with_context(
                logger, "WARNING",
                f"Unknown intent '{intent}' from model, falling back to 'general'",
                correlation_id=correlation_id,
            )
            intent = "general"
            confidence = min(confidence, 0.3)

        # Clamp confidence
        confidence = max(0.0, min(1.0, confidence))

        return intent, confidence

    except (json.JSONDecodeError, KeyError, ValueError) as parse_err:
        log_with_context(
            logger, "WARNING",
            f"Intent classification parse error: {parse_err}, defaulting to 'general'",
            correlation_id=correlation_id,
        )
        return "general", 0.3


# ---------------------------------------------------------------------------
# Response generation (Bedrock)
# ---------------------------------------------------------------------------

def _generate_response(transcript: str, intent: str, resident_id: str, correlation_id: str) -> str:
    """Generate a contextual spoken response using Bedrock.

    The response is suitable for text-to-speech playback to an elderly resident.
    """
    prompt = (
        "You are AETHER, a caring and supportive voice assistant for elderly residents "
        "in an assisted-living environment. Speak warmly, clearly, and concisely.\n\n"
        f"The resident (ID: {resident_id}) said: \"{transcript}\"\n"
        f"Detected intent: {intent}\n\n"
        "Generate a short, empathetic spoken response (1–3 sentences). "
        "Use simple language appropriate for elderly users. "
        "If the intent is 'emergency', reassure the resident that help is being contacted immediately. "
        "If the intent is 'cancel_alert', confirm the alert is being cancelled. "
        "If the intent is 'medication_query', provide a helpful but safe response suggesting they consult their care plan. "
        "Do not include any markup or annotations — just the spoken text."
    )

    try:
        response = invoke_bedrock_model(prompt, model_id=BEDROCK_MODEL_ID, max_tokens=256, temperature=0.5)
        return response.strip().strip('"')
    except Exception as gen_err:
        log_with_context(
            logger, "WARNING",
            f"Response generation failed: {gen_err}",
            correlation_id=correlation_id,
        )
        # Provide fallback responses per intent
        fallbacks = {
            "cancel_alert": "I'm cancelling the alert for you now.",
            "confirm_ok": "Thank you for confirming. I'm glad you're okay.",
            "call_contact": "I'll connect you with your contact right away.",
            "medication_query": "Please check your care plan or ask your caregiver about your medication schedule.",
            "health_query": "Your health data is being monitored. Please speak to your caregiver for details.",
            "emergency": "I'm alerting your caregivers and emergency contacts right now. Help is on the way.",
            "daily_checkin": "Let's start your daily check-in. How are you feeling today?",
            "general": "I'm here to help. Could you tell me more about what you need?",
        }
        return fallbacks.get(intent, "I'm here to help. Could you please repeat that?")


# ---------------------------------------------------------------------------
# Speech synthesis (AWS Polly)
# ---------------------------------------------------------------------------

def _synthesize_speech(
    text: str,
    voice_id: str,
    language_code: str,
    correlation_id: str,
) -> Tuple[str, int]:
    """Synthesize speech via Polly and upload to S3.

    Returns:
        (presigned_url, estimated_duration_ms)
    """
    polly = _get_polly_client()

    response = polly.synthesize_speech(
        Text=text,
        VoiceId=voice_id,
        LanguageCode=language_code,
        Engine=POLLY_ENGINE,
        OutputFormat="mp3",
        SampleRate="24000",
    )

    audio_stream = response["AudioStream"].read()
    duration_ms = _estimate_audio_duration_ms(audio_stream, "mp3")

    # Upload to S3
    bucket = evidence_bucket_name()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d/%H%M%S")
    s3_key = f"voice/synthesis/{ts}-{uuid.uuid4().hex[:8]}.mp3"

    s3_client = get_s3_client()
    s3_client.put_object(
        Bucket=bucket,
        Key=s3_key,
        Body=audio_stream,
        ContentType="audio/mpeg",
        Metadata={
            "voice_id": voice_id,
            "language_code": language_code,
            "engine": POLLY_ENGINE,
            "correlation_id": correlation_id,
        },
    )

    # Generate presigned URL (1 hour expiry)
    audio_url = s3_get_presigned_url(bucket, s3_key, expires_in=3600)

    log_with_context(
        logger, "INFO",
        f"Speech synthesized: voice={voice_id}, size={len(audio_stream)} bytes, duration≈{duration_ms}ms",
        correlation_id=correlation_id,
    )

    return audio_url, duration_ms


def _synthesize_and_upload(
    text: str,
    voice_id: str,
    language_code: str,
    correlation_id: str,
) -> str:
    """Convenience wrapper that synthesizes and returns only the URL."""
    audio_url, _ = _synthesize_speech(text, voice_id, language_code, correlation_id)
    return audio_url


def _estimate_audio_duration_ms(audio_bytes: bytes, fmt: str) -> int:
    """Estimate audio duration from byte length and format.

    For MP3 at 48kbps (typical Polly neural output), duration ≈ bytes / 6 ms.
    This is a rough heuristic; for precise duration, use ffprobe or mutagen.
    """
    if fmt == "mp3":
        # Polly neural MP3 at 24kHz ~48kbps → ~6 bytes per ms
        return max(0, len(audio_bytes) // 6)
    # Fallback: assume ~16 bytes per ms for PCM
    return max(0, len(audio_bytes) // 16)


# ---------------------------------------------------------------------------
# Emergency handling
# ---------------------------------------------------------------------------

def _handle_emergency_intent(
    transcript: str,
    resident_id: str,
    home_id: str,
    correlation_id: str,
) -> None:
    """Escalate an emergency voice command by storing an event and publishing SNS alert."""
    log_with_context(
        logger, "WARNING",
        f"Emergency intent detected from resident {resident_id}",
        correlation_id=correlation_id,
    )

    event_id = generate_event_id()
    now = get_current_timestamp()

    event_record = {
        "home_id": home_id,
        "timestamp": now,
        "event_id": event_id,
        "event_type": "voice_emergency",
        "severity": Severity.CRITICAL,
        "resident_id": resident_id,
        "source": "voice_processor",
        "description": f"Voice emergency from resident: {transcript[:200]}",
        "acknowledged": False,
        "correlation_id": correlation_id,
    }

    try:
        dynamo_put_item(events_table_name(), event_record)
    except Exception as db_err:
        log_with_context(logger, "ERROR", f"Failed to store emergency event: {db_err}", correlation_id=correlation_id)

    # Publish SNS alert
    topic_arn = alerts_topic_arn()
    if topic_arn:
        try:
            sns_publish_structured_alert(
                topic_arn=topic_arn,
                event_type="voice_emergency",
                severity=Severity.CRITICAL,
                home_id=home_id,
                message=json_dumps({
                    "event_id": event_id,
                    "resident_id": resident_id,
                    "transcript": transcript[:500],
                    "timestamp": now,
                    "source": "voice_processor",
                }),
            )
        except Exception as sns_err:
            log_with_context(logger, "ERROR", f"Failed to publish SNS alert: {sns_err}", correlation_id=correlation_id)


# ---------------------------------------------------------------------------
# Check-in session management (DynamoDB)
# ---------------------------------------------------------------------------

def _checkin_table_name() -> str:
    """Return the DynamoDB table used for check-in sessions.

    Reuses the events table with a prefixed partition key to avoid
    requiring a separate table.
    """
    return events_table_name()


def _create_checkin_session(resident_id: str, correlation_id: str) -> Dict[str, Any]:
    """Create a new check-in session in DynamoDB."""
    session_id = f"checkin-{uuid.uuid4().hex}"
    now = get_current_timestamp()
    ttl = int(time.time()) + CHECKIN_SESSION_TTL_SECONDS

    session = {
        "home_id": f"checkin#{session_id}",
        "timestamp": now,
        "session_id": session_id,
        "resident_id": resident_id,
        "current_step": "greeting",
        "responses": {},
        "is_complete": False,
        "created_at": now,
        "updated_at": now,
        "ttl": ttl,
        "correlation_id": correlation_id,
    }

    dynamo_put_item(_checkin_table_name(), session)

    log_with_context(
        logger, "INFO",
        f"Created check-in session: {session_id} for resident {resident_id}",
        correlation_id=correlation_id,
    )

    return session


def _load_checkin_session(session_id: str, correlation_id: str) -> Optional[Dict[str, Any]]:
    """Load an existing check-in session from DynamoDB."""
    item = dynamo_get_item(
        _checkin_table_name(),
        key={"home_id": f"checkin#{session_id}", "timestamp": ""},
    )

    if not item:
        # Try querying by session key pattern (timestamp may vary)
        from boto3.dynamodb.conditions import Key
        from shared.utils import get_dynamodb_table

        table = get_dynamodb_table(_checkin_table_name())
        response = table.query(
            KeyConditionExpression=Key("home_id").eq(f"checkin#{session_id}"),
            Limit=1,
            ScanIndexForward=False,
        )
        items = response.get("Items", [])
        if items:
            item = items[0]

    if item and item.get("is_complete"):
        log_with_context(logger, "INFO", f"Session {session_id} already completed", correlation_id=correlation_id)
        return None

    return item


def _update_checkin_session(
    session_id: str,
    current_step: str,
    is_complete: bool,
    correlation_id: str,
) -> None:
    """Update the check-in session state in DynamoDB."""
    # Load session to get the exact timestamp key
    session = _load_checkin_session(session_id, correlation_id)
    if not session:
        return

    try:
        dynamo_update_item(
            _checkin_table_name(),
            key={
                "home_id": f"checkin#{session_id}",
                "timestamp": session["timestamp"],
            },
            update_expression="SET current_step = :step, is_complete = :done, updated_at = :now",
            expression_attribute_values={
                ":step": current_step,
                ":done": is_complete,
                ":now": get_current_timestamp(),
            },
        )
    except Exception as update_err:
        log_with_context(logger, "ERROR", f"Failed to update session: {update_err}", correlation_id=correlation_id)


def _record_checkin_response(
    session_id: str,
    step: str,
    user_response: str,
    correlation_id: str,
) -> None:
    """Record a resident's response for a specific check-in step."""
    session = _load_checkin_session(session_id, correlation_id)
    if not session:
        return

    try:
        dynamo_update_item(
            _checkin_table_name(),
            key={
                "home_id": f"checkin#{session_id}",
                "timestamp": session["timestamp"],
            },
            update_expression="SET responses.#step = :resp, updated_at = :now",
            expression_attribute_values={
                ":resp": user_response,
                ":now": get_current_timestamp(),
            },
            expression_attribute_names={
                "#step": step,
            },
        )
    except Exception as rec_err:
        log_with_context(logger, "ERROR", f"Failed to record response: {rec_err}", correlation_id=correlation_id)


# ---------------------------------------------------------------------------
# Check-in question generation (Bedrock)
# ---------------------------------------------------------------------------

_CHECKIN_QUESTION_TEMPLATES: Dict[str, str] = {
    "greeting": "Good {time_of_day}! This is your daily wellness check-in. How are you feeling today?",
    "mood": "How would you describe your mood today? Are you feeling happy, calm, anxious, or something else?",
    "pain": "Are you experiencing any pain or discomfort today? If so, where and how would you rate it?",
    "sleep": "How did you sleep last night? Did you get enough rest?",
    "hydration": "How much water or fluids have you had today? Have you been drinking enough?",
    "meals": "Have you had your meals today? What did you eat?",
    "summary": "Thank you for completing your check-in. Let me prepare your summary.",
}


def _generate_checkin_question(
    step: str,
    resident_id: str,
    session_id: str,
    correlation_id: str,
) -> str:
    """Generate a contextual check-in question for the current step.

    Uses a template fallback with optional Bedrock enhancement for
    personalisation based on prior responses.
    """
    # Determine time of day for greeting
    hour = datetime.now(timezone.utc).hour
    if hour < 12:
        time_of_day = "morning"
    elif hour < 17:
        time_of_day = "afternoon"
    else:
        time_of_day = "evening"

    # Use template as baseline
    template = _CHECKIN_QUESTION_TEMPLATES.get(step, "How are you doing?")
    baseline_question = template.format(time_of_day=time_of_day)

    # For greeting, use template directly (no context yet)
    if step == "greeting":
        return baseline_question

    # Try to enhance with Bedrock for follow-up steps
    try:
        session = _load_checkin_session(session_id, correlation_id)
        previous_responses = session.get("responses", {}) if session else {}

        context_lines = []
        for prev_step in CHECKIN_STEPS:
            if prev_step in previous_responses:
                context_lines.append(f"- {prev_step}: {previous_responses[prev_step]}")

        context_str = "\n".join(context_lines) if context_lines else "No prior responses yet."

        prompt = (
            "You are AETHER, a caring voice assistant conducting a daily wellness check-in "
            "with an elderly resident. Generate a warm, conversational question for the current step.\n\n"
            f"Current step: {step}\n"
            f"Previous responses:\n{context_str}\n\n"
            f"Default question for this step: \"{baseline_question}\"\n\n"
            "Generate a personalised version of this question that acknowledges their previous "
            "responses. Keep it short (1-2 sentences), warm, and easy to understand. "
            "Output only the question text, nothing else."
        )

        enhanced = invoke_bedrock_model(prompt, model_id=BEDROCK_MODEL_ID, max_tokens=150, temperature=0.6)
        enhanced = enhanced.strip().strip('"')
        if enhanced and len(enhanced) > 10:
            return enhanced
    except Exception as enhance_err:
        log_with_context(
            logger, "DEBUG",
            f"Bedrock question enhancement failed (using template): {enhance_err}",
            correlation_id=correlation_id,
        )

    return baseline_question


# ---------------------------------------------------------------------------
# Check-in summary generation
# ---------------------------------------------------------------------------

def _generate_checkin_summary(
    session_id: str,
    resident_id: str,
    correlation_id: str,
) -> Dict[str, Any]:
    """Generate a structured check-in summary report from collected responses."""
    session = _load_checkin_session(session_id, correlation_id)
    responses = session.get("responses", {}) if session else {}

    # Build report structure
    report: Dict[str, Any] = {
        "session_id": session_id,
        "resident_id": resident_id,
        "completed_at": get_current_timestamp(),
        "responses": dict(responses),
        "steps_completed": len(responses),
        "total_steps": len(CHECKIN_STEPS) - 2,  # exclude greeting and summary
    }

    # Use Bedrock to generate an AI summary and risk assessment
    try:
        responses_text = "\n".join(
            f"- {step}: {resp}" for step, resp in responses.items()
        )

        prompt = (
            "You are a clinical wellness analyst for an elderly care system. "
            "Analyse the following daily check-in responses and provide a structured assessment.\n\n"
            f"Resident ID: {resident_id}\n"
            f"Responses:\n{responses_text}\n\n"
            "Provide a JSON response with these fields:\n"
            "{\n"
            '  "overall_wellness_score": <1-10 integer>,\n'
            '  "mood_assessment": "<brief text>",\n'
            '  "concerns": ["<list of any concerns>"],\n'
            '  "recommendations": ["<list of recommendations>"],\n'
            '  "requires_follow_up": <true/false>,\n'
            '  "summary": "<2-3 sentence summary>"\n'
            "}\n"
            "Respond with valid JSON only."
        )

        raw = invoke_bedrock_model(prompt, model_id=BEDROCK_MODEL_ID, max_tokens=512, temperature=0.3)
        cleaned = raw.strip()
        if "```" in cleaned:
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        ai_assessment = json.loads(cleaned)
        report["ai_assessment"] = ai_assessment

    except Exception as ai_err:
        log_with_context(
            logger, "WARNING",
            f"AI summary generation failed: {ai_err}",
            correlation_id=correlation_id,
        )
        report["ai_assessment"] = {
            "overall_wellness_score": None,
            "summary": "AI assessment unavailable. Manual review recommended.",
            "requires_follow_up": True,
        }

    return report


def _store_checkin_event(
    resident_id: str,
    session_id: str,
    report: Dict[str, Any],
    correlation_id: str,
) -> None:
    """Store a completed check-in as an event in the events table."""
    now = get_current_timestamp()
    event_id = generate_event_id()

    wellness_score = None
    requires_follow_up = False
    ai_assessment = report.get("ai_assessment", {})
    if ai_assessment:
        wellness_score = ai_assessment.get("overall_wellness_score")
        requires_follow_up = ai_assessment.get("requires_follow_up", False)

    # Map wellness score to severity
    if wellness_score is not None:
        if wellness_score <= 3:
            severity = Severity.HIGH
        elif wellness_score <= 5:
            severity = Severity.MEDIUM
        elif wellness_score <= 7:
            severity = Severity.LOW
        else:
            severity = Severity.INFO
    else:
        severity = Severity.LOW

    event_record = {
        "home_id": resident_id,
        "timestamp": now,
        "event_id": event_id,
        "event_type": EventType.CHECK_IN_COMPLETED,
        "severity": severity,
        "resident_id": resident_id,
        "source": "voice_processor",
        "description": f"Daily check-in completed via voice (session: {session_id})",
        "check_in_session_id": session_id,
        "wellness_score": wellness_score,
        "requires_follow_up": requires_follow_up,
        "check_in_report": json_dumps(report),
        "acknowledged": not requires_follow_up,
        "correlation_id": correlation_id,
    }

    try:
        dynamo_put_item(events_table_name(), event_record)
        log_with_context(
            logger, "INFO",
            f"Check-in event stored: {event_id}, wellness_score={wellness_score}",
            correlation_id=correlation_id,
        )
    except Exception as db_err:
        log_with_context(logger, "ERROR", f"Failed to store check-in event: {db_err}", correlation_id=correlation_id)

    # If follow-up required, publish SNS alert
    if requires_follow_up:
        topic_arn = alerts_topic_arn()
        if topic_arn:
            try:
                sns_publish_structured_alert(
                    topic_arn=topic_arn,
                    event_type=EventType.CHECK_IN_COMPLETED,
                    severity=severity,
                    home_id=resident_id,
                    message=json_dumps({
                        "event_id": event_id,
                        "resident_id": resident_id,
                        "session_id": session_id,
                        "wellness_score": wellness_score,
                        "concerns": ai_assessment.get("concerns", []),
                        "timestamp": now,
                        "source": "voice_processor",
                    }),
                )
            except Exception as sns_err:
                log_with_context(logger, "ERROR", f"Failed to publish check-in alert: {sns_err}", correlation_id=correlation_id)
