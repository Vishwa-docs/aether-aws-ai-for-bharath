"""
AETHER CareOps Platform — DynamoDB Seed Script
================================================
Seeds all 5 DynamoDB tables with realistic demo data for 3 residents.
Run: python scripts/seed_dynamodb.py
"""

import boto3
import json
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

# Load .env if present
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

REGION = os.environ.get('AWS_REGION', 'ap-south-1')
dynamodb = boto3.resource('dynamodb', region_name=REGION)

TABLES = {
    'events': os.environ.get('EVENTS_TABLE', 'aether-events'),
    'timeline': os.environ.get('TIMELINE_TABLE', 'aether-timeline'),
    'residents': os.environ.get('RESIDENTS_TABLE', 'aether-residents'),
    'consent': os.environ.get('CONSENT_TABLE', 'aether-consent'),
    'clinic_ops': os.environ.get('CLINIC_OPS_TABLE', 'aether-clinic-ops'),
}

# ─── Residents ──────────────────────────────────────────────────────────

RESIDENTS = [
    {
        'resident_id': 'RES-001',
        'name': 'Kamala Devi',
        'date_of_birth': '1951-03-15',
        'age': 75,
        'gender': 'Female',
        'home_id': 'HOME-001',
        'room': 'Master Bedroom',
        'photo_url': '',
        'medical_conditions': ['Type 2 Diabetes', 'Hypertension', 'Mild Arthritis', 'Early Cognitive Decline'],
        'medications': [
            {'name': 'Metformin', 'dosage': '500mg', 'frequency': 'twice_daily', 'timing': ['08:00', '20:00']},
            {'name': 'Amlodipine', 'dosage': '5mg', 'frequency': 'once_daily', 'timing': ['08:00']},
            {'name': 'Aspirin', 'dosage': '75mg', 'frequency': 'once_daily', 'timing': ['08:00']},
            {'name': 'Calcium + Vitamin D', 'dosage': '500mg', 'frequency': 'once_daily', 'timing': ['12:00']},
        ],
        'emergency_contacts': [
            {'name': 'Arjun Mehta', 'relationship': 'Son', 'phone': '+91-9876543210', 'priority': 1},
            {'name': 'Priya Mehta', 'relationship': 'Daughter-in-law', 'phone': '+91-9876543211', 'priority': 2},
            {'name': 'Dr. Suresh Kumar', 'relationship': 'Primary Doctor', 'phone': '+91-9876543212', 'priority': 3},
        ],
        'mobility_level': 'moderate',
        'cognitive_status': 'mild_impairment',
        'fall_risk_score': 6.5,
        'preferences': {
            'language': 'hi',
            'voice_enabled': True,
            'privacy_mode': 'event_plus_stats',
            'wake_time': '06:30',
            'sleep_time': '21:30',
            'meal_times': ['08:00', '12:30', '19:00'],
        },
        'baseline': {
            'avg_steps': 3200,
            'avg_sleep_hours': 6.5,
            'avg_heart_rate': 72,
            'avg_hydration_ml': 1800,
            'nighttime_bathroom_visits': 1.5,
        },
        'status': 'active',
        'created_at': '2026-02-25T10:00:00Z',
        'updated_at': '2026-03-08T10:00:00Z',
    },
    {
        'resident_id': 'RES-002',
        'name': 'Rajesh Sharma',
        'date_of_birth': '1948-07-22',
        'age': 77,
        'gender': 'Male',
        'home_id': 'HOME-002',
        'room': 'Ground Floor Suite',
        'photo_url': '',
        'medical_conditions': ['COPD', 'Atrial Fibrillation', 'Osteoporosis', 'Mild Depression'],
        'medications': [
            {'name': 'Tiotropium Inhaler', 'dosage': '18mcg', 'frequency': 'once_daily', 'timing': ['07:00']},
            {'name': 'Warfarin', 'dosage': '5mg', 'frequency': 'once_daily', 'timing': ['18:00']},
            {'name': 'Sertraline', 'dosage': '50mg', 'frequency': 'once_daily', 'timing': ['08:00']},
            {'name': 'Calcium + D3', 'dosage': '1000mg', 'frequency': 'once_daily', 'timing': ['12:00']},
            {'name': 'Salbutamol Inhaler', 'dosage': '100mcg', 'frequency': 'as_needed', 'timing': []},
        ],
        'emergency_contacts': [
            {'name': 'Meera Sharma', 'relationship': 'Wife', 'phone': '+91-9876543220', 'priority': 1},
            {'name': 'Vikram Sharma', 'relationship': 'Son', 'phone': '+91-9876543221', 'priority': 2},
        ],
        'mobility_level': 'limited',
        'cognitive_status': 'normal',
        'fall_risk_score': 7.8,
        'preferences': {
            'language': 'en',
            'voice_enabled': True,
            'privacy_mode': 'event_only',
            'wake_time': '06:00',
            'sleep_time': '22:00',
            'meal_times': ['07:30', '12:00', '19:30'],
        },
        'baseline': {
            'avg_steps': 1800,
            'avg_sleep_hours': 5.8,
            'avg_heart_rate': 78,
            'avg_hydration_ml': 1500,
            'nighttime_bathroom_visits': 2.5,
        },
        'status': 'active',
        'created_at': '2026-02-25T10:00:00Z',
        'updated_at': '2026-03-08T10:00:00Z',
    },
    {
        'resident_id': 'RES-003',
        'name': 'Lakshmi Iyer',
        'date_of_birth': '1953-11-08',
        'age': 72,
        'gender': 'Female',
        'home_id': 'HOME-003',
        'room': 'Assisted Living Unit 4B',
        'photo_url': '',
        'medical_conditions': ['Type 1 Diabetes', 'Diabetic Neuropathy', 'Glaucoma', 'Hypothyroidism'],
        'medications': [
            {'name': 'Insulin Glargine', 'dosage': '20 units', 'frequency': 'once_daily', 'timing': ['22:00']},
            {'name': 'Insulin Lispro', 'dosage': '8 units', 'frequency': 'thrice_daily', 'timing': ['08:00', '13:00', '19:00']},
            {'name': 'Levothyroxine', 'dosage': '50mcg', 'frequency': 'once_daily', 'timing': ['06:30']},
            {'name': 'Timolol Eye Drops', 'dosage': '0.5%', 'frequency': 'twice_daily', 'timing': ['08:00', '20:00']},
            {'name': 'Pregabalin', 'dosage': '75mg', 'frequency': 'twice_daily', 'timing': ['08:00', '20:00']},
        ],
        'emergency_contacts': [
            {'name': 'Sanjay Iyer', 'relationship': 'Son', 'phone': '+91-9876543230', 'priority': 1},
            {'name': 'Facility Nurse Station', 'relationship': 'Facility', 'phone': '+91-9876543231', 'priority': 2},
        ],
        'mobility_level': 'moderate',
        'cognitive_status': 'normal',
        'fall_risk_score': 5.2,
        'preferences': {
            'language': 'ta',
            'voice_enabled': True,
            'privacy_mode': 'event_plus_vectors',
            'wake_time': '05:30',
            'sleep_time': '21:00',
            'meal_times': ['07:30', '12:30', '19:00'],
        },
        'baseline': {
            'avg_steps': 4100,
            'avg_sleep_hours': 7.0,
            'avg_heart_rate': 68,
            'avg_hydration_ml': 2000,
            'nighttime_bathroom_visits': 1.0,
        },
        'status': 'active',
        'created_at': '2026-02-25T10:00:00Z',
        'updated_at': '2026-03-08T10:00:00Z',
    },
]

# ─── Event types ────────────────────────────────────────────────────────

EVENT_TYPES = [
    ('fall_detected', 'CRITICAL', ['imu_sensor', 'pose_camera', 'acoustic_sensor']),
    ('fall_detected', 'HIGH', ['imu_sensor', 'pose_camera']),
    ('medication_taken', 'INFO', ['pressure_sensor', 'nfc_reader']),
    ('medication_missed', 'HIGH', ['pressure_sensor', 'schedule_engine']),
    ('medication_late', 'MEDIUM', ['pressure_sensor', 'schedule_engine']),
    ('meal_detected', 'INFO', ['load_cell', 'utensil_sensor']),
    ('meal_skipped', 'MEDIUM', ['load_cell', 'schedule_engine']),
    ('hydration_low', 'MEDIUM', ['bottle_sensor', 'schedule_engine']),
    ('sleep_disrupted', 'LOW', ['bed_sensor', 'acoustic_sensor']),
    ('bed_exit_night', 'MEDIUM', ['bed_sensor', 'pir_sensor']),
    ('vital_anomaly', 'HIGH', ['smartwatch', 'pulse_oximeter']),
    ('vital_reading', 'INFO', ['smartwatch']),
    ('voice_checkin_complete', 'INFO', ['microphone', 'voice_engine']),
    ('environment_alert', 'HIGH', ['temp_sensor', 'humidity_sensor']),
    ('air_quality_poor', 'MEDIUM', ['co2_sensor', 'pm25_sensor']),
    ('door_opened', 'LOW', ['contact_sensor']),
    ('wandering_detected', 'HIGH', ['contact_sensor', 'pir_sensor']),
    ('bathroom_long_stay', 'MEDIUM', ['humidity_sensor', 'pir_sensor']),
    ('stove_left_on', 'CRITICAL', ['heat_sensor', 'pir_sensor']),
    ('gait_anomaly', 'MEDIUM', ['pose_camera', 'imu_sensor']),
    ('respiratory_distress', 'HIGH', ['acoustic_sensor', 'pulse_oximeter']),
    ('cognitive_assessment', 'INFO', ['voice_engine', 'interaction_tracker']),
    ('social_isolation', 'LOW', ['interaction_tracker', 'voice_engine']),
    ('caregiver_visit', 'INFO', ['contact_sensor', 'app_checkin']),
]


def generate_event(resident, event_date, event_type_info, hour=None):
    """Generate a single realistic event."""
    event_type, severity, sensors = event_type_info
    
    if hour is None:
        # Weight hours based on event type
        if 'sleep' in event_type or 'bed_exit' in event_type:
            hour = random.choice([0, 1, 2, 3, 4, 5, 22, 23])
        elif 'meal' in event_type:
            hour = random.choice([7, 8, 12, 13, 19, 20])
        elif 'medication' in event_type:
            hour = random.choice([7, 8, 12, 18, 20, 22])
        elif 'stove' in event_type:
            hour = random.choice([7, 8, 12, 13, 18, 19, 20])
        else:
            hour = random.randint(6, 22)
    
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    
    ts_dt = event_date.replace(hour=hour, minute=minute, second=second, tzinfo=timezone.utc)
    timestamp = int(ts_dt.timestamp())  # Epoch seconds (Number type for DynamoDB)
    timestamp_iso = ts_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    confidence = round(random.uniform(0.7, 0.99), 3)
    
    # Build event data based on type
    data = {}
    if event_type == 'fall_detected':
        data = {
            'fall_type': random.choice(['forward', 'backward', 'lateral', 'slip']),
            'impact_force': round(random.uniform(2.0, 8.0), 1),
            'immobility_seconds': random.randint(0, 120),
            'location': random.choice(['bathroom', 'bedroom', 'hallway', 'kitchen', 'living_room']),
            'voice_response': random.choice([True, False]),
        }
    elif 'medication' in event_type:
        med = random.choice(resident['medications'])
        med_timing = med.get('timing', ['08:00'])
        if not med_timing:
            med_timing = ['08:00']
        data = {
            'medication': med['name'],
            'dosage': med['dosage'],
            'scheduled_time': random.choice(med_timing),
            'actual_time': f"{hour:02d}:{minute:02d}",
            'compartment': random.randint(1, 7),
        }
        if event_type == 'medication_missed':
            data['hours_overdue'] = round(random.uniform(2, 6), 1)
    elif 'meal' in event_type:
        data = {
            'meal_type': random.choice(['breakfast', 'lunch', 'dinner', 'snack']),
            'duration_minutes': random.randint(10, 45),
            'calories_estimated': random.randint(200, 800),
        }
    elif event_type == 'hydration_low':
        data = {
            'current_ml': random.randint(400, 1200),
            'target_ml': resident['baseline']['avg_hydration_ml'],
            'deficit_pct': round(random.uniform(25, 50), 1),
        }
    elif 'vital' in event_type:
        data = {
            'heart_rate': random.randint(55, 110),
            'blood_pressure': f"{random.randint(110, 160)}/{random.randint(65, 95)}",
            'spo2': random.randint(88, 99),
            'temperature': round(random.uniform(36.0, 37.8), 1),
        }
    elif event_type == 'sleep_disrupted':
        data = {
            'sleep_hours': round(random.uniform(3.0, 6.5), 1),
            'awakenings': random.randint(2, 6),
            'restlessness_score': round(random.uniform(0.4, 0.9), 2),
        }
    elif event_type == 'environment_alert':
        data = {
            'temperature_c': round(random.uniform(35, 42), 1),
            'humidity_pct': random.randint(65, 90),
            'heat_index': round(random.uniform(38, 48), 1),
        }
    elif event_type == 'gait_anomaly':
        data = {
            'stride_length_cm': random.randint(30, 50),
            'sway_score': round(random.uniform(0.3, 0.8), 2),
            'asymmetry_pct': round(random.uniform(5, 25), 1),
            'baseline_deviation_pct': round(random.uniform(15, 40), 1),
        }
    elif event_type == 'cognitive_assessment':
        data = {
            'assessment_type': 'voice_interaction',
            'clarity_score': round(random.uniform(0.5, 1.0), 2),
            'response_time_ms': random.randint(1500, 5000),
            'word_recall_score': round(random.uniform(0.4, 0.9), 2),
        }
    
    return {
        'event_id': f'EVT-{uuid4().hex[:12]}',
        'home_id': resident['home_id'],
        'resident_id': resident['resident_id'],
        'event_type': event_type,
        'severity': severity,
        'timestamp': timestamp,
        'timestamp_iso': timestamp_iso,
        'data': data,
        'confidence': Decimal(str(confidence)),
        'source_sensors': sensors,
        'privacy_level': 'PRIVATE',
        'correlation_id': f'COR-{uuid4().hex[:8]}',
        'submitted_via': 'edge_gateway',
    }


def generate_timeline_entry(resident, date, events_for_day):
    """Generate a timeline summary entry for a single day."""
    severity_counts = {}
    type_counts = {}
    fall_count = 0
    med_taken = 0
    med_missed = 0
    
    for evt in events_for_day:
        sev = evt['severity']
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        etype = evt['event_type']
        type_counts[etype] = type_counts.get(etype, 0) + 1
        if etype == 'fall_detected':
            fall_count += 1
        if etype == 'medication_taken':
            med_taken += 1
        if etype == 'medication_missed':
            med_missed += 1
    
    total_meds = med_taken + med_missed
    adherence = round((med_taken / total_meds * 100) if total_meds > 0 else 100.0, 1)
    activity_score = round(random.uniform(40, 95), 1)
    
    return {
        'home_id': resident['home_id'],
        'date': date.strftime('%Y-%m-%d'),
        'resident_id': resident['resident_id'],
        'total_events': len(events_for_day),
        'fall_count': fall_count,
        'medication_adherence_pct': Decimal(str(adherence)),
        'activity_score': Decimal(str(activity_score)),
        'events_by_severity': {k: v for k, v in severity_counts.items()},
        'events_by_type': {k: v for k, v in type_counts.items()},
        'sleep_hours': Decimal(str(round(random.uniform(4.5, 8.0), 1))),
        'hydration_ml': random.randint(1000, 2500),
        'steps': random.randint(800, 5000),
        'mood_score': Decimal(str(round(random.uniform(3.0, 8.0), 1))),
        'heart_rate_avg': random.randint(62, 85),
        'spo2_avg': random.randint(92, 99),
        'summary': f"Day summary for {resident['name']}",
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }


def generate_consent(resident):
    """Generate consent record for a resident."""
    return {
        'resident_id': resident['resident_id'],
        'timestamp': int(datetime(2026, 2, 25, 10, 0, 0, tzinfo=timezone.utc).timestamp()),
        'consent_version': 'v1.0',
        'granted_at': '2026-02-25T10:00:00Z',
        'granted_by': resident['emergency_contacts'][0]['name'],
        'data_sharing': {
            'sensor_data': True,
            'health_metrics': True,
            'location': False,
            'voice_recordings': True,
            'pose_vectors': True,
            'raw_video': False,
            'raw_audio': False,
        },
        'sharing_with': {
            'family_caregivers': True,
            'doctors': True,
            'nurses': True,
            'emergency_services': True,
            'research': False,
        },
        'privacy_mode': resident['preferences']['privacy_mode'],
        'data_retention_days': 365,
        'status': 'active',
    }


def generate_clinic_ops(resident):
    """Generate clinic ops / care tasks for a resident."""
    now_epoch = int(datetime.now(timezone.utc).timestamp())
    tasks = [
        {
            'clinic_id': f'CLINIC-{resident["home_id"]}',
            'timestamp': now_epoch - 100,
            'task_id': f'TASK-{uuid4().hex[:8]}',
            'resident_id': resident['resident_id'],
            'home_id': resident['home_id'],
            'task_type': 'medication_refill',
            'title': f"Refill {resident['medications'][0]['name']} prescription",
            'description': f"Prescription for {resident['medications'][0]['name']} {resident['medications'][0]['dosage']} needs refilling within 7 days.",
            'priority': 'MEDIUM',
            'status': 'pending',
            'assigned_to': 'caregiver_001',
            'due_date': (datetime.now(timezone.utc) + timedelta(days=7)).strftime('%Y-%m-%d'),
            'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'sla_hours': 168,
        },
        {
            'clinic_id': f'CLINIC-{resident["home_id"]}',
            'timestamp': now_epoch - 200,
            'task_id': f'TASK-{uuid4().hex[:8]}',
            'resident_id': resident['resident_id'],
            'home_id': resident['home_id'],
            'task_type': 'doctor_appointment',
            'title': f"Schedule quarterly check-up for {resident['name']}",
            'description': f"Quarterly health review with Dr. Suresh Kumar. Last visit was 3 months ago.",
            'priority': 'LOW',
            'status': 'in_progress',
            'assigned_to': 'caregiver_001',
            'due_date': (datetime.now(timezone.utc) + timedelta(days=14)).strftime('%Y-%m-%d'),
            'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'sla_hours': 336,
        },
        {
            'clinic_id': f'CLINIC-{resident["home_id"]}',
            'timestamp': now_epoch - 300,
            'task_id': f'TASK-{uuid4().hex[:8]}',
            'resident_id': resident['resident_id'],
            'home_id': resident['home_id'],
            'task_type': 'wellness_checkin',
            'title': f"Daily wellness check-in call with {resident['name']}",
            'description': 'Routine daily wellness check-in via voice companion.',
            'priority': 'HIGH',
            'status': 'completed',
            'assigned_to': 'ai_companion',
            'completed_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'outcome': 'Resident reports feeling well. Mood: positive. No pain complaints.',
            'created_at': (datetime.now(timezone.utc) - timedelta(hours=4)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'sla_hours': 24,
        },
    ]
    return tasks


def convert_for_dynamo(item):
    """Convert Python types to DynamoDB-compatible types."""
    if isinstance(item, dict):
        return {k: convert_for_dynamo(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [convert_for_dynamo(i) for i in item]
    elif isinstance(item, float):
        return Decimal(str(round(item, 6)))
    elif isinstance(item, bool):
        return item
    elif isinstance(item, int):
        return item
    elif isinstance(item, str):
        return item
    elif item is None:
        return None
    else:
        return str(item)


def seed_residents():
    """Seed the residents table."""
    table = dynamodb.Table(TABLES['residents'])
    print(f"\n📋 Seeding {TABLES['residents']}...")
    
    for resident in RESIDENTS:
        item = convert_for_dynamo(resident)
        table.put_item(Item=item)
        print(f"  ✅ {resident['name']} ({resident['resident_id']})")
    
    print(f"  Total: {len(RESIDENTS)} residents")


def seed_events():
    """Seed the events table with 14 days of data."""
    table = dynamodb.Table(TABLES['events'])
    print(f"\n📊 Seeding {TABLES['events']}...")
    
    total = 0
    now = datetime.now(timezone.utc)
    
    for resident in RESIDENTS:
        resident_events = 0
        for day_offset in range(14):
            event_date = now - timedelta(days=day_offset)
            
            # Generate 8-20 events per day per resident
            num_events = random.randint(8, 20)
            
            for _ in range(num_events):
                # Weight event types towards normal daily activities (24 types)
                weights = [1, 1, 8, 2, 2, 6, 1, 2, 2, 2, 1, 4, 3, 1, 1, 3, 1, 1, 1, 2, 1, 1, 1, 3]
                event_type_info = random.choices(EVENT_TYPES, weights=weights, k=1)[0]
                
                evt = generate_event(resident, event_date, event_type_info)
                item = convert_for_dynamo(evt)
                table.put_item(Item=item)
                resident_events += 1
        
        total += resident_events
        print(f"  ✅ {resident['name']}: {resident_events} events (14 days)")
    
    print(f"  Total: {total} events")


def seed_timeline():
    """Seed the timeline table with daily summaries."""
    table = dynamodb.Table(TABLES['timeline'])
    print(f"\n📅 Seeding {TABLES['timeline']}...")
    
    total = 0
    now = datetime.now(timezone.utc)
    
    for resident in RESIDENTS:
        for day_offset in range(14):
            date = now - timedelta(days=day_offset)
            
            # Generate some fake events for the summary
            num_events = random.randint(8, 20)
            day_events = []
            for _ in range(num_events):
                weights = [1, 1, 8, 2, 2, 6, 1, 2, 2, 2, 1, 4, 3, 1, 1, 3, 1, 1, 1, 2, 1, 1, 1, 3]
                event_type_info = random.choices(EVENT_TYPES, weights=weights, k=1)[0]
                day_events.append({
                    'event_type': event_type_info[0],
                    'severity': event_type_info[1],
                })
            
            entry = generate_timeline_entry(resident, date, day_events)
            item = convert_for_dynamo(entry)
            table.put_item(Item=item)
            total += 1
        
        print(f"  ✅ {resident['name']}: 14 daily summaries")
    
    print(f"  Total: {total} timeline entries")


def seed_consent():
    """Seed the consent table."""
    table = dynamodb.Table(TABLES['consent'])
    print(f"\n🔒 Seeding {TABLES['consent']}...")
    
    for resident in RESIDENTS:
        consent = generate_consent(resident)
        item = convert_for_dynamo(consent)
        table.put_item(Item=item)
        print(f"  ✅ {resident['name']}")
    
    print(f"  Total: {len(RESIDENTS)} consent records")


def seed_clinic_ops():
    """Seed the clinic ops table with care tasks."""
    table = dynamodb.Table(TABLES['clinic_ops'])
    print(f"\n🏥 Seeding {TABLES['clinic_ops']}...")
    
    total = 0
    for resident in RESIDENTS:
        tasks = generate_clinic_ops(resident)
        for task in tasks:
            item = convert_for_dynamo(task)
            table.put_item(Item=item)
            total += 1
        print(f"  ✅ {resident['name']}: {len(tasks)} tasks")
    
    print(f"  Total: {total} clinic ops records")


def main():
    print("=" * 60)
    print("🚀 AETHER CareOps — DynamoDB Seed Script")
    print("=" * 60)
    print(f"Region: {REGION}")
    print(f"Tables: {', '.join(TABLES.values())}")
    
    try:
        seed_residents()
        seed_events()
        seed_timeline()
        seed_consent()
        seed_clinic_ops()
        
        print("\n" + "=" * 60)
        print("✅ All tables seeded successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
