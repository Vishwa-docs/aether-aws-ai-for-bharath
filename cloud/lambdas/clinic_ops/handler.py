"""
AETHER Clinic / B2B Operations Lambda
=======================================
Provides operational data for multi-site fleet management, edge gateway
health monitoring, SLA tracking, caregiver burnout metrics, staff
scheduling, and sensor drift detection.

Endpoints
---------
GET  /api/clinic/dashboard          – Multi-site operational dashboard
GET  /api/clinic/sites              – List all sites with health status
GET  /api/clinic/sites/{site_id}    – Site detail with gateway and sensor status
GET  /api/clinic/sla                – SLA response time metrics
GET  /api/clinic/burnout            – Caregiver burnout metrics
GET  /api/clinic/heatmap            – Site-level health heatmap data
POST /api/clinic/report             – Generate operational report
POST /api/clinic/sensors/calibrate  – Trigger sensor calibration check
"""

from __future__ import annotations

import json
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
    SiteHealth,
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
    s3_put_object,
    setup_logger,
    clinic_ops_table_name,
    get_dynamodb_table,
)

logger = setup_logger("clinic_ops")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CLINIC_TABLE = clinic_ops_table_name()
SITES_TABLE = get_env("SITES_TABLE", "aether-sites")
STAFF_TABLE = get_env("STAFF_TABLE", "aether-staff")
BEDROCK_MODEL = get_env("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

# SLA targets (seconds)
SLA_CRITICAL_TARGET = int(get_env("SLA_CRITICAL_TARGET_SECONDS", "30"))
SLA_HIGH_TARGET = int(get_env("SLA_HIGH_TARGET_SECONDS", "120"))
SLA_MEDIUM_TARGET = int(get_env("SLA_MEDIUM_TARGET_SECONDS", "600"))

# Burnout thresholds
BURNOUT_ALERTS_PER_SHIFT = int(get_env("BURNOUT_ALERTS_THRESHOLD", "15"))
BURNOUT_SHIFT_HOURS = float(get_env("BURNOUT_MAX_SHIFT_HOURS", "12"))


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

    # Multi-tenant isolation: extract tenant_id from authorizer context
    tenant_id = _extract_tenant_id(event)

    log_with_context(
        logger, "INFO",
        f"{http_method} {path}",
        correlation_id=correlation_id,
        tenant_id=tenant_id,
    )

    try:
        response = _route_request(http_method, path, event, correlation_id, tenant_id)
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
# Router (with tenant context)
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
    tenant_id: str = "",
) -> Dict[str, Any]:
    for route_method, pattern, handler_fn in _ROUTES:
        if method != route_method:
            continue
        match = re.match(pattern, path)
        if match:
            # Inject tenant_id into event for handlers
            event["_tenant_id"] = tenant_id
            return handler_fn(event, match, correlation_id)
    return api_error(404, "not_found", f"No route matches {method} {path}", correlation_id)


def _extract_tenant_id(event: Dict[str, Any]) -> str:
    """Extract tenant_id from API Gateway authorizer context or headers."""
    authorizer = (event.get("requestContext") or {}).get("authorizer") or {}
    tenant_id = authorizer.get("tenant_id", "")
    if not tenant_id:
        headers = event.get("headers") or {}
        tenant_id = headers.get("X-Tenant-Id", headers.get("x-tenant-id", "default"))
    return tenant_id


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
# GET /api/clinic/dashboard
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/clinic/dashboard/?$")
def _get_dashboard(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Multi-site operational dashboard data."""
    tenant_id = event.get("_tenant_id", "default")

    sites = _fetch_sites(tenant_id)
    now = datetime.now(timezone.utc)

    # Aggregate across all sites
    total_residents = 0
    total_gateways = 0
    online_gateways = 0
    total_sensors = 0
    active_sensors = 0
    total_alerts_24h = 0
    sites_summary: List[Dict[str, Any]] = []

    for site in sites:
        site_id = site.get("site_id", "")
        health = _get_site_health(site_id)

        gateway_status = health.get("gateway_status", {})
        sensor_counts = health.get("sensor_counts", {})

        site_gateways = gateway_status.get("total", 0)
        site_online = gateway_status.get("online", 0)
        site_sensors = sensor_counts.get("total", 0)
        site_active = sensor_counts.get("active", 0)
        site_residents = site.get("resident_count", 0)

        total_residents += site_residents
        total_gateways += site_gateways
        online_gateways += site_online
        total_sensors += site_sensors
        active_sensors += site_active

        sites_summary.append({
            "site_id": site_id,
            "name": site.get("name", ""),
            "status": "healthy" if site_online == site_gateways and site_gateways > 0 else "degraded",
            "residents": site_residents,
            "gateways_online": f"{site_online}/{site_gateways}",
            "sensors_active": f"{site_active}/{site_sensors}",
        })

    dashboard = {
        "tenant_id": tenant_id,
        "generated_at": get_current_timestamp(),
        "fleet_overview": {
            "total_sites": len(sites),
            "total_residents": total_residents,
            "total_gateways": total_gateways,
            "gateways_online": online_gateways,
            "gateway_uptime_pct": round(online_gateways / max(total_gateways, 1) * 100, 1),
            "total_sensors": total_sensors,
            "sensors_active": active_sensors,
            "sensor_health_pct": round(active_sensors / max(total_sensors, 1) * 100, 1),
        },
        "sites": sites_summary,
        "correlation_id": correlation_id,
    }

    return api_response(200, dashboard)


# ---------------------------------------------------------------------------
# GET /api/clinic/sites
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/clinic/sites/?$")
def _get_sites(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """List all sites with health status."""
    tenant_id = event.get("_tenant_id", "default")
    sites = _fetch_sites(tenant_id)

    enriched_sites = []
    for site in sites:
        site_id = site.get("site_id", "")
        health = _get_site_health(site_id)
        site_data = {**site, "health": health}
        enriched_sites.append(site_data)

    return api_response(200, {
        "tenant_id": tenant_id,
        "sites": enriched_sites,
        "count": len(enriched_sites),
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# GET /api/clinic/sites/{site_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/clinic/sites/(?P<site_id>[^/]+)/?$")
def _get_site_detail(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Detailed site information with gateway and sensor status."""
    site_id = match.group("site_id")
    tenant_id = event.get("_tenant_id", "default")

    site = dynamo_get_item(
        table_name=SITES_TABLE,
        key={"site_id": site_id},
    )

    if not site:
        return api_error(404, "not_found", f"Site {site_id} not found", correlation_id)

    # Enforce tenant isolation
    if site.get("tenant_id") and site["tenant_id"] != tenant_id:
        return api_error(403, "forbidden", "Access denied to this site", correlation_id)

    health = _get_site_health(site_id)
    gateways = _get_gateway_details(site_id)
    sensor_drift = _check_sensor_drift(site_id)
    sla = _get_site_sla(site_id)

    return api_response(200, {
        "site": site,
        "health": health,
        "gateways": gateways,
        "sensor_drift_alerts": sensor_drift,
        "sla_metrics": sla,
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# GET /api/clinic/sla
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/clinic/sla/?$")
def _get_sla(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """SLA response time tracking across sites."""
    tenant_id = event.get("_tenant_id", "default")
    period = _query_param(event, "period", "7d")

    days = {"24h": 1, "7d": 7, "30d": 30}.get(period, 7)
    sites = _fetch_sites(tenant_id)

    sla_data: List[Dict[str, Any]] = []
    overall_met = 0
    overall_total = 0

    for site in sites:
        site_id = site.get("site_id", "")
        site_sla = _get_site_sla(site_id, days)
        sla_data.append({
            "site_id": site_id,
            "site_name": site.get("name", ""),
            **site_sla,
        })
        overall_met += site_sla.get("met_count", 0)
        overall_total += site_sla.get("total_count", 0)

    return api_response(200, {
        "tenant_id": tenant_id,
        "period": period,
        "overall_sla_pct": round(overall_met / max(overall_total, 1) * 100, 1),
        "sla_targets": {
            "critical_seconds": SLA_CRITICAL_TARGET,
            "high_seconds": SLA_HIGH_TARGET,
            "medium_seconds": SLA_MEDIUM_TARGET,
        },
        "sites": sla_data,
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# GET /api/clinic/burnout
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/clinic/burnout/?$")
def _get_burnout(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Caregiver burnout metrics across sites."""
    tenant_id = event.get("_tenant_id", "default")
    period = _query_param(event, "period", "7d")
    days = {"24h": 1, "7d": 7, "30d": 30}.get(period, 7)

    staff = _fetch_staff(tenant_id)

    burnout_metrics: List[Dict[str, Any]] = []
    at_risk_count = 0

    for member in staff:
        caregiver_id = member.get("staff_id", "")
        name = member.get("name", "Unknown")
        site_id = member.get("site_id", "")

        metrics = _calculate_caregiver_burnout(caregiver_id, site_id, days)

        risk_level = "low"
        if metrics["alerts_per_shift"] > BURNOUT_ALERTS_PER_SHIFT:
            risk_level = "high"
            at_risk_count += 1
        elif metrics["alerts_per_shift"] > BURNOUT_ALERTS_PER_SHIFT * 0.7:
            risk_level = "moderate"
        if metrics["avg_shift_hours"] > BURNOUT_SHIFT_HOURS:
            risk_level = "high"
            at_risk_count += 1
        if metrics["overtime_hours"] > 10:
            risk_level = max(risk_level, "moderate")

        burnout_metrics.append({
            "caregiver_id": caregiver_id,
            "name": name,
            "site_id": site_id,
            "risk_level": risk_level,
            **metrics,
        })

    # Sort by risk (high first)
    risk_order = {"high": 0, "moderate": 1, "low": 2}
    burnout_metrics.sort(key=lambda x: risk_order.get(x.get("risk_level", "low"), 3))

    return api_response(200, {
        "tenant_id": tenant_id,
        "period": period,
        "total_caregivers": len(burnout_metrics),
        "at_risk_count": at_risk_count,
        "thresholds": {
            "max_alerts_per_shift": BURNOUT_ALERTS_PER_SHIFT,
            "max_shift_hours": BURNOUT_SHIFT_HOURS,
        },
        "caregivers": burnout_metrics,
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# GET /api/clinic/heatmap
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/clinic/heatmap/?$")
def _get_heatmap(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Site-level health heatmap data."""
    tenant_id = event.get("_tenant_id", "default")
    sites = _fetch_sites(tenant_id)

    heatmap_data: List[Dict[str, Any]] = []

    for site in sites:
        site_id = site.get("site_id", "")
        health = _get_site_health(site_id)

        heatmap_data.append({
            "site_id": site_id,
            "name": site.get("name", ""),
            "latitude": site.get("latitude", 0),
            "longitude": site.get("longitude", 0),
            "health_score": health.get("overall_health_score", 0),
            "gateway_uptime": health.get("gateway_status", {}).get("uptime_pct", 0),
            "alert_density": health.get("alert_density", 0),
            "resident_count": site.get("resident_count", 0),
        })

    return api_response(200, {
        "tenant_id": tenant_id,
        "heatmap": heatmap_data,
        "generated_at": get_current_timestamp(),
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# POST /api/clinic/report
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/clinic/report/?$")
def _post_report(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Generate an operational report using Bedrock."""
    body = _parse_body(event)
    tenant_id = event.get("_tenant_id", "default")
    report_type = body.get("report_type", "weekly")
    site_id = body.get("site_id")  # Optional: specific site

    sites = _fetch_sites(tenant_id)
    if site_id:
        sites = [s for s in sites if s.get("site_id") == site_id]

    # Gather operational data
    ops_data: Dict[str, Any] = {
        "total_sites": len(sites),
        "site_summaries": [],
    }

    for site in sites:
        sid = site.get("site_id", "")
        health = _get_site_health(sid)
        sla = _get_site_sla(sid)
        ops_data["site_summaries"].append({
            "site_id": sid,
            "name": site.get("name", ""),
            "health": health,
            "sla": sla,
        })

    # Generate narrative report
    prompt = f"""You are an operations analyst for AETHER, an elderly care monitoring platform.
Generate a {report_type} operational report based on the following data.

OPERATIONAL DATA:
{json_dumps(ops_data, indent=2)}

Include sections:
1. Executive Summary
2. Fleet Health Overview (gateway uptime, sensor status)
3. SLA Performance
4. Key Issues & Recommendations
5. Action Items

Keep it concise and actionable. Format as plain text with section headers."""

    try:
        report_text = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=2048,
            temperature=0.3,
        )
    except Exception as exc:
        log_with_context(
            logger, "WARNING",
            f"Report generation failed: {exc}",
            correlation_id=correlation_id,
        )
        report_text = "Report generation failed. Please review raw operational data."

    report_id = f"ops-{uuid.uuid4().hex[:12]}"

    # Store report
    report_record = {
        "report_id": report_id,
        "tenant_id": tenant_id,
        "report_type": report_type,
        "generated_at": get_current_timestamp(),
        "report_text": report_text,
        "operational_data": ops_data,
        "correlation_id": correlation_id,
    }

    dynamo_put_item(CLINIC_TABLE, report_record)

    # Also store in S3
    s3_put_object(
        bucket=evidence_bucket_name(),
        key=f"clinic/reports/{tenant_id}/{report_id}.json",
        body=report_record,
    )

    return api_response(200, {
        "report_id": report_id,
        "report_type": report_type,
        "report": report_text,
        "generated_at": report_record["generated_at"],
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# POST /api/clinic/sensors/calibrate
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/clinic/sensors/calibrate/?$")
def _post_calibrate(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Trigger sensor drift detection and calibration check."""
    body = _parse_body(event)
    site_id = body.get("site_id")

    if not site_id:
        return api_error(400, "missing_parameter", "site_id is required", correlation_id)

    drift_alerts = _check_sensor_drift(site_id)

    return api_response(200, {
        "site_id": site_id,
        "drift_alerts": drift_alerts,
        "total_alerts": len(drift_alerts),
        "checked_at": get_current_timestamp(),
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _fetch_sites(tenant_id: str) -> List[Dict[str, Any]]:
    """Fetch all sites for a tenant."""
    from boto3.dynamodb.conditions import Key

    try:
        items, _ = dynamo_query_items(
            table_name=SITES_TABLE,
            key_condition_expression=Key("tenant_id").eq(tenant_id),
            scan_forward=True,
            limit=100,
        )
        return items
    except Exception:
        return []


def _fetch_staff(tenant_id: str) -> List[Dict[str, Any]]:
    """Fetch all staff members for a tenant."""
    from boto3.dynamodb.conditions import Key

    try:
        items, _ = dynamo_query_items(
            table_name=STAFF_TABLE,
            key_condition_expression=Key("tenant_id").eq(tenant_id),
            scan_forward=True,
            limit=200,
        )
        return items
    except Exception:
        return []


def _get_site_health(site_id: str) -> Dict[str, Any]:
    """Get current health status for a site."""
    try:
        item = dynamo_get_item(
            table_name=CLINIC_TABLE,
            key={"record_type": f"health#{site_id}", "record_id": site_id},
        )
        if item:
            return item
    except Exception:
        pass

    # Return default structure
    return {
        "site_id": site_id,
        "overall_health_score": 0,
        "gateway_status": {"total": 0, "online": 0, "offline": 0, "uptime_pct": 0},
        "sensor_counts": {"total": 0, "active": 0, "inactive": 0, "error": 0},
        "alert_density": 0,
        "last_updated": get_current_timestamp(),
    }


def _get_gateway_details(site_id: str) -> List[Dict[str, Any]]:
    """Get detailed gateway status for a site."""
    from boto3.dynamodb.conditions import Key

    try:
        items, _ = dynamo_query_items(
            table_name=CLINIC_TABLE,
            key_condition_expression=Key("record_type").eq(f"gateway#{site_id}"),
            scan_forward=True,
            limit=50,
        )
        return items
    except Exception:
        return []


def _get_site_sla(site_id: str, days: int = 7) -> Dict[str, Any]:
    """Get SLA metrics for a site."""
    try:
        item = dynamo_get_item(
            table_name=CLINIC_TABLE,
            key={"record_type": f"sla#{site_id}", "record_id": site_id},
        )
        if item:
            return item
    except Exception:
        pass

    return {
        "site_id": site_id,
        "response_time_avg_seconds": 0,
        "response_time_p95_seconds": 0,
        "met_count": 0,
        "missed_count": 0,
        "total_count": 0,
        "sla_pct": 100.0,
    }


def _check_sensor_drift(site_id: str) -> List[Dict[str, Any]]:
    """Detect sensor drift and calibration issues for a site."""
    from boto3.dynamodb.conditions import Key

    try:
        items, _ = dynamo_query_items(
            table_name=CLINIC_TABLE,
            key_condition_expression=Key("record_type").eq(f"sensor_drift#{site_id}"),
            scan_forward=False,
            limit=50,
        )
        return items
    except Exception:
        return []


def _calculate_caregiver_burnout(
    caregiver_id: str,
    site_id: str,
    days: int,
) -> Dict[str, Any]:
    """Calculate burnout metrics for a caregiver."""
    try:
        item = dynamo_get_item(
            table_name=CLINIC_TABLE,
            key={"record_type": f"burnout#{caregiver_id}", "record_id": caregiver_id},
        )
        if item:
            return {
                "alerts_per_shift": item.get("alerts_per_shift", 0),
                "avg_shift_hours": item.get("avg_shift_hours", 8),
                "overtime_hours": item.get("overtime_hours", 0),
                "total_alerts": item.get("total_alerts", 0),
                "shifts_count": item.get("shifts_count", 0),
                "last_shift_end": item.get("last_shift_end", ""),
            }
    except Exception:
        pass

    return {
        "alerts_per_shift": 0,
        "avg_shift_hours": 8.0,
        "overtime_hours": 0,
        "total_alerts": 0,
        "shifts_count": 0,
        "last_shift_end": "",
    }
