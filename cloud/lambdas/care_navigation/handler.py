"""
AETHER Care Navigation Lambda
===============================
Accepts natural-language care queries from family caregivers and returns
AI-generated responses using Amazon Bedrock with RAG (Knowledge Bases).

Safety guardrails
------------------
- NEVER provides a medical diagnosis.
- Always recommends consulting a healthcare provider for serious concerns.
- Includes safety disclaimers in every response.
- Supports multi-language responses.
- All queries and responses are logged for audit.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.models import get_current_timestamp
from shared.utils import (
    api_error,
    api_response,
    bedrock_model_id,
    dynamo_put_item,
    generate_correlation_id,
    get_env,
    invoke_bedrock_model,
    json_dumps,
    knowledge_base_id,
    log_with_context,
    retrieve_and_generate,
    setup_logger,
)

logger = setup_logger("care_navigation")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AUDIT_TABLE = get_env("CARE_NAV_AUDIT_TABLE", "aether-care-navigation-audit")
MAX_QUERY_LENGTH = int(get_env("MAX_QUERY_LENGTH", "2000"))
DEFAULT_LANGUAGE = get_env("DEFAULT_LANGUAGE", "en")

# Supported languages (ISO 639-1)
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "hi": "Hindi",
    "ar": "Arabic",
}

# Safety disclaimer appended to every response
SAFETY_DISCLAIMER = (
    "\n\n---\n"
    "**Disclaimer:** This information is provided for general guidance only and "
    "does not constitute medical advice, diagnosis, or treatment. Always consult "
    "a qualified healthcare professional for medical concerns. If you believe "
    "there is a medical emergency, call emergency services immediately."
)

SAFETY_DISCLAIMER_TRANSLATIONS: Dict[str, str] = {
    "es": (
        "\n\n---\n"
        "**Aviso:** Esta información es solo orientativa y no constituye consejo "
        "médico, diagnóstico ni tratamiento. Consulte siempre a un profesional "
        "sanitario cualificado. En caso de emergencia, llame a los servicios de emergencia."
    ),
    "fr": (
        "\n\n---\n"
        "**Avertissement :** Ces informations sont fournies à titre indicatif "
        "uniquement et ne constituent pas un avis médical. Consultez toujours un "
        "professionnel de santé qualifié. En cas d'urgence, appelez les services d'urgence."
    ),
}


# System prompt with guardrails
_SYSTEM_PROMPT = """You are AETHER Care Navigator, a compassionate and knowledgeable assistant
for family caregivers of elderly individuals living independently.

STRICT RULES you MUST follow:
1. NEVER provide a medical diagnosis.
2. NEVER prescribe or recommend specific medications or dosages.
3. NEVER tell the user NOT to seek medical attention.
4. For ANY symptom that could indicate a serious condition (chest pain, stroke signs,
   difficulty breathing, severe bleeding, sudden confusion, etc.), ALWAYS recommend
   calling emergency services or visiting the ER immediately.
5. Always recommend consulting a healthcare provider for persistent or worsening symptoms.
6. Be empathetic, concise, and actionable in your responses.
7. When uncertain, err on the side of recommending professional medical evaluation.
8. Use plain language appropriate for non-medical caregivers.
9. If asked about the AETHER system features, answer based on your knowledge.
10. Respond in the language requested by the user.

You may provide:
- General wellness information
- Signs and symptoms to watch for
- When to seek emergency care vs. routine care
- Caregiving tips and best practices
- Emotional support and caregiver self-care advice
- Explanation of common medical terms in plain language
"""

# Emergency keywords that trigger immediate ER guidance
_EMERGENCY_KEYWORDS = {
    "chest pain", "heart attack", "stroke", "can't breathe", "cannot breathe",
    "unconscious", "unresponsive", "severe bleeding", "choking", "seizure",
    "suicidal", "suicide", "overdose", "poisoning", "anaphylaxis",
    "not breathing", "stopped breathing", "no pulse",
}


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point.

    Accepts API Gateway proxy events or direct invocations with a ``query``
    field.
    """
    correlation_id = generate_correlation_id()
    log_with_context(logger, "INFO", "Care navigation invoked", correlation_id=correlation_id)

    try:
        # Parse request
        request = _parse_request(event)
        query = request.get("query", "").strip()
        language = request.get("language", DEFAULT_LANGUAGE).lower()
        home_id = request.get("home_id", "unknown")
        user_id = request.get("user_id", "anonymous")
        session_id = request.get("session_id", "")

        # Validate
        if not query:
            return api_error(400, "missing_query", "The 'query' field is required.", correlation_id)

        if len(query) > MAX_QUERY_LENGTH:
            return api_error(
                400, "query_too_long",
                f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters.",
                correlation_id,
            )

        if language not in SUPPORTED_LANGUAGES:
            language = DEFAULT_LANGUAGE

        log_with_context(
            logger, "INFO",
            f"Processing care query",
            correlation_id=correlation_id,
            language=language,
            query_length=len(query),
            home_id=home_id,
        )

        # Check for emergency keywords
        emergency_detected = _detect_emergency(query)

        # Generate response
        response_text, citations, model_used = _generate_response(
            query=query,
            language=language,
            emergency_detected=emergency_detected,
            correlation_id=correlation_id,
        )

        # Append safety disclaimer
        disclaimer = SAFETY_DISCLAIMER_TRANSLATIONS.get(language, SAFETY_DISCLAIMER)
        full_response = response_text + disclaimer

        # Build result
        result: Dict[str, Any] = {
            "response": full_response,
            "language": language,
            "emergency_detected": emergency_detected,
            "citations": citations,
            "model_used": model_used,
            "correlation_id": correlation_id,
        }

        # Audit log
        _audit_log(
            correlation_id=correlation_id,
            query=query,
            response=response_text,
            language=language,
            home_id=home_id,
            user_id=user_id,
            session_id=session_id,
            emergency_detected=emergency_detected,
            model_used=model_used,
        )

        return api_response(200, result)

    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Care navigation error: {exc}",
            correlation_id=correlation_id,
            traceback=traceback.format_exc(),
        )
        return api_error(500, "internal_error", "An internal error occurred. Please try again.", correlation_id)


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

def _parse_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the query payload from an API Gateway or direct invocation."""
    # API Gateway proxy
    if "body" in event and isinstance(event["body"], str):
        try:
            return json.loads(event["body"])
        except json.JSONDecodeError:
            return {"query": event["body"]}

    if "body" in event and isinstance(event["body"], dict):
        return event["body"]

    # Direct invocation
    return event


# ---------------------------------------------------------------------------
# Emergency detection
# ---------------------------------------------------------------------------

def _detect_emergency(query: str) -> bool:
    """Scan the query for emergency keywords."""
    query_lower = query.lower()
    return any(kw in query_lower for kw in _EMERGENCY_KEYWORDS)


_EMERGENCY_PREFIX = (
    "⚠️ **This sounds like it could be a medical emergency.** "
    "If someone is in immediate danger, please call emergency services (911 / 112 / 108) right away. "
    "Do not wait for this response to take action.\n\n"
)


# ---------------------------------------------------------------------------
# Response generation
# ---------------------------------------------------------------------------

def _generate_response(
    query: str,
    language: str,
    emergency_detected: bool,
    correlation_id: str,
) -> tuple:
    """Generate a care navigation response using Bedrock.

    Returns:
        Tuple of ``(response_text, citations, model_used)``.
    """
    citations: List[Dict[str, Any]] = []
    model_used = bedrock_model_id()

    # Try RAG approach first (Knowledge Bases)
    kb_id = knowledge_base_id()
    if kb_id:
        try:
            rag_result = _query_knowledge_base(query, language, kb_id, correlation_id)
            response_text = rag_result.get("output", "")
            citations = rag_result.get("citations", [])
            model_used = f"rag:{model_used}"

            if response_text:
                if emergency_detected:
                    response_text = _EMERGENCY_PREFIX + response_text
                return response_text, citations, model_used
        except Exception as exc:
            log_with_context(
                logger, "WARNING",
                f"RAG query failed, falling back to direct model: {exc}",
                correlation_id=correlation_id,
            )

    # Fallback: direct model invocation
    response_text = _query_direct_model(query, language, emergency_detected, correlation_id)
    return response_text, citations, model_used


def _query_knowledge_base(
    query: str,
    language: str,
    kb_id: str,
    correlation_id: str,
) -> Dict[str, Any]:
    """Query Bedrock Knowledge Base with retrieve-and-generate."""
    lang_instruction = ""
    if language != "en":
        lang_name = SUPPORTED_LANGUAGES.get(language, language)
        lang_instruction = f"\n\nPlease respond in {lang_name}."

    augmented_query = f"{query}{lang_instruction}"

    log_with_context(
        logger, "INFO",
        "Querying Knowledge Base",
        correlation_id=correlation_id,
        kb_id=kb_id,
    )

    result = retrieve_and_generate(
        query=augmented_query,
        kb_id=kb_id,
    )

    return result


def _query_direct_model(
    query: str,
    language: str,
    emergency_detected: bool,
    correlation_id: str,
) -> str:
    """Query Bedrock model directly without RAG."""
    lang_instruction = ""
    if language != "en":
        lang_name = SUPPORTED_LANGUAGES.get(language, language)
        lang_instruction = f"\nRespond in {lang_name}."

    prompt = f"""{_SYSTEM_PROMPT}
{lang_instruction}

User Question: {query}

Provide a helpful, empathetic response following all the rules above."""

    log_with_context(
        logger, "INFO",
        "Querying Bedrock model directly",
        correlation_id=correlation_id,
    )

    response_text = invoke_bedrock_model(
        prompt=prompt,
        max_tokens=1024,
        temperature=0.4,
    )

    if emergency_detected:
        response_text = _EMERGENCY_PREFIX + response_text

    return response_text.strip()


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

def _audit_log(
    correlation_id: str,
    query: str,
    response: str,
    language: str,
    home_id: str,
    user_id: str,
    session_id: str,
    emergency_detected: bool,
    model_used: str,
) -> None:
    """Persist query and response to the audit table for compliance."""
    timestamp = get_current_timestamp()

    audit_record: Dict[str, Any] = {
        "correlation_id": correlation_id,
        "timestamp": timestamp,
        "home_id": home_id,
        "user_id": user_id,
        "session_id": session_id,
        "query": query,
        "response_preview": response[:500],  # truncate for storage efficiency
        "response_length": len(response),
        "language": language,
        "emergency_detected": emergency_detected,
        "model_used": model_used,
    }

    try:
        dynamo_put_item(AUDIT_TABLE, audit_record)
        log_with_context(
            logger, "INFO",
            "Audit record stored",
            correlation_id=correlation_id,
            table=AUDIT_TABLE,
        )
    except Exception as exc:
        # Audit failure should not break the user-facing flow
        log_with_context(
            logger, "ERROR",
            f"Failed to store audit record: {exc}",
            correlation_id=correlation_id,
        )
