"""
AETHER Ride Booking & Ordering Agent Lambda (DEMO ONLY)
========================================================
Accepts natural-language requests from elders and simulates booking rides,
ordering food, scheduling appointments, and shopping. All operations are
SIMULATED for demo purposes only.

Endpoints
---------
POST /api/bookings/request     – Submit a natural-language request
POST /api/bookings/cancel      – Cancel an existing booking
GET  /api/bookings/{booking_id} – Get booking details
GET  /api/bookings?resident_id=X – List bookings for a resident

⚠️ DEMO ONLY: No real transactions are executed.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import traceback
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.models import (
    Booking,
    get_current_timestamp,
)
from shared.utils import (
    api_error,
    api_response,
    bedrock_model_id,
    dynamo_get_item,
    dynamo_put_item,
    dynamo_query_items,
    dynamo_update_item,
    generate_correlation_id,
    get_env,
    invoke_bedrock_model,
    json_dumps,
    log_with_context,
    setup_logger,
    sns_publish_structured_alert,
    alerts_topic_arn,
)

logger = setup_logger("ride_booking")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BOOKINGS_TABLE = get_env("BOOKINGS_TABLE", "aether-bookings")
BEDROCK_MODEL = get_env("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")

# Valid booking types
BOOKING_TYPES = {"transport", "food_order", "appointment", "shopping"}

# Simulated service providers
TRANSPORT_PROVIDERS = ["Ola", "Uber", "Auto Stand", "Rapido"]
FOOD_PROVIDERS = ["Zomato", "Swiggy", "Local Kitchen"]
VEHICLE_TYPES = ["Auto", "Mini", "Sedan", "XL"]


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


def _generate_booking_id() -> str:
    return f"bk-{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# POST /api/bookings/request
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/bookings/request/?$")
def _post_request(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Process a natural-language booking request from an elder."""
    body = _parse_body(event)
    request_text = body.get("request", "").strip()
    resident_id = body.get("resident_id")
    home_id = body.get("home_id", "unknown")

    if not request_text:
        return api_error(400, "missing_parameter", "request text is required", correlation_id)
    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id is required", correlation_id)

    log_with_context(
        logger, "INFO",
        f"Processing booking request from resident {resident_id}",
        correlation_id=correlation_id,
        request_length=len(request_text),
    )

    # --- 1. Parse intent with Bedrock ------------------------------------------
    parsed_intent = _parse_intent(request_text, correlation_id)
    booking_type = parsed_intent.get("type", "transport")

    if booking_type not in BOOKING_TYPES:
        booking_type = "transport"  # fallback

    log_with_context(
        logger, "INFO",
        f"Parsed intent: type={booking_type}",
        correlation_id=correlation_id,
    )

    # --- 2. Simulate booking based on type -------------------------------------
    booking_id = _generate_booking_id()
    now = get_current_timestamp()

    if booking_type == "transport":
        details = _simulate_transport(parsed_intent)
    elif booking_type == "food_order":
        details = _simulate_food_order(parsed_intent)
    elif booking_type == "appointment":
        details = _simulate_appointment(parsed_intent)
    elif booking_type == "shopping":
        details = _simulate_shopping(parsed_intent)
    else:
        details = {"description": "General request processed"}

    # --- 3. Generate confirmation message --------------------------------------
    confirmation = _generate_confirmation(booking_type, details, correlation_id)

    # --- 4. Build and store booking record -------------------------------------
    booking = Booking(
        booking_id=booking_id,
        resident_id=resident_id,
        home_id=home_id,
        booking_type=booking_type,
        status="confirmed",
        request_text=request_text,
        parsed_intent=parsed_intent,
        details=details,
        confirmation_message=confirmation,
        demo_only=True,
        created_at=now,
        updated_at=now,
        correlation_id=correlation_id,
    )

    dynamo_put_item(BOOKINGS_TABLE, booking.to_dict())

    # --- 5. Notify caregiver ---------------------------------------------------
    _notify_caregiver(booking, correlation_id)

    return api_response(200, {
        "booking_id": booking_id,
        "type": booking_type,
        "status": "confirmed",
        "details": details,
        "confirmation_message": confirmation,
        "demo_only": True,
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# POST /api/bookings/cancel
# ---------------------------------------------------------------------------

@_route("POST", r"^/api/bookings/cancel/?$")
def _post_cancel(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Cancel an existing booking."""
    body = _parse_body(event)
    booking_id = body.get("booking_id")
    reason = body.get("reason", "Cancelled by user")

    if not booking_id:
        return api_error(400, "missing_parameter", "booking_id is required", correlation_id)

    # Fetch existing booking
    item = dynamo_get_item(
        table_name=BOOKINGS_TABLE,
        key={"booking_id": booking_id},
    )

    if not item:
        return api_error(404, "not_found", f"Booking {booking_id} not found", correlation_id)

    if item.get("status") == "cancelled":
        return api_error(400, "already_cancelled", "This booking is already cancelled", correlation_id)

    # Update status
    from boto3.dynamodb.conditions import Attr

    dynamo_update_item(
        table_name=BOOKINGS_TABLE,
        key={"booking_id": booking_id},
        update_expression="SET #status = :status, updated_at = :updated, cancellation_reason = :reason",
        expression_attribute_names={"#status": "status"},
        expression_attribute_values={
            ":status": "cancelled",
            ":updated": get_current_timestamp(),
            ":reason": reason,
        },
    )

    log_with_context(
        logger, "INFO",
        f"Booking {booking_id} cancelled",
        correlation_id=correlation_id,
    )

    return api_response(200, {
        "booking_id": booking_id,
        "status": "cancelled",
        "reason": reason,
        "demo_only": True,
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# GET /api/bookings/{booking_id}
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/bookings/(?P<booking_id>bk-[a-f0-9]+)/?$")
def _get_booking(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """Retrieve a booking by ID."""
    booking_id = match.group("booking_id")

    item = dynamo_get_item(
        table_name=BOOKINGS_TABLE,
        key={"booking_id": booking_id},
    )

    if not item:
        return api_error(404, "not_found", f"Booking {booking_id} not found", correlation_id)

    return api_response(200, {**item, "correlation_id": correlation_id})


# ---------------------------------------------------------------------------
# GET /api/bookings?resident_id=X
# ---------------------------------------------------------------------------

@_route("GET", r"^/api/bookings/?$")
def _list_bookings(
    event: Dict[str, Any],
    match: re.Match,
    correlation_id: str,
) -> Dict[str, Any]:
    """List bookings for a resident."""
    from boto3.dynamodb.conditions import Key

    resident_id = _query_param(event, "resident_id")
    if not resident_id:
        return api_error(400, "missing_parameter", "resident_id is required", correlation_id)

    status_filter = _query_param(event, "status")

    items, _ = dynamo_query_items(
        table_name=BOOKINGS_TABLE,
        key_condition_expression=Key("resident_id").eq(resident_id),
        index_name="resident-index",
        scan_forward=False,
        limit=50,
    )

    if status_filter:
        items = [i for i in items if i.get("status") == status_filter]

    return api_response(200, {
        "resident_id": resident_id,
        "bookings": items,
        "count": len(items),
        "correlation_id": correlation_id,
    })


# ---------------------------------------------------------------------------
# Intent parsing
# ---------------------------------------------------------------------------

def _parse_intent(request_text: str, correlation_id: str) -> Dict[str, Any]:
    """Use Bedrock to parse the natural-language request into structured intent."""
    prompt = f"""You are a helpful assistant for AETHER, an elderly care system.
Parse the following natural-language request from an elderly person into a structured intent.

REQUEST: "{request_text}"

Determine the intent type and extract relevant details.
Return a JSON object with:
- "type": one of "transport", "food_order", "appointment", "shopping"
- "destination": where they want to go (for transport)
- "pickup": pickup location if mentioned
- "items": list of items (for food/shopping)
- "restaurant": restaurant name if mentioned
- "doctor_type": doctor specialty if mentioned (for appointment)
- "preferred_time": preferred time if mentioned
- "urgency": "normal" or "urgent"
- "notes": any additional context

Return ONLY the JSON object."""

    try:
        response_text = invoke_bedrock_model(
            prompt=prompt,
            model_id=BEDROCK_MODEL,
            max_tokens=512,
            temperature=0.2,
        )
        return _extract_json_object(response_text)
    except Exception as exc:
        log_with_context(
            logger, "WARNING",
            f"Intent parsing failed, using fallback: {exc}",
            correlation_id=correlation_id,
        )
        # Simple keyword-based fallback
        text_lower = request_text.lower()
        if any(kw in text_lower for kw in ["food", "order", "eat", "zomato", "swiggy", "hungry"]):
            return {"type": "food_order", "notes": request_text}
        elif any(kw in text_lower for kw in ["doctor", "appointment", "clinic", "checkup"]):
            return {"type": "appointment", "notes": request_text}
        elif any(kw in text_lower for kw in ["buy", "shop", "store", "grocery", "medicine"]):
            return {"type": "shopping", "notes": request_text}
        else:
            return {"type": "transport", "destination": request_text, "notes": request_text}


# ---------------------------------------------------------------------------
# Simulated booking handlers
# ---------------------------------------------------------------------------

def _simulate_transport(intent: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate a ride booking."""
    destination = intent.get("destination", "Hospital")
    pickup = intent.get("pickup", "Home")
    provider = random.choice(TRANSPORT_PROVIDERS)
    vehicle = random.choice(VEHICLE_TYPES)
    eta_minutes = random.randint(5, 20)
    distance_km = round(random.uniform(2.0, 25.0), 1)
    cost_inr = round(distance_km * random.uniform(8.0, 15.0), 0)

    arrival = datetime.now(timezone.utc) + timedelta(minutes=eta_minutes)

    return {
        "service": "transport",
        "provider": provider,
        "vehicle_type": vehicle,
        "driver_name": f"Driver_{random.randint(100, 999)}",
        "driver_phone": f"+91-98765-{random.randint(10000, 99999)}",
        "pickup_location": pickup,
        "destination": destination,
        "eta_minutes": eta_minutes,
        "estimated_arrival": arrival.isoformat().replace("+00:00", "Z"),
        "distance_km": distance_km,
        "estimated_cost_inr": int(cost_inr),
        "vehicle_number": f"KA-{random.randint(10, 99)}-{random.choice('ABCDEFGH')}-{random.randint(1000, 9999)}",
        "tracking_url": f"https://demo.aether.care/track/T{random.randint(100000, 999999)}",
        "demo_only": True,
    }


def _simulate_food_order(intent: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate a food order."""
    restaurant = intent.get("restaurant", random.choice(["Anna's Kitchen", "Sagar Restaurant", "Mom's Tiffin", "Fresh & Healthy"]))
    items = intent.get("items") or ["Meal combo"]
    provider = random.choice(FOOD_PROVIDERS)
    delivery_minutes = random.randint(25, 50)
    cost_inr = random.randint(150, 500)

    delivery_time = datetime.now(timezone.utc) + timedelta(minutes=delivery_minutes)

    return {
        "service": "food_order",
        "provider": provider,
        "restaurant": restaurant,
        "items": items if isinstance(items, list) else [items],
        "delivery_time_minutes": delivery_minutes,
        "estimated_delivery": delivery_time.isoformat().replace("+00:00", "Z"),
        "total_cost_inr": cost_inr,
        "order_id": f"ORD-{random.randint(100000, 999999)}",
        "delivery_partner": f"Delivery_{random.randint(100, 999)}",
        "tracking_url": f"https://demo.aether.care/track/F{random.randint(100000, 999999)}",
        "special_instructions": "Elderly-friendly packaging. Less spicy.",
        "demo_only": True,
    }


def _simulate_appointment(intent: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate a doctor appointment booking."""
    doctor_type = intent.get("doctor_type", "General Physician")
    preferred_time = intent.get("preferred_time", "morning")

    # Simulate slot finding
    now = datetime.now(timezone.utc)
    if "urgent" in str(intent.get("urgency", "")).lower():
        slot = now + timedelta(hours=random.randint(2, 6))
    else:
        slot = now + timedelta(days=random.randint(1, 3), hours=random.randint(9, 16))

    doctor_names = [
        "Dr. Sharma", "Dr. Patel", "Dr. Reddy", "Dr. Gupta",
        "Dr. Iyer", "Dr. Mehta", "Dr. Kumar",
    ]

    return {
        "service": "appointment",
        "doctor_name": random.choice(doctor_names),
        "specialty": doctor_type,
        "clinic_name": f"{doctor_type} Clinic",
        "appointment_time": slot.isoformat().replace("+00:00", "Z"),
        "appointment_date": slot.strftime("%Y-%m-%d"),
        "appointment_slot": slot.strftime("%I:%M %p"),
        "clinic_address": "123 Health Street, Bangalore 560001",
        "clinic_phone": f"+91-80-{random.randint(20000000, 29999999)}",
        "consultation_fee_inr": random.choice([300, 500, 700, 1000]),
        "reminder_set": True,
        "reminder_time": (slot - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "confirmation_code": f"APT-{random.randint(10000, 99999)}",
        "demo_only": True,
    }


def _simulate_shopping(intent: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate a shopping/grocery order."""
    items = intent.get("items") or ["General items"]
    delivery_minutes = random.randint(30, 90)
    cost_inr = random.randint(200, 2000)

    delivery_time = datetime.now(timezone.utc) + timedelta(minutes=delivery_minutes)

    return {
        "service": "shopping",
        "store": random.choice(["BigBasket", "Dunzo", "More Supermarket", "Local Store"]),
        "items": items if isinstance(items, list) else [items],
        "delivery_time_minutes": delivery_minutes,
        "estimated_delivery": delivery_time.isoformat().replace("+00:00", "Z"),
        "total_cost_inr": cost_inr,
        "order_id": f"SHP-{random.randint(100000, 999999)}",
        "delivery_partner": f"Delivery_{random.randint(100, 999)}",
        "tracking_url": f"https://demo.aether.care/track/S{random.randint(100000, 999999)}",
        "substitution_policy": "Call before substituting",
        "demo_only": True,
    }


# ---------------------------------------------------------------------------
# Confirmation message generation
# ---------------------------------------------------------------------------

def _generate_confirmation(
    booking_type: str,
    details: Dict[str, Any],
    correlation_id: str,
) -> str:
    """Generate a friendly confirmation message for the elder."""
    try:
        if booking_type == "transport":
            return (
                f"Your {details.get('vehicle_type', 'ride')} has been booked! 🚗\n"
                f"Driver: {details.get('driver_name', 'Assigned')}\n"
                f"Vehicle: {details.get('vehicle_number', '')}\n"
                f"From: {details.get('pickup_location', 'Home')}\n"
                f"To: {details.get('destination', 'Destination')}\n"
                f"ETA: {details.get('eta_minutes', '?')} minutes\n"
                f"Cost: ₹{details.get('estimated_cost_inr', '?')}\n"
                f"[DEMO - No real booking made]"
            )
        elif booking_type == "food_order":
            items = ", ".join(details.get("items", ["Meal"]))
            return (
                f"Your food order has been placed! 🍽️\n"
                f"Restaurant: {details.get('restaurant', 'Restaurant')}\n"
                f"Items: {items}\n"
                f"Delivery in: {details.get('delivery_time_minutes', '?')} minutes\n"
                f"Cost: ₹{details.get('total_cost_inr', '?')}\n"
                f"[DEMO - No real order placed]"
            )
        elif booking_type == "appointment":
            return (
                f"Your appointment has been booked! 🏥\n"
                f"Doctor: {details.get('doctor_name', 'Doctor')}\n"
                f"Specialty: {details.get('specialty', '')}\n"
                f"Date: {details.get('appointment_date', '')}\n"
                f"Time: {details.get('appointment_slot', '')}\n"
                f"Fee: ₹{details.get('consultation_fee_inr', '?')}\n"
                f"A reminder will be sent 2 hours before.\n"
                f"[DEMO - No real appointment made]"
            )
        elif booking_type == "shopping":
            items = ", ".join(details.get("items", ["Items"]))
            return (
                f"Your order has been placed! 🛒\n"
                f"Store: {details.get('store', 'Store')}\n"
                f"Items: {items}\n"
                f"Delivery in: {details.get('delivery_time_minutes', '?')} minutes\n"
                f"Cost: ₹{details.get('total_cost_inr', '?')}\n"
                f"[DEMO - No real order placed]"
            )
        else:
            return "Your request has been processed. [DEMO]"
    except Exception:
        return "Your request has been confirmed. [DEMO - No real booking made]"


# ---------------------------------------------------------------------------
# Caregiver notification
# ---------------------------------------------------------------------------

def _notify_caregiver(booking: Booking, correlation_id: str) -> None:
    """Notify caregiver about a new booking."""
    topic_arn = alerts_topic_arn()
    if not topic_arn:
        return

    message = (
        f"Booking Notification (DEMO)\n"
        f"Resident: {booking.resident_id}\n"
        f"Type: {booking.booking_type}\n"
        f"Status: {booking.status}\n"
        f"Booking ID: {booking.booking_id}\n\n"
        f"Details:\n{json_dumps(booking.details, indent=2)}\n\n"
        f"⚠️ This is a DEMO booking – no real transaction was made."
    )

    try:
        sns_publish_structured_alert(
            topic_arn=topic_arn,
            event_type="booking_created",
            severity="INFO",
            home_id=booking.home_id,
            message=message,
        )
    except Exception as exc:
        log_with_context(
            logger, "ERROR",
            f"Failed to notify caregiver: {exc}",
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _extract_json_object(text: str) -> Dict[str, Any]:
    """Extract a JSON object from model response text."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return {"type": "transport", "notes": text}
