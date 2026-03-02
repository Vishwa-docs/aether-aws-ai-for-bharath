"""
AETHER Timeline Aggregator Lambda
===================================
Aggregates sensor events into daily timeline summaries per home.

Trigger modes:
- **Scheduled** – Invoked hourly via EventBridge to roll up recent events.
- **On-demand** – Invoked via API Gateway to query existing timeline data.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.models import (
    EventType,
    Severity,
    TimelineEntry,
    get_current_timestamp,
)
from shared.utils import (
    api_error,
    api_response,
    bedrock_model_id,
    dynamo_get_item,
    dynamo_put_item,
    dynamo_query_items,
    events_table_name,
    generate_correlation_id,
    get_env,
    invoke_bedrock_model,
    json_dumps,
    log_with_context,
    setup_logger,
    timeline_table_name,
)

logger = setup_logger("timeline_aggregator")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NARRATIVE_ENABLED = get_env("NARRATIVE_ENABLED", "true").lower() == "true"
MAX_KEY_EVENTS = int(get_env("MAX_KEY_EVENTS", "10"))

# Medication event types for adherence calculation
_MED_TAKEN = {EventType.MEDICATION_TAKEN, "medication_taken"}
_MED_MISSED = {EventType.MEDICATION_MISSED, "medication_missed"}
_MED_LATE = {EventType.MEDICATION_LATE, "medication_late"}
_MED_ALL = _MED_TAKEN | _MED_MISSED | _MED_LATE


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point.

    Determines the trigger source and dispatches accordingly:
    - EventBridge scheduled event → aggregate for all active homes.
    - API Gateway request → query timeline data for a specific home / date.
    """
    correlation_id = generate_correlation_id()
    log_with_context(logger, "INFO", "Timeline aggregator invoked", correlation_id=correlation_id)

    try:
        # Detect trigger source
        if _is_eventbridge(event):
            return _handle_scheduled_aggregation(event, correlation_id)
        elif _is_api_gateway(event):
            return _handle_api_query(event, correlation_id)
        elif "home_id" in event:
            # Direct invocation for a specific home
            return _handle_single_home(event, correlation_id)
        else:
            return _handle_scheduled_aggregation(event, correlation_id)
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Timeline aggregator error: {exc}",
            correlation_id=correlation_id,
            traceback=traceback.format_exc(),
        )
        return api_error(500, "internal_error", str(exc), correlation_id)


# ---------------------------------------------------------------------------
# Trigger detection
# ---------------------------------------------------------------------------

def _is_eventbridge(event: Dict[str, Any]) -> bool:
    return event.get("source") == "aws.events" or "detail-type" in event


def _is_api_gateway(event: Dict[str, Any]) -> bool:
    return "httpMethod" in event or "requestContext" in event


# ---------------------------------------------------------------------------
# Scheduled aggregation
# ---------------------------------------------------------------------------

def _handle_scheduled_aggregation(
    event: Dict[str, Any],
    correlation_id: str,
) -> Dict[str, Any]:
    """Run aggregation for today (and optionally yesterday) for all homes with events."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    # Discover homes with recent events (scan the event table by date prefix)
    home_ids = _discover_active_homes(today, correlation_id)
    if not home_ids:
        # Also check yesterday if we have no events today yet
        home_ids = _discover_active_homes(yesterday, correlation_id)

    log_with_context(
        logger, "INFO",
        f"Aggregating timelines for {len(home_ids)} home(s) on {today}",
        correlation_id=correlation_id,
    )

    results: List[Dict[str, Any]] = []
    for home_id in home_ids:
        try:
            entry = _aggregate_day(home_id, today, correlation_id)
            results.append({"home_id": home_id, "date": today, "status": "ok"})
        except Exception as exc:
            log_with_context(
                logger, "ERROR",
                f"Aggregation failed for {home_id}: {exc}",
                correlation_id=correlation_id,
            )
            results.append({"home_id": home_id, "date": today, "status": "error", "error": str(exc)})

    return {
        "statusCode": 200,
        "body": {
            "correlation_id": correlation_id,
            "date": today,
            "homes_processed": len(results),
            "results": results,
        },
    }


def _handle_single_home(event: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Aggregate a single home, optionally for a specific date."""
    home_id = event["home_id"]
    date = event.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    entry = _aggregate_day(home_id, date, correlation_id)
    return {
        "statusCode": 200,
        "body": entry.to_dict(),
    }


# ---------------------------------------------------------------------------
# API query handling
# ---------------------------------------------------------------------------

def _handle_api_query(event: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Handle an API Gateway request for timeline data."""
    http_method = event.get("httpMethod", "GET")
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    home_id = path_params.get("home_id") or query_params.get("home_id")
    if not home_id:
        return api_error(400, "missing_parameter", "home_id is required", correlation_id)

    date = query_params.get("date")
    start_date = query_params.get("start")
    end_date = query_params.get("end")

    if date:
        # Single day query
        entry = _get_timeline_entry(home_id, date)
        if entry is None:
            # Try to aggregate on-the-fly
            try:
                entry = _aggregate_day(home_id, date, correlation_id)
            except Exception:
                return api_error(404, "not_found", f"No timeline for {home_id} on {date}", correlation_id)
        return api_response(200, entry.to_dict() if isinstance(entry, TimelineEntry) else entry)

    elif start_date and end_date:
        # Date range query
        entries = _query_timeline_range(home_id, start_date, end_date)
        return api_response(200, {
            "home_id": home_id,
            "start": start_date,
            "end": end_date,
            "entries": [e.to_dict() if isinstance(e, TimelineEntry) else e for e in entries],
            "count": len(entries),
        })

    else:
        # Default: last 7 days
        now = datetime.now(timezone.utc)
        end = now.strftime("%Y-%m-%d")
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        entries = _query_timeline_range(home_id, start, end)
        return api_response(200, {
            "home_id": home_id,
            "start": start,
            "end": end,
            "entries": [e.to_dict() if isinstance(e, TimelineEntry) else e for e in entries],
            "count": len(entries),
        })


# ---------------------------------------------------------------------------
# Core aggregation logic
# ---------------------------------------------------------------------------

def _aggregate_day(home_id: str, date: str, correlation_id: str) -> TimelineEntry:
    """Aggregate all events for *home_id* on *date* into a TimelineEntry."""
    log_with_context(
        logger, "INFO",
        f"Aggregating day: {home_id} / {date}",
        correlation_id=correlation_id,
    )

    # Fetch events for the day
    from boto3.dynamodb.conditions import Key

    start_ts = f"{date}T00:00:00Z"
    end_ts = f"{date}T23:59:59.999999Z"

    events, _ = dynamo_query_items(
        table_name=events_table_name(),
        key_condition_expression=Key("home_id").eq(home_id) & Key("timestamp").between(start_ts, end_ts),
        max_pages=20,
    )

    # Filter out escalation-state records
    events = [e for e in events if not str(e.get("timestamp", "")).startswith("ESC#")]

    log_with_context(
        logger, "INFO",
        f"Found {len(events)} events for {home_id} on {date}",
        correlation_id=correlation_id,
    )

    # Count by type
    type_counter: Counter = Counter()
    severity_counter: Counter = Counter()
    fall_count = 0
    med_taken = 0
    med_total = 0
    key_events: List[Dict[str, Any]] = []

    for evt in events:
        etype = evt.get("event_type", "unknown")
        esev = evt.get("severity", "INFO")
        type_counter[etype] += 1
        severity_counter[esev] += 1

        if etype == "fall_detected":
            fall_count += 1

        if etype in _MED_ALL:
            med_total += 1
            if etype in _MED_TAKEN:
                med_taken += 1

        # Capture key events (CRITICAL / HIGH / falls)
        if esev in (Severity.CRITICAL, Severity.HIGH) or etype == "fall_detected":
            key_events.append({
                "event_id": evt.get("event_id", ""),
                "event_type": etype,
                "severity": esev,
                "timestamp": evt.get("timestamp", ""),
                "confidence": evt.get("confidence", 0),
            })

    # Medication adherence
    med_adherence = (med_taken / med_total * 100) if med_total > 0 else 100.0

    # Activity score (simple heuristic: 100 minus penalties)
    activity_score = _calculate_activity_score(events, type_counter, severity_counter)

    # Trim key events
    key_events = sorted(key_events, key=lambda e: e.get("timestamp", ""), reverse=True)[:MAX_KEY_EVENTS]

    # Build entry
    entry = TimelineEntry(
        home_id=home_id,
        date=date,
        total_events=len(events),
        events_by_type=dict(type_counter),
        events_by_severity=dict(severity_counter),
        fall_count=fall_count,
        medication_adherence_pct=round(med_adherence, 1),
        activity_score=round(activity_score, 1),
        key_events=key_events,
        updated_at=get_current_timestamp(),
    )

    # Generate narrative summary via Bedrock
    if NARRATIVE_ENABLED and events:
        try:
            entry.narrative_summary = _generate_narrative(entry, correlation_id)
        except Exception as exc:
            log_with_context(
                logger, "WARNING",
                f"Narrative generation failed: {exc}",
                correlation_id=correlation_id,
            )
            entry.narrative_summary = _generate_fallback_narrative(entry)
    elif not events:
        entry.narrative_summary = f"No events recorded for {home_id} on {date}."
    else:
        entry.narrative_summary = _generate_fallback_narrative(entry)

    # Persist
    dynamo_put_item(timeline_table_name(), entry.to_dict())
    log_with_context(
        logger, "INFO",
        f"Timeline entry stored for {home_id}/{date}",
        correlation_id=correlation_id,
    )

    return entry


# ---------------------------------------------------------------------------
# Activity score heuristic
# ---------------------------------------------------------------------------

def _calculate_activity_score(
    events: List[Dict[str, Any]],
    type_counter: Counter,
    severity_counter: Counter,
) -> float:
    """Calculate a 0–100 daily activity score.

    Starts at 100 and applies penalties for negative events and bonuses for
    positive engagement signals.
    """
    score = 100.0

    # Penalties
    score -= type_counter.get("fall_detected", 0) * 20
    score -= type_counter.get("acoustic_scream", 0) * 15
    score -= type_counter.get("acoustic_glass_break", 0) * 10
    score -= type_counter.get("acoustic_impact", 0) * 8
    score -= type_counter.get("acoustic_silence", 0) * 5
    score -= type_counter.get("medication_missed", 0) * 10
    score -= type_counter.get("medication_late", 0) * 3
    score -= type_counter.get("vital_alert", 0) * 15
    score -= type_counter.get("routine_anomaly", 0) * 5

    score -= severity_counter.get(Severity.CRITICAL, 0) * 10
    score -= severity_counter.get(Severity.HIGH, 0) * 5

    # Bonuses
    score += type_counter.get("check_in_completed", 0) * 5
    score += type_counter.get("medication_taken", 0) * 3

    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Narrative generation
# ---------------------------------------------------------------------------

_NARRATIVE_PROMPT = """You are a concise health-monitoring assistant for the AETHER elderly care system.
Summarise the following daily activity data in exactly 2-3 sentences suitable for a caregiver dashboard.

Home: {home_id}
Date: {date}
Total Events: {total_events}
Falls: {fall_count}
Medication Adherence: {med_adherence}%
Activity Score: {activity_score}/100
Events by Type: {events_by_type}
Events by Severity: {events_by_severity}
Key Events: {key_events}

Write a concise, empathetic, factual summary. Do NOT provide medical advice or diagnoses.
Focus on what happened and what caregivers should be aware of.
"""


def _generate_narrative(entry: TimelineEntry, correlation_id: str) -> str:
    """Use Bedrock to generate a 2-3 sentence daily narrative."""
    prompt = _NARRATIVE_PROMPT.format(
        home_id=entry.home_id,
        date=entry.date,
        total_events=entry.total_events,
        fall_count=entry.fall_count,
        med_adherence=entry.medication_adherence_pct,
        activity_score=entry.activity_score,
        events_by_type=json_dumps(entry.events_by_type),
        events_by_severity=json_dumps(entry.events_by_severity),
        key_events=json_dumps(entry.key_events[:5]),
    )

    log_with_context(
        logger, "INFO",
        "Generating narrative via Bedrock",
        correlation_id=correlation_id,
    )

    narrative = invoke_bedrock_model(prompt, max_tokens=256, temperature=0.4)
    return narrative.strip()[:1000]  # safety cap


def _generate_fallback_narrative(entry: TimelineEntry) -> str:
    """Generate a simple template-based narrative when Bedrock is unavailable."""
    parts = [
        f"On {entry.date}, {entry.total_events} event(s) were recorded for home {entry.home_id}.",
    ]
    if entry.fall_count > 0:
        parts.append(f"{entry.fall_count} fall(s) detected.")
    if entry.medication_adherence_pct < 100:
        parts.append(f"Medication adherence was {entry.medication_adherence_pct}%.")
    else:
        parts.append("All medications were taken on time.")
    parts.append(f"Overall activity score: {entry.activity_score}/100.")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _get_timeline_entry(home_id: str, date: str) -> Optional[TimelineEntry]:
    """Retrieve a single timeline entry from DynamoDB."""
    item = dynamo_get_item(
        table_name=timeline_table_name(),
        key={"home_id": home_id, "date": date},
    )
    if item:
        return TimelineEntry.from_dict(item)
    return None


def _query_timeline_range(
    home_id: str,
    start_date: str,
    end_date: str,
) -> List[TimelineEntry]:
    """Query timeline entries for a date range."""
    from boto3.dynamodb.conditions import Key

    items, _ = dynamo_query_items(
        table_name=timeline_table_name(),
        key_condition_expression=Key("home_id").eq(home_id) & Key("date").between(start_date, end_date),
        scan_forward=True,
        max_pages=10,
    )
    return [TimelineEntry.from_dict(item) for item in items]


def _discover_active_homes(date: str, correlation_id: str) -> List[str]:
    """Find all home_ids that have events on a given date.

    Uses a scan with a filter – acceptable for moderate table sizes. For
    very large deployments, a GSI on ``date`` or an external list of active
    homes is recommended.
    """
    import boto3
    from boto3.dynamodb.conditions import Attr, Key

    table = boto3.resource("dynamodb").Table(events_table_name())
    start_ts = f"{date}T00:00:00Z"
    end_ts = f"{date}T23:59:59.999999Z"

    home_ids: set = set()
    scan_kwargs: Dict[str, Any] = {
        "FilterExpression": Attr("timestamp").between(start_ts, end_ts),
        "ProjectionExpression": "home_id",
    }

    try:
        pages = 0
        while pages < 5:
            response = table.scan(**scan_kwargs)
            for item in response.get("Items", []):
                home_ids.add(item["home_id"])
            pages += 1
            if "LastEvaluatedKey" not in response:
                break
            scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
    except Exception as exc:
        log_with_context(
            logger, "WARNING",
            f"Home discovery scan failed: {exc}",
            correlation_id=correlation_id,
        )

    # Fallback: check environment for a configured home list
    if not home_ids:
        configured = get_env("ACTIVE_HOME_IDS", "")
        if configured:
            home_ids = set(configured.split(","))

    return list(home_ids)
