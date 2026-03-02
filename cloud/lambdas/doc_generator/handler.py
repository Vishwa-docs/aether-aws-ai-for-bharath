"""
AETHER Documentation Generator Lambda
======================================
Generates SOAP-like clinical documentation from timeline events using
AWS Bedrock (amazon.nova-lite-v1:0).

Endpoints
---------
POST /api/docs/generate  – Generate a new clinical document
GET  /api/docs/{doc_id}  – Retrieve a previously generated document
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
import uuid
from datetime import datetime, timedelta, timezone
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
    dynamo_query_items,
    events_table_name,
    evidence_bucket_name,
    generate_correlation_id,
    get_env,
    invoke_bedrock_model,
    json_dumps,
    log_with_context,
    s3_get_object,
    s3_get_presigned_url,
    s3_put_object,
    setup_logger,
    timeline_table_name,
    residents_table_name,
    bedrock_model_id,
)

logger = setup_logger("doc_generator")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VALID_DOC_TYPES = {"soap_note", "daily_summary", "weekly_report", "incident_report"}

BEDROCK_MODEL = get_env("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

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

    http_method = event.get("httpMethod", "GET").upper()
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
            f"Unhandled error: {exc}",
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


def _generate_doc_id() -> str:
    """Generate a unique document identifier."""
    return f"doc-{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# POST /api/docs/generate
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/docs/generate/?$")
def _post_generate(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Generate a clinical document from timeline events."""
    from boto3.dynamodb.conditions import Key, Attr

    body = _parse_body(event)
    home_id = body.get("home_id")
    resident_id = body.get("resident_id")
    date_range = body.get("date_range", {})
    doc_type = body.get("doc_type", "soap_note")

    # --- Validation ---
    if not home_id:
        return api_error(400, "missing_parameter", "home_id is required", correlation_id)
    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id is required", correlation_id)
    if doc_type not in VALID_DOC_TYPES:
        return api_error(
            400, "invalid_parameter",
            f"doc_type must be one of: {', '.join(sorted(VALID_DOC_TYPES))}",
            correlation_id,
        )

    # Date range defaults
    now = datetime.now(timezone.utc)
    start_date = date_range.get("start")
    end_date = date_range.get("end")

    if not start_date:
        if doc_type == "weekly_report":
            start_date = (now - timedelta(days=7)).isoformat() + "Z"
        else:
            start_date = (now - timedelta(days=1)).isoformat() + "Z"
    if not end_date:
        end_date = now.isoformat() + "Z"

    log_with_context(
        logger, "INFO",
        f"Generating {doc_type} for home={home_id} resident={resident_id} "
        f"range={start_date} to {end_date}",
        correlation_id=correlation_id,
    )

    # --- Fetch events from DynamoDB ---
    key_condition = Key("home_id").eq(home_id) & Key("timestamp").between(start_date, end_date)

    # Filter out escalation state records
    filter_expr = Attr("timestamp").not_contains("ESC#")

    items, _ = dynamo_query_items(
        table_name=events_table_name(),
        key_condition_expression=key_condition,
        filter_expression=filter_expr,
        scan_forward=True,
        max_pages=20,
    )

    # Optionally narrow to the specific resident
    if resident_id:
        items = [
            e for e in items
            if e.get("resident_id") == resident_id
            or e.get("metadata", {}).get("resident_id") == resident_id
        ]

    log_with_context(
        logger, "INFO",
        f"Fetched {len(items)} events for document generation",
        correlation_id=correlation_id,
    )

    # --- Fetch resident profile ---
    resident_profile = dynamo_get_item(
        residents_table_name(),
        {"resident_id": resident_id},
    )
    resident_name = "Unknown Resident"
    if resident_profile:
        resident_name = resident_profile.get("name", resident_name)

    # --- Build prompt & call Bedrock ---
    events_summary = _summarize_events_for_prompt(items)
    prompt = _build_prompt(doc_type, resident_name, resident_id, home_id, start_date, end_date, events_summary)

    log_with_context(
        logger, "INFO",
        f"Invoking Bedrock model {BEDROCK_MODEL} for {doc_type}",
        correlation_id=correlation_id,
    )

    generated_content = invoke_bedrock_model(
        prompt=prompt,
        model_id=BEDROCK_MODEL,
        max_tokens=2048,
        temperature=0.3,
    )

    # --- Build final document ---
    doc_id = _generate_doc_id()
    created_at = get_current_timestamp()

    document = {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "home_id": home_id,
        "resident_id": resident_id,
        "resident_name": resident_name,
        "date_range": {"start": start_date, "end": end_date},
        "event_count": len(items),
        "content": generated_content,
        "created_at": created_at,
        "correlation_id": correlation_id,
    }

    # --- Store in S3 ---
    bucket = evidence_bucket_name()
    s3_key = f"docs/{home_id}/{resident_id}/{doc_type}/{doc_id}.json"

    s3_put_object(
        bucket=bucket,
        key=s3_key,
        body=document,
        content_type="application/json",
        metadata={
            "doc_type": doc_type,
            "home_id": home_id,
            "resident_id": resident_id,
            "correlation_id": correlation_id,
        },
    )

    s3_url = f"s3://{bucket}/{s3_key}"

    log_with_context(
        logger, "INFO",
        f"Stored document {doc_id} at {s3_url}",
        correlation_id=correlation_id,
    )

    # --- Store metadata in DynamoDB ---
    doc_metadata = {
        "home_id": home_id,
        "timestamp": f"DOC#{created_at}#{doc_id}",
        "event_id": doc_id,
        "event_type": "document_generated",
        "severity": "INFO",
        "resident_id": resident_id,
        "doc_type": doc_type,
        "s3_key": s3_key,
        "s3_bucket": bucket,
        "event_count": len(items),
        "date_range_start": start_date,
        "date_range_end": end_date,
        "created_at": created_at,
        "correlation_id": correlation_id,
    }

    dynamo_put_item(events_table_name(), doc_metadata)

    # --- Return result ---
    return api_response(201, {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "content": generated_content,
        "s3_url": s3_url,
        "created_at": created_at,
        "event_count": len(items),
        "resident_name": resident_name,
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# GET /api/docs/{doc_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/docs/(?P<doc_id>[^/]+)/?$")
def _get_document(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Retrieve a previously generated document from S3."""
    from boto3.dynamodb.conditions import Key, Attr

    doc_id = match.group("doc_id")

    log_with_context(
        logger, "INFO",
        f"Retrieving document {doc_id}",
        correlation_id=correlation_id,
    )

    # Scan the events table for the doc metadata record
    # Documents are stored with event_type = "document_generated"
    # We use a GSI or scan to find by doc_id
    # First, try to locate via a query on a known home_id or scan
    # For simplicity, we'll scan with a filter on event_id = doc_id
    from boto3.dynamodb.conditions import Attr as DAttr

    table_name = events_table_name()
    table = __import__("boto3").resource("dynamodb").Table(table_name)

    response = table.scan(
        FilterExpression=DAttr("event_id").eq(doc_id) & DAttr("event_type").eq("document_generated"),
        Limit=1,
    )

    items = response.get("Items", [])
    if not items:
        return api_error(404, "not_found", f"Document {doc_id} not found", correlation_id)

    doc_meta = items[0]
    s3_key = doc_meta.get("s3_key")
    bucket = doc_meta.get("s3_bucket", evidence_bucket_name())

    if not s3_key:
        return api_error(404, "not_found", f"Document {doc_id} has no S3 reference", correlation_id)

    # Retrieve document content from S3
    try:
        raw = s3_get_object(bucket, s3_key)
        document = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Failed to retrieve document from S3: {exc}",
            correlation_id=correlation_id,
        )
        return api_error(500, "s3_error", f"Failed to retrieve document: {exc}", correlation_id)

    # Generate a presigned URL for direct download
    presigned_url = s3_get_presigned_url(bucket, s3_key, expires_in=3600)
    document["presigned_url"] = presigned_url

    return api_response(200, document)


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------


def _summarize_events_for_prompt(events: List[Dict[str, Any]]) -> str:
    """Convert raw DynamoDB events into a concise textual summary for the LLM."""
    if not events:
        return "No events recorded during this period."

    lines: List[str] = []
    for evt in events:
        ts = evt.get("timestamp", "unknown")
        etype = evt.get("event_type", "unknown")
        severity = evt.get("severity", "INFO")
        description = evt.get("description", evt.get("metadata", {}).get("description", ""))
        confidence = evt.get("confidence", evt.get("metadata", {}).get("confidence", ""))

        line = f"- [{ts}] {etype} (severity={severity})"
        if description:
            line += f": {description}"
        if confidence:
            line += f" [confidence={confidence}]"

        # Include relevant metadata
        metadata = evt.get("metadata", {})
        if metadata.get("sensor_id"):
            line += f" sensor={metadata['sensor_id']}"
        if metadata.get("location"):
            line += f" location={metadata['location']}"

        lines.append(line)

    return "\n".join(lines)


def _build_prompt(
    doc_type: str,
    resident_name: str,
    resident_id: str,
    home_id: str,
    start_date: str,
    end_date: str,
    events_summary: str,
) -> str:
    """Build the Bedrock prompt based on document type."""

    header = (
        f"You are a clinical documentation assistant for the AETHER elderly care "
        f"monitoring system. Generate a professional clinical document based on "
        f"the following sensor and event data.\n\n"
        f"Resident: {resident_name} (ID: {resident_id})\n"
        f"Home: {home_id}\n"
        f"Date Range: {start_date} to {end_date}\n\n"
        f"Events:\n{events_summary}\n\n"
    )

    if doc_type == "soap_note":
        return header + (
            "Generate a SOAP note with the following sections:\n\n"
            "**S (Subjective):** Summarize the resident's reported or inferred "
            "status based on sensor readings and behavioral patterns. Note any "
            "check-ins, voice interactions, or routine deviations.\n\n"
            "**O (Objective):** List measurable observations: sensor events, "
            "vital signs, medication adherence data, fall detection events, "
            "acoustic alerts, and activity patterns with timestamps.\n\n"
            "**A (Assessment):** Provide a clinical assessment of the resident's "
            "current status, identify risk factors, trends (improving/declining), "
            "and any concerns requiring attention.\n\n"
            "**P (Plan):** Recommend next steps: care adjustments, follow-up "
            "monitoring, escalation needs, medication review, or caregiver "
            "notifications.\n\n"
            "Use professional clinical language. Reference specific events and "
            "timestamps from the data."
        )

    elif doc_type == "daily_summary":
        return header + (
            "Generate a comprehensive daily care summary including:\n\n"
            "1. **Overview:** Brief narrative of the day's events and overall status.\n"
            "2. **Activity Timeline:** Chronological summary of key events.\n"
            "3. **Medication Adherence:** Summary of medication events (taken, missed, late).\n"
            "4. **Safety Events:** Any falls, acoustic alerts, or anomalies.\n"
            "5. **Vital Signs:** Summary of any vital sign data.\n"
            "6. **Behavioral Patterns:** Routine adherence, sleep/wake patterns, activity levels.\n"
            "7. **Concerns & Notes:** Items requiring caregiver attention.\n\n"
            "Write in clear, professional language suitable for care team handoff."
        )

    elif doc_type == "weekly_report":
        return header + (
            "Generate a weekly care report including:\n\n"
            "1. **Executive Summary:** High-level overview of the week.\n"
            "2. **Trends Analysis:** Week-over-week changes in activity, adherence, and health indicators.\n"
            "3. **Medication Adherence Statistics:** Daily adherence rates, missed doses, patterns.\n"
            "4. **Safety Incidents:** Falls, alerts, and response times.\n"
            "5. **Risk Assessment:** Current risk level with supporting data points.\n"
            "6. **Activity & Engagement:** Daily activity scores, routine deviations.\n"
            "7. **Recommendations:** Suggested care plan adjustments based on trends.\n"
            "8. **Metrics Dashboard:** Key statistics in a structured format.\n\n"
            "Include specific numbers and percentages where possible."
        )

    elif doc_type == "incident_report":
        return header + (
            "Generate a detailed incident report including:\n\n"
            "1. **Incident Summary:** What happened, when, and where.\n"
            "2. **Detection Details:** How the incident was detected (sensor type, "
            "confidence score, detection method).\n"
            "3. **Timeline of Events:** Minute-by-minute sequence of events "
            "surrounding the incident.\n"
            "4. **Evidence References:** Sensor data, acoustic recordings, "
            "vital signs, and other supporting evidence.\n"
            "5. **Response Actions:** Escalation steps taken, notifications sent, "
            "response times.\n"
            "6. **Impact Assessment:** Effect on resident's condition and care plan.\n"
            "7. **Root Cause Analysis:** Contributing factors and potential causes.\n"
            "8. **Preventive Recommendations:** Steps to reduce recurrence.\n\n"
            "Focus on the most critical events. Be thorough and factual."
        )

    # Fallback
    return header + "Generate a clinical summary of the events listed above."
