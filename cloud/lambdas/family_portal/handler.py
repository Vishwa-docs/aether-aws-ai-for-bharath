"""
AETHER Family Portal Lambda
==============================
Manages shared calendars, emergency contact trees, offline care binders,
caregiver handoff checklists, notification preferences, consent/privacy
settings, patient education tracking, and family summary reports.

Endpoints
---------
GET    /api/family/calendar/{resident_id}         – Get shared calendar
POST   /api/family/calendar/{resident_id}/event   – Add calendar event
DELETE /api/family/calendar/{resident_id}/event/{event_id} – Remove event

GET    /api/family/emergency/{resident_id}        – Emergency contact card
PUT    /api/family/emergency/{resident_id}        – Update emergency contacts

GET    /api/family/binder/{resident_id}           – Offline care binder data
POST   /api/family/handoff                        – Create caregiver handoff

GET    /api/family/preferences/{resident_id}      – Notification preferences
PUT    /api/family/preferences/{resident_id}      – Update preferences

GET    /api/family/consent/{resident_id}          – Privacy/consent settings
PUT    /api/family/consent/{resident_id}          – Update consent

GET    /api/family/education/{resident_id}        – Education progress
POST   /api/family/education/{resident_id}/complete – Mark lesson complete

POST   /api/family/report                         – Generate family summary
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
    FamilyCalendarEvent,
    CareHandoff,
    ConsentRecord,
    get_current_timestamp,
)
from shared.utils import (
    api_error,
    api_response,
    bedrock_model_id,
    consent_table_name,
    decimalize,
    dynamo_get_item,
    dynamo_put_item,
    dynamo_query_items,
    dynamo_update_item,
    events_table_name,
    evidence_bucket_name,
    generate_correlation_id,
    get_env,
    invoke_bedrock_model,
    json_dumps,
    log_with_context,
    residents_table_name,
    s3_put_object,
    setup_logger,
    timeline_table_name,
)

logger = setup_logger("family_portal")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CALENDAR_TABLE = get_env("CALENDAR_TABLE", "aether-family-calendar")
EMERGENCY_TABLE = get_env("EMERGENCY_TABLE", "aether-emergency-contacts")
HANDOFF_TABLE = get_env("HANDOFF_TABLE", "aether-care-handoffs")
PREFERENCES_TABLE = get_env("PREFERENCES_TABLE", "aether-notification-preferences")
CONSENT_TABLE = consent_table_name()
EDUCATION_TABLE = get_env("EDUCATION_TABLE", "aether-education-tracking")
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
    body = event.get("body")
    if body is None:
        return {}
    if isinstance(body, dict):
        return body
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        return {}


def _query_param(event: Dict[str, Any], name: str, default: Optional[str] = None) -> Optional[str]:
    params = event.get("queryStringParameters") or {}
    return params.get(name, default)


# ===================================================================
# SHARED CALENDAR
# ===================================================================

# ---------------------------------------------------------------------------
# GET /api/family/calendar/{resident_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/family/calendar/(?P<resident_id>[^/]+)/?$")
def _get_calendar(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Retrieve shared calendar events for a resident."""
    from boto3.dynamodb.conditions import Key

    resident_id = match.group("resident_id")
    start_date = _query_param(event, "start")
    end_date = _query_param(event, "end")

    now = datetime.now(timezone.utc)
    if not start_date:
        start_date = now.strftime("%Y-%m-%d")
    if not end_date:
        end_date = (now + timedelta(days=30)).strftime("%Y-%m-%d")

    items, _ = dynamo_query_items(
        table_name=CALENDAR_TABLE,
        key_condition_expression=Key("resident_id").eq(resident_id) & Key("event_datetime").between(
            start_date, end_date + "Z"
        ),
        scan_forward=True,
        limit=200,
    )

    # Group by type
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        evt_type = item.get("event_type", "other")
        by_type.setdefault(evt_type, []).append(item)

    return api_response(200, {
        "resident_id": resident_id,
        "start_date": start_date,
        "end_date": end_date,
        "events": items,
        "by_type": by_type,
        "total": len(items),
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# POST /api/family/calendar/{resident_id}/event
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/family/calendar/(?P<resident_id>[^/]+)/event/?$")
def _post_calendar_event(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Add a new event to the shared calendar."""
    resident_id = match.group("resident_id")
    body = _parse_body(event)

    event_type = body.get("event_type")
    title = body.get("title")
    event_datetime = body.get("datetime")
    participants = body.get("participants", [])
    recurrence = body.get("recurrence")
    notes = body.get("notes", "")

    if not event_type:
        return api_error(400, "missing_parameter", "event_type is required", correlation_id)
    if not title:
        return api_error(400, "missing_parameter", "title is required", correlation_id)
    if not event_datetime:
        return api_error(400, "missing_parameter", "datetime is required", correlation_id)

    valid_types = {"medication", "appointment", "transport", "therapy", "social", "meal", "other"}
    if event_type not in valid_types:
        return api_error(
            400, "invalid_parameter",
            f"event_type must be one of: {', '.join(sorted(valid_types))}",
            correlation_id,
        )

    event_id = f"cal-{uuid.uuid4().hex}"

    calendar_event = FamilyCalendarEvent(
        event_id=event_id,
        resident_id=resident_id,
        event_type=event_type,
        title=title,
        event_datetime=event_datetime,
        participants=participants,
        recurrence=recurrence,
        notes=notes,
        created_by=body.get("created_by", "unknown"),
        created_at=get_current_timestamp(),
    )

    dynamo_put_item(CALENDAR_TABLE, calendar_event.to_dict())

    log_with_context(
        logger, "INFO",
        f"Calendar event created: {event_id}",
        correlation_id=correlation_id,
    )

    return api_response(201, {
        "event_id": event_id,
        "message": "Calendar event created",
        "event": calendar_event.to_dict(),
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# DELETE /api/family/calendar/{resident_id}/event/{event_id}
# ---------------------------------------------------------------------------

@_route("DELETE", r"^/api/family/calendar/(?P<resident_id>[^/]+)/event/(?P<event_id>[^/]+)/?$")
def _delete_calendar_event(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Remove a calendar event."""
    resident_id = match.group("resident_id")
    event_id = match.group("event_id")

    # Verify event exists
    existing = dynamo_get_item(
        table_name=CALENDAR_TABLE,
        key={"resident_id": resident_id, "event_id": event_id},
    )

    if not existing:
        return api_error(404, "not_found", f"Calendar event {event_id} not found", correlation_id)

    # Soft delete by marking status
    dynamo_update_item(
        table_name=CALENDAR_TABLE,
        key={"resident_id": resident_id, "event_id": event_id},
        update_expression="SET #status = :status, deleted_at = :ts",
        expression_attribute_names={"#status": "status"},
        expression_attribute_values={
            ":status": "deleted",
            ":ts": get_current_timestamp(),
        },
    )

    return api_response(200, {
        "event_id": event_id,
        "status": "deleted",
        "correlation_id": correlation_id,
    })


# ===================================================================
# EMERGENCY CONTACTS
# ===================================================================

# ---------------------------------------------------------------------------
# GET /api/family/emergency/{resident_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/family/emergency/(?P<resident_id>[^/]+)/?$")
def _get_emergency(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Get emergency contact card with contact tree."""
    resident_id = match.group("resident_id")

    item = dynamo_get_item(
        table_name=EMERGENCY_TABLE,
        key={"resident_id": resident_id},
    )

    if not item:
        # Return default structure
        item = {
            "resident_id": resident_id,
            "primary_contact": None,
            "secondary_contact": None,
            "tertiary_contact": None,
            "emergency_services": "108/112",
            "contact_tree": [],
            "fallback_instructions": "If no contact reached within 5 minutes, call emergency services.",
        }

    return api_response(200, {**item, "correlation_id": correlation_id})


# ---------------------------------------------------------------------------
# PUT /api/family/emergency/{resident_id}
# ---------------------------------------------------------------------------

@_route("PUT", r"^/api/family/emergency/(?P<resident_id>[^/]+)/?$")
def _put_emergency(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Update emergency contacts and contact tree."""
    resident_id = match.group("resident_id")
    body = _parse_body(event)

    # Build contact tree with escalation order
    contact_tree: List[Dict[str, Any]] = []

    primary = body.get("primary_contact")
    if primary:
        contact_tree.append({**primary, "tier": 1, "label": "Primary"})

    secondary = body.get("secondary_contact")
    if secondary:
        contact_tree.append({**secondary, "tier": 2, "label": "Secondary"})

    tertiary = body.get("tertiary_contact")
    if tertiary:
        contact_tree.append({**tertiary, "tier": 3, "label": "Tertiary"})

    record = {
        "resident_id": resident_id,
        "primary_contact": primary,
        "secondary_contact": secondary,
        "tertiary_contact": tertiary,
        "emergency_services": body.get("emergency_services", "108/112"),
        "contact_tree": contact_tree,
        "fallback_instructions": body.get(
            "fallback_instructions",
            "If no contact reached within 5 minutes, call emergency services."
        ),
        "updated_at": get_current_timestamp(),
        "updated_by": body.get("updated_by", "unknown"),
    }

    dynamo_put_item(EMERGENCY_TABLE, record)

    return api_response(200, {
        "message": "Emergency contacts updated",
        "resident_id": resident_id,
        "contact_tree_size": len(contact_tree),
        "correlation_id": correlation_id,
    })


# ===================================================================
# OFFLINE CARE BINDER
# ===================================================================

# ---------------------------------------------------------------------------
# GET /api/family/binder/{resident_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/family/binder/(?P<resident_id>[^/]+)/?$")
def _get_binder(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Compile offline care binder data (med list, allergies, contacts, incidents)."""
    resident_id = match.group("resident_id")

    # Fetch resident profile
    resident = dynamo_get_item(
        table_name=residents_table_name(),
        key={"resident_id": resident_id},
    ) or {}

    # Fetch emergency contacts
    emergency = dynamo_get_item(
        table_name=EMERGENCY_TABLE,
        key={"resident_id": resident_id},
    ) or {}

    # Fetch recent medications
    medications = _fetch_medications(resident_id)

    # Fetch recent incidents (critical/high events from last 90 days)
    incidents = _fetch_recent_incidents(resident_id, resident.get("home_id", ""))

    binder = {
        "resident_id": resident_id,
        "generated_at": get_current_timestamp(),
        "personal_info": {
            "name": resident.get("name", ""),
            "date_of_birth": resident.get("date_of_birth", ""),
            "blood_type": resident.get("blood_type", ""),
            "weight_kg": resident.get("weight_kg"),
            "height_cm": resident.get("height_cm"),
        },
        "medical_info": {
            "conditions": resident.get("medical_conditions", []),
            "allergies": resident.get("allergies", []),
            "dietary_restrictions": resident.get("dietary_restrictions", []),
        },
        "medications": medications,
        "emergency_contacts": emergency.get("contact_tree", []),
        "doctor_contacts": resident.get("doctor_contacts", []),
        "recent_incidents": incidents,
        "insurance_info": resident.get("insurance_info", {}),
        "advance_directives": resident.get("advance_directives", {}),
        "notes": resident.get("care_notes", ""),
        "offline_ready": True,
        "correlation_id": correlation_id,
    }

    return api_response(200, binder)


# ===================================================================
# CAREGIVER HANDOFF
# ===================================================================

# ---------------------------------------------------------------------------
# POST /api/family/handoff
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/family/handoff/?$")
def _post_handoff(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Create a caregiver handoff checklist."""
    body = _parse_body(event)

    from_caregiver = body.get("from_caregiver")
    to_caregiver = body.get("to_caregiver")
    resident_id = body.get("resident_id")
    home_id = body.get("home_id")

    if not from_caregiver:
        return api_error(400, "missing_parameter", "from_caregiver is required", correlation_id)
    if not to_caregiver:
        return api_error(400, "missing_parameter", "to_caregiver is required", correlation_id)
    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id is required", correlation_id)

    # Default checklist items
    default_checklist = [
        {"item": "Medications administered on schedule", "completed": False},
        {"item": "Vital signs checked and recorded", "completed": False},
        {"item": "Meal and fluid intake noted", "completed": False},
        {"item": "Mobility and activity status reviewed", "completed": False},
        {"item": "Any incidents or concerns documented", "completed": False},
        {"item": "Emergency contacts verified", "completed": False},
        {"item": "Sensor system status confirmed", "completed": False},
    ]

    custom_items = body.get("checklist_items", [])
    checklist = default_checklist + [
        {"item": item, "completed": False} for item in custom_items
    ]

    handoff_id = f"ho-{uuid.uuid4().hex}"

    handoff = CareHandoff(
        handoff_id=handoff_id,
        resident_id=resident_id,
        home_id=home_id or "unknown",
        from_caregiver=from_caregiver,
        to_caregiver=to_caregiver,
        checklist=checklist,
        notes=body.get("notes", ""),
        shift_summary=body.get("shift_summary", ""),
        pending_tasks=body.get("pending_tasks", []),
        timestamp=get_current_timestamp(),
        status="pending",
    )

    dynamo_put_item(HANDOFF_TABLE, handoff.to_dict())

    log_with_context(
        logger, "INFO",
        f"Handoff created: {handoff_id} from {from_caregiver} to {to_caregiver}",
        correlation_id=correlation_id,
    )

    return api_response(201, {
        "handoff_id": handoff_id,
        "message": "Handoff checklist created",
        "handoff": handoff.to_dict(),
        "correlation_id": correlation_id,
    })


# ===================================================================
# NOTIFICATION PREFERENCES
# ===================================================================

# ---------------------------------------------------------------------------
# GET /api/family/preferences/{resident_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/family/preferences/(?P<resident_id>[^/]+)/?$")
def _get_preferences(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Get family member notification preferences."""
    resident_id = match.group("resident_id")

    item = dynamo_get_item(
        table_name=PREFERENCES_TABLE,
        key={"resident_id": resident_id},
    )

    if not item:
        item = {
            "resident_id": resident_id,
            "family_members": [],
            "default_preferences": {
                "critical_alerts": {"sms": True, "push": True, "email": True, "call": True},
                "high_alerts": {"sms": True, "push": True, "email": True, "call": False},
                "medium_alerts": {"sms": False, "push": True, "email": True, "call": False},
                "low_alerts": {"sms": False, "push": False, "email": True, "call": False},
                "daily_summary": {"email": True},
                "weekly_report": {"email": True},
            },
        }

    return api_response(200, {**item, "correlation_id": correlation_id})


# ---------------------------------------------------------------------------
# PUT /api/family/preferences/{resident_id}
# ---------------------------------------------------------------------------

@_route("PUT", r"^/api/family/preferences/(?P<resident_id>[^/]+)/?$")
def _put_preferences(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Update notification preferences."""
    resident_id = match.group("resident_id")
    body = _parse_body(event)

    record = {
        "resident_id": resident_id,
        "family_members": body.get("family_members", []),
        "default_preferences": body.get("default_preferences", {}),
        "quiet_hours": body.get("quiet_hours", {"start": "22:00", "end": "07:00"}),
        "updated_at": get_current_timestamp(),
        "updated_by": body.get("updated_by", "unknown"),
    }

    dynamo_put_item(PREFERENCES_TABLE, record)

    return api_response(200, {
        "message": "Notification preferences updated",
        "resident_id": resident_id,
        "correlation_id": correlation_id,
    })


# ===================================================================
# CONSENT / PRIVACY CENTER
# ===================================================================

# ---------------------------------------------------------------------------
# GET /api/family/consent/{resident_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/family/consent/(?P<resident_id>[^/]+)/?$")
def _get_consent(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Get consent and privacy settings."""
    resident_id = match.group("resident_id")

    item = dynamo_get_item(
        table_name=CONSENT_TABLE,
        key={"resident_id": resident_id},
    )

    if not item:
        item = {
            "resident_id": resident_id,
            "data_types": {
                "health_metrics": {"allowed_viewers": ["primary_caregiver"], "retention_days": 365},
                "location_data": {"allowed_viewers": ["primary_caregiver"], "retention_days": 30},
                "audio_events": {"allowed_viewers": ["primary_caregiver"], "retention_days": 90},
                "medication_history": {"allowed_viewers": ["primary_caregiver", "physician"], "retention_days": 730},
                "incident_reports": {"allowed_viewers": ["primary_caregiver", "physician"], "retention_days": 730},
                "activity_patterns": {"allowed_viewers": ["primary_caregiver"], "retention_days": 180},
            },
            "data_sharing_enabled": True,
            "export_allowed": True,
            "delete_on_request": True,
            "last_reviewed": None,
        }

    return api_response(200, {**item, "correlation_id": correlation_id})


# ---------------------------------------------------------------------------
# PUT /api/family/consent/{resident_id}
# ---------------------------------------------------------------------------

@_route("PUT", r"^/api/family/consent/(?P<resident_id>[^/]+)/?$")
def _put_consent(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Update consent and privacy settings."""
    resident_id = match.group("resident_id")
    body = _parse_body(event)

    now = get_current_timestamp()

    record = ConsentRecord(
        resident_id=resident_id,
        data_types=body.get("data_types", {}),
        data_sharing_enabled=body.get("data_sharing_enabled", True),
        export_allowed=body.get("export_allowed", True),
        delete_on_request=body.get("delete_on_request", True),
        last_reviewed=now,
        updated_at=now,
        updated_by=body.get("updated_by", "unknown"),
    )

    dynamo_put_item(CONSENT_TABLE, record.to_dict())

    # Audit trail for consent changes
    s3_put_object(
        bucket=evidence_bucket_name(),
        key=f"consent/{resident_id}/{now.replace(':', '-')}_consent_update.json",
        body={
            "action": "consent_updated",
            "resident_id": resident_id,
            "timestamp": now,
            "updated_by": body.get("updated_by", "unknown"),
            "changes": body,
            "correlation_id": correlation_id,
        },
    )

    return api_response(200, {
        "message": "Consent settings updated",
        "resident_id": resident_id,
        "last_reviewed": now,
        "correlation_id": correlation_id,
    })


# ===================================================================
# PATIENT EDUCATION
# ===================================================================

# ---------------------------------------------------------------------------
# GET /api/family/education/{resident_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/family/education/(?P<resident_id>[^/]+)/?$")
def _get_education(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Get patient education micro-lesson progress."""
    resident_id = match.group("resident_id")

    item = dynamo_get_item(
        table_name=EDUCATION_TABLE,
        key={"resident_id": resident_id},
    )

    if not item:
        item = {
            "resident_id": resident_id,
            "completed_lessons": [],
            "available_lessons": _get_available_lessons(),
            "progress_pct": 0,
        }
    else:
        completed = set(item.get("completed_lessons", []))
        available = _get_available_lessons()
        item["available_lessons"] = available
        item["progress_pct"] = round(len(completed) / max(len(available), 1) * 100, 1)

    return api_response(200, {**item, "correlation_id": correlation_id})


# ---------------------------------------------------------------------------
# POST /api/family/education/{resident_id}/complete
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/family/education/(?P<resident_id>[^/]+)/complete/?$")
def _post_lesson_complete(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Mark a micro-lesson as completed."""
    resident_id = match.group("resident_id")
    body = _parse_body(event)
    lesson_id = body.get("lesson_id")

    if not lesson_id:
        return api_error(400, "missing_parameter", "lesson_id is required", correlation_id)

    # Fetch or create progress record
    item = dynamo_get_item(
        table_name=EDUCATION_TABLE,
        key={"resident_id": resident_id},
    )

    completed = item.get("completed_lessons", []) if item else []
    if lesson_id not in completed:
        completed.append(lesson_id)

    record = {
        "resident_id": resident_id,
        "completed_lessons": completed,
        "last_completed": lesson_id,
        "last_completed_at": get_current_timestamp(),
        "progress_pct": round(len(completed) / max(len(_get_available_lessons()), 1) * 100, 1),
    }

    dynamo_put_item(EDUCATION_TABLE, record)

    return api_response(200, {
        "message": f"Lesson {lesson_id} marked complete",
        "resident_id": resident_id,
        "total_completed": len(completed),
        "progress_pct": record["progress_pct"],
        "correlation_id": correlation_id,
    })


# ===================================================================
# FAMILY SUMMARY REPORT
# ===================================================================

# ---------------------------------------------------------------------------
# POST /api/family/report
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/family/report/?$")
def _post_report(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Generate a family-friendly summary report."""
    body = _parse_body(event)
    resident_id = body.get("resident_id")
    home_id = body.get("home_id")
    period = body.get("period", "7d")

    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id is required", correlation_id)
    if not home_id:
        return api_error(400, "missing_parameter", "home_id is required", correlation_id)

    days = {"24h": 1, "7d": 7, "30d": 30}.get(period, 7)

    # Gather data
    resident = dynamo_get_item(
        table_name=residents_table_name(),
        key={"resident_id": resident_id},
    ) or {}

    timeline_entries = _fetch_timeline(home_id, days)

    # Compute summary stats
    total_events = sum(e.get("total_events", 0) for e in timeline_entries)
    falls = sum(e.get("fall_count", 0) for e in timeline_entries)
    med_adherence_values = [e.get("medication_adherence_pct", 100) for e in timeline_entries if e.get("total_events", 0) > 0]
    avg_adherence = sum(med_adherence_values) / len(med_adherence_values) if med_adherence_values else 100

    # Generate family-friendly narrative
    prompt = f"""You are a caring assistant for AETHER, an elderly care monitoring system.
Write a warm, easy-to-understand weekly summary for the family of an elderly person.

RESIDENT: {resident.get('name', 'Your loved one')}
PERIOD: past {days} day(s)
TOTAL EVENTS: {total_events}
FALLS: {falls}
MEDICATION ADHERENCE: {avg_adherence:.0f}%
DAYS WITH DATA: {len(timeline_entries)}

Write 3-4 paragraphs that:
1. Start with a warm greeting
2. Summarize how the resident is doing overall
3. Highlight any important events or concerns
4. End with encouragement and any action items

Use simple, compassionate language. Avoid medical jargon.
If there are concerns, be honest but gentle."""

    try:
        narrative = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=1024,
            temperature=0.4,
        )
    except Exception:
        narrative = (
            f"Over the past {days} days, {total_events} events were recorded. "
            f"Medication adherence was at {avg_adherence:.0f}%. "
            f"{'No falls detected.' if falls == 0 else f'{falls} fall(s) were detected – please review.'}"
        )

    report = {
        "resident_id": resident_id,
        "period": period,
        "generated_at": get_current_timestamp(),
        "summary": {
            "total_events": total_events,
            "falls": falls,
            "medication_adherence_pct": round(avg_adherence, 1),
            "days_with_data": len(timeline_entries),
        },
        "narrative": narrative.strip(),
        "correlation_id": correlation_id,
    }

    return api_response(200, report)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _fetch_medications(resident_id: str) -> List[Dict[str, Any]]:
    """Fetch current medications for a resident."""
    from boto3.dynamodb.conditions import Key

    try:
        items, _ = dynamo_query_items(
            table_name=get_env("MEDICATIONS_TABLE", "aether-medications"),
            key_condition_expression=Key("resident_id").eq(resident_id),
            scan_forward=False,
            limit=50,
        )
        return items
    except Exception:
        return []


def _fetch_recent_incidents(resident_id: str, home_id: str) -> List[Dict[str, Any]]:
    """Fetch recent critical/high events for the care binder."""
    from boto3.dynamodb.conditions import Key, Attr

    if not home_id:
        return []

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=90)).isoformat() + "Z"
    end = now.isoformat() + "Z"

    try:
        items, _ = dynamo_query_items(
            table_name=events_table_name(),
            key_condition_expression=Key("home_id").eq(home_id) & Key("timestamp").between(start, end),
            filter_expression=Attr("severity").is_in(["CRITICAL", "HIGH"]),
            scan_forward=False,
            limit=20,
        )

        return [
            {
                "event_id": i.get("event_id", ""),
                "event_type": i.get("event_type", ""),
                "severity": i.get("severity", ""),
                "timestamp": i.get("timestamp", ""),
                "summary": i.get("data", {}).get("summary", ""),
            }
            for i in items
            if i.get("resident_id") == resident_id
        ]
    except Exception:
        return []


def _fetch_timeline(home_id: str, days: int) -> List[Dict[str, Any]]:
    """Fetch timeline entries for a period."""
    from boto3.dynamodb.conditions import Key

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")

    try:
        items, _ = dynamo_query_items(
            table_name=timeline_table_name(),
            key_condition_expression=Key("home_id").eq(home_id) & Key("date").between(start, end),
            scan_forward=True,
            limit=100,
        )
        return items
    except Exception:
        return []


def _get_available_lessons() -> List[Dict[str, str]]:
    """Return the library of available micro-lessons."""
    return [
        {"id": "fall-prevention", "title": "Fall Prevention at Home", "category": "safety"},
        {"id": "medication-management", "title": "Managing Medications Safely", "category": "medication"},
        {"id": "nutrition-seniors", "title": "Nutrition for Seniors", "category": "wellness"},
        {"id": "hydration-tips", "title": "Staying Hydrated", "category": "wellness"},
        {"id": "sleep-hygiene", "title": "Better Sleep for Seniors", "category": "wellness"},
        {"id": "emergency-response", "title": "What to Do in an Emergency", "category": "safety"},
        {"id": "caregiver-selfcare", "title": "Caregiver Self-Care", "category": "caregiver"},
        {"id": "communication-tips", "title": "Communicating with Your Loved One", "category": "caregiver"},
        {"id": "cognitive-exercises", "title": "Daily Brain Exercises", "category": "cognitive"},
        {"id": "mobility-exercises", "title": "Safe Mobility Exercises", "category": "mobility"},
        {"id": "tech-comfort", "title": "Getting Comfortable with Monitoring Tech", "category": "technology"},
        {"id": "signs-decline", "title": "Recognizing Signs of Health Changes", "category": "awareness"},
    ]
