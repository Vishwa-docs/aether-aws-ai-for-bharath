"""
AETHER LLM Safety Guardrails
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A comprehensive safety layer for all LLM interactions in the AETHER
elder-care system.  Ensures that AI outputs never cross clinical
boundaries, detects emergencies, sanitises PHI, and blocks prompt-
injection attacks.

Features
--------
* Regex-based detection of medical diagnosis, prescription, and dosage language
* Emergency keyword detection (English + Hindi)
* AWS Bedrock Guardrails API integration (with local rule-based fallback)
* PHI sanitisation (SSN, phone, email, address, DOB, MRN patterns)
* Prompt-injection detection
* Configurable severity levels and audit logging
* Teach-back validation helpers
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Enums & result dataclasses
# ---------------------------------------------------------------------------

class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Violation:
    """A single guardrail violation."""
    rule: str
    severity: Severity
    matched_text: str
    description: str


@dataclass
class ValidationResult:
    """Result of a guardrail validation check."""
    is_safe: bool
    violations: List[Violation] = field(default_factory=list)
    sanitized_text: Optional[str] = None
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)

    @property
    def highest_severity(self) -> Optional[Severity]:
        if not self.violations:
            return None
        order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        return max(self.violations, key=lambda v: order.index(v.severity)).severity


@dataclass
class GuardrailResult:
    """Result from the full apply_guardrail pipeline."""
    action: str  # "ALLOWED", "MODIFIED", "BLOCKED"
    original_response: str
    final_response: str
    input_validation: Optional[ValidationResult] = None
    output_validation: Optional[ValidationResult] = None
    bedrock_applied: bool = False
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Pattern libraries
# ---------------------------------------------------------------------------

# Medical diagnosis patterns — NEVER let the AI diagnose
_DIAGNOSIS_PATTERNS = [
    r"\byou\s+have\s+(?:been\s+)?(?:diagnosed\s+with\s+)?\w+",
    r"\bdiagnos(?:e|is|ed|ing)\b",
    r"\byou(?:'re| are)\s+(?:likely\s+)?suffering\s+from\b",
    r"\bthis\s+(?:is|looks?\s+like|appears?\s+to\s+be|could\s+be|seems?\s+like)\s+(?:a\s+case\s+of\s+)?\w+\s*(?:disease|syndrome|disorder|condition|infection)\b",
    r"\bI\s+(?:think|believe|suspect)\s+(?:you\s+have|this\s+is|it\'s)\b",
    r"\bmy\s+(?:assessment|evaluation|clinical\s+judgment)\b",
    r"\bpathology\s+(?:indicates|suggests|confirms)\b",
    r"\bprognosis\b",
    r"\bdifferential\s+diagnosis\b",
]

# Prescription / dosage patterns — NEVER prescribe
_PRESCRIPTION_PATTERNS = [
    r"\btake\s+\d+\s*(?:mg|ml|mcg|units?|tablets?|capsules?|pills?)\b",
    r"\bprescri(?:be|ption|bed|bing)\b",
    r"\bincrease\s+(?:your\s+)?(?:dose|dosage|medication)\b",
    r"\bdecrease\s+(?:your\s+)?(?:dose|dosage|medication)\b",
    r"\bchange\s+(?:your\s+)?(?:dose|dosage|medication)\b",
    r"\bstop\s+taking\b",
    r"\bstart\s+taking\b",
    r"\bswitch\s+(?:to|from)\s+\w+\s*(?:mg|ml)?\b",
    r"\b\d+\s*(?:mg|ml|mcg)\s+(?:once|twice|three\s+times|daily|hourly|every)\b",
    r"\badminister\s+\d+\b",
    r"\bdosage\s+(?:adjustment|change|modification)\b",
    r"\btitrat(?:e|ion|ing)\b",
]

# Harmful / inappropriate content patterns
_HARMFUL_PATTERNS = [
    r"\bkill\s+(?:your|him|her|them)self\b",
    r"\bsuicid(?:e|al)\b",
    r"\bself[- ]?harm\b",
    r"\bend\s+(?:your|their|his|her)\s+life\b",
    r"\bnot\s+worth\s+living\b",
    r"\bgive\s+up\s+on\s+(?:life|treatment)\b",
]

# Emergency keywords — English
_EMERGENCY_KEYWORDS_EN = [
    r"\bchest\s+pain\b",
    r"\bcan'?t\s+breathe\b",
    r"\bdifficulty\s+breathing\b",
    r"\bshortness\s+of\s+breath\b",
    r"\bstroke\b",
    r"\bheart\s+attack\b",
    r"\bbleeding\s+(?:a\s+lot|heavily|profusely|won'?t\s+stop)\b",
    r"\bsevere\s+bleeding\b",
    r"\bunconscious\b",
    r"\bpassed\s+out\b",
    r"\bfainted\b",
    r"\bseizure\b",
    r"\bconvulsion\b",
    r"\bchoking\b",
    r"\bcan'?t\s+(?:move|feel)\s+(?:my|the)\s+(?:arm|leg|side|face)\b",
    r"\bsudden\s+(?:weakness|numbness|confusion|vision\s+(?:loss|change))\b",
    r"\bhead\s+(?:injury|trauma)\b",
    r"\bfall(?:en|ing)\s+(?:down|over|and\s+hit)\b",
    r"\bsevere\s+(?:pain|headache|allergic)\b",
    r"\banaphyla(?:xis|ctic)\b",
    r"\boverdose\b",
    r"\bpoisoning\b",
    r"\bsuicid(?:e|al)\b",
    r"\bhelp\s+me\b",
    r"\bcall\s+(?:911|ambulance|emergency|doctor\s+now)\b",
]

# Emergency keywords — Hindi (transliterated)
_EMERGENCY_KEYWORDS_HI = [
    r"\bseene\s+mein\s+dard\b",       # chest pain
    r"\bsaans\s+nahi\b",              # can't breathe
    r"\bsaans\s+lene\s+mein\b",       # difficulty breathing
    r"\bkhoon\s+(?:beh|bah)\s+raha\b", # bleeding
    r"\bbeho(?:o)?sh\b",              # unconscious
    r"\bgir\s+(?:gaya|gayi|pade)\b",  # fallen
    r"\bdaurah?\s+pad\b",             # seizure
    r"\bdil\s+ka\s+daura\b",          # heart attack
    r"\bstroke\b",
    r"\btej\s+dard\b",               # severe pain
    r"\bmadad\b",                     # help
    r"\bambulance\s+bulao\b",         # call ambulance
    r"\bdoctor\s+ko\s+bulao\b",       # call doctor
    r"\bjaan\s+khatre\s+mein\b",      # life in danger
]

# Prompt injection patterns
_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules)",
    r"disregard\s+(?:all\s+)?(?:previous|prior|above|your)\s+(?:instructions|guidelines|rules|programming)",
    r"you\s+are\s+now\s+(?:a|an|the)\s+(?:different|new)\b",
    r"forget\s+(?:all\s+)?(?:everything|your\s+(?:instructions|rules|guidelines))",
    r"(?:system|admin)\s*(?:prompt|mode|override)\s*:",
    r"(?:act|pretend|behave)\s+(?:as\s+if|like)\s+(?:you\s+(?:are|were)|there\s+(?:are|were))\s+no\s+(?:rules|restrictions|guardrails)",
    r"jailbreak",
    r"DAN\s+mode",
    r"\bdo\s+anything\s+now\b",
    r"bypass\s+(?:your\s+)?(?:safety|content|guardrail|filter)",
    r"reveal\s+(?:your\s+)?(?:system\s+)?prompt",
    r"output\s+(?:your\s+)?(?:system\s+)?(?:prompt|instructions)",
]

# PHI patterns
_PHI_PATTERNS = {
    "ssn": (re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"), "***-**-****"),
    "phone": (re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[PHONE REDACTED]"),
    "email": (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL REDACTED]"),
    "dob": (re.compile(r"\b(?:0[1-9]|1[0-2])[/\-](?:0[1-9]|[12]\d|3[01])[/\-](?:19|20)\d{2}\b"), "[DOB REDACTED]"),
    "mrn": (re.compile(r"\bMRN\s*[:#]?\s*\d{5,10}\b", re.IGNORECASE), "[MRN REDACTED]"),
    "address": (
        re.compile(
            r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}(?:St(?:reet)?|Ave(?:nue)?|Blvd|Dr(?:ive)?|"
            r"Rd|Road|Ln|Lane|Ct|Court|Pl|Place|Way|Circle|Cir)\b\.?",
            re.IGNORECASE,
        ),
        "[ADDRESS REDACTED]",
    ),
}

# Required disclaimers by topic
_REQUIRED_DISCLAIMERS = {
    "medical": (
        "Please note: I am an AI assistant, not a medical professional. "
        "This information is not a substitute for professional medical advice, "
        "diagnosis, or treatment. Please consult your healthcare provider."
    ),
    "medication": (
        "Important: Never change or stop your medication without consulting your "
        "doctor or pharmacist first."
    ),
    "mental_health": (
        "If you or someone you know is in crisis, please contact your care team "
        "or call emergency services immediately."
    ),
    "nutrition": (
        "Dietary suggestions are general in nature. Please consult a dietitian or "
        "your healthcare provider for personalised advice."
    ),
    "exercise": (
        "Please check with your doctor before starting any new exercise routine, "
        "especially if you have existing health conditions."
    ),
    "general": (
        "I'm here to help, but I'm an AI assistant. For any health concerns, "
        "please reach out to your care team."
    ),
}

# Compile pattern lists once at import time
_COMPILED_DIAGNOSIS = [re.compile(p, re.IGNORECASE) for p in _DIAGNOSIS_PATTERNS]
_COMPILED_PRESCRIPTION = [re.compile(p, re.IGNORECASE) for p in _PRESCRIPTION_PATTERNS]
_COMPILED_HARMFUL = [re.compile(p, re.IGNORECASE) for p in _HARMFUL_PATTERNS]
_COMPILED_EMERGENCY_EN = [re.compile(p, re.IGNORECASE) for p in _EMERGENCY_KEYWORDS_EN]
_COMPILED_EMERGENCY_HI = [re.compile(p, re.IGNORECASE) for p in _EMERGENCY_KEYWORDS_HI]
_COMPILED_INJECTION = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


# ---------------------------------------------------------------------------
# AetherGuardrails
# ---------------------------------------------------------------------------

class AetherGuardrails:
    """Safety guardrails for all LLM outputs in the AETHER system.

    Parameters
    ----------
    guardrail_id : str, optional
        AWS Bedrock Guardrail identifier.  When provided, the Bedrock
        Guardrails API is used for an additional layer of validation.
    guardrail_version : str
        Version of the Bedrock guardrail to use (default ``"DRAFT"``).
    audit_log_path : str, optional
        File path for the audit log.  If not set, audit entries are emitted
        via the ``logging`` module only.
    """

    BLOCKED_PATTERNS = _DIAGNOSIS_PATTERNS + _PRESCRIPTION_PATTERNS + _HARMFUL_PATTERNS
    REQUIRED_DISCLAIMERS = _REQUIRED_DISCLAIMERS
    EMERGENCY_KEYWORDS = _EMERGENCY_KEYWORDS_EN + _EMERGENCY_KEYWORDS_HI

    def __init__(
        self,
        *,
        guardrail_id: Optional[str] = None,
        guardrail_version: str = "DRAFT",
        audit_log_path: Optional[str] = None,
    ):
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version
        self.audit_log_path = audit_log_path
        self._bedrock_client = None

        if self.guardrail_id:
            try:
                import boto3
                self._bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=os.environ.get("AWS_REGION", "us-east-1"),
                )
                logger.info(
                    "Bedrock Guardrails client initialised (guardrail_id=%s)",
                    self.guardrail_id,
                )
            except Exception as exc:
                logger.warning("Bedrock client unavailable: %s — using local rules only", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_input(self, text: str) -> ValidationResult:
        """Validate user input for injection attacks and inappropriate content."""
        violations: List[Violation] = []

        # 1. Prompt injection detection
        for pat in _COMPILED_INJECTION:
            match = pat.search(text)
            if match:
                violations.append(Violation(
                    rule="prompt_injection",
                    severity=Severity.CRITICAL,
                    matched_text=match.group(),
                    description="Potential prompt-injection attack detected.",
                ))

        # 2. Harmful content in input
        for pat in _COMPILED_HARMFUL:
            match = pat.search(text)
            if match:
                violations.append(Violation(
                    rule="harmful_content_input",
                    severity=Severity.HIGH,
                    matched_text=match.group(),
                    description="Potentially harmful / self-harm language detected in input.",
                ))

        is_safe = len(violations) == 0
        result = ValidationResult(
            is_safe=is_safe,
            violations=violations,
            sanitized_text=text if is_safe else None,
        )
        self._audit("validate_input", text, result)
        return result

    def validate_output(
        self,
        text: str,
        context: str = "general",
    ) -> ValidationResult:
        """Validate an LLM-generated output for safety violations.

        Checks
        ------
        1. Medical diagnosis language
        2. Prescription / dosage advice
        3. Harmful content
        4. Contradicting care plan (flagged, cannot fully verify without plan)
        """
        violations: List[Violation] = []

        # 1. Diagnosis
        for pat in _COMPILED_DIAGNOSIS:
            match = pat.search(text)
            if match:
                violations.append(Violation(
                    rule="medical_diagnosis",
                    severity=Severity.HIGH,
                    matched_text=match.group(),
                    description="LLM output contains diagnostic language. AI must never diagnose.",
                ))

        # 2. Prescription / dosage
        for pat in _COMPILED_PRESCRIPTION:
            match = pat.search(text)
            if match:
                violations.append(Violation(
                    rule="prescription_advice",
                    severity=Severity.CRITICAL,
                    matched_text=match.group(),
                    description="LLM output contains prescription or dosage language. AI must never prescribe.",
                ))

        # 3. Harmful content
        for pat in _COMPILED_HARMFUL:
            match = pat.search(text)
            if match:
                violations.append(Violation(
                    rule="harmful_content_output",
                    severity=Severity.CRITICAL,
                    matched_text=match.group(),
                    description="LLM output contains potentially harmful content.",
                ))

        is_safe = len(violations) == 0
        sanitized = text if is_safe else self._strip_violations(text, violations)
        result = ValidationResult(
            is_safe=is_safe,
            violations=violations,
            sanitized_text=sanitized,
        )
        self._audit("validate_output", text, result, context=context)
        return result

    def apply_guardrail(
        self,
        prompt: str,
        response: str,
    ) -> GuardrailResult:
        """Full guardrail pipeline: validate input, validate output, optionally
        use Bedrock Guardrails API, then return the final result."""

        # Step 1 — validate input
        input_val = self.validate_input(prompt)

        # Step 2 — if input is unsafe, block immediately
        if not input_val.is_safe:
            gr = GuardrailResult(
                action="BLOCKED",
                original_response=response,
                final_response=(
                    "I'm sorry, but I wasn't able to process that request. "
                    "Could you please rephrase your question?"
                ),
                input_validation=input_val,
            )
            self._audit("apply_guardrail", prompt, gr)
            return gr

        # Step 3 — validate output (local rules)
        output_val = self.validate_output(response)

        # Step 4 — Bedrock Guardrails API (if configured)
        bedrock_applied = False
        bedrock_action = None
        bedrock_output = response
        if self._bedrock_client and self.guardrail_id:
            try:
                bedrock_result = self._invoke_bedrock_guardrail(prompt, response)
                bedrock_applied = True
                bedrock_action = bedrock_result.get("action", "NONE")
                if bedrock_action == "GUARDRAIL_INTERVENED":
                    # Use the Bedrock-sanitised output
                    outputs = bedrock_result.get("outputs", [])
                    if outputs:
                        bedrock_output = outputs[0].get("text", response)
                    else:
                        bedrock_output = (
                            "I'm sorry, I'm not able to provide that information. "
                            "Please check with your care team."
                        )
            except Exception as exc:
                logger.warning("Bedrock guardrail invocation failed: %s", exc)

        # Step 5 — determine final action & response
        if not output_val.is_safe:
            if output_val.highest_severity in (Severity.CRITICAL, Severity.HIGH):
                action = "BLOCKED"
                final = (
                    "I'm sorry, I'm not able to provide that information. "
                    "Please consult your healthcare provider or care team for guidance."
                )
            else:
                action = "MODIFIED"
                final = output_val.sanitized_text or response
        elif bedrock_applied and bedrock_action == "GUARDRAIL_INTERVENED":
            action = "MODIFIED"
            final = bedrock_output
        else:
            action = "ALLOWED"
            final = response

        gr = GuardrailResult(
            action=action,
            original_response=response,
            final_response=final,
            input_validation=input_val,
            output_validation=output_val,
            bedrock_applied=bedrock_applied,
        )
        self._audit("apply_guardrail", prompt, gr)
        return gr

    def detect_emergency(self, text: str) -> bool:
        """Detect emergency keywords in user speech (English + Hindi)."""
        for pat in _COMPILED_EMERGENCY_EN:
            if pat.search(text):
                logger.critical("EMERGENCY detected (EN): %s", pat.pattern)
                self._audit("emergency_detected", text, {"language": "en", "pattern": pat.pattern})
                return True
        for pat in _COMPILED_EMERGENCY_HI:
            if pat.search(text):
                logger.critical("EMERGENCY detected (HI): %s", pat.pattern)
                self._audit("emergency_detected", text, {"language": "hi", "pattern": pat.pattern})
                return True
        return False

    def add_disclaimer(self, text: str, topic: str = "general") -> str:
        """Add an appropriate safety disclaimer to an LLM response."""
        disclaimer = _REQUIRED_DISCLAIMERS.get(topic, _REQUIRED_DISCLAIMERS["general"])
        # Avoid double-adding
        if disclaimer in text:
            return text
        return f"{text}\n\n---\n{disclaimer}"

    def sanitize_phi(self, text: str) -> str:
        """Remove or mask Protected Health Information (PHI) from text."""
        sanitized = text
        for phi_type, (pattern, replacement) in _PHI_PATTERNS.items():
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    def validate_teach_back(self, original: str, patient_response: str) -> Dict[str, Any]:
        """Validate whether the patient understood the information (teach-back).

        Checks if the patient's response demonstrates comprehension of the
        key points in the original information.
        """
        # Extract key terms from original
        key_terms = set(re.findall(r"\b[a-z]{4,}\b", original.lower()))
        # Ignore very common words
        stop_words = {
            "that", "this", "with", "from", "have", "been", "will", "your",
            "they", "them", "their", "then", "than", "when", "what", "where",
            "which", "would", "could", "should", "about", "into", "over",
            "after", "before", "between", "through", "during", "each", "also",
            "more", "some", "very", "just", "like", "make", "made", "well",
            "back", "only", "come", "take", "know", "good", "need", "want",
        }
        key_terms -= stop_words

        # Check overlap
        response_terms = set(re.findall(r"\b[a-z]{4,}\b", patient_response.lower()))
        response_terms -= stop_words
        overlap = key_terms & response_terms

        if not key_terms:
            comprehension_score = 1.0
        else:
            comprehension_score = len(overlap) / len(key_terms)

        understood = comprehension_score >= 0.3

        return {
            "understood": understood,
            "comprehension_score": round(comprehension_score, 2),
            "key_terms_matched": sorted(overlap),
            "key_terms_total": len(key_terms),
            "recommendation": (
                "Patient appears to understand the information."
                if understood
                else "Consider rephrasing and re-explaining. Patient may not have fully understood."
            ),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _strip_violations(self, text: str, violations: List[Violation]) -> str:
        """Remove matched violation text from the output."""
        sanitized = text
        for v in violations:
            sanitized = sanitized.replace(
                v.matched_text,
                "[CONTENT REMOVED BY SAFETY GUARDRAIL]",
            )
        return sanitized

    def _invoke_bedrock_guardrail(
        self,
        prompt: str,
        response: str,
    ) -> Dict[str, Any]:
        """Call the AWS Bedrock Guardrails API."""
        if not self._bedrock_client or not self.guardrail_id:
            return {"action": "NONE"}

        result = self._bedrock_client.apply_guardrail(
            guardrailIdentifier=self.guardrail_id,
            guardrailVersion=self.guardrail_version,
            source="OUTPUT",
            content=[{"text": {"text": response}}],
        )
        return result

    def _audit(self, action: str, text: str, result: Any, **extra: Any) -> None:
        """Write an audit log entry."""
        entry = {
            "timestamp": time.time(),
            "action": action,
            "input_preview": text[:200] if isinstance(text, str) else str(text)[:200],
            "result_type": type(result).__name__,
            **extra,
        }

        # Enrich entry based on result type
        if isinstance(result, ValidationResult):
            entry["is_safe"] = result.is_safe
            entry["violation_count"] = len(result.violations)
            entry["violations"] = [
                {"rule": v.rule, "severity": v.severity.value, "description": v.description}
                for v in result.violations
            ]
            entry["audit_id"] = result.audit_id
        elif isinstance(result, GuardrailResult):
            entry["guardrail_action"] = result.action
            entry["bedrock_applied"] = result.bedrock_applied
            entry["audit_id"] = result.audit_id
        elif isinstance(result, dict):
            entry.update(result)

        logger.info("GUARDRAIL_AUDIT: %s", json.dumps(entry, default=str))

        # Optionally write to file
        if self.audit_log_path:
            try:
                with open(self.audit_log_path, "a") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
            except OSError as exc:
                logger.warning("Failed to write audit log: %s", exc)
