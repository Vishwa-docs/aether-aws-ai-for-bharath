"""
AETHER CareOps — Backend API Server
=====================================
Lightweight FastAPI server that proxies requests to AWS services.
Used for dashboard connectivity and demo deployment.

Run: python3 api/server.py
"""

import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Load .env
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'fastapi', 'uvicorn[standard]', 'boto3'])
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn

import boto3

# ─── AWS Clients ────────────────────────────────────────────────────────

REGION = os.environ.get('AWS_REGION', 'ap-south-1')
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'apac.amazon.nova-lite-v1:0')

dynamodb = boto3.resource('dynamodb', region_name=REGION)
bedrock = boto3.client('bedrock-runtime', region_name=REGION)
polly_client = boto3.client('polly', region_name=REGION)
s3_client = boto3.client('s3', region_name=REGION)

EVENTS_TABLE = os.environ.get('EVENTS_TABLE', 'aether-events')
TIMELINE_TABLE = os.environ.get('TIMELINE_TABLE', 'aether-timeline')
RESIDENTS_TABLE = os.environ.get('RESIDENTS_TABLE', 'aether-residents')
CONSENT_TABLE = os.environ.get('CONSENT_TABLE', 'aether-consent')
CLINIC_OPS_TABLE = os.environ.get('CLINIC_OPS_TABLE', 'aether-clinic-ops')

# ─── FastAPI App ────────────────────────────────────────────────────────

app = FastAPI(
    title="AETHER CareOps API",
    description="Backend API for AETHER elderly care platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


def extract_json_from_text(text: str) -> dict:
    """Extract JSON from text that might be wrapped in markdown code blocks."""
    import re as _re
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code blocks
    patterns = [r'```json\s*(.*?)\s*```', r'```\s*(.*?)\s*```', r'\{.*\}']
    for pat in patterns:
        match = _re.search(pat, text, _re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1) if '```' in pat else match.group(0))
            except (json.JSONDecodeError, IndexError):
                continue
    return None


def to_json_safe(data):
    """Convert DynamoDB Decimal types to JSON-safe types."""
    if isinstance(data, dict):
        return {k: to_json_safe(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [to_json_safe(i) for i in data]
    elif isinstance(data, Decimal):
        if data % 1 == 0:
            return int(data)
        return float(data)
    return data


# ─── Health Check ───────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "aether-careops-api", "region": REGION, "timestamp": datetime.now(timezone.utc).isoformat()}


# ─── Residents ──────────────────────────────────────────────────────────

@app.get("/api/residents")
async def list_residents():
    table = dynamodb.Table(RESIDENTS_TABLE)
    response = table.scan(Limit=50)
    items = to_json_safe(response.get('Items', []))
    return {"residents": items, "count": len(items)}


@app.get("/api/residents/{resident_id}")
async def get_resident(resident_id: str):
    table = dynamodb.Table(RESIDENTS_TABLE)
    response = table.get_item(Key={'resident_id': resident_id})
    item = response.get('Item')
    if not item:
        raise HTTPException(status_code=404, detail=f"Resident {resident_id} not found")
    return to_json_safe(item)


# ─── Events ────────────────────────────────────────────────────────────

@app.get("/api/events")
async def get_events(home_id: str, limit: int = 50):
    table = dynamodb.Table(EVENTS_TABLE)
    from boto3.dynamodb.conditions import Key
    
    response = table.query(
        KeyConditionExpression=Key('home_id').eq(home_id),
        ScanIndexForward=False,
        Limit=limit,
    )
    items = to_json_safe(response.get('Items', []))
    return {"events": items, "count": len(items), "home_id": home_id}


@app.post("/api/events")
async def create_event(request: Request):
    body = await request.json()
    table = dynamodb.Table(EVENTS_TABLE)
    
    event_id = f'EVT-{uuid4().hex[:12]}'
    now = datetime.now(timezone.utc)
    
    item = {
        'event_id': event_id,
        'home_id': body['home_id'],
        'resident_id': body['resident_id'],
        'event_type': body['event_type'],
        'severity': body['severity'],
        'timestamp': int(now.timestamp()),
        'timestamp_iso': now.isoformat(),
        'data': body.get('data', {}),
        'confidence': Decimal(str(body.get('confidence', 0.85))),
        'source_sensors': body.get('source_sensors', []),
        'privacy_level': 'PRIVATE',
    }
    
    table.put_item(Item=item)
    return {"message": "Event created", "event_id": event_id}


# ─── Timeline ──────────────────────────────────────────────────────────

@app.get("/api/timeline/{home_id}")
async def get_timeline(home_id: str, days: int = 14):
    table = dynamodb.Table(TIMELINE_TABLE)
    from boto3.dynamodb.conditions import Key
    
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days)).strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    
    response = table.query(
        KeyConditionExpression=Key('home_id').eq(home_id) & Key('date').between(start_date, end_date),
        ScanIndexForward=True,
    )
    items = to_json_safe(response.get('Items', []))
    return {"entries": items, "count": len(items), "home_id": home_id, "start": start_date, "end": end_date}


# ─── Dashboard Stats ───────────────────────────────────────────────────

@app.get("/api/dashboard")
async def dashboard_stats(home_id: Optional[str] = None):
    if not home_id:
        # Return stats for all homes
        table = dynamodb.Table(RESIDENTS_TABLE)
        residents_response = table.scan(Limit=50)
        residents = to_json_safe(residents_response.get('Items', []))
        
        return {
            "total_residents": len(residents),
            "residents": residents,
            "active_alerts": 3,
            "pending_tasks": 5,
            "sensor_health": 94.2,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    
    # Specific home stats
    timeline_table = dynamodb.Table(TIMELINE_TABLE)
    from boto3.dynamodb.conditions import Key
    
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    
    response = timeline_table.query(
        KeyConditionExpression=Key('home_id').eq(home_id) & Key('date').between(start_date, end_date),
    )
    entries = to_json_safe(response.get('Items', []))
    
    total_events = sum(e.get('total_events', 0) for e in entries)
    total_falls = sum(e.get('fall_count', 0) for e in entries)
    
    return {
        "home_id": home_id,
        "period_days": 7,
        "total_events": total_events,
        "total_falls": total_falls,
        "entries": entries,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Care Navigation AI (Bedrock) ──────────────────────────────────────

@app.post("/api/care-navigation/query")
async def care_navigation_query(request: Request):
    body = await request.json()
    query = body.get('query', '')
    language = body.get('language', 'en')
    resident_id = body.get('resident_id', '')
    
    # Get resident context if available
    resident_context = ""
    if resident_id:
        try:
            table = dynamodb.Table(RESIDENTS_TABLE)
            response = table.get_item(Key={'resident_id': resident_id})
            resident = response.get('Item')
            if resident:
                resident_context = f"""
Patient Context:
- Name: {resident.get('name', 'Unknown')}
- Age: {resident.get('age', 'Unknown')}
- Conditions: {', '.join(resident.get('medical_conditions', []))}
- Medications: {', '.join(m['name'] + ' ' + m['dosage'] for m in resident.get('medications', []))}
- Mobility Level: {resident.get('mobility_level', 'Unknown')}
- Cognitive Status: {resident.get('cognitive_status', 'Unknown')}
"""
        except Exception:
            pass
    
    prompt = f"""You are AETHER CareOps AI, an elderly care navigation assistant. You provide evidence-based care guidance.

{resident_context}

IMPORTANT RULES:
1. Never diagnose conditions or prescribe treatments
2. Always recommend consulting a healthcare professional for medical decisions
3. Provide actionable, practical care guidance
4. Cite evidence-based sources when possible
5. Consider the patient's specific conditions and medications
6. Respond in {language} if not English

User Query: {query}

Respond in this JSON format:
{{
    "response": "Your detailed care guidance response",
    "action_tier": "self_care|gp_visit|urgent_care|emergency",
    "citations": ["list of evidence sources"],
    "follow_up_tasks": ["list of recommended follow-up actions"],
    "confidence": 0.85,
    "safety_note": "any safety considerations"
}}"""

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 1024, "temperature": 0.3},
            }),
        )
        response_body = json.loads(response['body'].read())
        ai_text = response_body.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', '{}')
        
        result = extract_json_from_text(ai_text)
        if not result:
            result = {
                "response": ai_text,
                "action_tier": "gp_visit",
                "citations": ["AETHER CareOps AI"],
                "follow_up_tasks": [],
                "confidence": 0.75,
                "safety_note": "Please consult your healthcare provider for medical decisions."
            }
        
        result["ai_model"] = BEDROCK_MODEL_ID
        result["source"] = "aws_bedrock"
        return result
        
    except Exception as e:
        print(f"Bedrock error: {e}")
        traceback.print_exc()
        return {
            "response": f"I understand you're asking about: {query}. While I'm having trouble connecting to the AI service right now, I recommend consulting your healthcare provider for personalized guidance. For immediate concerns, please contact your emergency contact or call emergency services.",
            "action_tier": "gp_visit",
            "citations": ["AETHER Care Navigation System"],
            "follow_up_tasks": ["Schedule appointment with primary care physician"],
            "confidence": 0.5,
            "safety_note": "AI service temporarily unavailable. Please consult healthcare provider.",
            "ai_model": "fallback",
            "source": "fallback",
            "error": str(e),
        }


# ─── Clinical Document Generation (Bedrock) ────────────────────────────

@app.post("/api/documents/generate")
async def generate_document(request: Request):
    body = await request.json()
    doc_type = body.get('doc_type', 'daily_summary')
    resident_id = body.get('resident_id', '')
    
    # Get resident data
    resident = None
    if resident_id:
        try:
            table = dynamodb.Table(RESIDENTS_TABLE)
            response = table.get_item(Key={'resident_id': resident_id})
            resident = to_json_safe(response.get('Item'))
        except Exception:
            pass
    
    # Get recent events
    events_data = []
    if resident and resident.get('home_id'):
        try:
            events_table = dynamodb.Table(EVENTS_TABLE)
            from boto3.dynamodb.conditions import Key
            response = events_table.query(
                KeyConditionExpression=Key('home_id').eq(resident['home_id']),
                ScanIndexForward=False,
                Limit=20,
            )
            events_data = to_json_safe(response.get('Items', []))
        except Exception:
            pass
    
    resident_info = ""
    if resident:
        resident_info = f"""
Patient: {resident.get('name', 'Unknown')} ({resident.get('age', 'Unknown')} years old)
Conditions: {', '.join(resident.get('medical_conditions', []))}
Medications: {', '.join(m['name'] + ' ' + m['dosage'] for m in resident.get('medications', []))}
Mobility: {resident.get('mobility_level', 'Unknown')}
Cognitive Status: {resident.get('cognitive_status', 'Unknown')}
Fall Risk Score: {resident.get('fall_risk_score', 'N/A')}
"""
    
    events_summary = ""
    if events_data:
        events_summary = "\nRecent Events (last 20):\n"
        for evt in events_data[:10]:
            events_summary += f"- {evt.get('event_type', 'unknown')} ({evt.get('severity', 'N/A')}) - Confidence: {evt.get('confidence', 'N/A')}\n"
    
    doc_prompts = {
        'soap_note': f"""Generate a clinical SOAP note for this elderly patient based on the following data:

{resident_info}
{events_summary}

Format as a proper SOAP note with:
- Subjective: Based on voice check-ins and reported symptoms
- Objective: Based on sensor data and vital signs  
- Assessment: Clinical assessment with risk factors
- Plan: Recommended care actions and follow-ups

Keep it professional, concise, and clinically relevant. Do NOT diagnose - provide observations only.""",

        'daily_summary': f"""Generate a comprehensive daily care summary for this elderly patient:

{resident_info}
{events_summary}

Include sections:
1. Overall Status (traffic light: green/yellow/red)
2. Key Observations
3. Medication Adherence
4. Activity & Mobility Summary
5. Sleep Quality
6. Nutrition & Hydration
7. Alerts & Concerns
8. Recommended Actions for Caregivers""",

        'weekly_report': f"""Generate a weekly health report for this elderly patient:

{resident_info}
{events_summary}

Include:
1. Week Overview
2. Health Trends (improving/stable/declining)
3. Medication Adherence Rate
4. Activity Level Trends
5. Sleep Pattern Analysis
6. Risk Assessment
7. Family/Caregiver Recommendations
8. Suggested Doctor Discussion Points""",

        'pre_consult': f"""Generate a pre-consultation summary for a telehealth/doctor visit:

{resident_info}
{events_summary}

Include:
1. Patient Summary
2. Current Medications & Adherence
3. Recent Health Events & Alerts
4. Vital Signs Trends
5. Notable Pattern Changes
6. Questions for Discussion
7. Recommended Assessments

This should help the doctor quickly understand the patient's current status.""",

        'incident_report': f"""Generate an incident report based on the following:

{resident_info}
{events_summary}

Include:
1. Incident Summary
2. Timeline of Events
3. Actions Taken
4. Response Time Analysis
5. Outcome
6. Prevention Recommendations""",
    }
    
    prompt = doc_prompts.get(doc_type, doc_prompts['daily_summary'])
    
    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 2048, "temperature": 0.3},
            }),
        )
        response_body = json.loads(response['body'].read())
        content = response_body.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', 'No content generated')
        
        return {
            "document_id": f"DOC-{uuid4().hex[:8]}",
            "doc_type": doc_type,
            "content": content,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ai_model": BEDROCK_MODEL_ID,
            "review_status": "draft",
            "resident_id": resident_id,
            "source": "aws_bedrock",
        }
    except Exception as e:
        print(f"Bedrock error: {e}")
        return {
            "document_id": f"DOC-{uuid4().hex[:8]}",
            "doc_type": doc_type,
            "content": f"[AI Service Error] Unable to generate {doc_type}. Error: {str(e)}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ai_model": "fallback",
            "review_status": "error",
            "resident_id": resident_id,
            "source": "fallback",
        }


# ─── Voice Check-in / AI Companion ─────────────────────────────────────

@app.post("/api/voice/session")
async def voice_session(request: Request):
    body = await request.json()
    resident_id = body.get('resident_id', '')
    session_type = body.get('session_type', 'companion')
    message = body.get('message', '')
    language = body.get('language', 'en')
    
    # Get resident context
    resident = None
    if resident_id:
        try:
            table = dynamodb.Table(RESIDENTS_TABLE)
            response = table.get_item(Key={'resident_id': resident_id})
            resident = to_json_safe(response.get('Item'))
        except Exception:
            pass
    
    resident_name = resident.get('name', 'there') if resident else 'there'
    resident_conditions = ', '.join(resident.get('medical_conditions', [])) if resident else 'unknown'
    
    session_prompts = {
        'daily_checkin': f"""You are AETHER, a caring AI companion for elderly individuals. You're conducting a daily wellness check-in with {resident_name}.
        
Known conditions: {resident_conditions}

Start the check-in warmly and ask about:
1. How they're feeling today
2. Any pain or discomfort
3. Sleep quality last night
4. If they've had breakfast/lunch
5. Hydration - have they been drinking water
6. Mood and emotional wellbeing

Be warm, patient, and supportive. Use simple language. If they report any concerning symptoms, note them for caregiver follow-up.
Current message from {resident_name}: {message if message else 'Starting check-in'}""",

        'companion': f"""You are AETHER, a friendly AI companion for {resident_name}, an elderly individual. 
You're having a casual, warm conversation. Be:
- Empathetic and patient
- Good listener
- Engaging in conversation about their interests
- Supportive without being patronizing
- Able to tell stories, discuss news, or reminisce

Known conditions: {resident_conditions}
Message from {resident_name}: {message if message else 'Hello!'}""",

        'medication_reminder': f"""You are AETHER, reminding {resident_name} about their medications.
Be gentle, clear, and supportive. Confirm they understand which medication to take and when.
Medications: {json.dumps([m['name'] + ' ' + m['dosage'] for m in (resident.get('medications', []) if resident else [])], indent=2)}

Message: {message if message else 'Medication reminder time'}""",

        'emergency_check': f"""You are AETHER, conducting an emergency wellness check on {resident_name}.
A sensor alert was triggered. Ask clearly and calmly:
1. "Are you okay?"
2. "Did you fall or hurt yourself?"
3. "Do you need help?"
4. "Should I call your emergency contact?"

Be calm but urgent. If they say they're in trouble, confirm you're alerting their caregiver.
Message: {message if message else 'Checking on you after an alert'}""",
    }
    
    prompt = session_prompts.get(session_type, session_prompts['companion'])
    
    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 512, "temperature": 0.7},
            }),
        )
        response_body = json.loads(response['body'].read())
        ai_text = response_body.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', 'Hello! How are you today?')
        
        # Analyze sentiment
        sentiment = "positive" if any(w in ai_text.lower() for w in ['good', 'great', 'wonderful', 'happy']) else "neutral"
        mood_score = 7.0 if sentiment == "positive" else 5.0
        follow_up = any(w in ai_text.lower() for w in ['concern', 'doctor', 'caregiver', 'emergency', 'pain', 'help'])
        
        return {
            "session_id": f"SESS-{uuid4().hex[:8]}",
            "response_text": ai_text,
            "sentiment": sentiment,
            "mood_score": mood_score,
            "follow_up_needed": follow_up,
            "insights": [],
            "session_type": session_type,
            "ai_model": BEDROCK_MODEL_ID,
            "source": "aws_bedrock",
        }
    except Exception as e:
        print(f"Bedrock error: {e}")
        return {
            "session_id": f"SESS-{uuid4().hex[:8]}",
            "response_text": f"Hello {resident_name}! I'm here for you. How are you feeling today?",
            "sentiment": "neutral",
            "mood_score": 5.0,
            "follow_up_needed": False,
            "insights": [],
            "session_type": session_type,
            "ai_model": "fallback",
            "source": "fallback",
            "error": str(e),
        }


# ─── Polypharmacy Check (Bedrock) ──────────────────────────────────────

@app.post("/api/polypharmacy/check")
async def check_polypharmacy(request: Request):
    body = await request.json()
    medications = body.get('medications', [])
    conditions = body.get('conditions', [])
    age = body.get('age', 75)
    
    med_list = "\n".join([f"- {m.get('name', 'Unknown')} {m.get('dosage', '')} ({m.get('frequency', '')})" for m in medications])
    conditions_list = ", ".join(conditions) if conditions else "Not specified"
    
    prompt = f"""You are a pharmacovigilance AI assistant. Analyze the following medication list for drug interactions and polypharmacy risks.

Patient: {age} years old
Conditions: {conditions_list}

Current Medications:
{med_list}

Analyze for:
1. Drug-drug interactions (list each pair with severity: minor/moderate/major/contraindicated)
2. Beers Criteria flags (medications potentially inappropriate for elderly)
3. Overall polypharmacy risk score (0-10)
4. Deprescribing recommendations
5. Contraindications based on patient conditions

IMPORTANT: This is for informational purposes only. Always recommend physician review.

Respond in JSON format:
{{
    "interactions": [{{"drug1": "name", "drug2": "name", "severity": "minor|moderate|major|contraindicated", "description": "explanation"}}],
    "beers_criteria_flags": ["list of flagged medications with reason"],
    "risk_score": 5.0,
    "recommendations": ["list of recommendations"],
    "contraindications": ["list of contraindications"],
    "summary": "brief overall assessment"
}}"""
    
    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 1024, "temperature": 0.2},
            }),
        )
        response_body = json.loads(response['body'].read())
        ai_text = response_body.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', '{}')
        
        result = extract_json_from_text(ai_text)
        if not result:
            result = {
                "interactions": [],
                "beers_criteria_flags": [],
                "risk_score": 0,
                "recommendations": [ai_text],
                "contraindications": [],
                "summary": ai_text[:200],
            }
        
        result["ai_model"] = BEDROCK_MODEL_ID
        result["source"] = "aws_bedrock"
        return result
        
    except Exception as e:
        print(f"Bedrock error: {e}")
        return {
            "interactions": [],
            "beers_criteria_flags": [],
            "risk_score": 0,
            "recommendations": ["Unable to analyze. Please consult your pharmacist."],
            "contraindications": [],
            "summary": f"AI service error: {str(e)}",
            "ai_model": "fallback",
            "source": "fallback",
        }


# ─── Health Insights (Bedrock) ──────────────────────────────────────────

@app.post("/api/health-insights")
async def health_insights(request: Request):
    body = await request.json()
    resident_id = body.get('resident_id', '')
    domains = body.get('domains', ['mobility', 'sleep', 'medication', 'hydration', 'mood'])
    
    # Get resident and timeline data
    resident = None
    timeline_entries = []
    
    if resident_id:
        try:
            table = dynamodb.Table(RESIDENTS_TABLE)
            response = table.get_item(Key={'resident_id': resident_id})
            resident = to_json_safe(response.get('Item'))
        except:
            pass
        
        if resident and resident.get('home_id'):
            try:
                timeline_table = dynamodb.Table(TIMELINE_TABLE)
                from boto3.dynamodb.conditions import Key
                now = datetime.now(timezone.utc)
                response = timeline_table.query(
                    KeyConditionExpression=Key('home_id').eq(resident['home_id']) & Key('date').between(
                        (now - timedelta(days=14)).strftime('%Y-%m-%d'),
                        now.strftime('%Y-%m-%d')
                    ),
                )
                timeline_entries = to_json_safe(response.get('Items', []))
            except:
                pass
    
    timeline_summary = ""
    for entry in timeline_entries[-7:]:
        timeline_summary += f"Date: {entry.get('date', 'N/A')}, Events: {entry.get('total_events', 0)}, Falls: {entry.get('fall_count', 0)}, Adherence: {entry.get('medication_adherence_pct', 'N/A')}%, Sleep: {entry.get('sleep_hours', 'N/A')}h, Steps: {entry.get('steps', 'N/A')}, Mood: {entry.get('mood_score', 'N/A')}\n"
    
    prompt = f"""You are AETHER Health Insights AI. Analyze the following patient data and provide health insights.

Patient: {resident.get('name', 'Unknown') if resident else 'Unknown'} (Age: {resident.get('age', 'Unknown') if resident else 'Unknown'})
Conditions: {', '.join(resident.get('medical_conditions', [])) if resident else 'Unknown'}

Recent Timeline Data (last 7 days):
{timeline_summary}

Analyze for domains: {', '.join(domains)}

Provide insights in JSON format:
{{
    "overall_status": "green|yellow|red",
    "risk_score": 5.0,
    "domain_scores": {{"mobility": 7.5, "sleep": 6.0, ...}},
    "trends": {{"mobility": "improving|stable|declining", ...}},
    "insights": ["list of key observations"],
    "alerts": ["list of concerning patterns"],
    "recommendations": ["list of actionable recommendations"],
    "drift_detection": {{"detected": false, "patterns": []}}
}}

IMPORTANT: Do not diagnose. Provide observational insights only."""

    try:
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {"maxTokens": 1024, "temperature": 0.3},
            }),
        )
        response_body = json.loads(response['body'].read())
        ai_text = response_body.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', '{}')
        
        result = extract_json_from_text(ai_text)
        if not result:
            result = {
                "overall_status": "yellow",
                "risk_score": 5.0,
                "insights": [ai_text],
                "recommendations": [],
            }
        
        result["ai_model"] = BEDROCK_MODEL_ID
        result["source"] = "aws_bedrock"
        result["resident_id"] = resident_id
        return result
        
    except Exception as e:
        return {
            "overall_status": "yellow",
            "risk_score": 5.0,
            "insights": ["Health insights analysis temporarily unavailable"],
            "recommendations": ["Continue regular monitoring"],
            "source": "fallback",
            "error": str(e),
        }


# ─── Escalation Management ─────────────────────────────────────────────

@app.post("/api/escalation/trigger")
async def trigger_escalation(request: Request):
    body = await request.json()
    event_id = body.get('event_id', '')
    home_id = body.get('home_id', '')
    tier = body.get('tier', 1)
    reason = body.get('reason', 'Manual escalation')
    
    escalation_tiers = {
        1: {"action": "Voice prompt to resident", "response_time": "30 seconds", "contact": "AI Voice System"},
        2: {"action": "Notify primary caregiver", "response_time": "2 minutes", "contact": "Family Caregiver"},
        3: {"action": "Notify secondary caregiver + nurse", "response_time": "5 minutes", "contact": "Nurse Hotline"},
        4: {"action": "Emergency services notification", "response_time": "Immediate", "contact": "Emergency Services"},
    }
    
    tier_info = escalation_tiers.get(tier, escalation_tiers[1])
    
    return {
        "escalation_id": f"ESC-{uuid4().hex[:8]}",
        "event_id": event_id,
        "home_id": home_id,
        "tier": tier,
        "action": tier_info["action"],
        "response_time": tier_info["response_time"],
        "contact": tier_info["contact"],
        "reason": reason,
        "status": "triggered",
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Alerts Management ─────────────────────────────────────────────────

@app.post("/api/alerts/acknowledge")
async def acknowledge_alert(request: Request):
    body = await request.json()
    return {
        "message": "Alert acknowledged",
        "event_id": body.get('event_id'),
        "acknowledged_by": body.get('acknowledged_by', 'caregiver'),
        "acknowledged_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Analytics ──────────────────────────────────────────────────────────

@app.get("/api/analytics")
async def analytics(home_id: str, period: str = "7d"):
    import re as regex
    period_match = regex.match(r"^(\d+)d$", period)
    period_days = int(period_match.group(1)) if period_match else 7
    
    timeline_table = dynamodb.Table(TIMELINE_TABLE)
    from boto3.dynamodb.conditions import Key
    
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=period_days)).strftime('%Y-%m-%d')
    end_date = now.strftime('%Y-%m-%d')
    
    response = timeline_table.query(
        KeyConditionExpression=Key('home_id').eq(home_id) & Key('date').between(start_date, end_date),
    )
    entries = to_json_safe(response.get('Items', []))
    
    total_events = sum(e.get('total_events', 0) for e in entries)
    total_falls = sum(e.get('fall_count', 0) for e in entries)
    adherences = [e.get('medication_adherence_pct', 100) for e in entries]
    avg_adherence = sum(adherences) / len(adherences) if adherences else 100
    
    return {
        "home_id": home_id,
        "period": period,
        "total_events": total_events,
        "total_falls": total_falls,
        "avg_adherence": round(avg_adherence, 1),
        "daily": entries,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Text-to-Speech (Polly) ────────────────────────────────────────────

@app.post("/api/voice/synthesize")
async def synthesize_speech(request: Request):
    body = await request.json()
    text = body.get('text', 'Hello')
    voice_id = body.get('voice_id', 'Kajal')
    language = body.get('language', 'en-IN')
    
    try:
        response = polly_client.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id,
            Engine='neural',
            LanguageCode=language,
        )
        
        return {
            "message": "Speech synthesized",
            "content_type": response.get('ContentType', 'audio/mpeg'),
            "characters": len(text),
            "voice_id": voice_id,
            "source": "aws_polly",
        }
    except Exception as e:
        return {
            "message": "Speech synthesis failed",
            "error": str(e),
            "source": "fallback",
        }


# ─── Sensor Simulation / Edge Gateway ──────────────────────────────────

@app.post("/api/simulate/event")
async def simulate_event(request: Request):
    """Simulate a sensor event (for demo purposes)."""
    body = await request.json()
    scenario = body.get('scenario', 'fall_detection')
    resident_id = body.get('resident_id', 'RES-001')
    
    scenarios = {
        'fall_detection': {
            'event_type': 'fall_detected',
            'severity': 'CRITICAL',
            'data': {
                'fall_type': 'forward',
                'impact_force': 5.2,
                'location': 'bathroom',
                'pose_confidence': 0.92,
                'acoustic_confidence': 0.78,
                'imu_confidence': 0.95,
                'fusion_score': 0.89,
            },
            'source_sensors': ['pose_camera', 'acoustic_sensor', 'imu_sensor'],
        },
        'medication_missed': {
            'event_type': 'medication_missed',
            'severity': 'HIGH',
            'data': {
                'medication': 'Metformin',
                'dosage': '500mg',
                'scheduled_time': '08:00',
                'hours_overdue': 3.5,
            },
            'source_sensors': ['pressure_sensor', 'schedule_engine'],
        },
        'choking_detected': {
            'event_type': 'choking_detected',
            'severity': 'CRITICAL',
            'data': {
                'acoustic_confidence': 0.87,
                'duration_seconds': 5,
                'location': 'dining_room',
            },
            'source_sensors': ['acoustic_sensor', 'pose_camera'],
        },
        'wandering': {
            'event_type': 'wandering_detected',
            'severity': 'HIGH',
            'data': {
                'door': 'front_door',
                'time_of_day': 'night',
                'outdoor_temperature': 15,
            },
            'source_sensors': ['contact_sensor', 'pir_sensor'],
        },
        'vital_anomaly': {
            'event_type': 'vital_anomaly',
            'severity': 'HIGH',
            'data': {
                'heart_rate': 105,
                'blood_pressure': '155/92',
                'spo2': 89,
                'temperature': 37.8,
            },
            'source_sensors': ['smartwatch', 'pulse_oximeter'],
        },
    }
    
    scenario_data = scenarios.get(scenario, scenarios['fall_detection'])
    
    # Get resident info
    resident = None
    try:
        table = dynamodb.Table(RESIDENTS_TABLE)
        response = table.get_item(Key={'resident_id': resident_id})
        resident = to_json_safe(response.get('Item'))
    except:
        pass
    
    home_id = resident.get('home_id', 'HOME-001') if resident else 'HOME-001'
    
    # Create and store event
    event_id = f'EVT-{uuid4().hex[:12]}'
    now = datetime.now(timezone.utc)
    
    event_item = {
        'event_id': event_id,
        'home_id': home_id,
        'resident_id': resident_id,
        'event_type': scenario_data['event_type'],
        'severity': scenario_data['severity'],
        'timestamp': int(now.timestamp()),
        'timestamp_iso': now.isoformat(),
        'data': scenario_data['data'],
        'confidence': Decimal('0.89'),
        'source_sensors': scenario_data['source_sensors'],
        'privacy_level': 'PRIVATE',
        'simulated': True,
    }
    
    try:
        events_table = dynamodb.Table(EVENTS_TABLE)
        events_table.put_item(Item=event_item)
    except Exception as e:
        print(f"Failed to store event: {e}")
    
    return {
        "message": f"Scenario '{scenario}' triggered",
        "event_id": event_id,
        "event_type": scenario_data['event_type'],
        "severity": scenario_data['severity'],
        "resident_id": resident_id,
        "home_id": home_id,
        "timestamp": now.isoformat(),
        "data": scenario_data['data'],
    }


# ─── Main ──────────────────────────────────────────────────────────────

# Serve React dashboard static files (production)
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dashboard', 'dist')
if os.path.exists(STATIC_DIR):
    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="static-assets")

    # Serve other static files (manifest, icons, etc.)
    @app.get("/manifest.json")
    async def serve_manifest():
        fpath = os.path.join(STATIC_DIR, "manifest.json")
        if os.path.exists(fpath):
            return FileResponse(fpath, media_type="application/json")
        raise HTTPException(status_code=404)

    # SPA catch-all: serve index.html for any non-API route
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Don't catch API routes
        if full_path.startswith("api/") or full_path == "docs" or full_path == "openapi.json":
            raise HTTPException(status_code=404)
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path, media_type="text/html")
        raise HTTPException(status_code=404)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8001))
    print(f"\n🚀 AETHER CareOps API starting on port {port}")
    print(f"   Region: {REGION}")
    print(f"   Bedrock Model: {BEDROCK_MODEL_ID}")
    if os.path.exists(STATIC_DIR):
        print(f"   Dashboard: Serving from {STATIC_DIR}")
    else:
        print(f"   Dashboard: Not built (run 'cd dashboard && npm run build')")
    print(f"   Docs: http://localhost:{port}/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
