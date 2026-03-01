"""
AETHER Analytics Processor Lambda
===================================
Generates analytics, metrics, and AI-powered insights from event data.

Triggers
--------
- API Gateway: GET /api/analytics?type=dashboard|clinic|resident&period=24h|7d|30d
- EventBridge: Hourly background metric computation (detail-type: "ScheduledAnalytics")
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
import uuid
from collections import Counter, defaultdict
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
    residents_table_name,
    s3_put_object,
    setup_logger,
    timeline_table_name,
    bedrock_model_id,
    alerts_topic_arn,
    sns_publish_structured_alert,
    get_dynamodb_table,
)

logger = setup_logger("analytics_processor")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VALID_ANALYTICS_TYPES = {"dashboard", "clinic", "resident"}
VALID_PERIODS = {"24h", "7d", "30d"}

PERIOD_TO_DAYS: Dict[str, int] = {
    "24h": 1,
    "7d": 7,
    "30d": 30,
}

BEDROCK_MODEL = get_env("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point.

    Dispatches between API Gateway proxy integration and EventBridge
    scheduled invocations.
    """
    # Detect EventBridge scheduled invocation
    source = event.get("source")
    detail_type = event.get("detail-type")

    if source == "aws.events" or detail_type == "ScheduledAnalytics":
        return _handle_scheduled(event, context)

    # Otherwise, treat as API Gateway proxy integration
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


def _query_param(event: Dict[str, Any], name: str, default: Optional[str] = None) -> Optional[str]:
    """Extract a query-string parameter."""
    params = event.get("queryStringParameters") or {}
    return params.get(name, default)


# ---------------------------------------------------------------------------
# GET /api/analytics
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/analytics/?$")
def _get_analytics(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Return analytics data with metrics, charts data, and AI insights."""
    analytics_type = _query_param(event, "type", "dashboard")
    period = _query_param(event, "period", "7d")
    home_id = _query_param(event, "home_id")
    resident_id = _query_param(event, "resident_id")

    if analytics_type not in VALID_ANALYTICS_TYPES:
        return api_error(
            400, "invalid_parameter",
            f"type must be one of: {', '.join(sorted(VALID_ANALYTICS_TYPES))}",
            correlation_id,
        )
    if period not in VALID_PERIODS:
        return api_error(
            400, "invalid_parameter",
            f"period must be one of: {', '.join(sorted(VALID_PERIODS))}",
            correlation_id,
        )

    log_with_context(
        logger, "INFO",
        f"Analytics request: type={analytics_type} period={period} "
        f"home_id={home_id} resident_id={resident_id}",
        correlation_id=correlation_id,
    )

    days = PERIOD_TO_DAYS[period]
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days)).isoformat() + "Z"
    end_date = now.isoformat() + "Z"

    # Fetch events
    events = _fetch_events_for_period(home_id, start_date, end_date)

    # Compute all metrics
    metrics = _compute_metrics(events, days)

    # Compute chart data
    charts = _compute_chart_data(events, days)

    # Type-specific enrichment
    if analytics_type == "resident" and resident_id:
        resident_events = [
            e for e in events
            if e.get("resident_id") == resident_id
            or e.get("metadata", {}).get("resident_id") == resident_id
        ]
        metrics["resident_metrics"] = _compute_resident_metrics(resident_events, resident_id, days)

    elif analytics_type == "clinic":
        metrics["clinic_metrics"] = _compute_clinic_metrics(events, days)

    # Generate AI insights via Bedrock
    ai_insights = _generate_ai_insights(analytics_type, period, metrics, events)

    result = {
        "analytics_type": analytics_type,
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "generated_at": get_current_timestamp(),
        "total_events_analyzed": len(events),
        "metrics": metrics,
        "charts": charts,
        "ai_insights": ai_insights,
        "correlation_id": correlation_id,
    }

    if home_id:
        result["home_id"] = home_id
    if resident_id:
        result["resident_id"] = resident_id

    return api_response(200, result)


# ---------------------------------------------------------------------------
# EventBridge scheduled handler
# ---------------------------------------------------------------------------


def _handle_scheduled(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle hourly EventBridge invocation for background metric computation."""
    correlation_id = generate_correlation_id()

    log_with_context(
        logger, "INFO",
        "Scheduled analytics computation started",
        correlation_id=correlation_id,
    )

    now = datetime.now(timezone.utc)
    periods = {
        "24h": 1,
        "7d": 7,
        "30d": 30,
    }

    results: Dict[str, Any] = {}

    for period_label, days in periods.items():
        start_date = (now - timedelta(days=days)).isoformat() + "Z"
        end_date = now.isoformat() + "Z"

        events = _fetch_events_for_period(None, start_date, end_date)
        metrics = _compute_metrics(events, days)

        results[period_label] = {
            "total_events": len(events),
            "metrics": metrics,
            "computed_at": get_current_timestamp(),
        }

    # Store aggregated results in S3 for caching
    bucket = evidence_bucket_name()
    s3_key = f"analytics/scheduled/{now.strftime('%Y/%m/%d')}/metrics_{now.strftime('%H%M')}.json"

    s3_put_object(
        bucket=bucket,
        key=s3_key,
        body={
            "computed_at": get_current_timestamp(),
            "correlation_id": correlation_id,
            "periods": results,
        },
        content_type="application/json",
    )

    log_with_context(
        logger, "INFO",
        f"Scheduled analytics stored at s3://{bucket}/{s3_key}",
        correlation_id=correlation_id,
    )

    # Check for SLA violations and alert if needed
    _check_sla_violations(results, correlation_id)

    return {
        "status": "completed",
        "correlation_id": correlation_id,
        "periods_computed": list(results.keys()),
        "s3_key": s3_key,
    }


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def _fetch_events_for_period(
    home_id: Optional[str],
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """Fetch events from DynamoDB for the given time range.

    If home_id is None, scans the timeline table across all homes.
    """
    from boto3.dynamodb.conditions import Key, Attr

    if home_id:
        key_condition = Key("home_id").eq(home_id) & Key("timestamp").between(start_date, end_date)
        filter_expr = Attr("timestamp").not_contains("ESC#") & Attr("timestamp").not_contains("DOC#")

        items, _ = dynamo_query_items(
            table_name=events_table_name(),
            key_condition_expression=key_condition,
            filter_expression=filter_expr,
            scan_forward=True,
            max_pages=50,
        )
        return items

    # No home_id: fetch timeline entries and aggregate
    # For scheduled runs, query the timeline table which has daily aggregates
    table = get_dynamodb_table(timeline_table_name())

    # Scan timeline for all homes in the date range
    start_day = start_date[:10]  # YYYY-MM-DD
    end_day = end_date[:10]

    filter_expr = Attr("date").between(start_day, end_day)
    response = table.scan(FilterExpression=filter_expr, Limit=1000)
    timeline_entries = response.get("Items", [])

    # Also fetch raw events from a few known homes for detailed analysis
    # We pull home_ids from the timeline entries
    home_ids = list({e.get("home_id") for e in timeline_entries if e.get("home_id")})

    all_events: List[Dict[str, Any]] = []
    for hid in home_ids[:20]:  # Cap to avoid excessive queries
        key_condition = Key("home_id").eq(hid) & Key("timestamp").between(start_date, end_date)
        esc_filter = Attr("timestamp").not_contains("ESC#") & Attr("timestamp").not_contains("DOC#")
        items, _ = dynamo_query_items(
            table_name=events_table_name(),
            key_condition_expression=key_condition,
            filter_expression=esc_filter,
            scan_forward=True,
            max_pages=10,
        )
        all_events.extend(items)

    return all_events


# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------


def _compute_metrics(events: List[Dict[str, Any]], period_days: int) -> Dict[str, Any]:
    """Compute comprehensive analytics metrics from event data."""
    if not events:
        return _empty_metrics()

    # Event counts by type
    type_counts: Counter = Counter()
    severity_counts: Counter = Counter()
    home_counts: Counter = Counter()

    # Medication tracking
    med_taken = 0
    med_missed = 0
    med_late = 0

    # Fall detection
    falls_detected = 0
    falls_confirmed = 0
    falls_false_alarm = 0

    # Escalation response times
    response_times: List[float] = []

    # Sensor health
    sensor_last_seen: Dict[str, str] = {}
    sensor_battery: Dict[str, float] = {}

    for evt in events:
        event_type = evt.get("event_type", "unknown")
        severity = evt.get("severity", "INFO")
        home_id = evt.get("home_id", "unknown")
        metadata = evt.get("metadata", {})

        type_counts[event_type] += 1
        severity_counts[severity] += 1
        home_counts[home_id] += 1

        # Medication
        if event_type == "medication_taken":
            med_taken += 1
        elif event_type == "medication_missed":
            med_missed += 1
        elif event_type == "medication_late":
            med_late += 1

        # Falls
        if event_type == "fall_detected":
            falls_detected += 1
            confirmed = metadata.get("confirmed")
            if confirmed is True:
                falls_confirmed += 1
            elif confirmed is False:
                falls_false_alarm += 1

        # Response times
        if metadata.get("response_time_seconds"):
            try:
                response_times.append(float(metadata["response_time_seconds"]))
            except (ValueError, TypeError):
                pass

        # Sensor health
        sensor_id = metadata.get("sensor_id")
        if sensor_id:
            sensor_last_seen[sensor_id] = evt.get("timestamp", "")
            if metadata.get("battery_pct") is not None:
                try:
                    sensor_battery[sensor_id] = float(metadata["battery_pct"])
                except (ValueError, TypeError):
                    pass

    # Medication adherence
    total_med_events = med_taken + med_missed + med_late
    med_adherence_pct = (med_taken / total_med_events * 100) if total_med_events > 0 else 100.0

    # Fall detection accuracy
    fall_accuracy_pct = 0.0
    if falls_detected > 0:
        fall_accuracy_pct = (falls_confirmed / falls_detected * 100) if falls_confirmed > 0 else 0.0

    # Response time stats
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
    max_response_time = max(response_times) if response_times else 0.0
    min_response_time = min(response_times) if response_times else 0.0

    # Sensor health summary
    sensors_total = len(sensor_last_seen)
    low_battery_sensors = [
        sid for sid, pct in sensor_battery.items() if pct < 20.0
    ]

    # SLA compliance (target: 95% of escalations responded within 5 minutes)
    sla_target_seconds = 300  # 5 minutes
    within_sla = sum(1 for rt in response_times if rt <= sla_target_seconds)
    sla_compliance_pct = (within_sla / len(response_times) * 100) if response_times else 100.0

    # Events per day
    events_per_day = len(events) / period_days if period_days > 0 else len(events)

    return {
        "event_counts": {
            "total": len(events),
            "by_type": dict(type_counts.most_common()),
            "by_severity": dict(severity_counts.most_common()),
            "by_home": dict(home_counts.most_common()),
            "per_day_avg": round(events_per_day, 1),
        },
        "medication_adherence": {
            "taken": med_taken,
            "missed": med_missed,
            "late": med_late,
            "total_events": total_med_events,
            "adherence_pct": round(med_adherence_pct, 1),
        },
        "fall_detection": {
            "total_detected": falls_detected,
            "confirmed": falls_confirmed,
            "false_alarms": falls_false_alarm,
            "unconfirmed": falls_detected - falls_confirmed - falls_false_alarm,
            "accuracy_pct": round(fall_accuracy_pct, 1),
        },
        "escalation_response": {
            "avg_response_seconds": round(avg_response_time, 1),
            "max_response_seconds": round(max_response_time, 1),
            "min_response_seconds": round(min_response_time, 1),
            "total_escalations": len(response_times),
        },
        "sensor_health": {
            "total_sensors": sensors_total,
            "low_battery_count": len(low_battery_sensors),
            "low_battery_sensors": low_battery_sensors,
        },
        "sla_compliance": {
            "target_seconds": sla_target_seconds,
            "within_sla": within_sla,
            "total_measured": len(response_times),
            "compliance_pct": round(sla_compliance_pct, 1),
        },
    }


def _empty_metrics() -> Dict[str, Any]:
    """Return a zeroed-out metrics structure."""
    return {
        "event_counts": {
            "total": 0, "by_type": {}, "by_severity": {}, "by_home": {},
            "per_day_avg": 0.0,
        },
        "medication_adherence": {
            "taken": 0, "missed": 0, "late": 0, "total_events": 0,
            "adherence_pct": 100.0,
        },
        "fall_detection": {
            "total_detected": 0, "confirmed": 0, "false_alarms": 0,
            "unconfirmed": 0, "accuracy_pct": 0.0,
        },
        "escalation_response": {
            "avg_response_seconds": 0.0, "max_response_seconds": 0.0,
            "min_response_seconds": 0.0, "total_escalations": 0,
        },
        "sensor_health": {
            "total_sensors": 0, "low_battery_count": 0, "low_battery_sensors": [],
        },
        "sla_compliance": {
            "target_seconds": 300, "within_sla": 0, "total_measured": 0,
            "compliance_pct": 100.0,
        },
    }


def _compute_resident_metrics(
    events: List[Dict[str, Any]],
    resident_id: str,
    period_days: int,
) -> Dict[str, Any]:
    """Compute resident-specific metrics."""
    base = _compute_metrics(events, period_days)

    # Add resident-specific context
    activity_scores: List[float] = []
    routine_deviations = 0

    for evt in events:
        metadata = evt.get("metadata", {})
        if metadata.get("activity_score") is not None:
            try:
                activity_scores.append(float(metadata["activity_score"]))
            except (ValueError, TypeError):
                pass
        if evt.get("event_type") == "routine_anomaly":
            routine_deviations += 1

    avg_activity = sum(activity_scores) / len(activity_scores) if activity_scores else 0.0

    base["resident_id"] = resident_id
    base["activity"] = {
        "avg_activity_score": round(avg_activity, 1),
        "routine_deviations": routine_deviations,
        "data_points": len(activity_scores),
    }

    return base


def _compute_clinic_metrics(
    events: List[Dict[str, Any]],
    period_days: int,
) -> Dict[str, Any]:
    """Compute clinic-wide aggregate metrics."""
    # Group by home
    homes: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for evt in events:
        homes[evt.get("home_id", "unknown")].append(evt)

    home_metrics: List[Dict[str, Any]] = []
    for hid, home_events in homes.items():
        hm = _compute_metrics(home_events, period_days)
        hm["home_id"] = hid
        home_metrics.append(hm)

    # Aggregate across homes
    total_homes = len(homes)
    adherence_rates = [
        hm["medication_adherence"]["adherence_pct"] for hm in home_metrics
    ]
    avg_adherence = sum(adherence_rates) / len(adherence_rates) if adherence_rates else 100.0

    sla_rates = [
        hm["sla_compliance"]["compliance_pct"] for hm in home_metrics
    ]
    avg_sla = sum(sla_rates) / len(sla_rates) if sla_rates else 100.0

    return {
        "total_homes_monitored": total_homes,
        "avg_medication_adherence_pct": round(avg_adherence, 1),
        "avg_sla_compliance_pct": round(avg_sla, 1),
        "homes": home_metrics,
    }


# ---------------------------------------------------------------------------
# Chart data computation
# ---------------------------------------------------------------------------


def _compute_chart_data(
    events: List[Dict[str, Any]],
    period_days: int,
) -> Dict[str, Any]:
    """Compute structured data for dashboard charts."""
    now = datetime.now(timezone.utc)

    # Events per day for time-series chart
    events_by_day: Dict[str, int] = defaultdict(int)
    severity_by_day: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    type_by_day: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for evt in events:
        ts = evt.get("timestamp", "")
        day = ts[:10] if len(ts) >= 10 else "unknown"
        events_by_day[day] += 1
        severity_by_day[day][evt.get("severity", "INFO")] += 1
        type_by_day[day][evt.get("event_type", "unknown")] += 1

    # Fill gaps in days
    daily_series: List[Dict[str, Any]] = []
    for i in range(period_days):
        day = (now - timedelta(days=period_days - 1 - i)).strftime("%Y-%m-%d")
        daily_series.append({
            "date": day,
            "total_events": events_by_day.get(day, 0),
            "severity_breakdown": dict(severity_by_day.get(day, {})),
            "type_breakdown": dict(type_by_day.get(day, {})),
        })

    # Severity distribution (pie/donut chart data)
    severity_dist: Counter = Counter()
    for evt in events:
        severity_dist[evt.get("severity", "INFO")] += 1

    # Event type distribution
    type_dist: Counter = Counter()
    for evt in events:
        type_dist[evt.get("event_type", "unknown")] += 1

    # Hourly distribution (heatmap data)
    hourly_dist: Dict[int, int] = defaultdict(int)
    for evt in events:
        ts = evt.get("timestamp", "")
        try:
            hour = int(ts[11:13]) if len(ts) >= 13 else 0
            hourly_dist[hour] += 1
        except (ValueError, IndexError):
            pass

    # Trend: compare current half vs previous half
    mid_point = now - timedelta(days=period_days / 2)
    mid_str = mid_point.isoformat() + "Z"
    first_half = [e for e in events if e.get("timestamp", "") < mid_str]
    second_half = [e for e in events if e.get("timestamp", "") >= mid_str]

    first_half_count = len(first_half)
    second_half_count = len(second_half)
    trend_pct = 0.0
    if first_half_count > 0:
        trend_pct = ((second_half_count - first_half_count) / first_half_count) * 100

    return {
        "daily_events": daily_series,
        "severity_distribution": dict(severity_dist.most_common()),
        "event_type_distribution": dict(type_dist.most_common()),
        "hourly_distribution": {str(h): c for h, c in sorted(hourly_dist.items())},
        "trend": {
            "first_half_events": first_half_count,
            "second_half_events": second_half_count,
            "change_pct": round(trend_pct, 1),
            "direction": "increasing" if trend_pct > 5 else ("decreasing" if trend_pct < -5 else "stable"),
        },
    }


# ---------------------------------------------------------------------------
# AI Insights via Bedrock
# ---------------------------------------------------------------------------


def _generate_ai_insights(
    analytics_type: str,
    period: str,
    metrics: Dict[str, Any],
    events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Use Bedrock to generate AI-powered insights and recommendations."""
    try:
        metrics_summary = json_dumps(metrics, indent=2)
        # Truncate to avoid exceeding model input limits
        if len(metrics_summary) > 6000:
            metrics_summary = metrics_summary[:6000] + "\n... (truncated)"

        prompt = (
            "You are an analytics AI for the AETHER elderly care monitoring system. "
            "Analyze the following metrics and provide actionable insights.\n\n"
            f"Analytics Type: {analytics_type}\n"
            f"Period: {period}\n"
            f"Total Events: {len(events)}\n\n"
            f"Metrics:\n{metrics_summary}\n\n"
            "Provide your analysis in the following JSON structure:\n"
            "{\n"
            '  "summary": "2-3 sentence executive summary",\n'
            '  "key_findings": ["finding 1", "finding 2", ...],\n'
            '  "risk_alerts": ["risk 1", ...],\n'
            '  "recommendations": ["action 1", "action 2", ...],\n'
            '  "trends": "description of notable trends",\n'
            '  "confidence": "high|medium|low"\n'
            "}\n\n"
            "Focus on clinically relevant insights for elderly care. "
            "Highlight any concerning patterns in falls, medication adherence, "
            "or response times."
        )

        raw_response = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=1024,
            temperature=0.3,
        )

        # Try to parse as JSON; fall back to raw text
        try:
            # Find JSON in the response
            json_start = raw_response.find("{")
            json_end = raw_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                insights = json.loads(raw_response[json_start:json_end])
                insights["generated_by"] = "bedrock"
                insights["model"] = BEDROCK_MODEL
                return insights
        except (json.JSONDecodeError, ValueError):
            pass

        # Fallback: return raw text
        return {
            "summary": raw_response,
            "key_findings": [],
            "risk_alerts": [],
            "recommendations": [],
            "trends": "",
            "confidence": "low",
            "generated_by": "bedrock",
            "model": BEDROCK_MODEL,
            "raw": True,
        }

    except Exception as exc:
        log_with_context(
            logger, "WARNING",
            f"Bedrock insights generation failed: {exc}",
        )
        return {
            "summary": "AI insights unavailable.",
            "key_findings": [],
            "risk_alerts": [],
            "recommendations": [],
            "trends": "",
            "confidence": "none",
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# SLA violation alerting
# ---------------------------------------------------------------------------


def _check_sla_violations(
    results: Dict[str, Dict[str, Any]],
    correlation_id: str,
) -> None:
    """Check computed metrics for SLA violations and publish alerts."""
    topic_arn = alerts_topic_arn()
    if not topic_arn:
        return

    # Check 24h metrics for immediate SLA issues
    metrics_24h = results.get("24h", {}).get("metrics", {})
    sla = metrics_24h.get("sla_compliance", {})
    compliance_pct = sla.get("compliance_pct", 100.0)

    if compliance_pct < 95.0:
        log_with_context(
            logger, "WARNING",
            f"SLA compliance below threshold: {compliance_pct}%",
            correlation_id=correlation_id,
        )
        try:
            sns_publish_structured_alert(
                topic_arn=topic_arn,
                event_type="sla_violation",
                severity="HIGH",
                home_id="system",
                message=(
                    f"AETHER SLA compliance alert: Response time SLA at "
                    f"{compliance_pct}% (target: 95%). "
                    f"Total escalations measured: {sla.get('total_measured', 0)}"
                ),
            )
        except Exception as exc:
            log_with_context(
                logger, "ERROR",
                f"Failed to publish SLA alert: {exc}",
                correlation_id=correlation_id,
            )

    # Check medication adherence
    med = metrics_24h.get("medication_adherence", {})
    adherence_pct = med.get("adherence_pct", 100.0)

    if adherence_pct < 80.0:
        log_with_context(
            logger, "WARNING",
            f"Medication adherence below threshold: {adherence_pct}%",
            correlation_id=correlation_id,
        )
        try:
            sns_publish_structured_alert(
                topic_arn=topic_arn,
                event_type="medication_adherence_low",
                severity="MEDIUM",
                home_id="system",
                message=(
                    f"AETHER medication adherence alert: System-wide adherence "
                    f"at {adherence_pct}% over last 24h. "
                    f"Missed: {med.get('missed', 0)}, Late: {med.get('late', 0)}"
                ),
            )
        except Exception as exc:
            log_with_context(
                logger, "ERROR",
                f"Failed to publish adherence alert: {exc}",
                correlation_id=correlation_id,
            )
