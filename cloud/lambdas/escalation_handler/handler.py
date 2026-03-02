"""
AETHER Escalation Handler Lambda
==================================
Implements the four-tier escalation ladder for critical events.

Escalation Tiers
-----------------
1. **Local Alarm** – Edge Gateway siren + voice alert (immediate).
2. **Caregiver Notification** – Push + SMS via SNS (30 s with no response).
3. **Nurse / Professional Alert** – Push + SMS + call (2 min with no response).
4. **Emergency Services** – Auto-call 911 / 108 (5 min with no response).

The handler is invoked by Step Functions at each tier transition and also
handles ``acknowledge`` / ``cancel`` events that halt the escalation.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.models import (
    EscalationState,
    EscalationTier,
    Event,
    Severity,
    generate_escalation_id,
    get_current_timestamp,
)
from shared.utils import (
    alerts_topic_arn,
    decimalize,
    dynamo_get_item,
    dynamo_put_item,
    dynamo_update_item,
    events_table_name,
    generate_correlation_id,
    get_env,
    json_dumps,
    log_with_context,
    setup_logger,
    sns_publish_alert,
    sns_publish_structured_alert,
    timeline_table_name,
)

logger = setup_logger("escalation_handler")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ESCALATION_TABLE = get_env("ESCALATION_TABLE", "aether-events")  # stored alongside events
ESCALATION_STATE_PREFIX = "ESC#"

# Tier timing (seconds) – configurable via environment
TIER2_DELAY = int(get_env("TIER2_DELAY_SECONDS", "30"))
TIER3_DELAY = int(get_env("TIER3_DELAY_SECONDS", "120"))
TIER4_DELAY = int(get_env("TIER4_DELAY_SECONDS", "300"))

# Quiet hours (local time for the home – simplified to UTC here)
QUIET_HOURS_START = int(get_env("QUIET_HOURS_START", "22"))  # 10 PM
QUIET_HOURS_END = int(get_env("QUIET_HOURS_END", "7"))       # 7 AM

# Safety exceptions: event types that bypass quiet hours
QUIET_HOURS_BYPASS_TYPES = {
    "fall_detected",
    "acoustic_scream",
    "acoustic_glass_break",
    "acoustic_impact",
    "vital_alert",
}

# Voice-command cancellation phrases
CANCEL_PHRASES = {
    "i'm okay",
    "im okay",
    "i am okay",
    "cancel alert",
    "cancel alarm",
    "false alarm",
    "i'm fine",
    "im fine",
    "i am fine",
    "stop alarm",
    "stop alert",
}

# Caregiver and nurse topic ARNs
CAREGIVER_TOPIC_ARN = get_env("CAREGIVER_TOPIC_ARN", "")
NURSE_TOPIC_ARN = get_env("NURSE_TOPIC_ARN", "")
EMERGENCY_TOPIC_ARN = get_env("EMERGENCY_TOPIC_ARN", "")
IOT_ENDPOINT = get_env("IOT_ENDPOINT", "")


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point.

    Invoked by Step Functions with an ``action`` field indicating the
    requested operation:

    - ``escalate``   – Execute the next escalation tier.
    - ``acknowledge`` – Mark escalation acknowledged by a caregiver.
    - ``cancel``     – Cancel escalation (voice command or manual).
    - ``check_tier`` – Evaluate whether to advance to the next tier.
    """
    correlation_id = event.get("correlation_id") or generate_correlation_id()
    action = event.get("action", "escalate")

    log_with_context(
        logger, "INFO",
        f"Escalation handler invoked: action={action}",
        correlation_id=correlation_id,
    )

    try:
        if action == "acknowledge":
            return _handle_acknowledge(event, correlation_id)
        elif action == "cancel":
            return _handle_cancel(event, correlation_id)
        elif action == "check_tier":
            return _handle_check_tier(event, correlation_id)
        else:
            return _handle_escalate(event, correlation_id)
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Escalation handler error: {exc}",
            correlation_id=correlation_id,
            traceback=traceback.format_exc(),
        )
        return {
            "statusCode": 500,
            "body": {"error": str(exc), "correlation_id": correlation_id},
        }


# ---------------------------------------------------------------------------
# Escalation entry point
# ---------------------------------------------------------------------------

def _handle_escalate(payload: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Start or continue escalation for an event."""
    event_data = payload.get("event", payload)
    event = Event.from_dict(event_data)
    triage_card_data = payload.get("triage_card")
    requested_tier = int(payload.get("tier", EscalationTier.LOCAL_ALARM))

    # Load or create escalation state
    state = _load_escalation_state(event.event_id, event.home_id)
    if state is None:
        state = EscalationState(
            event_id=event.event_id,
            escalation_id=generate_escalation_id(),
            current_tier=0,
            started_at=get_current_timestamp(),
            home_id=event.home_id,
            resident_id=event.resident_id,
            severity=event.severity,
        )

    # Already resolved?
    if state.resolved:
        log_with_context(
            logger, "INFO",
            f"Escalation {state.escalation_id} already resolved; skipping",
            correlation_id=correlation_id,
        )
        return _build_response(state, "already_resolved")

    # Quiet hours check
    if _is_quiet_hours() and event.event_type not in QUIET_HOURS_BYPASS_TYPES:
        log_with_context(
            logger, "INFO",
            "Quiet hours active; deferring non-safety escalation",
            correlation_id=correlation_id,
        )
        state.add_step(
            tier=requested_tier,
            action="deferred_quiet_hours",
            details={"reason": "quiet hours active"},
        )
        _save_escalation_state(state)
        return _build_response(state, "deferred_quiet_hours")

    # Execute the requested tier
    tier_handlers = {
        EscalationTier.LOCAL_ALARM: _execute_tier1_local_alarm,
        EscalationTier.CAREGIVER: _execute_tier2_caregiver,
        EscalationTier.NURSE: _execute_tier3_nurse,
        EscalationTier.EMERGENCY: _execute_tier4_emergency,
    }

    tier_fn = tier_handlers.get(requested_tier, _execute_tier1_local_alarm)
    tier_fn(state, event, triage_card_data, correlation_id)

    _save_escalation_state(state)
    _log_escalation_to_timeline(state, event, correlation_id)

    return _build_response(state, "escalated", next_tier=_next_tier(requested_tier))


# ---------------------------------------------------------------------------
# Tier implementations
# ---------------------------------------------------------------------------

def _execute_tier1_local_alarm(
    state: EscalationState,
    event: Event,
    triage_card: Optional[Dict[str, Any]],
    correlation_id: str,
) -> None:
    """Tier 1: Activate local alarm on Edge Gateway via IoT Core MQTT."""
    log_with_context(
        logger, "INFO",
        "Executing Tier 1: Local alarm",
        correlation_id=correlation_id,
        event_id=event.event_id,
    )

    # Publish alarm command to Edge Gateway via IoT Core
    _publish_iot_command(
        home_id=event.home_id,
        command="activate_alarm",
        payload={
            "event_id": event.event_id,
            "event_type": event.event_type,
            "severity": event.severity,
            "siren": True,
            "voice_alert": _build_voice_alert(event),
            "escalation_id": state.escalation_id,
        },
        correlation_id=correlation_id,
    )

    state.add_step(
        tier=EscalationTier.LOCAL_ALARM,
        action="local_alarm_activated",
        details={
            "siren": True,
            "voice_alert": True,
            "iot_topic": f"aether/{event.home_id}/commands/alarm",
        },
    )


def _execute_tier2_caregiver(
    state: EscalationState,
    event: Event,
    triage_card: Optional[Dict[str, Any]],
    correlation_id: str,
) -> None:
    """Tier 2: Caregiver notification via push + SMS."""
    log_with_context(
        logger, "INFO",
        "Executing Tier 2: Caregiver notification",
        correlation_id=correlation_id,
        event_id=event.event_id,
    )

    message = _build_caregiver_message(event, triage_card)
    topic = CAREGIVER_TOPIC_ARN or alerts_topic_arn()

    if topic:
        sns_publish_structured_alert(
            topic_arn=topic,
            event_type=event.event_type,
            severity=event.severity,
            home_id=event.home_id,
            message=message,
        )
    else:
        log_with_context(
            logger, "WARNING",
            "No caregiver topic ARN configured",
            correlation_id=correlation_id,
        )

    state.add_step(
        tier=EscalationTier.CAREGIVER,
        action="caregiver_notified",
        details={
            "channels": ["push", "sms"],
            "topic_arn": topic,
            "delay_seconds": TIER2_DELAY,
        },
    )


def _execute_tier3_nurse(
    state: EscalationState,
    event: Event,
    triage_card: Optional[Dict[str, Any]],
    correlation_id: str,
) -> None:
    """Tier 3: Nurse / professional alert via push + SMS + call."""
    log_with_context(
        logger, "INFO",
        "Executing Tier 3: Nurse/professional alert",
        correlation_id=correlation_id,
        event_id=event.event_id,
    )

    message = _build_nurse_message(event, triage_card)
    topic = NURSE_TOPIC_ARN or alerts_topic_arn()

    if topic:
        sns_publish_structured_alert(
            topic_arn=topic,
            event_type=event.event_type,
            severity=event.severity,
            home_id=event.home_id,
            message=message,
        )
    else:
        log_with_context(
            logger, "WARNING",
            "No nurse topic ARN configured",
            correlation_id=correlation_id,
        )

    # Initiate phone call via SNS (requires phone number subscription)
    _initiate_voice_call(event, state, correlation_id)

    state.add_step(
        tier=EscalationTier.NURSE,
        action="nurse_alerted",
        details={
            "channels": ["push", "sms", "voice_call"],
            "topic_arn": topic,
            "delay_seconds": TIER3_DELAY,
        },
    )


def _execute_tier4_emergency(
    state: EscalationState,
    event: Event,
    triage_card: Optional[Dict[str, Any]],
    correlation_id: str,
) -> None:
    """Tier 4: Emergency services notification."""
    log_with_context(
        logger, "CRITICAL",
        "Executing Tier 4: Emergency services",
        correlation_id=correlation_id,
        event_id=event.event_id,
    )

    emergency_message = _build_emergency_message(event, triage_card, state)
    topic = EMERGENCY_TOPIC_ARN or alerts_topic_arn()

    if topic:
        sns_publish_structured_alert(
            topic_arn=topic,
            event_type=event.event_type,
            severity="CRITICAL",
            home_id=event.home_id,
            message=emergency_message,
        )
    else:
        log_with_context(
            logger, "ERROR",
            "No emergency topic ARN configured for Tier 4!",
            correlation_id=correlation_id,
        )

    # Also publish to IoT Core for edge gateway to initiate emergency call
    _publish_iot_command(
        home_id=event.home_id,
        command="emergency_call",
        payload={
            "event_id": event.event_id,
            "escalation_id": state.escalation_id,
            "event_type": event.event_type,
            "message": emergency_message,
        },
        correlation_id=correlation_id,
    )

    state.add_step(
        tier=EscalationTier.EMERGENCY,
        action="emergency_services_contacted",
        details={
            "channels": ["emergency_call", "push", "sms"],
            "topic_arn": topic,
            "delay_seconds": TIER4_DELAY,
        },
    )


# ---------------------------------------------------------------------------
# Acknowledge / Cancel
# ---------------------------------------------------------------------------

def _handle_acknowledge(payload: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Handle an acknowledgement that stops escalation."""
    event_id = payload.get("event_id", "")
    home_id = payload.get("home_id", "")
    acknowledged_by = payload.get("acknowledged_by", "unknown")

    log_with_context(
        logger, "INFO",
        f"Acknowledgement received for {event_id}",
        correlation_id=correlation_id,
        acknowledged_by=acknowledged_by,
    )

    state = _load_escalation_state(event_id, home_id)
    if state is None:
        return {
            "statusCode": 404,
            "body": {"error": "escalation_not_found", "event_id": event_id},
        }

    if state.resolved:
        return _build_response(state, "already_resolved")

    state.acknowledged_by = acknowledged_by
    state.acknowledged_at = get_current_timestamp()
    state.resolved = True
    state.add_step(
        tier=state.current_tier,
        action="acknowledged",
        details={"acknowledged_by": acknowledged_by},
    )

    _save_escalation_state(state)

    # Deactivate local alarm
    _publish_iot_command(
        home_id=home_id,
        command="deactivate_alarm",
        payload={
            "event_id": event_id,
            "escalation_id": state.escalation_id,
            "reason": "acknowledged",
        },
        correlation_id=correlation_id,
    )

    return _build_response(state, "acknowledged")


def _handle_cancel(payload: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Handle a cancellation from voice command or manual action."""
    event_id = payload.get("event_id", "")
    home_id = payload.get("home_id", "")
    cancel_reason = payload.get("reason", "manual_cancel")
    voice_text = payload.get("voice_text", "")

    # Validate voice cancellation phrase if provided
    if voice_text:
        normalised = voice_text.strip().lower()
        if normalised not in CANCEL_PHRASES:
            log_with_context(
                logger, "INFO",
                f"Voice text '{voice_text}' not recognised as cancel phrase",
                correlation_id=correlation_id,
            )
            return {
                "statusCode": 400,
                "body": {
                    "error": "invalid_cancel_phrase",
                    "message": "Voice command not recognised as a cancellation phrase",
                },
            }
        cancel_reason = f"voice_command: {voice_text}"

    log_with_context(
        logger, "INFO",
        f"Cancel received for {event_id}: {cancel_reason}",
        correlation_id=correlation_id,
    )

    state = _load_escalation_state(event_id, home_id)
    if state is None:
        return {
            "statusCode": 404,
            "body": {"error": "escalation_not_found", "event_id": event_id},
        }

    if state.resolved:
        return _build_response(state, "already_resolved")

    state.resolved = True
    state.acknowledged_by = cancel_reason
    state.acknowledged_at = get_current_timestamp()
    state.add_step(
        tier=state.current_tier,
        action="cancelled",
        details={"reason": cancel_reason, "voice_text": voice_text},
    )

    _save_escalation_state(state)

    # Deactivate local alarm
    _publish_iot_command(
        home_id=home_id,
        command="deactivate_alarm",
        payload={
            "event_id": event_id,
            "escalation_id": state.escalation_id,
            "reason": cancel_reason,
        },
        correlation_id=correlation_id,
    )

    return _build_response(state, "cancelled")


def _handle_check_tier(payload: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Check whether the escalation should advance to the next tier.

    Called by Step Functions ``Wait`` → ``Task`` transitions.
    """
    event_id = payload.get("event_id", "")
    home_id = payload.get("home_id", "")
    expected_tier = int(payload.get("expected_tier", 2))

    state = _load_escalation_state(event_id, home_id)
    if state is None:
        return {"should_escalate": False, "reason": "not_found"}

    if state.resolved:
        return {"should_escalate": False, "reason": "resolved"}

    # Calculate elapsed time
    started = datetime.fromisoformat(state.started_at.replace("Z", "+00:00"))
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()

    tier_thresholds = {
        EscalationTier.CAREGIVER: TIER2_DELAY,
        EscalationTier.NURSE: TIER3_DELAY,
        EscalationTier.EMERGENCY: TIER4_DELAY,
    }

    threshold = tier_thresholds.get(expected_tier, TIER2_DELAY)

    if elapsed >= threshold:
        log_with_context(
            logger, "INFO",
            f"Advancing to tier {expected_tier} after {elapsed:.0f}s",
            correlation_id=correlation_id,
        )
        return {
            "should_escalate": True,
            "next_tier": expected_tier,
            "elapsed_seconds": elapsed,
            "event": payload.get("event", {}),
            "triage_card": payload.get("triage_card"),
            "correlation_id": correlation_id,
        }

    return {
        "should_escalate": False,
        "reason": "threshold_not_reached",
        "elapsed_seconds": elapsed,
        "threshold_seconds": threshold,
    }


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def _escalation_sort_key(event_id: str) -> str:
    """Build the sort key for an escalation state record."""
    return f"{ESCALATION_STATE_PREFIX}{event_id}"


def _load_escalation_state(event_id: str, home_id: str) -> Optional[EscalationState]:
    """Load an existing escalation state from DynamoDB."""
    item = dynamo_get_item(
        table_name=events_table_name(),
        key={"home_id": home_id, "timestamp": _escalation_sort_key(event_id)},
    )
    if item is None:
        return None
    return EscalationState.from_dict(item)


def _save_escalation_state(state: EscalationState) -> None:
    """Persist escalation state to DynamoDB."""
    item = state.to_dict()
    item["timestamp"] = _escalation_sort_key(state.event_id)
    dynamo_put_item(events_table_name(), item)


# ---------------------------------------------------------------------------
# Message builders
# ---------------------------------------------------------------------------

def _build_voice_alert(event: Event) -> str:
    """Build a spoken voice alert message for the local siren."""
    type_labels = {
        "fall_detected": "A fall has been detected",
        "acoustic_scream": "A distress sound has been detected",
        "acoustic_glass_break": "Breaking glass has been detected",
        "acoustic_impact": "A loud impact has been detected",
        "acoustic_silence": "Extended silence has been detected",
        "vital_alert": "An abnormal vital sign reading has been detected",
        "medication_missed": "A medication has been missed",
    }
    description = type_labels.get(event.event_type, f"An alert of type {event.event_type} has occurred")
    return (
        f"Attention. {description}. "
        "If you are safe and well, please say 'I'm okay' or press the acknowledgement button. "
        "Otherwise, help is on the way."
    )


def _build_caregiver_message(event: Event, triage_card: Optional[Dict[str, Any]]) -> str:
    """Build the caregiver notification message."""
    lines = [
        f"🚨 AETHER ALERT – {event.severity}",
        f"Event: {event.event_type.replace('_', ' ').title()}",
        f"Home: {event.home_id}",
        f"Resident: {event.resident_id}",
        f"Time: {event.timestamp}",
        f"Confidence: {event.confidence:.0%}",
        "",
        "Please acknowledge this alert in the AETHER app or call the resident.",
        f"If no response within {TIER3_DELAY}s, nursing staff will be notified.",
    ]
    if triage_card:
        lines.insert(6, f"Risk Score: {triage_card.get('risk_score', 'N/A')}")
        lines.insert(7, f"Assessment: {triage_card.get('assessment', 'N/A')}")
    return "\n".join(lines)


def _build_nurse_message(event: Event, triage_card: Optional[Dict[str, Any]]) -> str:
    """Build the nurse/professional alert message."""
    lines = [
        f"🏥 AETHER ESCALATION – Tier 3 – {event.severity}",
        f"Caregivers have NOT responded after {TIER2_DELAY}s.",
        "",
        f"Event: {event.event_type.replace('_', ' ').title()}",
        f"Home: {event.home_id}",
        f"Resident: {event.resident_id}",
        f"Time: {event.timestamp}",
        f"Confidence: {event.confidence:.0%}",
    ]
    if triage_card:
        lines.append(f"Risk Score: {triage_card.get('risk_score', 'N/A')}")
        lines.append(f"Assessment: {triage_card.get('assessment', 'N/A')}")
        actions = triage_card.get("recommended_actions", [])
        if actions:
            lines.append("Recommended Actions:")
            for a in actions:
                lines.append(f"  • {a}")
    lines.append("")
    lines.append(f"If no response within {TIER4_DELAY - TIER3_DELAY}s, emergency services will be contacted.")
    return "\n".join(lines)


def _build_emergency_message(
    event: Event,
    triage_card: Optional[Dict[str, Any]],
    state: EscalationState,
) -> str:
    """Build the emergency services message."""
    lines = [
        "🚑 AETHER EMERGENCY – AUTOMATIC ESCALATION",
        f"No response received after {TIER4_DELAY}s.",
        "",
        f"Event: {event.event_type.replace('_', ' ').title()}",
        f"Home ID: {event.home_id}",
        f"Resident ID: {event.resident_id}",
        f"Original Time: {event.timestamp}",
        f"Escalation ID: {state.escalation_id}",
    ]
    if triage_card:
        lines.append(f"AI Risk Score: {triage_card.get('risk_score', 'N/A')}/100")
        lines.append(f"AI Assessment: {triage_card.get('assessment', 'N/A')}")
    lines.append("")
    lines.append("Escalation History:")
    for step in state.escalation_history:
        lines.append(f"  [{step.get('timestamp', '')}] Tier {step.get('tier', '?')}: {step.get('action', '?')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# IoT Core integration
# ---------------------------------------------------------------------------

def _publish_iot_command(
    home_id: str,
    command: str,
    payload: Dict[str, Any],
    correlation_id: str,
) -> None:
    """Publish a command to the Edge Gateway via IoT Core MQTT."""
    try:
        import boto3
        from botocore.config import Config as BotoConfig

        iot_client = boto3.client(
            "iot-data",
            config=BotoConfig(retries={"max_attempts": 2, "mode": "adaptive"}),
        )

        topic = f"aether/{home_id}/commands/{command}"
        payload["correlation_id"] = correlation_id
        payload["issued_at"] = get_current_timestamp()

        iot_client.publish(
            topic=topic,
            qos=1,
            payload=json.dumps(payload),
        )

        log_with_context(
            logger, "INFO",
            f"IoT command published: {topic}",
            correlation_id=correlation_id,
        )
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Failed to publish IoT command: {exc}",
            correlation_id=correlation_id,
        )


def _initiate_voice_call(
    event: Event,
    state: EscalationState,
    correlation_id: str,
) -> None:
    """Initiate a voice call via Amazon Connect or SNS.

    This is a placeholder that publishes a call-request event.  In production
    this would integrate with Amazon Connect outbound calling API.
    """
    log_with_context(
        logger, "INFO",
        f"Initiating voice call for escalation {state.escalation_id}",
        correlation_id=correlation_id,
    )

    # Publish a call-request to a dedicated topic
    call_topic = NURSE_TOPIC_ARN or alerts_topic_arn()
    if call_topic:
        sns_publish_alert(
            topic_arn=call_topic,
            subject=f"AETHER CALL REQUEST – {event.severity}",
            message=(
                f"Voice call requested for home {event.home_id}, "
                f"resident {event.resident_id}. "
                f"Event: {event.event_type}. "
                f"Escalation ID: {state.escalation_id}."
            ),
            message_attributes={
                "channel": {"DataType": "String", "StringValue": "voice_call"},
                "severity": {"DataType": "String", "StringValue": event.severity},
            },
        )


# ---------------------------------------------------------------------------
# Quiet hours
# ---------------------------------------------------------------------------

def _is_quiet_hours() -> bool:
    """Check whether the current UTC hour falls within quiet hours."""
    current_hour = datetime.now(timezone.utc).hour
    if QUIET_HOURS_START > QUIET_HOURS_END:
        # Spans midnight, e.g. 22–07
        return current_hour >= QUIET_HOURS_START or current_hour < QUIET_HOURS_END
    return QUIET_HOURS_START <= current_hour < QUIET_HOURS_END


# ---------------------------------------------------------------------------
# Timeline integration
# ---------------------------------------------------------------------------

def _log_escalation_to_timeline(
    state: EscalationState,
    event: Event,
    correlation_id: str,
) -> None:
    """Record escalation activity in the daily timeline."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        dynamo_update_item(
            table_name=timeline_table_name(),
            key={"home_id": event.home_id, "date": date_str},
            update_expression=(
                "SET updated_at = :now "
                "ADD escalation_count :one"
            ),
            expression_attribute_values={
                ":now": get_current_timestamp(),
                ":one": 1,
            },
        )
    except Exception as exc:
        log_with_context(
            logger, "WARNING",
            f"Failed to log escalation to timeline: {exc}",
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _next_tier(current_tier: int) -> Optional[int]:
    """Return the next escalation tier, or ``None`` if at max."""
    order = [
        EscalationTier.LOCAL_ALARM,
        EscalationTier.CAREGIVER,
        EscalationTier.NURSE,
        EscalationTier.EMERGENCY,
    ]
    for i, t in enumerate(order):
        if t == current_tier and i + 1 < len(order):
            return order[i + 1]
    return None


def _build_response(
    state: EscalationState,
    status: str,
    next_tier: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a standardised response dict."""
    resp: Dict[str, Any] = {
        "statusCode": 200,
        "body": {
            "status": status,
            "escalation_id": state.escalation_id,
            "event_id": state.event_id,
            "current_tier": state.current_tier,
            "resolved": state.resolved,
            "escalation_history": state.escalation_history,
        },
    }
    if next_tier is not None:
        resp["body"]["next_tier"] = next_tier
    if state.acknowledged_by:
        resp["body"]["acknowledged_by"] = state.acknowledged_by
        resp["body"]["acknowledged_at"] = state.acknowledged_at
    return resp
