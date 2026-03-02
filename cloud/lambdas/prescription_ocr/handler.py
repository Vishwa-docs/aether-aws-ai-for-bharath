"""
AETHER Prescription OCR Lambda
================================
Processes uploaded prescription PDFs and images using AWS Textract,
parses medication details, cross-references for conflicts, and stores
structured prescription records.

Triggers
--------
- S3 event (``s3:ObjectCreated:*``) on the prescriptions bucket
- API Gateway: POST /api/prescriptions/process (direct upload)
- API Gateway: GET  /api/prescriptions/{document_id}
- API Gateway: GET  /api/prescriptions?resident_id=X
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
    PrescriptionRecord,
    get_current_timestamp,
    generate_event_id,
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
    s3_get_object,
    s3_put_object,
    setup_logger,
    sns_publish_structured_alert,
    alerts_topic_arn,
    get_dynamodb_table,
)

logger = setup_logger("prescription_ocr")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PRESCRIPTIONS_TABLE = get_env("PRESCRIPTIONS_TABLE", "aether-prescriptions")
PRESCRIPTIONS_BUCKET = get_env("PRESCRIPTIONS_BUCKET", "aether-prescriptions-upload")
MEDICATIONS_TABLE = get_env("MEDICATIONS_TABLE", "aether-medications")
BEDROCK_MODEL = get_env("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
CONFIDENCE_THRESHOLD = float(get_env("CONFIDENCE_THRESHOLD", "0.7"))


# ---------------------------------------------------------------------------
# Textract client (lazy init)
# ---------------------------------------------------------------------------

_textract_client: Optional[Any] = None


def _get_textract_client() -> Any:
    global _textract_client
    if _textract_client is None:
        import boto3
        from botocore.config import Config

        _textract_client = boto3.client(
            "textract",
            config=Config(retries={"max_attempts": 3, "mode": "adaptive"}),
        )
    return _textract_client


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AWS Lambda entry point.

    Dispatches between S3 event triggers and API Gateway proxy integration.
    """
    correlation_id = generate_correlation_id()

    # Detect S3 event trigger
    if "Records" in event and event["Records"][0].get("eventSource") == "aws:s3":
        return _handle_s3_event(event, correlation_id)

    # API Gateway proxy integration
    correlation_id = (
        (event.get("headers") or {}).get("X-Correlation-Id")
        or (event.get("headers") or {}).get("x-correlation-id")
        or correlation_id
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


def _generate_document_id() -> str:
    return f"rx-{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# S3 Event Handler
# ---------------------------------------------------------------------------

def _handle_s3_event(event: Dict[str, Any], correlation_id: str) -> Dict[str, Any]:
    """Process an S3 upload event for a prescription document."""
    results: List[Dict[str, Any]] = []

    for record in event.get("Records", []):
        s3_info = record.get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name", "")
        key = s3_info.get("object", {}).get("key", "")

        log_with_context(
            logger, "INFO",
            f"Processing uploaded document: s3://{bucket}/{key}",
            correlation_id=correlation_id,
        )

        try:
            # Extract resident_id and home_id from S3 key pattern:
            # prescriptions/{home_id}/{resident_id}/{filename}
            key_parts = key.split("/")
            home_id = key_parts[1] if len(key_parts) > 1 else "unknown"
            resident_id = key_parts[2] if len(key_parts) > 2 else "unknown"

            result = _process_document(
                bucket=bucket,
                key=key,
                home_id=home_id,
                resident_id=resident_id,
                correlation_id=correlation_id,
            )
            results.append(result)

        except Exception as exc:
            log_with_context(
                logger, "ERROR",
                f"Failed to process document s3://{bucket}/{key}: {exc}",
                correlation_id=correlation_id,
                traceback=traceback.format_exc(),
            )
            results.append({"status": "error", "key": key, "error": str(exc)})

    return {
        "statusCode": 200,
        "body": {
            "correlation_id": correlation_id,
            "processed": len(results),
            "results": results,
        },
    }


# ---------------------------------------------------------------------------
# POST /api/prescriptions/process
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/prescriptions/process/?$")
def _post_process(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Process a prescription document from a provided S3 location."""
    body = _parse_body(event)
    bucket = body.get("bucket", PRESCRIPTIONS_BUCKET)
    key = body.get("s3_key")
    home_id = body.get("home_id")
    resident_id = body.get("resident_id")

    if not key:
        return api_error(400, "missing_parameter", "s3_key is required", correlation_id)
    if not home_id:
        return api_error(400, "missing_parameter", "home_id is required", correlation_id)
    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id is required", correlation_id)

    result = _process_document(
        bucket=bucket,
        key=key,
        home_id=home_id,
        resident_id=resident_id,
        correlation_id=correlation_id,
    )

    return api_response(200, {
        "document_id": result["document_id"],
        "medications": result["medications"],
        "confidence_score": result["confidence_score"],
        "conflicts": result.get("conflicts", []),
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# GET /api/prescriptions/{document_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/prescriptions/(?P<document_id>rx-[a-f0-9]+)/?$")
def _get_prescription(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Retrieve a previously parsed prescription by document_id."""
    document_id = match.group("document_id")

    item = dynamo_get_item(
        table_name=PRESCRIPTIONS_TABLE,
        key={"document_id": document_id},
    )

    if not item:
        return api_error(404, "not_found", f"Prescription {document_id} not found", correlation_id)

    return api_response(200, {**item, "correlation_id": correlation_id})


# ---------------------------------------------------------------------------
# GET /api/prescriptions?resident_id=X
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/prescriptions/?$")
def _list_prescriptions(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """List prescriptions for a resident."""
    from boto3.dynamodb.conditions import Key

    resident_id = _query_param(event, "resident_id")
    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id query parameter is required", correlation_id)

    items, last_key = dynamo_query_items(
        table_name=PRESCRIPTIONS_TABLE,
        key_condition_expression=Key("resident_id").eq(resident_id),
        index_name="resident-index",
        scan_forward=False,
        limit=50,
    )

    return api_response(200, {
        "resident_id": resident_id,
        "prescriptions": items,
        "count": len(items),
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# Core processing pipeline
# ---------------------------------------------------------------------------

def _process_document(
    bucket: str,
    key: str,
    home_id: str,
    resident_id: str,
    correlation_id: str,
) -> Dict[str, Any]:
    """Full prescription processing pipeline.

    1. Call Textract to extract text
    2. Parse extracted text with Bedrock to identify medications
    3. Cross-reference with existing medications for conflicts
    4. Store the parsed prescription
    5. Notify caregiver via SNS
    6. Return structured result
    """
    document_id = _generate_document_id()
    now = get_current_timestamp()

    log_with_context(
        logger, "INFO",
        f"Starting OCR pipeline for document {document_id}",
        correlation_id=correlation_id,
        bucket=bucket,
        key=key,
    )

    # --- 1. Extract text via Textract -----------------------------------------
    extracted_text, page_count, raw_confidence = _extract_text_textract(bucket, key, correlation_id)

    log_with_context(
        logger, "INFO",
        f"Textract extracted {len(extracted_text)} chars from {page_count} page(s), "
        f"avg confidence: {raw_confidence:.2f}",
        correlation_id=correlation_id,
    )

    # --- 2. Parse medications with Bedrock ------------------------------------
    parsed = _parse_prescription_text(extracted_text, correlation_id)
    medications = parsed.get("medications", [])
    doctor_name = parsed.get("doctor_name", "")
    prescription_date = parsed.get("date", "")
    field_confidences = parsed.get("field_confidences", {})

    # Compute overall confidence (average of Textract confidence and field-level)
    field_conf_values = list(field_confidences.values()) if field_confidences else [raw_confidence]
    overall_confidence = round(
        (raw_confidence + (sum(field_conf_values) / len(field_conf_values))) / 2, 3
    )

    log_with_context(
        logger, "INFO",
        f"Parsed {len(medications)} medication(s), confidence={overall_confidence}",
        correlation_id=correlation_id,
    )

    # --- 3. Cross-reference for conflicts -------------------------------------
    conflicts = _check_medication_conflicts(resident_id, medications, correlation_id)

    # --- 4. Build and store prescription record --------------------------------
    prescription = PrescriptionRecord(
        document_id=document_id,
        resident_id=resident_id,
        home_id=home_id,
        medications=medications,
        doctor=doctor_name,
        date=prescription_date,
        source_url=f"s3://{bucket}/{key}",
        confidence_score=overall_confidence,
        field_confidences=field_confidences,
        page_count=page_count,
        raw_text=extracted_text[:5000],  # truncate for storage
        conflicts=conflicts,
        status="processed" if overall_confidence >= CONFIDENCE_THRESHOLD else "review_needed",
        created_at=now,
        correlation_id=correlation_id,
    )

    dynamo_put_item(PRESCRIPTIONS_TABLE, prescription.to_dict())

    # --- 5. Store audit trail in evidence bucket --------------------------------
    audit_record = {
        "document_id": document_id,
        "action": "prescription_parsed",
        "timestamp": now,
        "correlation_id": correlation_id,
        "source": f"s3://{bucket}/{key}",
        "page_count": page_count,
        "textract_confidence": raw_confidence,
        "overall_confidence": overall_confidence,
        "medications_found": len(medications),
        "conflicts_found": len(conflicts),
        "status": prescription.status,
    }

    s3_put_object(
        bucket=evidence_bucket_name(),
        key=f"prescriptions/{home_id}/{resident_id}/{document_id}/audit.json",
        body=audit_record,
    )

    # --- 6. Notify caregiver ---------------------------------------------------
    _notify_caregiver(prescription, conflicts, correlation_id)

    return {
        "document_id": document_id,
        "status": prescription.status,
        "medications": medications,
        "doctor": doctor_name,
        "date": prescription_date,
        "confidence_score": overall_confidence,
        "conflicts": conflicts,
        "page_count": page_count,
    }


# ---------------------------------------------------------------------------
# Textract integration
# ---------------------------------------------------------------------------

def _extract_text_textract(
    bucket: str,
    key: str,
    correlation_id: str,
) -> Tuple[str, int, float]:
    """Extract text from a document using AWS Textract.

    Supports single-page (DetectDocumentText) and multi-page
    (StartDocumentTextDetection) documents.

    Returns:
        Tuple of (extracted_text, page_count, average_confidence).
    """
    client = _get_textract_client()

    # Determine if multi-page (PDF) or single-page (image)
    is_pdf = key.lower().endswith(".pdf")

    if is_pdf:
        return _extract_text_multipage(client, bucket, key, correlation_id)
    else:
        return _extract_text_singlepage(client, bucket, key, correlation_id)


def _extract_text_singlepage(
    client: Any,
    bucket: str,
    key: str,
    correlation_id: str,
) -> Tuple[str, int, float]:
    """Extract text from a single-page image document."""
    response = client.detect_document_text(
        Document={"S3Object": {"Bucket": bucket, "Name": key}}
    )

    lines: List[str] = []
    confidences: List[float] = []

    for block in response.get("Blocks", []):
        if block["BlockType"] == "LINE":
            lines.append(block.get("Text", ""))
            confidences.append(block.get("Confidence", 0.0) / 100.0)

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return "\n".join(lines), 1, round(avg_confidence, 3)


def _extract_text_multipage(
    client: Any,
    bucket: str,
    key: str,
    correlation_id: str,
) -> Tuple[str, int, float]:
    """Extract text from a multi-page PDF using async Textract API."""
    import time

    # Start async job
    start_response = client.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}}
    )
    job_id = start_response["JobId"]

    log_with_context(
        logger, "INFO",
        f"Textract async job started: {job_id}",
        correlation_id=correlation_id,
    )

    # Poll for completion
    max_wait = 300  # 5 minutes
    poll_interval = 5
    elapsed = 0

    while elapsed < max_wait:
        result = client.get_document_text_detection(JobId=job_id)
        status = result["JobStatus"]

        if status == "SUCCEEDED":
            break
        elif status == "FAILED":
            raise RuntimeError(f"Textract job {job_id} failed: {result.get('StatusMessage', 'unknown')}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    if elapsed >= max_wait:
        raise TimeoutError(f"Textract job {job_id} timed out after {max_wait}s")

    # Collect all pages
    lines: List[str] = []
    confidences: List[float] = []
    pages: set = set()
    next_token: Optional[str] = None

    while True:
        kwargs: Dict[str, Any] = {"JobId": job_id}
        if next_token:
            kwargs["NextToken"] = next_token

        result = client.get_document_text_detection(**kwargs)

        for block in result.get("Blocks", []):
            if block["BlockType"] == "LINE":
                lines.append(block.get("Text", ""))
                confidences.append(block.get("Confidence", 0.0) / 100.0)
            if "Page" in block:
                pages.add(block["Page"])

        next_token = result.get("NextToken")
        if not next_token:
            break

    page_count = len(pages) if pages else 1
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return "\n".join(lines), page_count, round(avg_confidence, 3)


# ---------------------------------------------------------------------------
# Bedrock prescription parsing
# ---------------------------------------------------------------------------

def _parse_prescription_text(
    extracted_text: str,
    correlation_id: str,
) -> Dict[str, Any]:
    """Use Bedrock to parse extracted text into structured prescription data."""
    prompt = f"""You are a medical document parser for the AETHER elderly care system.
Parse the following prescription text and extract structured information.

Return a JSON object with these fields:
- "medications": array of objects, each with:
  - "name": medication name
  - "dosage": dosage (e.g., "500mg")
  - "frequency": how often (e.g., "twice daily", "every 8 hours")
  - "route": administration route (e.g., "oral", "topical")
  - "duration": prescribed duration if mentioned
  - "instructions": any special instructions
- "doctor_name": prescribing doctor's name
- "date": prescription date (ISO format if possible)
- "field_confidences": object with confidence scores (0-1) for each top-level field:
  - "medications": confidence in medication extraction
  - "doctor_name": confidence in doctor name extraction
  - "date": confidence in date extraction

Return ONLY the JSON object, no other text.

PRESCRIPTION TEXT:
{extracted_text}"""

    try:
        response_text = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=2048,
            temperature=0.1,
        )

        # Extract JSON from response
        parsed = _extract_json_from_response(response_text)
        return parsed

    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Bedrock parsing failed: {exc}",
            correlation_id=correlation_id,
        )
        return {
            "medications": [],
            "doctor_name": "",
            "date": "",
            "field_confidences": {"medications": 0.0, "doctor_name": 0.0, "date": 0.0},
        }


def _extract_json_from_response(text: str) -> Dict[str, Any]:
    """Extract a JSON object from model response text."""
    # Try direct parsing first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from code blocks
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return {
        "medications": [],
        "doctor_name": "",
        "date": "",
        "field_confidences": {"medications": 0.0, "doctor_name": 0.0, "date": 0.0},
    }


# ---------------------------------------------------------------------------
# Conflict checking
# ---------------------------------------------------------------------------

def _check_medication_conflicts(
    resident_id: str,
    new_medications: List[Dict[str, Any]],
    correlation_id: str,
) -> List[Dict[str, Any]]:
    """Cross-reference new medications against the resident's existing medication list."""
    from boto3.dynamodb.conditions import Key

    if not new_medications:
        return []

    # Fetch existing medications
    try:
        existing_items, _ = dynamo_query_items(
            table_name=MEDICATIONS_TABLE,
            key_condition_expression=Key("resident_id").eq(resident_id),
            scan_forward=False,
            limit=100,
        )
    except Exception as exc:
        log_with_context(
            logger, "WARNING",
            f"Could not fetch existing medications: {exc}",
            correlation_id=correlation_id,
        )
        existing_items = []

    if not existing_items:
        return []

    existing_med_names = [
        item.get("medication_name", "").lower()
        for item in existing_items
    ]

    new_med_names = [
        med.get("name", "").lower()
        for med in new_medications
    ]

    conflicts: List[Dict[str, Any]] = []

    # Check for duplicates
    for new_med in new_med_names:
        if new_med in existing_med_names:
            conflicts.append({
                "type": "duplicate",
                "medication": new_med,
                "severity": "moderate",
                "description": f"'{new_med}' is already on the active medication list. "
                               "Verify this is not a duplicate prescription.",
            })

    # Use Bedrock to check for interactions if we have both lists
    if existing_med_names and new_med_names:
        interaction_conflicts = _check_interactions_bedrock(
            existing_med_names, new_med_names, correlation_id
        )
        conflicts.extend(interaction_conflicts)

    return conflicts


def _check_interactions_bedrock(
    existing_meds: List[str],
    new_meds: List[str],
    correlation_id: str,
) -> List[Dict[str, Any]]:
    """Use Bedrock to check for drug interactions between medication lists."""
    prompt = f"""You are a pharmacology assistant for the AETHER elderly care system.
Check for potential drug-drug interactions between these medication lists.

EXISTING MEDICATIONS: {', '.join(existing_meds)}
NEW MEDICATIONS: {', '.join(new_meds)}

Return a JSON array of interaction objects, each with:
- "drug_a": first medication
- "drug_b": second medication
- "severity": one of "minor", "moderate", "severe", "contraindicated"
- "description": brief description of the interaction
- "recommendation": recommended action

If no interactions are found, return an empty array [].
Return ONLY the JSON array, no other text."""

    try:
        response_text = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=1024,
            temperature=0.1,
        )

        # Parse response
        try:
            interactions = json.loads(response_text)
        except json.JSONDecodeError:
            # Try extracting array
            start = response_text.find("[")
            end = response_text.rfind("]")
            if start != -1 and end != -1:
                interactions = json.loads(response_text[start:end + 1])
            else:
                interactions = []

        return [
            {
                "type": "interaction",
                "medication": f"{i.get('drug_a', '')} + {i.get('drug_b', '')}",
                "severity": i.get("severity", "unknown"),
                "description": i.get("description", ""),
                "recommendation": i.get("recommendation", ""),
            }
            for i in interactions
            if isinstance(i, dict)
        ]

    except Exception as exc:
        log_with_context(
            logger, "WARNING",
            f"Bedrock interaction check failed: {exc}",
            correlation_id=correlation_id,
        )
        return []


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def _notify_caregiver(
    prescription: PrescriptionRecord,
    conflicts: List[Dict[str, Any]],
    correlation_id: str,
) -> None:
    """Send caregiver notification about the parsed prescription."""
    topic_arn = alerts_topic_arn()
    if not topic_arn:
        log_with_context(
            logger, "WARNING",
            "No alerts topic ARN configured; skipping notification",
            correlation_id=correlation_id,
        )
        return

    med_names = [m.get("name", "unknown") for m in prescription.medications]
    conflict_count = len(conflicts)
    severe_conflicts = [c for c in conflicts if c.get("severity") in ("severe", "contraindicated")]

    severity = "HIGH" if severe_conflicts else ("MEDIUM" if conflict_count > 0 else "INFO")
    event_type = "prescription_processed"

    summary = (
        f"Prescription processed for resident.\n"
        f"Doctor: {prescription.doctor}\n"
        f"Medications: {', '.join(med_names)}\n"
        f"Confidence: {prescription.confidence_score:.0%}\n"
    )

    if conflict_count > 0:
        summary += f"\n⚠️ {conflict_count} potential conflict(s) detected"
        if severe_conflicts:
            summary += f" ({len(severe_conflicts)} SEVERE)"
        summary += ":\n"
        for c in conflicts:
            summary += f"  - [{c.get('severity', 'unknown').upper()}] {c.get('description', '')}\n"

    if prescription.status == "review_needed":
        summary += "\n⚠️ Low confidence – manual review recommended."

    try:
        sns_publish_structured_alert(
            topic_arn=topic_arn,
            event_type=event_type,
            severity=severity,
            home_id=prescription.home_id,
            message=summary,
        )
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Failed to send caregiver notification: {exc}",
            correlation_id=correlation_id,
        )
