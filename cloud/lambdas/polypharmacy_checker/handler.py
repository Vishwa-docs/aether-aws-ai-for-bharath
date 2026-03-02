"""
AETHER Polypharmacy Checker Lambda
====================================
Checks for drug-drug interactions, contraindications, duplicate therapies,
and generates risk scores for medication lists using AWS Bedrock (Claude).

Endpoints
---------
POST /api/polypharmacy/check       – Run interaction check on a medication list
GET  /api/polypharmacy/{report_id} – Retrieve a previous interaction report
GET  /api/polypharmacy?resident_id=X – List reports for a resident
"""

from __future__ import annotations

import json
import os
import re
import sys
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.models import (
    DrugInteraction,
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
    evidence_bucket_name,
    generate_correlation_id,
    get_env,
    invoke_bedrock_model,
    json_dumps,
    log_with_context,
    s3_put_object,
    setup_logger,
    sns_publish_structured_alert,
    alerts_topic_arn,
)

logger = setup_logger("polypharmacy_checker")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

INTERACTIONS_TABLE = get_env("INTERACTIONS_TABLE", "aether-drug-interactions")
MEDICATIONS_TABLE = get_env("MEDICATIONS_TABLE", "aether-medications")
RESIDENTS_TABLE = get_env("RESIDENTS_TABLE", "aether-residents")
BEDROCK_MODEL = get_env("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

# Severity weights for risk score calculation
SEVERITY_WEIGHTS: Dict[str, float] = {
    "contraindicated": 4.0,
    "severe": 3.0,
    "moderate": 2.0,
    "minor": 1.0,
}


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


def _generate_report_id() -> str:
    return f"phr-{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# POST /api/polypharmacy/check
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/polypharmacy/check/?$")
def _post_check(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Run a comprehensive polypharmacy and interaction check."""
    body = _parse_body(event)
    resident_id = body.get("resident_id")
    home_id = body.get("home_id", "unknown")
    medications = body.get("medications", [])
    conditions = body.get("conditions", [])

    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id is required", correlation_id)
    if not medications:
        return api_error(400, "missing_parameter", "medications list is required", correlation_id)

    log_with_context(
        logger, "INFO",
        f"Checking {len(medications)} medication(s) for resident {resident_id}",
        correlation_id=correlation_id,
    )

    # If conditions not provided, fetch from resident profile
    if not conditions:
        conditions = _fetch_resident_conditions(resident_id, correlation_id)

    report_id = _generate_report_id()
    now = get_current_timestamp()

    # --- 1. Check drug-drug interactions ---------------------------------------
    interactions = _check_drug_interactions(medications, correlation_id)

    # --- 2. Check contraindications against conditions -------------------------
    contraindications = _check_contraindications(medications, conditions, correlation_id)

    # --- 3. Identify duplicate therapies ---------------------------------------
    duplicates = _check_duplicate_therapies(medications, correlation_id)

    # --- 4. Identify high-risk combinations ------------------------------------
    high_risk = _check_high_risk_combinations(medications, conditions, correlation_id)

    # --- 5. Calculate risk score -----------------------------------------------
    all_findings = interactions + contraindications + duplicates + high_risk
    risk_score = _calculate_risk_score(all_findings, len(medications))

    # --- 6. Generate recommendations -------------------------------------------
    recommendations = _generate_recommendations(
        medications, conditions, all_findings, risk_score, correlation_id
    )

    # --- 7. Build report -------------------------------------------------------
    report = {
        "report_id": report_id,
        "resident_id": resident_id,
        "home_id": home_id,
        "medications_checked": medications,
        "conditions": conditions,
        "interactions": [i.to_dict() if hasattr(i, "to_dict") else i for i in interactions],
        "contraindications": contraindications,
        "duplicate_therapies": duplicates,
        "high_risk_combinations": high_risk,
        "risk_score": risk_score,
        "risk_level": _risk_level(risk_score),
        "recommendations": recommendations,
        "total_findings": len(all_findings),
        "findings_by_severity": _count_by_severity(all_findings),
        "created_at": now,
        "correlation_id": correlation_id,
    }

    # --- 8. Store report -------------------------------------------------------
    dynamo_put_item(INTERACTIONS_TABLE, report)

    # Store audit copy in S3
    s3_put_object(
        bucket=evidence_bucket_name(),
        key=f"polypharmacy/{resident_id}/{report_id}/report.json",
        body=report,
    )

    # --- 9. Alert if high risk -------------------------------------------------
    if risk_score >= 7:
        _send_high_risk_alert(report, correlation_id)

    log_with_context(
        logger, "INFO",
        f"Polypharmacy check complete: risk_score={risk_score}, findings={len(all_findings)}",
        correlation_id=correlation_id,
    )

    return api_response(200, report)


# ---------------------------------------------------------------------------
# GET /api/polypharmacy/{report_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/polypharmacy/(?P<report_id>phr-[a-f0-9]+)/?$")
def _get_report(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Retrieve a previous interaction report."""
    report_id = match.group("report_id")

    item = dynamo_get_item(
        table_name=INTERACTIONS_TABLE,
        key={"report_id": report_id},
    )

    if not item:
        return api_error(404, "not_found", f"Report {report_id} not found", correlation_id)

    return api_response(200, {**item, "correlation_id": correlation_id})


# ---------------------------------------------------------------------------
# GET /api/polypharmacy?resident_id=X
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/polypharmacy/?$")
def _list_reports(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """List interaction reports for a resident."""
    from boto3.dynamodb.conditions import Key

    resident_id = _query_param(event, "resident_id")
    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id is required", correlation_id)

    items, _ = dynamo_query_items(
        table_name=INTERACTIONS_TABLE,
        key_condition_expression=Key("resident_id").eq(resident_id),
        index_name="resident-index",
        scan_forward=False,
        limit=25,
    )

    return api_response(200, {
        "resident_id": resident_id,
        "reports": items,
        "count": len(items),
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# Bedrock interaction checking
# ---------------------------------------------------------------------------

def _check_drug_interactions(
    medications: List[Dict[str, Any]],
    correlation_id: str,
) -> List[DrugInteraction]:
    """Use Bedrock to identify drug-drug interactions."""
    med_names = [m.get("name", "") for m in medications if m.get("name")]
    if len(med_names) < 2:
        return []

    prompt = f"""You are a clinical pharmacology expert for the AETHER elderly care system.
Analyze the following medication list for potential drug-drug interactions.

MEDICATIONS: {', '.join(med_names)}

For each interaction found, provide:
- "drug_a": first medication name
- "drug_b": second medication name
- "severity": one of "minor", "moderate", "severe", "contraindicated"
- "description": clinical description of the interaction mechanism
- "recommendation": specific clinical recommendation

Return a JSON array of interaction objects. If no interactions exist, return [].
Return ONLY the JSON array."""

    try:
        response_text = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=2048,
            temperature=0.1,
        )

        raw = _parse_json_array(response_text)

        return [
            DrugInteraction(
                drug_a=item.get("drug_a", ""),
                drug_b=item.get("drug_b", ""),
                severity=item.get("severity", "unknown"),
                description=item.get("description", ""),
                recommendation=item.get("recommendation", ""),
            )
            for item in raw
            if isinstance(item, dict) and item.get("drug_a")
        ]

    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Drug interaction check failed: {exc}",
            correlation_id=correlation_id,
        )
        return []


def _check_contraindications(
    medications: List[Dict[str, Any]],
    conditions: List[str],
    correlation_id: str,
) -> List[Dict[str, Any]]:
    """Check medications against resident's medical conditions for contraindications."""
    if not medications or not conditions:
        return []

    med_names = [m.get("name", "") for m in medications if m.get("name")]

    prompt = f"""You are a clinical pharmacology expert for the AETHER elderly care system.
Check the following medications against the patient's medical conditions for contraindications.

MEDICATIONS: {', '.join(med_names)}
MEDICAL CONDITIONS: {', '.join(conditions)}

For each contraindication found, provide:
- "medication": the medication name
- "condition": the condition it conflicts with
- "severity": one of "minor", "moderate", "severe", "contraindicated"
- "description": why this is contraindicated
- "recommendation": what should be done

Return a JSON array. If no contraindications exist, return [].
Return ONLY the JSON array."""

    try:
        response_text = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=1024,
            temperature=0.1,
        )
        return _parse_json_array(response_text)
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Contraindication check failed: {exc}",
            correlation_id=correlation_id,
        )
        return []


def _check_duplicate_therapies(
    medications: List[Dict[str, Any]],
    correlation_id: str,
) -> List[Dict[str, Any]]:
    """Identify medications in the same therapeutic class (duplicate therapy)."""
    if len(medications) < 2:
        return []

    med_details = [
        f"{m.get('name', '')} ({m.get('dosage', 'unknown dose')})"
        for m in medications
    ]

    prompt = f"""You are a clinical pharmacology expert for the AETHER elderly care system.
Identify any duplicate therapy in the following medication list (medications from
the same therapeutic class that may be redundant).

MEDICATIONS: {'; '.join(med_details)}

For each duplicate therapy found, provide:
- "medications": list of medication names in the same class
- "therapeutic_class": the shared therapeutic class
- "severity": "moderate" or "severe"
- "description": why this is a concern
- "recommendation": what should be done

Return a JSON array. If no duplicates exist, return [].
Return ONLY the JSON array."""

    try:
        response_text = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=1024,
            temperature=0.1,
        )
        return _parse_json_array(response_text)
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Duplicate therapy check failed: {exc}",
            correlation_id=correlation_id,
        )
        return []


def _check_high_risk_combinations(
    medications: List[Dict[str, Any]],
    conditions: List[str],
    correlation_id: str,
) -> List[Dict[str, Any]]:
    """Flag high-risk medication combinations for elderly patients."""
    if not medications:
        return []

    med_names = [m.get("name", "") for m in medications if m.get("name")]

    prompt = f"""You are a geriatric pharmacology expert for the AETHER elderly care system.
Identify high-risk medication combinations specifically for ELDERLY patients (age 65+).

Consider:
- Beers Criteria high-risk medications
- Anticholinergic burden
- Fall risk increasing drugs (FRIDs)
- Medications requiring renal/hepatic dose adjustment in elderly
- QT-prolonging combinations

MEDICATIONS: {', '.join(med_names)}
CONDITIONS: {', '.join(conditions) if conditions else 'not specified'}

For each high-risk finding, provide:
- "medications": list of medications involved
- "risk_category": type of risk (e.g., "falls", "cognitive", "renal", "cardiac")
- "severity": one of "moderate", "severe"
- "description": clinical concern
- "recommendation": action to take

Return a JSON array. If no high-risk combinations exist, return [].
Return ONLY the JSON array."""

    try:
        response_text = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=1024,
            temperature=0.1,
        )
        return _parse_json_array(response_text)
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"High-risk combination check failed: {exc}",
            correlation_id=correlation_id,
        )
        return []


# ---------------------------------------------------------------------------
# Risk score calculation
# ---------------------------------------------------------------------------

def _calculate_risk_score(
    findings: List[Any],
    medication_count: int,
) -> int:
    """Calculate a risk score from 1-10 based on findings.

    Score methodology:
    - Base: 1 (no risk)
    - Each finding adds weighted severity points
    - Normalized to 1-10 scale
    - Polypharmacy bonus: +1 if ≥5 meds, +2 if ≥10 meds
    """
    if not findings:
        base = 1
        if medication_count >= 10:
            base += 2
        elif medication_count >= 5:
            base += 1
        return min(base, 10)

    weighted_sum = 0.0
    for finding in findings:
        severity = ""
        if isinstance(finding, DrugInteraction):
            severity = finding.severity
        elif isinstance(finding, dict):
            severity = finding.get("severity", "minor")
        weighted_sum += SEVERITY_WEIGHTS.get(severity.lower(), 1.0)

    # Polypharmacy bonus
    poly_bonus = 0
    if medication_count >= 10:
        poly_bonus = 2
    elif medication_count >= 5:
        poly_bonus = 1

    # Normalize: raw score maps to 1-10
    raw = weighted_sum + poly_bonus
    score = min(10, max(1, int(1 + (raw / max(len(findings), 1)) * 2.5)))

    return score


def _risk_level(score: int) -> str:
    """Map numeric risk score to risk level string."""
    if score >= 8:
        return "critical"
    elif score >= 6:
        return "high"
    elif score >= 4:
        return "moderate"
    elif score >= 2:
        return "low"
    return "minimal"


def _count_by_severity(findings: List[Any]) -> Dict[str, int]:
    """Count findings grouped by severity."""
    counts: Dict[str, int] = {}
    for finding in findings:
        severity = ""
        if isinstance(finding, DrugInteraction):
            severity = finding.severity
        elif isinstance(finding, dict):
            severity = finding.get("severity", "unknown")
        severity = severity.lower()
        counts[severity] = counts.get(severity, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def _generate_recommendations(
    medications: List[Dict[str, Any]],
    conditions: List[str],
    findings: List[Any],
    risk_score: int,
    correlation_id: str,
) -> List[Dict[str, Any]]:
    """Generate actionable recommendations for doctor review."""
    if not findings:
        return [{
            "priority": "low",
            "recommendation": "No significant interactions detected. Continue current regimen.",
            "action_required": False,
        }]

    findings_text = json_dumps(findings[:10])  # Limit for prompt size

    prompt = f"""You are a geriatric pharmacology consultant for the AETHER elderly care system.
Based on the following polypharmacy analysis, generate specific, actionable recommendations
for the prescribing physician to review.

RISK SCORE: {risk_score}/10
MEDICATIONS: {json_dumps([m.get('name', '') for m in medications])}
CONDITIONS: {json_dumps(conditions)}
FINDINGS: {findings_text}

Generate 3-5 prioritized recommendations. For each:
- "priority": "high", "medium", or "low"
- "recommendation": specific, actionable clinical recommendation
- "action_required": true if immediate physician action needed, false if informational
- "rationale": brief clinical rationale

Return a JSON array of recommendation objects.
Return ONLY the JSON array."""

    try:
        response_text = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=1024,
            temperature=0.2,
        )
        recommendations = _parse_json_array(response_text)
        return recommendations if recommendations else [{
            "priority": "medium",
            "recommendation": "Review identified interactions with prescribing physician.",
            "action_required": True,
        }]
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Recommendation generation failed: {exc}",
            correlation_id=correlation_id,
        )
        return [{
            "priority": "medium",
            "recommendation": "Review identified interactions with prescribing physician.",
            "action_required": True,
        }]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_resident_conditions(
    resident_id: str,
    correlation_id: str,
) -> List[str]:
    """Fetch medical conditions from the resident profile."""
    try:
        item = dynamo_get_item(
            table_name=RESIDENTS_TABLE,
            key={"resident_id": resident_id},
        )
        if item:
            return item.get("medical_conditions", item.get("conditions", []))
    except Exception as exc:
        log_with_context(
            logger, "WARNING",
            f"Could not fetch resident conditions: {exc}",
            correlation_id=correlation_id,
        )
    return []


def _send_high_risk_alert(report: Dict[str, Any], correlation_id: str) -> None:
    """Send SNS alert for high-risk polypharmacy findings."""
    topic_arn = alerts_topic_arn()
    if not topic_arn:
        return

    risk_score = report.get("risk_score", 0)
    resident_id = report.get("resident_id", "unknown")
    findings_count = report.get("total_findings", 0)

    message = (
        f"⚠️ HIGH-RISK Polypharmacy Alert\n"
        f"Resident: {resident_id}\n"
        f"Risk Score: {risk_score}/10 ({report.get('risk_level', 'unknown').upper()})\n"
        f"Total Findings: {findings_count}\n"
        f"Report ID: {report.get('report_id', '')}\n\n"
        f"Immediate physician review recommended."
    )

    try:
        sns_publish_structured_alert(
            topic_arn=topic_arn,
            event_type="polypharmacy_alert",
            severity="CRITICAL" if risk_score >= 9 else "HIGH",
            home_id=report.get("home_id", "unknown"),
            message=message,
        )
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Failed to send high-risk alert: {exc}",
            correlation_id=correlation_id,
        )


def _parse_json_array(text: str) -> List[Dict[str, Any]]:
    """Parse a JSON array from model response text."""
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try extracting from code blocks
    json_match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first [ to last ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return []
