"""
AETHER Event Processor Lambda
==============================
Triggered by AWS IoT Core rules when sensor events arrive via MQTT.

Responsibilities:
1.  Parse and validate the incoming event payload.
2.  Persist the event to DynamoDB (``aether-events``).
3.  For CRITICAL / HIGH severity events, generate a TriageCard via Bedrock.
4.  Store an evidence packet in S3 (``/{home_id}/{Y}/{M}/{D}/{event_id}.json``).
5.  Start an escalation workflow (Step Functions) when warranted.
6.  Update the daily timeline aggregation.
"""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Shared imports
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.models import (
    Event,
    Severity,
    TriageCard,
    generate_event_id,
    generate_triage_id,
    get_current_timestamp,
    validate_event_payload,
)
from shared.utils import (
    api_response,
    alerts_topic_arn,
    bedrock_model_id,
    decimalize,
    dynamo_put_item,
    dynamo_update_item,
    escalation_sfn_arn,
    events_table_name,
    evidence_bucket_name,
    generate_correlation_id,
    get_env,
    invoke_bedrock_model,
    json_dumps,
    log_with_context,
    s3_put_object,
    setup_logger,
    sns_publish_structured_alert,
    start_step_function,
    timeline_table_name,
)

logger = setup_logger("event_processor")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TRIAGE_ENABLED = get_env("TRIAGE_ENABLED", "true").lower() == "true"
ESCALATION_ENABLED = get_env("ESCALATION_ENABLED", "true").lower() == "true"


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point.

    ``event`` is the payload forwarded by the IoT Core SQL rule action and may
    contain either a single event dict or a batch (``records`` list).
    """
    correlation_id = generate_correlation_id()
    log_with_context(logger, "INFO", "Event processor invoked", correlation_id=correlation_id)

    try:
        # IoT Core may deliver a single event or a list
        records = _extract_records(event)
        log_with_context(
            logger, "INFO",
            f"Processing {len(records)} record(s)",
            correlation_id=correlation_id,
        )

        results: List[Dict[str, Any]] = []
        for raw in records:
            result = _process_single_event(raw, correlation_id)
            results.append(result)

        failed = [r for r in results if r.get("status") == "error"]
        log_with_context(
            logger, "INFO",
            f"Batch complete: {len(results)} processed, {len(failed)} failed",
            correlation_id=correlation_id,
        )

        return {
            "statusCode": 200,
            "body": {
                "correlation_id": correlation_id,
                "processed": len(results),
                "failed": len(failed),
                "results": results,
            },
        }

    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Unhandled exception: {exc}",
            correlation_id=correlation_id,
            traceback=traceback.format_exc(),
        )
        return {
            "statusCode": 500,
            "body": {"error": "internal_error", "message": str(exc), "correlation_id": correlation_id},
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_records(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalise the incoming payload into a list of raw event dicts."""
    if "records" in event:
        return event["records"]
    if "Records" in event:
        # Kinesis / SQS wrapping
        out = []
        for rec in event["Records"]:
            body = rec.get("body") or rec.get("Sns", {}).get("Message", "{}")
            if isinstance(body, str):
                body = json.loads(body)
            out.append(body)
        return out
    # Direct IoT Core rule action – single event
    return [event]


def _process_single_event(raw: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Validate, enrich, persist, and escalate a single event.

    Returns a result dict summarising the outcome.
    """
    # --- 1. Validation -------------------------------------------------------
    errors = validate_event_payload(raw)
    if errors:
        log_with_context(
            logger, "WARNING",
            "Validation failed",
            correlation_id=correlation_id,
            errors=errors,
        )
        return {"status": "error", "errors": errors}

    # --- 2. Enrich -----------------------------------------------------------
    event = Event(
        event_id=raw.get("event_id") or generate_event_id(),
        home_id=raw["home_id"],
        resident_id=raw["resident_id"],
        event_type=raw["event_type"],
        severity=raw["severity"],
        timestamp=raw["timestamp"],
        data=raw.get("data", {}),
        confidence=float(raw.get("confidence", 0.0)),
        source_sensors=raw.get("source_sensors", []),
        privacy_level=raw.get("privacy_level", "PRIVATE"),
        evidence_packet_id=None,  # will be set after S3 upload
    )

    log_with_context(
        logger, "INFO",
        f"Processing event {event.event_id}",
        correlation_id=correlation_id,
        event_type=event.event_type,
        severity=event.severity,
        home_id=event.home_id,
    )

    result: Dict[str, Any] = {"event_id": event.event_id, "status": "ok"}

    # --- 3. Store evidence packet in S3 --------------------------------------
    try:
        evidence_key = _build_evidence_key(event)
        evidence_payload = _build_evidence_packet(event, correlation_id)
        s3_put_object(
            bucket=evidence_bucket_name(),
            key=evidence_key,
            body=evidence_payload,
            metadata={
                "event_type": event.event_type,
                "severity": event.severity,
                "home_id": event.home_id,
            },
        )
        event.evidence_packet_id = evidence_key
        result["evidence_key"] = evidence_key
        log_with_context(
            logger, "INFO",
            f"Evidence stored: {evidence_key}",
            correlation_id=correlation_id,
        )
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"S3 evidence upload failed: {exc}",
            correlation_id=correlation_id,
            traceback=traceback.format_exc(),
        )
        # Non-fatal: continue processing

    # --- 4. Generate TriageCard for high-severity events ---------------------
    triage_card: Optional[TriageCard] = None
    if event.is_critical_or_high and TRIAGE_ENABLED:
        try:
            triage_card = _generate_triage_card(event, correlation_id)
            result["triage_card"] = triage_card.to_dict()
        except Exception as exc:
            log_with_context(
                logger, "ERROR",
                f"Triage card generation failed: {exc}",
                correlation_id=correlation_id,
                traceback=traceback.format_exc(),
            )

    # --- 5. Persist event to DynamoDB ----------------------------------------
    try:
        event_item = event.to_dict()
        if triage_card:
            event_item["triage_card"] = triage_card.to_dict()
        event_item["correlation_id"] = correlation_id

        dynamo_put_item(events_table_name(), event_item)
        log_with_context(
            logger, "INFO",
            f"Event persisted to DynamoDB: {event.event_id}",
            correlation_id=correlation_id,
        )
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"DynamoDB put failed: {exc}",
            correlation_id=correlation_id,
            traceback=traceback.format_exc(),
        )
        result["status"] = "error"
        result["errors"] = [f"DynamoDB write failed: {str(exc)}"]
        return result

    # --- 6. Start escalation workflow ----------------------------------------
    if event.is_critical_or_high and ESCALATION_ENABLED:
        try:
            _start_escalation(event, triage_card, correlation_id)
            result["escalation_started"] = True
        except Exception as exc:
            log_with_context(
                logger, "ERROR",
                f"Escalation start failed: {exc}",
                correlation_id=correlation_id,
                traceback=traceback.format_exc(),
            )

    # --- 7. Send SNS alert ---------------------------------------------------
    if event.severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM):
        try:
            _send_alert(event, triage_card, correlation_id)
        except Exception as exc:
            log_with_context(
                logger, "WARNING",
                f"SNS alert failed: {exc}",
                correlation_id=correlation_id,
            )

    # --- 8. Update timeline --------------------------------------------------
    try:
        _update_timeline(event, correlation_id)
    except Exception as exc:
        log_with_context(
            logger, "WARNING",
            f"Timeline update failed: {exc}",
            correlation_id=correlation_id,
        )

    return result


# ---------------------------------------------------------------------------
# Evidence packet
# ---------------------------------------------------------------------------

def _build_evidence_key(event: Event) -> str:
    """Build the S3 key path: ``/{home_id}/{Y}/{M}/{D}/{event_id}.json``."""
    ts = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
    return (
        f"{event.home_id}/{ts.year:04d}/{ts.month:02d}/"
        f"{ts.day:02d}/{event.event_id}.json"
    )


def _build_evidence_packet(event: Event, correlation_id: str) -> Dict[str, Any]:
    """Assemble the evidence packet that gets stored in S3."""
    return {
        "version": "1.0",
        "event": event.to_dict(),
        "correlation_id": correlation_id,
        "collected_at": get_current_timestamp(),
        "source": "event_processor",
    }


# ---------------------------------------------------------------------------
# Triage card generation via Bedrock
# ---------------------------------------------------------------------------

_TRIAGE_PROMPT_TEMPLATE = """You are a clinical triage AI for the AETHER elderly care system.
Analyse the following sensor event and produce a structured triage assessment.

Event Details:
- Type: {event_type}
- Severity: {severity}
- Confidence: {confidence}
- Sensors: {sensors}
- Data: {data}
- Timestamp: {timestamp}

Provide your response as JSON with exactly these keys:
{{
  "risk_score": <integer 0-100>,
  "assessment": "<concise clinical assessment in 2-3 sentences>",
  "recommended_actions": ["<action 1>", "<action 2>", ...]
}}

IMPORTANT: You are NOT providing a medical diagnosis.  You are triaging sensor
alerts to guide caregiver response.  Always include "Confirm with healthcare
provider" as a recommended action for HIGH/CRITICAL events.
"""


def _generate_triage_card(event: Event, correlation_id: str) -> TriageCard:
    """Call Bedrock to generate a TriageCard for a high-severity event."""
    prompt = _TRIAGE_PROMPT_TEMPLATE.format(
        event_type=event.event_type,
        severity=event.severity,
        confidence=event.confidence,
        sensors=", ".join(event.source_sensors) if event.source_sensors else "unknown",
        data=json_dumps(event.data),
        timestamp=event.timestamp,
    )

    log_with_context(
        logger, "INFO",
        "Invoking Bedrock for triage card",
        correlation_id=correlation_id,
        model=bedrock_model_id(),
    )

    raw_response = invoke_bedrock_model(prompt, max_tokens=512, temperature=0.2)

    # Try to parse JSON from the response
    try:
        # Model may wrap JSON in markdown code fences
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        log_with_context(
            logger, "WARNING",
            "Could not parse Bedrock response as JSON, using raw text",
            correlation_id=correlation_id,
        )
        parsed = {
            "risk_score": 75 if event.severity == Severity.CRITICAL else 50,
            "assessment": raw_response[:500],
            "recommended_actions": ["Review event details", "Confirm with healthcare provider"],
        }

    card = TriageCard(
        event_id=event.event_id,
        triage_id=generate_triage_id(),
        risk_score=float(parsed.get("risk_score", 0)),
        assessment=parsed.get("assessment", ""),
        recommended_actions=parsed.get("recommended_actions", []),
        model_used=bedrock_model_id(),
        generated_at=get_current_timestamp(),
    )

    log_with_context(
        logger, "INFO",
        f"Triage card generated: risk_score={card.risk_score}",
        correlation_id=correlation_id,
        triage_id=card.triage_id,
    )

    return card


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

def _start_escalation(
    event: Event,
    triage_card: Optional[TriageCard],
    correlation_id: str,
) -> None:
    """Start a Step Functions escalation workflow."""
    sfn_arn = escalation_sfn_arn()
    if not sfn_arn:
        log_with_context(
            logger, "WARNING",
            "ESCALATION_SFN_ARN not configured; skipping escalation",
            correlation_id=correlation_id,
        )
        return

    input_payload: Dict[str, Any] = {
        "event": event.to_dict(),
        "correlation_id": correlation_id,
    }
    if triage_card:
        input_payload["triage_card"] = triage_card.to_dict()

    execution_name = f"{event.event_id}-{int(datetime.now(timezone.utc).timestamp())}"
    # Step Functions execution names: alphanumeric, hyphens, underscores ≤80 chars
    execution_name = execution_name[:80]

    start_step_function(sfn_arn, execution_name, input_payload)
    log_with_context(
        logger, "INFO",
        f"Step Functions escalation started: {execution_name}",
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# SNS alert
# ---------------------------------------------------------------------------

def _send_alert(
    event: Event,
    triage_card: Optional[TriageCard],
    correlation_id: str,
) -> None:
    """Publish a structured alert to the SNS topic."""
    topic = alerts_topic_arn()
    if not topic:
        log_with_context(
            logger, "WARNING",
            "ALERTS_TOPIC_ARN not configured; skipping alert",
            correlation_id=correlation_id,
        )
        return

    message_parts = [
        f"AETHER Alert – {event.severity}",
        f"Event: {event.event_type}",
        f"Home: {event.home_id}",
        f"Resident: {event.resident_id}",
        f"Time: {event.timestamp}",
        f"Confidence: {event.confidence:.0%}",
    ]
    if triage_card:
        message_parts.append(f"Risk Score: {triage_card.risk_score}")
        message_parts.append(f"Assessment: {triage_card.assessment}")
        if triage_card.recommended_actions:
            message_parts.append("Actions: " + "; ".join(triage_card.recommended_actions))

    message = "\n".join(message_parts)

    sns_publish_structured_alert(
        topic_arn=topic,
        event_type=event.event_type,
        severity=event.severity,
        home_id=event.home_id,
        message=message,
    )


# ---------------------------------------------------------------------------
# Timeline update
# ---------------------------------------------------------------------------

def _update_timeline(event: Event, correlation_id: str) -> None:
    """Increment counters in today's timeline entry for the home."""
    ts = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
    date_str = ts.strftime("%Y-%m-%d")

    table = timeline_table_name()

    # Atomic counter updates
    update_parts = [
        "SET updated_at = :now",
        "ADD total_events :one",
    ]
    expr_values: Dict[str, Any] = {
        ":now": get_current_timestamp(),
        ":one": 1,
    }
    expr_names: Dict[str, str] = {}

    # Event type counter
    safe_type = event.event_type.replace("-", "_")
    update_parts.append(f"ADD events_by_type.#{safe_type} :one")
    expr_names[f"#{safe_type}"] = event.event_type

    # Severity counter
    safe_sev = event.severity.lower()
    update_parts.append(f"ADD events_by_severity.#{safe_sev} :one")
    expr_names[f"#{safe_sev}"] = event.severity

    # Fall counter
    if event.event_type == "fall_detected":
        update_parts.append("ADD fall_count :one")

    update_expression = " ".join(update_parts)

    try:
        dynamo_update_item(
            table_name=table,
            key={"home_id": event.home_id, "date": date_str},
            update_expression=update_expression,
            expression_attribute_values=expr_values,
            expression_attribute_names=expr_names if expr_names else None,
        )
        log_with_context(
            logger, "INFO",
            f"Timeline updated for {event.home_id}/{date_str}",
            correlation_id=correlation_id,
        )
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Timeline update failed: {exc}",
            correlation_id=correlation_id,
        )
        raise
