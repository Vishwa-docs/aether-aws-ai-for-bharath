"""
AETHER Edge Voice Pipeline – Intent Classifier
================================================
Classifies free-text utterances into care-relevant intents using a fast
rule-based (keyword) engine on-device, with optional Bedrock-powered
classification when cloud connectivity is available.

Designed for elderly care voice interactions: alert cancellation,
check-ins, medication queries, emergency detection, etc.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("aether.voice.intent_classifier")

SIMULATOR_MODE = os.getenv("SIMULATOR_MODE", "true").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Intent enum
# ---------------------------------------------------------------------------

class Intent(str, Enum):
    """Recognised voice intents for the AETHER care system."""

    CANCEL_ALERT = "cancel_alert"
    CONFIRM_OK = "confirm_ok"
    CALL_CONTACT = "call_contact"
    MEDICATION_QUERY = "medication_query"
    HEALTH_QUERY = "health_query"
    EMERGENCY = "emergency"
    DAILY_CHECKIN = "daily_checkin"
    SET_REMINDER = "set_reminder"
    GENERAL = "general"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    """Output of intent classification."""

    intent: Intent
    confidence: float  # 0.0 – 1.0
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""


# ---------------------------------------------------------------------------
# Keyword tables
# ---------------------------------------------------------------------------

# Each entry: (intent, keyword_phrases, base_confidence)
_KEYWORD_TABLE: List[Tuple[Intent, List[str], float]] = [
    (
        Intent.EMERGENCY,
        [
            "help", "emergency", "fell", "fall", "fallen",
            "can't breathe", "cannot breathe", "chest pain",
            "heart attack", "stroke", "bleeding", "unconscious",
        ],
        0.92,
    ),
    (
        Intent.CANCEL_ALERT,
        [
            "cancel", "false alarm", "stop", "i'm fine", "i am fine",
            "i'm okay", "i am okay", "never mind", "nevermind",
            "not an emergency", "no alert",
        ],
        0.90,
    ),
    (
        Intent.CONFIRM_OK,
        [
            "yes", "okay", "i'm alright", "i am alright", "all good",
            "doing fine", "no problem", "that's correct", "correct",
        ],
        0.88,
    ),
    (
        Intent.CALL_CONTACT,
        [
            "call my son", "call my daughter", "call nurse",
            "call doctor", "call my wife", "call my husband",
            "call my family", "phone", "ring",
        ],
        0.90,
    ),
    (
        Intent.MEDICATION_QUERY,
        [
            "medicine", "medication", "pill", "tablet",
            "when should i take", "drug", "prescription",
            "dosage", "next dose", "refill",
        ],
        0.88,
    ),
    (
        Intent.HEALTH_QUERY,
        [
            "blood pressure", "sugar level", "glucose",
            "health", "feeling", "temperature", "heart rate",
            "oxygen", "spo2", "pulse", "weight",
        ],
        0.85,
    ),
    (
        Intent.DAILY_CHECKIN,
        [
            "check in", "checkin", "check-in", "morning",
            "how am i", "daily report", "status",
        ],
        0.85,
    ),
    (
        Intent.SET_REMINDER,
        [
            "remind me", "set alarm", "wake me", "reminder",
            "set a timer", "alert me", "notify me",
        ],
        0.87,
    ),
]

# ---------------------------------------------------------------------------
# Entity extraction patterns
# ---------------------------------------------------------------------------

_CONTACT_PATTERN = re.compile(
    r"call\s+(?:my\s+)?(\w+)", re.IGNORECASE
)

_MEDICATION_NAME_PATTERN = re.compile(
    r"(?:take|taking|took|about)\s+(?:my\s+)?(\w+)", re.IGNORECASE
)

_TIME_PATTERN = re.compile(
    r"(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?)", re.IGNORECASE
)

_PAIN_LEVEL_PATTERN = re.compile(
    r"(?:pain|hurt|ache).*?(\d{1,2})\s*(?:out of|/)\s*10",
    re.IGNORECASE,
)

_SIMPLE_PAIN_PATTERN = re.compile(
    r"pain\s+(?:level\s+)?(?:is\s+)?(\d{1,2})",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Intent Classifier
# ---------------------------------------------------------------------------

class IntentClassifier:
    """Classify free-text into one of AETHER's care intents.

    Two classification backends:

    1. **Rule-based** (default / offline) – fast keyword matching suitable
       for edge devices without connectivity.
    2. **Bedrock** – sends the utterance to Amazon Bedrock for LLM-based
       classification when cloud access is available.

    Parameters
    ----------
    use_bedrock : bool
        Attempt Bedrock classification before falling back to rules.
    bedrock_model_id : str
        Foundation model ID for Bedrock.
    region_name : str
        AWS region for the Bedrock client.
    simulator : bool | None
        Force simulator (rule-based only) mode.
    """

    def __init__(
        self,
        use_bedrock: bool = False,
        bedrock_model_id: str = "amazon.nova-lite-v1:0",
        region_name: Optional[str] = None,
        simulator: Optional[bool] = None,
    ) -> None:
        self._use_bedrock = use_bedrock
        self._bedrock_model_id = bedrock_model_id
        self._region = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self._simulator = simulator if simulator is not None else SIMULATOR_MODE

        self._bedrock_client = None
        if self._use_bedrock and not self._simulator:
            try:
                import boto3
                from botocore.config import Config as BotoConfig

                self._bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=self._region,
                    config=BotoConfig(read_timeout=30),
                )
                logger.info("Bedrock client initialised for intent classification")
            except Exception as exc:
                logger.warning("Bedrock client init failed – using rule-based: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str) -> IntentResult:
        """Classify an utterance into an AETHER intent.

        Tries Bedrock first (if enabled), then falls back to rules.
        """
        if not text or not text.strip():
            return IntentResult(
                intent=Intent.GENERAL,
                confidence=0.0,
                raw_text=text,
            )

        normalised = text.strip().lower()

        # Try Bedrock
        if self._bedrock_client is not None:
            try:
                result = self._classify_bedrock(text)
                if result.confidence >= 0.6:
                    logger.info(
                        "Bedrock intent: %s (%.2f) for '%s'",
                        result.intent.value,
                        result.confidence,
                        text[:60],
                    )
                    return result
            except Exception as exc:
                logger.warning("Bedrock classification failed – falling back: %s", exc)

        # Rule-based
        result = self._classify_rules(normalised)
        result.raw_text = text

        # Entity extraction
        result.entities = self._extract_entities(normalised, result.intent)

        logger.info(
            "Rule-based intent: %s (%.2f) entities=%s for '%s'",
            result.intent.value,
            result.confidence,
            result.entities,
            text[:60],
        )
        return result

    # ------------------------------------------------------------------
    # Rule-based classifier
    # ------------------------------------------------------------------

    def _classify_rules(self, text: str) -> IntentResult:
        """Match utterance against the keyword table.

        Returns the intent whose keywords score highest. When multiple
        intents match, the one with the most keyword hits wins; ties are
        broken by the table's base confidence.
        """
        best_intent = Intent.GENERAL
        best_score = 0.0
        best_hits = 0

        for intent, keywords, base_conf in _KEYWORD_TABLE:
            hits = sum(1 for kw in keywords if kw in text)
            if hits > 0:
                score = base_conf + 0.02 * (hits - 1)  # slight boost for multiple hits
                score = min(score, 0.99)
                if hits > best_hits or (hits == best_hits and score > best_score):
                    best_intent = intent
                    best_score = score
                    best_hits = hits

        if best_hits == 0:
            return IntentResult(intent=Intent.GENERAL, confidence=0.4, raw_text=text)

        return IntentResult(intent=best_intent, confidence=best_score, raw_text=text)

    # ------------------------------------------------------------------
    # Entity extraction
    # ------------------------------------------------------------------

    def _extract_entities(self, text: str, intent: Intent) -> Dict[str, Any]:
        """Pull structured entities from the utterance."""
        entities: Dict[str, Any] = {}

        # Contact name
        if intent == Intent.CALL_CONTACT:
            m = _CONTACT_PATTERN.search(text)
            if m:
                entities["contact_name"] = m.group(1)

        # Medication name
        if intent == Intent.MEDICATION_QUERY:
            m = _MEDICATION_NAME_PATTERN.search(text)
            if m:
                entities["medication_name"] = m.group(1)

        # Time
        m = _TIME_PATTERN.search(text)
        if m:
            entities["time"] = m.group(1).strip()

        # Pain level
        m = _PAIN_LEVEL_PATTERN.search(text)
        if m:
            entities["pain_level"] = int(m.group(1))
        else:
            m = _SIMPLE_PAIN_PATTERN.search(text)
            if m:
                entities["pain_level"] = int(m.group(1))

        return entities

    # ------------------------------------------------------------------
    # Bedrock-based classifier
    # ------------------------------------------------------------------

    def _classify_bedrock(self, text: str) -> IntentResult:
        """Use Amazon Bedrock to classify the utterance."""

        intent_list = ", ".join(i.value for i in Intent)
        prompt = (
            "You are an intent classifier for an elderly care voice assistant called AETHER.\n"
            f"Valid intents: {intent_list}\n\n"
            "Respond with ONLY a JSON object: {\"intent\": \"<intent>\", \"confidence\": <0-1>, "
            "\"entities\": {<extracted entities>}}\n\n"
            "Entities to extract when relevant:\n"
            "- contact_name (for call_contact)\n"
            "- medication_name (for medication_query)\n"
            "- time (any mentioned time)\n"
            "- pain_level (1-10 scale)\n\n"
            f"Utterance: \"{text}\"\n"
        )

        body = json.dumps(
            {
                "inputText": prompt,
                "textGenerationConfig": {
                    "maxTokenCount": 200,
                    "temperature": 0.1,
                    "topP": 0.9,
                },
            }
        )

        resp = self._bedrock_client.invoke_model(
            modelId=self._bedrock_model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        result_body = json.loads(resp["body"].read())
        output_text = ""
        if "results" in result_body:
            output_text = result_body["results"][0].get("outputText", "")
        elif "output" in result_body:
            output_text = result_body["output"].get("text", "")

        # Parse JSON from response
        try:
            # Find JSON object in response
            json_match = re.search(r"\{[^{}]+\}", output_text)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                parsed = json.loads(output_text)

            intent_str = parsed.get("intent", "general")
            try:
                intent = Intent(intent_str)
            except ValueError:
                intent = Intent.GENERAL

            return IntentResult(
                intent=intent,
                confidence=float(parsed.get("confidence", 0.7)),
                entities=parsed.get("entities", {}),
                raw_text=text,
            )
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            logger.warning("Could not parse Bedrock response: %s – %s", output_text[:100], exc)
            raise
