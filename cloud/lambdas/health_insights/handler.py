"""
AETHER Health Insights & Trend Analysis Lambda
================================================
Aggregates sensor data, calculates domain health scores, detects declining
trends, and generates personalized health reports and pre-consultation
summaries using AWS Bedrock.

Endpoints
---------
POST /api/health/report          – Generate a health report
POST /api/health/preconsult      – Generate pre-consultation summary
GET  /api/health/profile/{resident_id} – Get current health profile
GET  /api/health/trends/{resident_id}  – Get trend data
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import traceback
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.models import (
    HealthProfile,
    get_current_timestamp,
)
from shared.utils import (
    api_error,
    api_response,
    bedrock_model_id,
    decimalize,
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
    residents_table_name,
    s3_put_object,
    setup_logger,
    timeline_table_name,
)

logger = setup_logger("health_insights")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

HEALTH_TABLE = get_env("HEALTH_TABLE", "aether-health-profiles")
BEDROCK_MODEL = get_env("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

# Health domains
HEALTH_DOMAINS = [
    "mobility", "sleep", "nutrition", "hydration",
    "respiratory", "cognitive", "emotional",
]

# Time window configurations
VALID_WINDOWS = {"24h": 1, "7d": 7, "30d": 30, "90d": 90}

# Trend detection thresholds
DECLINING_THRESHOLD = -0.15  # 15% decline triggers alert
CRITICAL_THRESHOLD = -0.30   # 30% decline triggers urgent alert


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


# ---------------------------------------------------------------------------
# POST /api/health/report
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/health/report/?$")
def _post_report(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Generate a comprehensive health report for a resident."""
    body = _parse_body(event)
    resident_id = body.get("resident_id")
    home_id = body.get("home_id")
    window = body.get("window", "7d")

    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id is required", correlation_id)
    if not home_id:
        return api_error(400, "missing_parameter", "home_id is required", correlation_id)
    if window not in VALID_WINDOWS:
        return api_error(
            400, "invalid_parameter",
            f"window must be one of: {', '.join(sorted(VALID_WINDOWS.keys()))}",
            correlation_id,
        )

    days = VALID_WINDOWS[window]

    log_with_context(
        logger, "INFO",
        f"Generating health report for {resident_id}, window={window}",
        correlation_id=correlation_id,
    )

    # Gather data
    events = _fetch_events(home_id, days)
    resident_events = [
        e for e in events
        if e.get("resident_id") == resident_id
    ]
    resident_profile = _fetch_resident_profile(resident_id)

    # Calculate domain scores
    domain_scores = _calculate_domain_scores(resident_events, days)

    # Detect trends
    trends = _detect_trends(home_id, resident_id, days)

    # Generate AI-powered narrative report
    report_narrative = _generate_health_narrative(
        resident_id=resident_id,
        domain_scores=domain_scores,
        trends=trends,
        event_count=len(resident_events),
        window=window,
        resident_profile=resident_profile,
        correlation_id=correlation_id,
    )

    # Build health profile
    profile = HealthProfile(
        resident_id=resident_id,
        home_id=home_id,
        domain_scores=domain_scores,
        trends=trends,
        overall_score=_calculate_overall_score(domain_scores),
        last_updated=get_current_timestamp(),
        report_window=window,
        event_count=len(resident_events),
        narrative=report_narrative,
    )

    # Store profile
    dynamo_put_item(HEALTH_TABLE, profile.to_dict())

    # Audit trail
    audit_record = {
        "action": "health_report_generated",
        "resident_id": resident_id,
        "timestamp": get_current_timestamp(),
        "correlation_id": correlation_id,
        "model_used": BEDROCK_MODEL,
        "window": window,
        "domain_scores": domain_scores,
        "overall_score": profile.overall_score,
        "narrative_length": len(report_narrative),
    }

    s3_put_object(
        bucket=evidence_bucket_name(),
        key=f"health/{resident_id}/reports/{datetime.now(timezone.utc).strftime('%Y/%m/%d')}/audit_{correlation_id}.json",
        body=audit_record,
    )

    return api_response(200, {
        "resident_id": resident_id,
        "window": window,
        "domain_scores": domain_scores,
        "overall_score": profile.overall_score,
        "trends": trends,
        "narrative": report_narrative,
        "event_count": len(resident_events),
        "generated_at": profile.last_updated,
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# POST /api/health/preconsult
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/health/preconsult/?$")
def _post_preconsult(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Generate a pre-consultation summary for telehealth."""
    body = _parse_body(event)
    resident_id = body.get("resident_id")
    home_id = body.get("home_id")
    consultation_type = body.get("consultation_type", "general")
    chief_complaints = body.get("chief_complaints", [])

    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id is required", correlation_id)
    if not home_id:
        return api_error(400, "missing_parameter", "home_id is required", correlation_id)

    log_with_context(
        logger, "INFO",
        f"Generating pre-consultation summary for {resident_id}",
        correlation_id=correlation_id,
    )

    # Gather comprehensive data (30-day window for pre-consult)
    events = _fetch_events(home_id, 30)
    resident_events = [e for e in events if e.get("resident_id") == resident_id]
    resident_profile = _fetch_resident_profile(resident_id)
    domain_scores = _calculate_domain_scores(resident_events, 30)
    trends = _detect_trends(home_id, resident_id, 30)

    # Fetch recent medications
    medications = _fetch_medications(resident_id)

    # Generate SOAP-like draft
    soap_draft = _generate_soap_draft(
        resident_id=resident_id,
        resident_profile=resident_profile,
        domain_scores=domain_scores,
        trends=trends,
        events=resident_events,
        medications=medications,
        chief_complaints=chief_complaints,
        consultation_type=consultation_type,
        correlation_id=correlation_id,
    )

    # Audit trail for compliance
    audit = {
        "action": "preconsult_summary_generated",
        "resident_id": resident_id,
        "timestamp": get_current_timestamp(),
        "correlation_id": correlation_id,
        "model_used": BEDROCK_MODEL,
        "consultation_type": consultation_type,
        "data_sources": ["events", "medications", "vitals", "activity"],
        "soap_draft_length": len(json_dumps(soap_draft)),
        "disclaimer": "AI-generated draft for nurse review. Not a medical record.",
    }

    s3_put_object(
        bucket=evidence_bucket_name(),
        key=f"health/{resident_id}/preconsult/{datetime.now(timezone.utc).strftime('%Y/%m/%d')}/audit_{correlation_id}.json",
        body=audit,
    )

    return api_response(200, {
        "resident_id": resident_id,
        "consultation_type": consultation_type,
        "soap_draft": soap_draft,
        "domain_scores": domain_scores,
        "trends": trends,
        "medications": medications,
        "generated_at": get_current_timestamp(),
        "disclaimer": "AI-generated draft for nurse/physician review only. Not a final medical record.",
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# GET /api/health/profile/{resident_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/health/profile/(?P<resident_id>[^/]+)/?$")
def _get_profile(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Retrieve the current health profile for a resident."""
    resident_id = match.group("resident_id")

    item = dynamo_get_item(
        table_name=HEALTH_TABLE,
        key={"resident_id": resident_id},
    )

    if not item:
        return api_error(404, "not_found", f"Health profile for {resident_id} not found", correlation_id)

    return api_response(200, {**item, "correlation_id": correlation_id})


# ---------------------------------------------------------------------------
# GET /api/health/trends/{resident_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/health/trends/(?P<resident_id>[^/]+)/?$")
def _get_trends(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Retrieve trend data for a resident."""
    resident_id = match.group("resident_id")
    window = _query_param(event, "window", "30d")
    home_id = _query_param(event, "home_id")

    if window not in VALID_WINDOWS:
        window = "30d"

    days = VALID_WINDOWS[window]

    if not home_id:
        # Try to get home_id from resident profile
        profile = _fetch_resident_profile(resident_id)
        home_id = profile.get("home_id", "unknown") if profile else "unknown"

    trends = _detect_trends(home_id, resident_id, days)

    return api_response(200, {
        "resident_id": resident_id,
        "window": window,
        "trends": trends,
        "generated_at": get_current_timestamp(),
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# Domain score calculation
# ---------------------------------------------------------------------------

def _calculate_domain_scores(
    events: List[Dict[str, Any]],
    days: int,
) -> Dict[str, float]:
    """Calculate health scores (0-100) per domain from event data."""
    scores: Dict[str, float] = {}

    # Mobility score
    mobility_events = [
        e for e in events
        if e.get("event_type") in ("fall_detected", "routine_anomaly")
           or "mobility" in str(e.get("data", {})).lower()
    ]
    fall_count = len([e for e in events if e.get("event_type") == "fall_detected"])
    anomaly_count = len([e for e in events if e.get("event_type") == "routine_anomaly"])

    mobility_base = 100
    mobility_base -= fall_count * 20  # Each fall = -20
    mobility_base -= anomaly_count * 5  # Each anomaly = -5
    scores["mobility"] = max(0, min(100, mobility_base))

    # Sleep score (based on acoustic events during night hours)
    night_events = [
        e for e in events
        if _is_night_event(e)
    ]
    sleep_disturbances = len(night_events)
    sleep_base = 100 - (sleep_disturbances * (100 / max(days * 2, 1)))
    scores["sleep"] = max(0, min(100, round(sleep_base, 1)))

    # Nutrition score (based on meal-related events)
    med_taken = len([e for e in events if e.get("event_type") == "medication_taken"])
    med_missed = len([e for e in events if e.get("event_type") == "medication_missed"])
    total_meds = med_taken + med_missed
    nutrition_base = (med_taken / max(total_meds, 1)) * 100 if total_meds > 0 else 75
    scores["nutrition"] = round(nutrition_base, 1)

    # Hydration score (proxy from activity patterns)
    checkins = len([e for e in events if e.get("event_type") == "check_in_completed"])
    expected_checkins = days * 2  # Expect 2 check-ins per day
    hydration_base = min(100, (checkins / max(expected_checkins, 1)) * 100)
    scores["hydration"] = round(hydration_base, 1)

    # Respiratory score (based on vital alerts)
    vital_alerts = len([e for e in events if e.get("event_type") == "vital_alert"])
    resp_base = 100 - (vital_alerts * 15)
    scores["respiratory"] = max(0, min(100, resp_base))

    # Cognitive score (based on check-in quality and routine adherence)
    routine_anomalies = len([
        e for e in events
        if e.get("event_type") == "routine_anomaly"
           and "cognitive" in str(e.get("data", {})).lower()
    ])
    cognitive_base = 100 - (routine_anomalies * 10) - (anomaly_count * 3)
    scores["cognitive"] = max(0, min(100, cognitive_base))

    # Emotional score (based on check-in responses and acoustic events)
    acoustic_events = len([
        e for e in events
        if e.get("event_type", "").startswith("acoustic_")
    ])
    emotional_base = 100 - (acoustic_events * 8)
    scores["emotional"] = max(0, min(100, emotional_base))

    return scores


def _calculate_overall_score(domain_scores: Dict[str, float]) -> float:
    """Weighted average of domain scores."""
    weights = {
        "mobility": 0.20,
        "sleep": 0.15,
        "nutrition": 0.15,
        "hydration": 0.10,
        "respiratory": 0.15,
        "cognitive": 0.15,
        "emotional": 0.10,
    }

    total_weight = 0.0
    weighted_sum = 0.0

    for domain, score in domain_scores.items():
        w = weights.get(domain, 0.1)
        weighted_sum += score * w
        total_weight += w

    return round(weighted_sum / max(total_weight, 0.001), 1)


def _is_night_event(event: Dict[str, Any]) -> bool:
    """Check if an event occurred during nighttime (10 PM - 6 AM)."""
    ts = event.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.hour >= 22 or dt.hour < 6
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# Trend detection
# ---------------------------------------------------------------------------

def _detect_trends(
    home_id: str,
    resident_id: str,
    days: int,
) -> Dict[str, Any]:
    """Detect trends over the time window using simple linear regression."""
    from boto3.dynamodb.conditions import Key

    now = datetime.now(timezone.utc)

    # Split into two halves for comparison
    half_days = max(days // 2, 1)
    mid_point = now - timedelta(days=half_days)

    earlier_start = (now - timedelta(days=days)).isoformat() + "Z"
    mid_str = mid_point.isoformat() + "Z"
    end_str = now.isoformat() + "Z"

    # Fetch timeline entries for both halves
    try:
        earlier_entries, _ = dynamo_query_items(
            table_name=timeline_table_name(),
            key_condition_expression=Key("home_id").eq(home_id) & Key("date").between(
                (now - timedelta(days=days)).strftime("%Y-%m-%d"),
                mid_point.strftime("%Y-%m-%d"),
            ),
            scan_forward=True,
            limit=100,
        )

        recent_entries, _ = dynamo_query_items(
            table_name=timeline_table_name(),
            key_condition_expression=Key("home_id").eq(home_id) & Key("date").between(
                mid_point.strftime("%Y-%m-%d"),
                now.strftime("%Y-%m-%d"),
            ),
            scan_forward=True,
            limit=100,
        )
    except Exception:
        earlier_entries = []
        recent_entries = []

    trends: Dict[str, Any] = {
        "window_days": days,
        "domains": {},
        "declining_domains": [],
        "improving_domains": [],
        "stable_domains": [],
    }

    # Compare key metrics between halves
    earlier_falls = sum(e.get("fall_count", 0) for e in earlier_entries)
    recent_falls = sum(e.get("fall_count", 0) for e in recent_entries)

    earlier_adherence = _avg([e.get("medication_adherence_pct", 100) for e in earlier_entries])
    recent_adherence = _avg([e.get("medication_adherence_pct", 100) for e in recent_entries])

    earlier_activity = _avg([e.get("activity_score", 50) for e in earlier_entries])
    recent_activity = _avg([e.get("activity_score", 50) for e in recent_entries])

    # Compute trend direction for each domain
    domain_changes = {
        "mobility": _trend_direction(earlier_falls, recent_falls, inverse=True),
        "sleep": _trend_direction(earlier_activity, recent_activity),
        "nutrition": _trend_direction(earlier_adherence, recent_adherence),
        "hydration": 0.0,  # Need more data points for this
        "respiratory": 0.0,
        "cognitive": _trend_direction(earlier_activity, recent_activity),
        "emotional": 0.0,
    }

    for domain, change in domain_changes.items():
        trend_status = "stable"
        if change <= CRITICAL_THRESHOLD:
            trend_status = "declining_critical"
        elif change <= DECLINING_THRESHOLD:
            trend_status = "declining"
        elif change >= 0.15:
            trend_status = "improving"

        trends["domains"][domain] = {
            "change_pct": round(change * 100, 1),
            "status": trend_status,
        }

        if "declining" in trend_status:
            trends["declining_domains"].append(domain)
        elif trend_status == "improving":
            trends["improving_domains"].append(domain)
        else:
            trends["stable_domains"].append(domain)

    return trends


def _trend_direction(earlier: float, recent: float, inverse: bool = False) -> float:
    """Calculate percentage change between two periods."""
    if earlier == 0:
        return 0.0
    change = (recent - earlier) / abs(earlier)
    return -change if inverse else change


def _avg(values: List[float]) -> float:
    """Safe average."""
    return sum(values) / len(values) if values else 0.0


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _fetch_events(home_id: str, days: int) -> List[Dict[str, Any]]:
    """Fetch events for a time window."""
    from boto3.dynamodb.conditions import Key

    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).isoformat() + "Z"
    end = now.isoformat() + "Z"

    try:
        items, _ = dynamo_query_items(
            table_name=events_table_name(),
            key_condition_expression=Key("home_id").eq(home_id) & Key("timestamp").between(start, end),
            scan_forward=False,
            limit=500,
        )
        return items
    except Exception:
        return []


def _fetch_resident_profile(resident_id: str) -> Optional[Dict[str, Any]]:
    """Fetch resident profile from DynamoDB."""
    try:
        return dynamo_get_item(
            table_name=residents_table_name(),
            key={"resident_id": resident_id},
        )
    except Exception:
        return None


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


# ---------------------------------------------------------------------------
# AI-powered report generation
# ---------------------------------------------------------------------------

def _generate_health_narrative(
    resident_id: str,
    domain_scores: Dict[str, float],
    trends: Dict[str, Any],
    event_count: int,
    window: str,
    resident_profile: Optional[Dict[str, Any]],
    correlation_id: str,
) -> str:
    """Generate a personalized health narrative using Bedrock."""
    profile_info = ""
    if resident_profile:
        name = resident_profile.get("name", "the resident")
        age = resident_profile.get("age", "unknown")
        conditions = resident_profile.get("medical_conditions", [])
        profile_info = f"Name: {name}, Age: {age}, Known conditions: {', '.join(conditions) if conditions else 'none reported'}"

    declining = trends.get("declining_domains", [])
    improving = trends.get("improving_domains", [])

    prompt = f"""You are a health insights assistant for the AETHER elderly care system.
Generate a clear, compassionate health summary report for a caregiver.

RESIDENT INFO: {profile_info}
REPORTING PERIOD: {window}
TOTAL EVENTS ANALYZED: {event_count}

DOMAIN HEALTH SCORES (0-100):
{json_dumps(domain_scores, indent=2)}

TREND ANALYSIS:
- Declining domains: {', '.join(declining) if declining else 'none'}
- Improving domains: {', '.join(improving) if improving else 'none'}

Write a 3-5 paragraph summary that:
1. Highlights overall health status
2. Calls out any concerning trends or low scores
3. Celebrates improvements
4. Provides 2-3 actionable suggestions for the caregiver
5. Uses simple, non-medical language appropriate for family caregivers

Do NOT provide medical diagnoses. Recommend consulting healthcare providers for concerns."""

    try:
        narrative = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=1024,
            temperature=0.3,
        )
        return narrative.strip()
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Health narrative generation failed: {exc}",
            correlation_id=correlation_id,
        )
        return (
            f"Health report for the past {window}: "
            f"Overall score {_calculate_overall_score(domain_scores)}/100. "
            f"{len(declining)} domain(s) showing decline. "
            "Please consult the detailed scores for more information."
        )


def _generate_soap_draft(
    resident_id: str,
    resident_profile: Optional[Dict[str, Any]],
    domain_scores: Dict[str, float],
    trends: Dict[str, Any],
    events: List[Dict[str, Any]],
    medications: List[Dict[str, Any]],
    chief_complaints: List[str],
    consultation_type: str,
    correlation_id: str,
) -> Dict[str, str]:
    """Generate a SOAP-like draft for nurse review."""
    profile_info = json_dumps(resident_profile or {})
    med_list = [m.get("medication_name", m.get("name", "unknown")) for m in medications]

    # Summarize recent notable events
    notable_events = [
        e for e in events
        if e.get("severity") in ("CRITICAL", "HIGH")
    ][:10]

    event_summary = [
        f"- {e.get('event_type', 'unknown')} ({e.get('severity', '')}) at {e.get('timestamp', '')}"
        for e in notable_events
    ]

    prompt = f"""You are a clinical documentation assistant for the AETHER elderly care system.
Generate a SOAP-note-style draft for nurse/physician review based on sensor data and health metrics.

RESIDENT PROFILE: {profile_info}
CONSULTATION TYPE: {consultation_type}
CHIEF COMPLAINTS: {', '.join(chief_complaints) if chief_complaints else 'routine check-up'}

CURRENT MEDICATIONS: {', '.join(med_list) if med_list else 'not available'}

HEALTH DOMAIN SCORES (past 30 days, 0-100):
{json_dumps(domain_scores, indent=2)}

NOTABLE EVENTS (past 30 days):
{chr(10).join(event_summary) if event_summary else 'No critical events'}

TRENDS:
{json_dumps(trends.get('domains', {}), indent=2)}

Generate a draft with these sections as a JSON object:
- "subjective": Patient-reported/sensor-inferred complaints and observations
- "objective": Data-driven findings from sensors (vitals, activity, sleep patterns)
- "assessment": Clinical assessment based on data patterns (keep tentative, flag for review)
- "plan": Suggested plan items for physician review

Include a disclaimer that this is AI-generated and requires clinician review.
Return ONLY the JSON object."""

    try:
        response_text = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=2048,
            temperature=0.2,
        )

        # Parse JSON response
        try:
            soap = json.loads(response_text)
        except json.JSONDecodeError:
            start = response_text.find("{")
            end = response_text.rfind("}")
            if start != -1 and end != -1:
                soap = json.loads(response_text[start:end + 1])
            else:
                raise ValueError("Could not parse SOAP response")

        soap["_disclaimer"] = (
            "AI-GENERATED DRAFT – This document was produced by the AETHER health insights "
            "system using sensor data and requires review by a licensed healthcare professional "
            "before being incorporated into the medical record."
        )
        soap["_model_used"] = BEDROCK_MODEL
        soap["_generated_at"] = get_current_timestamp()

        return soap

    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"SOAP draft generation failed: {exc}",
            correlation_id=correlation_id,
        )
        return {
            "subjective": "Unable to generate – see raw data",
            "objective": json_dumps(domain_scores),
            "assessment": "Automated assessment unavailable – manual review needed",
            "plan": "Review sensor data and domain scores manually",
            "_disclaimer": "AI generation failed – placeholder content only",
            "_model_used": BEDROCK_MODEL,
            "_generated_at": get_current_timestamp(),
        }
