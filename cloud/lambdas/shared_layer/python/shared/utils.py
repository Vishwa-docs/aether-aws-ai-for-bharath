"""
AETHER Elderly Care System – Shared Utilities
==============================================
Cross-cutting helpers used by every Lambda: DynamoDB / S3 / SNS wrappers,
structured logging, environment configuration, and serialisation.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Global boto3 clients – created once per Lambda container and reused.
# ---------------------------------------------------------------------------

_BOTO_CONFIG = Config(
    retries={"max_attempts": 3, "mode": "adaptive"},
    connect_timeout=5,
    read_timeout=10,
)

_dynamodb_resource: Optional[Any] = None
_s3_client: Optional[Any] = None
_sns_client: Optional[Any] = None
_sfn_client: Optional[Any] = None
_bedrock_client: Optional[Any] = None
_bedrock_agent_client: Optional[Any] = None


def _get_dynamodb_resource() -> Any:
    global _dynamodb_resource
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb", config=_BOTO_CONFIG)
    return _dynamodb_resource


def get_dynamodb_table(table_name: str) -> Any:
    """Return a DynamoDB ``Table`` resource, reused across invocations."""
    return _get_dynamodb_resource().Table(table_name)


def get_s3_client() -> Any:
    """Return a reusable S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3", config=_BOTO_CONFIG)
    return _s3_client


def get_sns_client() -> Any:
    """Return a reusable SNS client."""
    global _sns_client
    if _sns_client is None:
        _sns_client = boto3.client("sns", config=_BOTO_CONFIG)
    return _sns_client


def get_sfn_client() -> Any:
    """Return a reusable Step Functions client."""
    global _sfn_client
    if _sfn_client is None:
        _sfn_client = boto3.client("stepfunctions", config=_BOTO_CONFIG)
    return _sfn_client


def get_bedrock_client() -> Any:
    """Return a reusable Bedrock Runtime client."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client("bedrock-runtime", config=_BOTO_CONFIG)
    return _bedrock_client


def get_bedrock_agent_client() -> Any:
    """Return a reusable Bedrock Agent Runtime client (for Knowledge Bases)."""
    global _bedrock_agent_client
    if _bedrock_agent_client is None:
        _bedrock_agent_client = boto3.client("bedrock-agent-runtime", config=_BOTO_CONFIG)
    return _bedrock_agent_client


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------

def get_env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    """Read an environment variable with optional default.

    Args:
        name: Variable name.
        default: Fallback value when the variable is unset.
        required: If ``True`` and the variable is missing, raise.

    Returns:
        The environment variable value.

    Raises:
        EnvironmentError: When *required* is ``True`` and the variable is unset.
    """
    value = os.environ.get(name, default)
    if required and value is None:
        raise EnvironmentError(f"Required environment variable {name!r} is not set")
    return value  # type: ignore[return-value]


# Common table names
def events_table_name() -> str:
    return get_env("EVENTS_TABLE", "aether-events")


def timeline_table_name() -> str:
    return get_env("TIMELINE_TABLE", "aether-timeline")


def residents_table_name() -> str:
    return get_env("RESIDENTS_TABLE", "aether-residents")


def consent_table_name() -> str:
    return get_env("CONSENT_TABLE", "aether-consent")


def clinic_ops_table_name() -> str:
    return get_env("CLINIC_OPS_TABLE", "aether-clinic-ops")


def evidence_bucket_name() -> str:
    return get_env("EVIDENCE_BUCKET", "aether-evidence")


def alerts_topic_arn() -> str:
    return get_env("ALERTS_TOPIC_ARN", "")


def escalation_sfn_arn() -> str:
    return get_env("ESCALATION_SFN_ARN", "")


def bedrock_model_id() -> str:
    return get_env("BEDROCK_MODEL_ID", "nvidia.nemotron-mini-4b-instruct")


def knowledge_base_id() -> str:
    return get_env("KNOWLEDGE_BASE_ID", "")


# ---------------------------------------------------------------------------
# JSON / Decimal serialiser
# ---------------------------------------------------------------------------

class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that converts ``Decimal`` values to ``int`` or ``float``.

    DynamoDB returns all numbers as ``Decimal``; this encoder ensures they
    serialise cleanly to standard JSON numeric types.
    """

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            if obj == int(obj):
                return int(obj)
            return float(obj)
        if isinstance(obj, (datetime,)):
            return obj.isoformat()
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)


def json_dumps(obj: Any, **kwargs: Any) -> str:
    """Serialise *obj* to JSON using :class:`DecimalEncoder`."""
    return json.dumps(obj, cls=DecimalEncoder, default=str, **kwargs)


def decimalize(obj: Any) -> Any:
    """Recursively convert floats in *obj* to ``Decimal`` for DynamoDB."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: decimalize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [decimalize(v) for v in obj]
    return obj


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------

def setup_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """Create a structured JSON logger.

    Args:
        name: Logger name (typically the Lambda module name).
        level: Override log level (default from env ``LOG_LEVEL``).

    Returns:
        Configured :class:`logging.Logger`.
    """
    log_level = level or get_env("LOG_LEVEL", "INFO")
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Avoid duplicate handlers when Lambda runtime re-imports
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
                '"logger":"%(name)s","message":"%(message)s"}'
            )
        )
        logger.addHandler(handler)

    return logger


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for tracing a request across services."""
    return f"cor-{uuid.uuid4().hex}"


def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    correlation_id: Optional[str] = None,
    **extra: Any,
) -> None:
    """Emit a structured log entry with optional correlation ID and extras.

    Args:
        logger: The logger to use.
        level: Log level string (``"INFO"``, ``"ERROR"``, …).
        message: Human-readable message.
        correlation_id: Optional tracing identifier.
        **extra: Additional key-value pairs to include in the log.
    """
    payload: Dict[str, Any] = {"msg": message}
    if correlation_id:
        payload["correlation_id"] = correlation_id
    payload.update(extra)

    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn(json_dumps(payload))


# ---------------------------------------------------------------------------
# DynamoDB helpers
# ---------------------------------------------------------------------------

def dynamo_put_item(table_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
    """Put an item into a DynamoDB table.

    Converts Python floats to ``Decimal`` automatically.

    Returns:
        The DynamoDB ``put_item`` response metadata.
    """
    table = get_dynamodb_table(table_name)
    clean_item = decimalize(item)
    response = table.put_item(Item=clean_item)
    return response


def dynamo_get_item(
    table_name: str,
    key: Dict[str, Any],
    consistent: bool = False,
) -> Optional[Dict[str, Any]]:
    """Get a single item by primary key.

    Args:
        table_name: Target DynamoDB table.
        key: Primary key dict (e.g., ``{"home_id": "h1", "timestamp": "…"}``).
        consistent: Use strongly-consistent read.

    Returns:
        The item dict or ``None`` if not found.
    """
    table = get_dynamodb_table(table_name)
    kwargs: Dict[str, Any] = {"Key": key}
    if consistent:
        kwargs["ConsistentRead"] = True
    response = table.get_item(**kwargs)
    return response.get("Item")


def dynamo_query_items(
    table_name: str,
    key_condition_expression: Any,
    expression_attribute_values: Optional[Dict[str, Any]] = None,
    expression_attribute_names: Optional[Dict[str, str]] = None,
    filter_expression: Any = None,
    index_name: Optional[str] = None,
    scan_forward: bool = True,
    limit: Optional[int] = None,
    max_pages: int = 10,
    projection_expression: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Query a DynamoDB table with automatic pagination.

    Args:
        table_name: Table to query.
        key_condition_expression: A boto3 ``Key`` condition.
        expression_attribute_values: Bind variables.
        expression_attribute_names: Name aliases.
        filter_expression: Optional post-query filter.
        index_name: GSI / LSI name if querying an index.
        scan_forward: Sort ascending (``True``) or descending.
        limit: Per-page item limit.
        max_pages: Maximum number of API pages to fetch.
        projection_expression: Attributes to return.

    Returns:
        A tuple of ``(items, last_evaluated_key)``.
    """
    table = get_dynamodb_table(table_name)
    kwargs: Dict[str, Any] = {
        "KeyConditionExpression": key_condition_expression,
        "ScanIndexForward": scan_forward,
    }

    if expression_attribute_values:
        kwargs["ExpressionAttributeValues"] = decimalize(expression_attribute_values)
    if expression_attribute_names:
        kwargs["ExpressionAttributeNames"] = expression_attribute_names
    if filter_expression is not None:
        kwargs["FilterExpression"] = filter_expression
    if index_name:
        kwargs["IndexName"] = index_name
    if limit:
        kwargs["Limit"] = limit
    if projection_expression:
        kwargs["ProjectionExpression"] = projection_expression

    items: List[Dict[str, Any]] = []
    pages = 0
    last_key: Optional[Dict[str, Any]] = None

    while pages < max_pages:
        response = table.query(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        pages += 1

        if last_key is None:
            break
        kwargs["ExclusiveStartKey"] = last_key

    return items, last_key


def dynamo_update_item(
    table_name: str,
    key: Dict[str, Any],
    update_expression: str,
    expression_attribute_values: Optional[Dict[str, Any]] = None,
    expression_attribute_names: Optional[Dict[str, str]] = None,
    condition_expression: Optional[str] = None,
) -> Dict[str, Any]:
    """Update an item in DynamoDB.

    Returns:
        The update response.
    """
    table = get_dynamodb_table(table_name)
    kwargs: Dict[str, Any] = {
        "Key": key,
        "UpdateExpression": update_expression,
        "ReturnValues": "ALL_NEW",
    }
    if expression_attribute_values:
        kwargs["ExpressionAttributeValues"] = decimalize(expression_attribute_values)
    if expression_attribute_names:
        kwargs["ExpressionAttributeNames"] = expression_attribute_names
    if condition_expression:
        kwargs["ConditionExpression"] = condition_expression
    return table.update_item(**kwargs)


# ---------------------------------------------------------------------------
# S3 helpers
# ---------------------------------------------------------------------------

def s3_put_object(
    bucket: str,
    key: str,
    body: Any,
    content_type: str = "application/json",
    metadata: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Upload an object to S3.

    Args:
        bucket: Target S3 bucket name.
        key: Object key.
        body: String, bytes, or dict (auto-serialised to JSON).
        content_type: MIME type.
        metadata: Optional user metadata dict.

    Returns:
        The S3 ``put_object`` response.
    """
    client = get_s3_client()
    if isinstance(body, dict):
        body = json_dumps(body)
    if isinstance(body, str):
        body = body.encode("utf-8")

    kwargs: Dict[str, Any] = {
        "Bucket": bucket,
        "Key": key,
        "Body": body,
        "ContentType": content_type,
    }
    if metadata:
        kwargs["Metadata"] = metadata

    return client.put_object(**kwargs)


def s3_get_presigned_url(
    bucket: str,
    key: str,
    expires_in: int = 3600,
) -> str:
    """Generate a presigned GET URL for an S3 object.

    Args:
        bucket: S3 bucket.
        key: Object key.
        expires_in: URL validity in seconds (default 1 hour).

    Returns:
        The presigned URL string.
    """
    client = get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def s3_get_object(bucket: str, key: str) -> bytes:
    """Download an object from S3.

    Returns:
        Raw bytes of the object body.
    """
    client = get_s3_client()
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


# ---------------------------------------------------------------------------
# SNS helpers
# ---------------------------------------------------------------------------

def sns_publish_alert(
    topic_arn: str,
    subject: str,
    message: str,
    message_attributes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Publish a notification to an SNS topic.

    Args:
        topic_arn: The SNS topic ARN.
        subject: Message subject (for e-mail / SMS).
        message: Message body.
        message_attributes: Optional SNS message attributes.

    Returns:
        The SNS ``publish`` response.
    """
    client = get_sns_client()
    kwargs: Dict[str, Any] = {
        "TopicArn": topic_arn,
        "Subject": subject[:99],  # SNS subject max 100 chars
        "Message": message,
    }
    if message_attributes:
        kwargs["MessageAttributes"] = message_attributes
    return client.publish(**kwargs)


def sns_publish_structured_alert(
    topic_arn: str,
    event_type: str,
    severity: str,
    home_id: str,
    message: str,
) -> Dict[str, Any]:
    """Publish an alert with filterable message attributes.

    SNS subscriptions can use filter policies on ``event_type`` and
    ``severity`` to route notifications appropriately.
    """
    subject = f"AETHER [{severity}] {event_type} – Home {home_id}"
    attrs = {
        "event_type": {"DataType": "String", "StringValue": event_type},
        "severity": {"DataType": "String", "StringValue": severity},
        "home_id": {"DataType": "String", "StringValue": home_id},
    }
    return sns_publish_alert(topic_arn, subject, message, message_attributes=attrs)


# ---------------------------------------------------------------------------
# Step Functions helpers
# ---------------------------------------------------------------------------

def start_step_function(
    state_machine_arn: str,
    name: str,
    input_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Start a Step Functions execution.

    Args:
        state_machine_arn: ARN of the state machine.
        name: Execution name (must be unique within the state machine).
        input_data: Input payload.

    Returns:
        The ``start_execution`` response.
    """
    client = get_sfn_client()
    return client.start_execution(
        stateMachineArn=state_machine_arn,
        name=name,
        input=json_dumps(input_data),
    )


# ---------------------------------------------------------------------------
# Bedrock helpers
# ---------------------------------------------------------------------------

def invoke_bedrock_model(
    prompt: str,
    model_id: Optional[str] = None,
    max_tokens: int = 1024,
    temperature: float = 0.3,
) -> str:
    """Invoke a Bedrock model and return the generated text.

    Supports both Nemotron-style and general ``invoke_model`` payloads.

    Args:
        prompt: The text prompt.
        model_id: Override model ID (default from env).
        max_tokens: Maximum response tokens.
        temperature: Sampling temperature.

    Returns:
        The generated text string.
    """
    client = get_bedrock_client()
    model = model_id or bedrock_model_id()

    request_body = {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": max_tokens,
            "temperature": temperature,
            "topP": 0.9,
        },
    }

    response = client.invoke_model(
        modelId=model,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(request_body),
    )

    response_body = json.loads(response["body"].read())

    # Handle multiple response formats from different model providers
    if "results" in response_body:
        return response_body["results"][0].get("outputText", "")
    if "output" in response_body:
        if isinstance(response_body["output"], str):
            return response_body["output"]
        return response_body["output"].get("text", "")
    if "completion" in response_body:
        return response_body["completion"]
    if "content" in response_body:
        content = response_body["content"]
        if isinstance(content, list) and content:
            return content[0].get("text", "")
        return str(content)

    return json_dumps(response_body)


def retrieve_and_generate(
    query: str,
    kb_id: Optional[str] = None,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Use Bedrock Knowledge Bases retrieve-and-generate API.

    Args:
        query: Natural language question.
        kb_id: Knowledge Base ID (default from env).
        model_id: Foundation model ARN for generation.

    Returns:
        Dict with ``output``, ``citations``, and ``session_id``.
    """
    client = get_bedrock_agent_client()
    kb = kb_id or knowledge_base_id()
    model = model_id or bedrock_model_id()

    region = get_env("AWS_REGION", "us-east-1")
    model_arn = f"arn:aws:bedrock:{region}::foundation-model/{model}"

    response = client.retrieve_and_generate(
        input={"text": query},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": kb,
                "modelArn": model_arn,
            },
        },
    )

    return {
        "output": response.get("output", {}).get("text", ""),
        "citations": response.get("citations", []),
        "session_id": response.get("sessionId", ""),
    }


# ---------------------------------------------------------------------------
# API response builders
# ---------------------------------------------------------------------------

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": get_env("CORS_ORIGIN", "*"),
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Correlation-Id",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    "Content-Type": "application/json",
}


def api_response(
    status_code: int,
    body: Any,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build an API Gateway proxy-integration response.

    Args:
        status_code: HTTP status code.
        body: Response body (will be JSON-serialised).
        extra_headers: Additional response headers.

    Returns:
        An API Gateway-compatible response dict.
    """
    headers = {**_CORS_HEADERS}
    if extra_headers:
        headers.update(extra_headers)

    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json_dumps(body) if not isinstance(body, str) else body,
    }


def api_error(
    status_code: int,
    error: str,
    message: str,
    correlation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a structured error response."""
    body: Dict[str, Any] = {
        "error": error,
        "message": message,
        "status_code": status_code,
    }
    if correlation_id:
        body["correlation_id"] = correlation_id
    return api_response(status_code, body)
