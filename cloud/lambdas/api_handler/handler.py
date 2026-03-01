"""
AETHER API Handler Lambda
==========================
Unified Lambda function behind API Gateway (proxy integration) that routes
REST requests to the appropriate handler based on HTTP method and path.

Endpoints
---------
GET  /api/dashboard                         – Dashboard overview stats
GET  /api/events?home_id=X&start=X&end=X   – Events with filtering
GET  /api/timeline/{home_id}?date=…         – Daily timeline
GET  /api/residents/{resident_id}           – Resident profile
PUT  /api/residents/{resident_id}           – Update resident profile
POST /api/events                            – Submit event from edge
POST /api/alerts/acknowledge                – Acknowledge alert
GET  /api/analytics?home_id=X&period=7d     – Analytics data
GET  /api/evidence/{packet_id}              – Presigned S3 URL for evidence
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote_plus

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.models import (
    Event,
    Severity,
    generate_event_id,
    get_current_timestamp,
    validate_event_payload,
)
from shared.utils import (
    api_error,
    api_response,
    dynamo_get_item,
    dynamo_put_item,
    dynamo_query_items,
    dynamo_update_item,
    events_table_name,
    evidence_bucket_name,
    generate_correlation_id,
    get_env,
    json_dumps,
    log_with_context,
    residents_table_name,
    s3_get_presigned_url,
    setup_logger,
    sns_publish_structured_alert,
    alerts_topic_arn,
    timeline_table_name,
)

logger = setup_logger("api_handler")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE = int(get_env("DEFAULT_PAGE_SIZE", "25"))
MAX_PAGE_SIZE = int(get_env("MAX_PAGE_SIZE", "100"))


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
    http_method = event.get("httpMethod", "GET").upper()
    if http_method == "OPTIONS":
        return api_response(200, {"message": "OK"})

    path = event.get("path", "/")
    resource = event.get("resource", path)

    log_with_context(
        logger, "INFO",
        f"{http_method} {path}",
        correlation_id=correlation_id,
    )

    try:
        # Route the request
        response = _route_request(http_method, path, event, correlation_id)
        return response
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Unhandled API error: {exc}",
            correlation_id=correlation_id,
            traceback=traceback.format_exc(),
        )
        return api_error(500, "internal_error", "An unexpected error occurred.", correlation_id)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

# Route patterns: (method, regex, handler_function)
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

def _query_param(event: Dict[str, Any], name: str, default: Optional[str] = None) -> Optional[str]:
    """Extract a query-string parameter."""
    params = event.get("queryStringParameters") or {}
    return params.get(name, default)


def _path_param(event: Dict[str, Any], name: str) -> Optional[str]:
    """Extract a path parameter."""
    params = event.get("pathParameters") or {}
    return params.get(name)


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


def _pagination_params(event: Dict[str, Any]) -> Tuple[int, Optional[str]]:
    """Extract pagination parameters (page_size, next_token)."""
    page_size = int(_query_param(event, "page_size", str(DEFAULT_PAGE_SIZE)) or DEFAULT_PAGE_SIZE)
    page_size = min(page_size, MAX_PAGE_SIZE)
    next_token = _query_param(event, "next_token")
    return page_size, next_token


# ---------------------------------------------------------------------------
# GET /api/dashboard
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/dashboard/?$")
def _get_dashboard(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Return dashboard overview stats aggregated across homes."""
    home_id = _query_param(event, "home_id")
    period_days = int(_query_param(event, "period", "7") or "7")

    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=period_days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    log_with_context(
        logger, "INFO",
        f"Dashboard request: home_id={home_id}, period={period_days}d",
        correlation_id=correlation_id,
    )

    dashboard: Dict[str, Any] = {
        "period_days": period_days,
        "start_date": start_date,
        "end_date": end_date,
        "generated_at": get_current_timestamp(),
    }

    if home_id:
        dashboard["home_id"] = home_id
        timeline_entries = _fetch_timeline_range(home_id, start_date, end_date)

        total_events = sum(e.get("total_events", 0) for e in timeline_entries)
        total_falls = sum(e.get("fall_count", 0) for e in timeline_entries)
        med_adherences = [e.get("medication_adherence_pct", 100) for e in timeline_entries if e.get("total_events", 0) > 0]
        avg_adherence = sum(med_adherences) / len(med_adherences) if med_adherences else 100.0
        activity_scores = [e.get("activity_score", 0) for e in timeline_entries if e.get("total_events", 0) > 0]
        avg_activity = sum(activity_scores) / len(activity_scores) if activity_scores else 0.0

        # Severity breakdown
        severity_totals: Dict[str, int] = {}
        for entry in timeline_entries:
            for sev, count in entry.get("events_by_severity", {}).items():
                severity_totals[sev] = severity_totals.get(sev, 0) + int(count)

        dashboard.update({
            "total_events": total_events,
            "total_falls": total_falls,
            "avg_medication_adherence_pct": round(avg_adherence, 1),
            "avg_activity_score": round(avg_activity, 1),
            "severity_breakdown": severity_totals,
            "days_with_data": len([e for e in timeline_entries if e.get("total_events", 0) > 0]),
            "timeline_entries": len(timeline_entries),
        })
    else:
        dashboard["message"] = "Provide home_id query parameter for detailed stats."

    return api_response(200, dashboard)


# ---------------------------------------------------------------------------
# GET /api/events
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/events/?$")
def _get_events(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Fetch events with filtering by home_id, date range, type, severity."""
    from boto3.dynamodb.conditions import Attr, Key

    home_id = _query_param(event, "home_id")
    if not home_id:
        return api_error(400, "missing_parameter", "home_id is required", correlation_id)

    start = _query_param(event, "start")
    end = _query_param(event, "end")
    event_type = _query_param(event, "event_type")
    severity = _query_param(event, "severity")
    page_size, _ = _pagination_params(event)

    now = datetime.now(timezone.utc)
    if not start:
        start = (now - timedelta(days=1)).isoformat() + "Z"
    if not end:
        end = now.isoformat() + "Z"

    key_condition = Key("home_id").eq(home_id) & Key("timestamp").between(start, end)

    # Build optional filter
    filter_expr = None
    if event_type and severity:
        filter_expr = Attr("event_type").eq(event_type) & Attr("severity").eq(severity)
    elif event_type:
        filter_expr = Attr("event_type").eq(event_type)
    elif severity:
        filter_expr = Attr("severity").eq(severity)

    # Filter out escalation-state records
    esc_filter = Attr("timestamp").not_contains("ESC#")
    if filter_expr is not None:
        filter_expr = filter_expr & esc_filter
    else:
        filter_expr = esc_filter

    items, last_key = dynamo_query_items(
        table_name=events_table_name(),
        key_condition_expression=key_condition,
        filter_expression=filter_expr,
        scan_forward=False,
        limit=page_size,
    )

    result: Dict[str, Any] = {
        "home_id": home_id,
        "start": start,
        "end": end,
        "count": len(items),
        "events": items,
    }
    if last_key:
        result["next_token"] = json_dumps(last_key)
    if event_type:
        result["event_type_filter"] = event_type
    if severity:
        result["severity_filter"] = severity

    return api_response(200, result)


# ---------------------------------------------------------------------------
# GET /api/timeline/{home_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/timeline/(?P<home_id>[^/]+)/?$")
def _get_timeline(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Get timeline data for a home."""
    home_id = unquote_plus(match.group("home_id"))
    date = _query_param(event, "date")
    start = _query_param(event, "start")
    end = _query_param(event, "end")

    if date:
        item = dynamo_get_item(timeline_table_name(), {"home_id": home_id, "date": date})
        if not item:
            return api_error(404, "not_found", f"No timeline for {home_id} on {date}", correlation_id)
        return api_response(200, item)

    # Range query
    if not start or not end:
        now = datetime.now(timezone.utc)
        end = end or now.strftime("%Y-%m-%d")
        start = start or (now - timedelta(days=7)).strftime("%Y-%m-%d")

    entries = _fetch_timeline_range(home_id, start, end)
    return api_response(200, {
        "home_id": home_id,
        "start": start,
        "end": end,
        "count": len(entries),
        "entries": entries,
    })


# ---------------------------------------------------------------------------
# GET /api/residents/{resident_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/residents/(?P<resident_id>[^/]+)/?$")
def _get_resident(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Retrieve a resident profile."""
    resident_id = unquote_plus(match.group("resident_id"))

    item = dynamo_get_item(residents_table_name(), {"resident_id": resident_id})
    if not item:
        return api_error(404, "not_found", f"Resident {resident_id} not found", correlation_id)

    return api_response(200, item)


# ---------------------------------------------------------------------------
# PUT /api/residents/{resident_id}
# ---------------------------------------------------------------------------

@_route("PUT", r"^/api/residents/(?P<resident_id>[^/]+)/?$")
def _update_resident(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Update a resident profile."""
    resident_id = unquote_plus(match.group("resident_id"))
    body = _parse_body(event)

    if not body:
        return api_error(400, "empty_body", "Request body is required", correlation_id)

    # Prevent overwriting primary key
    body.pop("resident_id", None)

    # Build update expression
    update_parts: List[str] = ["SET updated_at = :updated_at"]
    expr_values: Dict[str, Any] = {":updated_at": get_current_timestamp()}
    expr_names: Dict[str, str] = {}

    # Allowed updatable fields
    allowed_fields = {
        "name", "date_of_birth", "home_id", "emergency_contacts",
        "medical_conditions", "medications", "preferences",
        "mobility_level", "cognitive_status", "notes",
    }

    for key, value in body.items():
        if key not in allowed_fields:
            continue
        safe_key = f"#f_{key}"
        placeholder = f":v_{key}"
        update_parts.append(f"{safe_key} = {placeholder}")
        expr_names[safe_key] = key
        expr_values[placeholder] = value

    if len(update_parts) <= 1:
        return api_error(400, "no_valid_fields", "No valid fields to update", correlation_id)

    update_expression = ", ".join(update_parts)

    try:
        result = dynamo_update_item(
            table_name=residents_table_name(),
            key={"resident_id": resident_id},
            update_expression=update_expression,
            expression_attribute_values=expr_values,
            expression_attribute_names=expr_names,
        )
        return api_response(200, {
            "message": "Resident updated",
            "resident_id": resident_id,
            "updated": result.get("Attributes", {}),
        })
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Failed to update resident {resident_id}: {exc}",
            correlation_id=correlation_id,
        )
        return api_error(500, "update_failed", str(exc), correlation_id)


# ---------------------------------------------------------------------------
# POST /api/events
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/events/?$")
def _post_event(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Submit an event from the Edge Gateway."""
    body = _parse_body(event)

    errors = validate_event_payload(body)
    if errors:
        return api_error(400, "validation_error", "; ".join(errors), correlation_id)

    # Enrich event
    evt = Event(
        event_id=body.get("event_id") or generate_event_id(),
        home_id=body["home_id"],
        resident_id=body["resident_id"],
        event_type=body["event_type"],
        severity=body["severity"],
        timestamp=body.get("timestamp") or get_current_timestamp(),
        data=body.get("data", {}),
        confidence=float(body.get("confidence", 0.0)),
        source_sensors=body.get("source_sensors", []),
        privacy_level=body.get("privacy_level", "PRIVATE"),
    )

    try:
        item = evt.to_dict()
        item["correlation_id"] = correlation_id
        item["submitted_via"] = "api"
        dynamo_put_item(events_table_name(), item)
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Failed to store event: {exc}",
            correlation_id=correlation_id,
        )
        return api_error(500, "storage_error", "Failed to store event", correlation_id)

    # Notify on high-severity events
    if evt.is_critical_or_high:
        try:
            topic = alerts_topic_arn()
            if topic:
                sns_publish_structured_alert(
                    topic_arn=topic,
                    event_type=evt.event_type,
                    severity=evt.severity,
                    home_id=evt.home_id,
                    message=f"AETHER API Event: {evt.event_type} ({evt.severity}) for home {evt.home_id}",
                )
        except Exception as exc:
            log_with_context(
                logger, "WARNING",
                f"SNS notification failed: {exc}",
                correlation_id=correlation_id,
            )

    return api_response(201, {
        "message": "Event created",
        "event_id": evt.event_id,
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# POST /api/alerts/acknowledge
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/alerts/acknowledge/?$")
def _acknowledge_alert(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Acknowledge an active alert / escalation."""
    body = _parse_body(event)
    event_id = body.get("event_id")
    home_id = body.get("home_id")
    acknowledged_by = body.get("acknowledged_by", "api_user")

    if not event_id or not home_id:
        return api_error(400, "missing_fields", "event_id and home_id are required", correlation_id)

    # Update the event record
    try:
        dynamo_update_item(
            table_name=events_table_name(),
            key={"home_id": home_id, "timestamp": f"ESC#{event_id}"},
            update_expression="SET acknowledged_by = :ack_by, acknowledged_at = :ack_at, resolved = :resolved",
            expression_attribute_values={
                ":ack_by": acknowledged_by,
                ":ack_at": get_current_timestamp(),
                ":resolved": True,
            },
        )
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Failed to acknowledge alert: {exc}",
            correlation_id=correlation_id,
        )
        return api_error(500, "acknowledge_failed", str(exc), correlation_id)

    log_with_context(
        logger, "INFO",
        f"Alert acknowledged: {event_id} by {acknowledged_by}",
        correlation_id=correlation_id,
    )

    return api_response(200, {
        "message": "Alert acknowledged",
        "event_id": event_id,
        "acknowledged_by": acknowledged_by,
    })


# ---------------------------------------------------------------------------
# GET /api/analytics
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/analytics/?$")
def _get_analytics(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Return analytics data for a home over a given period."""
    home_id = _query_param(event, "home_id")
    if not home_id:
        return api_error(400, "missing_parameter", "home_id is required", correlation_id)

    period = _query_param(event, "period", "7d") or "7d"
    # Parse period (e.g. "7d", "30d")
    period_match = re.match(r"^(\d+)d$", period)
    if not period_match:
        return api_error(400, "invalid_period", "Period must be in format Nd (e.g. 7d, 30d)", correlation_id)
    period_days = int(period_match.group(1))

    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=period_days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    entries = _fetch_timeline_range(home_id, start_date, end_date)

    # Compute analytics
    daily_events: List[Dict[str, Any]] = []
    total_events = 0
    total_falls = 0
    adherence_values: List[float] = []
    activity_values: List[float] = []
    type_totals: Dict[str, int] = {}
    severity_totals: Dict[str, int] = {}

    for entry in entries:
        day_events = int(entry.get("total_events", 0))
        total_events += day_events
        day_falls = int(entry.get("fall_count", 0))
        total_falls += day_falls
        adherence = float(entry.get("medication_adherence_pct", 100))
        activity = float(entry.get("activity_score", 0))

        if day_events > 0:
            adherence_values.append(adherence)
            activity_values.append(activity)

        daily_events.append({
            "date": entry.get("date", ""),
            "total_events": day_events,
            "fall_count": day_falls,
            "medication_adherence_pct": adherence,
            "activity_score": activity,
        })

        for etype, count in entry.get("events_by_type", {}).items():
            type_totals[etype] = type_totals.get(etype, 0) + int(count)
        for sev, count in entry.get("events_by_severity", {}).items():
            severity_totals[sev] = severity_totals.get(sev, 0) + int(count)

    avg_adherence = sum(adherence_values) / len(adherence_values) if adherence_values else 100.0
    avg_activity = sum(activity_values) / len(activity_values) if activity_values else 0.0

    # Trend calculation (comparing first half vs second half of period)
    mid = len(daily_events) // 2
    first_half = daily_events[:mid] if mid > 0 else []
    second_half = daily_events[mid:] if mid > 0 else daily_events

    def _avg_metric(entries_slice: List[Dict[str, Any]], key: str) -> float:
        vals = [e[key] for e in entries_slice if e["total_events"] > 0]
        return sum(vals) / len(vals) if vals else 0

    trends: Dict[str, Any] = {}
    if first_half and second_half:
        trends = {
            "events_trend": "increasing" if _avg_metric(second_half, "total_events") > _avg_metric(first_half, "total_events") else "decreasing",
            "adherence_trend": "improving" if _avg_metric(second_half, "medication_adherence_pct") >= _avg_metric(first_half, "medication_adherence_pct") else "declining",
            "activity_trend": "improving" if _avg_metric(second_half, "activity_score") >= _avg_metric(first_half, "activity_score") else "declining",
        }

    analytics: Dict[str, Any] = {
        "home_id": home_id,
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "summary": {
            "total_events": total_events,
            "total_falls": total_falls,
            "avg_medication_adherence_pct": round(avg_adherence, 1),
            "avg_activity_score": round(avg_activity, 1),
            "days_with_data": len([e for e in daily_events if e["total_events"] > 0]),
        },
        "events_by_type": type_totals,
        "events_by_severity": severity_totals,
        "trends": trends,
        "daily": daily_events,
        "generated_at": get_current_timestamp(),
    }

    return api_response(200, analytics)


# ---------------------------------------------------------------------------
# GET /api/evidence/{packet_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/evidence/(?P<packet_id>.+)$")
def _get_evidence(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Generate a presigned S3 URL for an evidence packet."""
    packet_id = unquote_plus(match.group("packet_id"))
    expires = int(_query_param(event, "expires", "3600") or "3600")

    # Clamp expiry between 5 min and 12 hours
    expires = max(300, min(expires, 43200))

    log_with_context(
        logger, "INFO",
        f"Generating presigned URL for evidence: {packet_id}",
        correlation_id=correlation_id,
    )

    try:
        url = s3_get_presigned_url(
            bucket=evidence_bucket_name(),
            key=packet_id,
            expires_in=expires,
        )
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Failed to generate presigned URL: {exc}",
            correlation_id=correlation_id,
        )
        return api_error(500, "presign_failed", "Unable to generate evidence URL", correlation_id)

    return api_response(200, {
        "packet_id": packet_id,
        "url": url,
        "expires_in": expires,
    })


# ---------------------------------------------------------------------------
# Timeline query helper
# ---------------------------------------------------------------------------

def _fetch_timeline_range(
    home_id: str,
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Query the timeline table for a date range."""
    from boto3.dynamodb.conditions import Key

    items, _ = dynamo_query_items(
        table_name=timeline_table_name(),
        key_condition_expression=Key("home_id").eq(home_id) & Key("date").between(start_date, end_date),
        scan_forward=True,
        max_pages=10,
    )
    return items
