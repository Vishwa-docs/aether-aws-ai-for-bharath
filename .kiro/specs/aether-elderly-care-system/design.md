# AETHER CareOps Platform — Technical Design Document

> **Version**: 2.0 — Full CareOps Platform Architecture  
> **Sprint**: 2-Month (8-Week) Development Sprint  
> **Last Updated**: 2025-07-13  
> **Status**: Planning & Architecture Phase

---

## 1. Architecture Overview

AETHER is a **3-tier distributed system** optimized for elderly care in India. It processes sensor data at the edge for privacy and latency, orchestrates intelligent care workflows in the cloud via agentic AI, and presents information through both a web dashboard and mobile application.

### 1.1 Architecture Principles

| Principle | Rationale |
|---|---|
| **Privacy-First Edge Processing** | Raw audio/video/sensor never leaves the home. Only features, events, and anonymized metrics transit to cloud. |
| **Offline-First Safety** | Fall detection, acoustic alerts, medication reminders function without internet. 72-hour event buffer. |
| **Agentic AI Over Rule-Based** | Complex care decisions handled by autonomous AI agents that reason, plan, and act — not static if/then rules. |
| **Voice-First UX** | Elderly interact via natural Hindi/English voice. The UI is a conversation, not a screen. |
| **Cost-Optimized AWS-Native** | Every architecture decision targets <₹5,000/month ($60) per home on AWS. Serverless-first, on-demand pricing. |
| **Multi-Tenant by Design** | Single deployment serves B2C homes and B2B clinics/facilities with isolated data and configurable features. |
| **Progressive Enhancement** | Core safety features work with minimal sensors. Additional sensors + AI unlock advanced features. |

### 1.2 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       CLIENT LAYER                              │
│                                                                 │
│   ┌──────────────────┐    ┌──────────────────┐                 │
│   │   Web Dashboard   │    │   Mobile App      │                │
│   │  (React/Amplify)  │    │ (React Native)    │                │
│   │                   │    │                   │                │
│   │  • Family View    │    │  • Elderly View   │                │
│   │  • Nurse View     │    │  • Family View    │                │
│   │  • Doctor View    │    │  • Nurse View     │                │
│   │  • Ops View       │    │  • Rx Camera      │                │
│   │  • Facility View  │    │  • Voice Postcard │                │
│   └────────┬─────────┘    └────────┬─────────┘                │
│            │                       │                            │
└────────────┼───────────────────────┼────────────────────────────┘
             │         HTTPS          │
             ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                       CLOUD LAYER (AWS)                         │
│                                                                 │
│   ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐   │
│   │ Cognito   │  │ API Gateway  │  │  IoT Core             │   │
│   │ (Auth)    │  │ (REST+WS)   │  │  (MQTT Broker)        │   │
│   └──────────┘  └──────┬───────┘  └───────────┬───────────┘   │
│                         │                      │                │
│   ┌─────────────────────┼──────────────────────┼──────────┐    │
│   │              PROCESSING LAYER               │          │    │
│   │                                              │          │    │
│   │  ┌──────────┐  ┌──────────┐  ┌─────────────┘          │    │
│   │  │ Lambda    │  │ Step      │  │ Kinesis                │    │
│   │  │ Functions │  │ Functions │  │ (Stream)               │    │
│   │  │ (8+)     │  │ (Workflows)│ │                        │    │
│   │  └──────────┘  └──────────┘  └────────────────────────┘    │
│   │                                                             │
│   │  ┌──────────────────────────────────────────────────┐      │
│   │  │         INTELLIGENCE LAYER (Bedrock)             │      │
│   │  │                                                   │      │
│   │  │  ┌─────────┐ ┌───────────┐ ┌──────────────────┐ │      │
│   │  │  │ Agents  │ │ Knowledge │ │   Guardrails     │ │      │
│   │  │  │ (6+)    │ │ Bases (4) │ │   (Safety)       │ │      │
│   │  │  └─────────┘ └───────────┘ └──────────────────┘ │      │
│   │  └──────────────────────────────────────────────────┘      │
│   │                                                             │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐     │
│   │  │ DynamoDB  │  │ S3       │  │ Textract +           │     │
│   │  │ (5 tables)│  │ (4 bkts) │  │ Comprehend Medical   │     │
│   │  └──────────┘  └──────────┘  └──────────────────────┘     │
│   └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
             ▲
             │  MQTT (TLS) over IoT Core
             │
┌─────────────────────────────────────────────────────────────────┐
│                       EDGE LAYER                                │
│                                                                 │
│   ┌──────────────────────────────────────────────────────────┐ │
│   │              Edge Hub (Raspberry Pi 5)                    │ │
│   │                                                           │ │
│   │  ┌────────────┐ ┌────────────┐ ┌─────────────────────┐  │ │
│   │  │ Sensor     │ │ AI/ML      │ │ Event Queue         │  │ │
│   │  │ Aggregator │ │ Engine     │ │ (SQLite, offline)   │  │ │
│   │  │ (MQTT)     │ │            │ │                     │  │ │
│   │  │            │ │ • Fall Det │ │ ┌─────────────────┐ │  │ │
│   │  │            │ │ • Acoustic │ │ │ Connectivity    │ │  │ │
│   │  │            │ │ • Wake Word│ │ │ Monitor         │ │  │ │
│   │  │            │ │ • Privacy  │ │ └─────────────────┘ │  │ │
│   │  │            │ │   Filter   │ │                     │  │ │
│   │  └────────────┘ └────────────┘ └─────────────────────┘  │ │
│   └──────────────────────────────────────────────────────────┘ │
│                          ▲                                      │
│                          │  MQTT (local)                        │
│                          │                                      │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐│
│   │Accel/IMU │ │Pressure  │ │Door/PIR  │ │Temp/Gas/Humidity ││
│   │(wearable)│ │Mat (bed) │ │Sensors   │ │Sensors           ││
│   └──────────┘ └──────────┘ └──────────┘ └──────────────────┘│
│                                                                 │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐                     │
│   │Microphone│ │Smart     │ │Smart     │   ALL SIMULATED     │
│   │(acoustic)│ │Pillbox   │ │Bottle    │   FOR DEMO          │
│   └──────────┘ └──────────┘ └──────────┘                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Edge Layer Architecture

### 2.1 Edge Hub Hardware

**Primary Platform**: Raspberry Pi 5 (8GB RAM)
- **CPU**: Quad-core Arm Cortex-A76 @ 2.4GHz — sufficient for lightweight ML inference
- **RAM**: 8GB — handles sensor aggregation + local ML + SQLite + MQTT broker
- **Storage**: 128GB microSD — for ML models, event queue, and cached TTS audio
- **Connectivity**: WiFi 6 + Ethernet + Bluetooth 5.0 + optional 4G HAT
- **Cost**: ~₹7,000 (~$85)

**Optional Upgrade**: NVIDIA Jetson Orin Nano (for GPU-accelerated inference)
- Enables real-time video analytics, larger ML models
- Cost: ~₹42,000 (~$500) — justified for facility deployments

### 2.2 Edge Software Stack

```python
# Edge Hub Runtime Architecture
class EdgeHub:
    """
    Central orchestrator running on Raspberry Pi 5.
    Manages sensor aggregation, local AI inference, and cloud sync.
    """
    
    def __init__(self, config: EdgeConfig):
        # Sensor layer
        self.mqtt_broker = LocalMQTTBroker(port=1883)
        self.sensor_aggregator = SensorAggregator(self.mqtt_broker)
        
        # AI/ML layer  
        self.fall_detector = FallDetectionEngine()        # Fused: accel + pressure + acoustic
        self.acoustic_classifier = AcousticClassifier()   # Scream, glass break, cough, silence
        self.wake_word_detector = WakeWordEngine()         # "Hey Aether" on-device
        self.privacy_filter = PrivacyFilter()              # Raw → features only
        
        # Communication layer
        self.event_queue = OfflineEventQueue(db_path="events.db")  # SQLite FIFO
        self.connectivity_monitor = ConnectivityMonitor()
        self.iot_client = AWSIoTClient(config.iot_endpoint, config.certificates)
        
        # Voice layer (local)
        self.tts_cache = TTSCache(cache_dir="tts_audio/")  # Pre-cached common phrases
        self.voice_responder = LocalVoiceResponder(self.tts_cache)
    
    async def process_sensor_data(self, topic: str, payload: dict):
        """Main sensor processing pipeline — runs entirely on-device."""
        # 1. Aggregate and timestamp
        reading = self.sensor_aggregator.normalize(topic, payload)
        
        # 2. Privacy filter — strip PII, extract features only
        safe_data = self.privacy_filter.apply(reading)
        
        # 3. Run local ML models
        events = []
        if reading.sensor_type == "accelerometer":
            fall_result = self.fall_detector.evaluate(safe_data)
            if fall_result.detected:
                events.append(FallEvent(severity=fall_result.severity, confidence=fall_result.confidence))
        
        if reading.sensor_type == "microphone":
            # Only process acoustic features — raw audio discarded
            acoustic_result = self.acoustic_classifier.classify(safe_data.features)
            if acoustic_result.event_detected:
                events.append(AcousticEvent(event_type=acoustic_result.label, confidence=acoustic_result.confidence))
        
        # 4. Queue events for cloud sync (or process locally if offline)
        for event in events:
            if self.connectivity_monitor.is_online():
                await self.iot_client.publish(event)
            else:
                self.event_queue.enqueue(event)
                # Critical events still trigger local response
                if event.severity >= Severity.ALERT:
                    await self.voice_responder.handle_critical_event(event)
```

### 2.3 Privacy Filter Design

The Privacy Filter is the hard boundary between raw sensor data and anything that leaves the device.

```python
class PrivacyFilter:
    """
    Enforces privacy boundary on edge device.
    Raw data goes in — only features and event labels come out.
    
    NEVER passes through:
    - Raw audio waveforms
    - Raw video frames
    - GPS coordinates (only room-level location)
    - Conversation transcripts (only extracted structured data)
    """
    
    ALLOWED_FEATURES = {
        "accelerometer": ["magnitude", "orientation", "step_count", "gait_metrics"],
        "microphone": ["event_label", "confidence", "db_level", "voice_biomarkers"],
        "pressure_mat": ["occupancy", "pressure_distribution", "weight_shift"],
        "door_sensor": ["state", "transition_count"],
        "pir_motion": ["motion_detected", "room_id"],
        "temperature": ["celsius", "humidity_percent"],
        "gas_sensor": ["gas_detected", "concentration_ppm"],
        "pillbox": ["compartment_opened", "compartment_id"],
    }
    
    def apply(self, reading: SensorReading) -> FilteredReading:
        allowed = self.ALLOWED_FEATURES.get(reading.sensor_type, [])
        filtered_features = {k: v for k, v in reading.features.items() if k in allowed}
        
        return FilteredReading(
            sensor_type=reading.sensor_type,
            timestamp=reading.timestamp,
            home_id=reading.home_id,  # Not a PII field
            room_id=reading.room_id,
            features=filtered_features,
            # Raw data explicitly not included
        )
```

### 2.4 Fall Detection Fusion Algorithm

```python
class FallDetectionEngine:
    """
    Multi-sensor fall detection with voice triage.
    
    Fuses data from:
    1. Accelerometer (wearable) — impact detection, orientation change
    2. Pressure mat (bed/chair) — sudden unloading
    3. Acoustic classifier — impact sounds, distress vocalizations
    4. PIR motion — sudden motion pattern change
    
    Decision matrix:
    - 1 sensor positive → Watch tier (monitor for 30s)
    - 2 sensors positive → Alert tier (initiate voice triage)
    - 3+ sensors positive → Emergency tier (immediate escalation)
    - Accelerometer + prolonged floor-level → Emergency regardless
    """
    
    FUSION_WEIGHTS = {
        "accelerometer": 0.40,  # Primary — most reliable for falls
        "pressure_mat": 0.25,   # Strong indicator when present
        "acoustic": 0.20,       # Impact sounds + distress vocalizations
        "pir_motion": 0.15,     # Supporting evidence
    }
    
    def evaluate(self, data: FusedSensorData) -> FallAssessment:
        scores = {}
        
        # Accelerometer: free-fall detection + impact + orientation change
        if data.has_accelerometer:
            accel_score = self._evaluate_accelerometer(data.accelerometer)
            scores["accelerometer"] = accel_score
        
        # Pressure mat: sudden unloading from bed/chair
        if data.has_pressure_mat:
            pressure_score = self._evaluate_pressure(data.pressure_mat)
            scores["pressure_mat"] = pressure_score
        
        # Acoustic: impact sound + distress vocalization
        if data.has_acoustic:
            acoustic_score = self._evaluate_acoustic(data.acoustic)
            scores["acoustic"] = acoustic_score
        
        # PIR: sudden cessation of expected motion
        if data.has_pir:
            pir_score = self._evaluate_pir(data.pir_motion)
            scores["pir_motion"] = pir_score
        
        # Fusion: weighted sum with multi-sensor bonus
        positive_sensors = sum(1 for s in scores.values() if s > 0.5)
        weighted_total = sum(
            scores[s] * self.FUSION_WEIGHTS[s] 
            for s in scores
        )
        
        # Multi-sensor agreement bonus
        if positive_sensors >= 2:
            weighted_total *= 1.3
        if positive_sensors >= 3:
            weighted_total *= 1.5
        
        return FallAssessment(
            detected=weighted_total > 0.6,
            severity=self._classify_severity(weighted_total, positive_sensors),
            confidence=min(weighted_total, 1.0),
            contributing_sensors=scores,
            recommended_tier=self._determine_tier(weighted_total, positive_sensors),
        )
    
    def _classify_severity(self, score: float, sensor_count: int) -> FallSeverity:
        if score > 0.9 or sensor_count >= 3:
            return FallSeverity.SEVERE
        elif score > 0.7:
            return FallSeverity.MODERATE
        else:
            return FallSeverity.MINOR
    
    def _determine_tier(self, score: float, sensor_count: int) -> TriageTier:
        if score > 0.9 or sensor_count >= 3:
            return TriageTier.EMERGENCY
        elif score > 0.6:
            return TriageTier.ALERT  # Will trigger voice triage
        elif score > 0.4:
            return TriageTier.WATCH
        else:
            return TriageTier.LOG
```

### 2.5 Offline Event Queue

```python
class OfflineEventQueue:
    """
    SQLite-backed FIFO event queue for offline operation.
    
    Guarantees:
    - At-least-once delivery for all events
    - 72-hour minimum buffer at max event rate
    - Automatic sync when connectivity resumes
    - Priority ordering: Emergency > Alert > Inform > Log
    """
    
    def __init__(self, db_path: str = "events.db"):
        self.db = sqlite3.connect(db_path)
        self._init_schema()
    
    def _init_schema(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS event_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT UNIQUE NOT NULL,
                priority INTEGER NOT NULL,  -- 0=Emergency, 1=Alert, 2=Inform, 3=Log
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,       -- JSON
                created_at TEXT NOT NULL,
                sync_status TEXT DEFAULT 'pending',  -- pending, syncing, synced, failed
                retry_count INTEGER DEFAULT 0,
                last_retry_at TEXT
            )
        """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sync_priority 
            ON event_queue(sync_status, priority, created_at)
        """)
    
    def enqueue(self, event: Event):
        self.db.execute(
            "INSERT OR IGNORE INTO event_queue (event_id, priority, event_type, payload, created_at) VALUES (?, ?, ?, ?, ?)",
            (event.id, event.priority.value, event.type, event.to_json(), event.timestamp.isoformat())
        )
        self.db.commit()
    
    async def sync_pending(self, iot_client: AWSIoTClient, batch_size: int = 50):
        """Sync pending events to cloud, highest priority first."""
        rows = self.db.execute(
            "SELECT id, event_id, payload FROM event_queue WHERE sync_status = 'pending' ORDER BY priority ASC, created_at ASC LIMIT ?",
            (batch_size,)
        ).fetchall()
        
        for row_id, event_id, payload in rows:
            try:
                self.db.execute("UPDATE event_queue SET sync_status = 'syncing' WHERE id = ?", (row_id,))
                await iot_client.publish(json.loads(payload))
                self.db.execute("UPDATE event_queue SET sync_status = 'synced' WHERE id = ?", (row_id,))
            except Exception:
                self.db.execute(
                    "UPDATE event_queue SET sync_status = 'failed', retry_count = retry_count + 1, last_retry_at = ? WHERE id = ?",
                    (datetime.utcnow().isoformat(), row_id)
                )
        self.db.commit()
```

### 2.6 Sensor Simulators Architecture

```python
class SensorSimulator:
    """
    Base class for sensor simulators.
    Generates realistic data streams over MQTT for development and demo.
    """
    
    def __init__(self, home_id: str, mqtt_client: MQTTClient):
        self.home_id = home_id
        self.mqtt = mqtt_client
        self.noise_level = 0.05  # 5% noise by default
    
    @abstractmethod
    def generate_reading(self, context: SimulationContext) -> dict:
        """Generate a single sensor reading."""
        pass
    
    def publish(self, reading: dict, sensor_type: str):
        topic = f"aether/{self.home_id}/sensors/{sensor_type}/data"
        self.mqtt.publish(topic, json.dumps(reading))


class AccelerometerSimulator(SensorSimulator):
    """Simulates wearable accelerometer with realistic motion patterns."""
    
    ACTIVITY_PROFILES = {
        "sleeping": {"mean_magnitude": 0.02, "variance": 0.01, "step_rate": 0},
        "sitting": {"mean_magnitude": 0.1, "variance": 0.05, "step_rate": 0},
        "walking": {"mean_magnitude": 0.8, "variance": 0.15, "step_rate": 100},
        "cooking": {"mean_magnitude": 0.5, "variance": 0.3, "step_rate": 20},
        "falling": {"mean_magnitude": 4.5, "variance": 1.0, "step_rate": 0},  # High-G impact
    }


class DailyRoutineScenario:
    """
    Scenario-based simulation of a full day.
    Coordinates multiple sensor simulators to tell a coherent story.
    """
    
    KAMALA_ROUTINE = [
        # (time_range, activity, sensors_involved)
        ("06:00-06:30", "waking_up", ["pressure_mat", "pir_motion", "accelerometer"]),
        ("06:30-07:00", "bathroom", ["door_sensor", "pir_motion", "accelerometer"]),
        ("07:00-07:30", "prayer", ["pir_motion", "accelerometer"]),  # Sitting still
        ("07:30-08:00", "breakfast_prep", ["pir_motion", "temperature", "gas_sensor"]),
        ("08:00-08:15", "morning_medication", ["pillbox", "microphone"]),  # Voice reminder
        ("08:15-10:00", "morning_activity", ["accelerometer", "pir_motion"]),
        ("10:00-10:30", "mid_morning_rest", ["pressure_mat", "accelerometer"]),
        # ... full day schedule
        ("12:30-13:00", "lunch_prep", ["pir_motion", "temperature", "gas_sensor"]),
        ("14:00-15:00", "afternoon_nap", ["pressure_mat", "accelerometer"]),
        ("15:30-16:00", "evening_medication", ["pillbox", "microphone"]),
        ("18:00-18:30", "dinner_prep", ["pir_motion", "temperature", "gas_sensor"]),
        ("20:00-20:15", "night_medication", ["pillbox", "microphone"]),
        ("21:00-06:00", "sleeping", ["pressure_mat", "accelerometer"]),
    ]
    
    FALL_SCENARIO = [
        ("10:15", "walking_to_bathroom", ["accelerometer", "pir_motion"]),
        ("10:15:30", "slip_and_fall", ["accelerometer", "pressure_mat", "microphone"]),  # Impact
        ("10:15:35", "on_floor", ["accelerometer", "pressure_mat"]),  # Floor-level, no movement
        ("10:16:00", "voice_triage", ["microphone"]),  # System asks "Are you okay?"
        ("10:16:10", "resident_responds", ["microphone"]),  # "Haan, gir gayi"
    ]
    
    GRADUAL_DECLINE_SCENARIO = [
        # 14-day drift: sleep quality drops, meal frequency decreases, activity reduces
        # Day 1-3: Normal baselines
        # Day 4-7: Sleep duration drops 10%, one meal missed/day
        # Day 8-10: Activity reduces 20%, bathroom visits increase 30%
        # Day 11-14: Voice energy drops 15%, medication adherence drops to 80%
        # → Composite Drift Score triggers alert on Day 12
    ]
```

---

## 3. Cloud Layer Architecture

### 3.1 AWS Service Inventory

| Service | Purpose | Cost Optimization |
|---|---|---|
| **API Gateway** (REST + WebSocket) | Client API + real-time dashboard updates | Regional, on-demand pricing |
| **Lambda** (8+ functions) | Event processing, API handlers, agent orchestration | ARM64 (Graviton), 256-512MB, <15s timeout |
| **DynamoDB** (5 tables) | Primary data store — events, residents, medications, alerts, timelines | On-demand capacity, TTL for old events |
| **S3** (4 buckets) | Prescriptions, knowledge bases, reports, audit logs | Intelligent-Tiering, lifecycle policies |
| **IoT Core** | MQTT broker for edge hub communication | Pay-per-message, ~$1/million messages |
| **Kinesis Data Streams** | Real-time event stream from IoT Core to Lambda | 1 shard for single-home (~$13/month) |
| **Bedrock** | LLM inference (agents, summarization, Q&A, triage) | On-demand per-token pricing |
| **Bedrock Agents** (6+) | Autonomous multi-step AI workflows | Included in Bedrock inference costs |
| **Bedrock Knowledge Bases** (4) | RAG for medical Q&A, drug info, dietary, schemes | S3 storage + embedding costs |
| **Bedrock Guardrails** | Safety filtering on all LLM outputs | Included in Bedrock pricing |
| **Cognito** | Authentication for web dashboard + mobile app | Free tier: 50,000 MAU |
| **Transcribe** (streaming) | Speech-to-text for voice commands | $0.024/minute |
| **Polly** (neural) | Text-to-speech for voice responses | $16/million characters |
| **Textract** | Prescription/lab report OCR | $1.50/1000 pages |
| **Comprehend Medical** | Medical entity extraction from OCR text | $0.01/unit (100 chars) |
| **Step Functions** | Complex workflow orchestration (escalation, Rx pipeline) | Standard: $0.025/1000 transitions |
| **SNS** | Push notifications, email alerts | Free tier covers demo |
| **SES** | Email delivery for reports/alerts | $0.10/1000 emails |
| **CloudWatch** | Monitoring, logging, alarming | Free tier + $3-5/month at demo scale |
| **KMS** | Encryption key management for PHI | $1/key/month |
| **Amplify** | Web dashboard hosting (React) | Free tier for first 12 months |
| **SageMaker** (optional) | Custom model training (gait, drift prediction) | Spot instances for training |

### 3.2 Estimated Monthly Cost (Single Home)

| Category | Service | Estimated Monthly Cost |
|---|---|---|
| Compute | Lambda (8 functions) | $2-5 |
| Storage | DynamoDB (on-demand) | $3-5 |
| Storage | S3 | $1-2 |
| Messaging | IoT Core + Kinesis (1 shard) | $15-18 |
| AI | Bedrock (agents + RAG) | $15-25 |
| Voice | Transcribe + Polly | $3-5 |
| Document AI | Textract + Comprehend Medical | $1-2 |
| Auth | Cognito | Free |
| Hosting | Amplify | Free |
| Monitoring | CloudWatch | $3-5 |
| Security | KMS | $1 |
| **Total** | | **$44-68** ✅ |

**Cost Optimization Strategies**:
1. **Bedrock model selection**: Use Claude Haiku (cheapest) for triage/classification, Claude Sonnet only for complex summarization
2. **Aggressive caching**: Cache frequently asked care navigation questions, TTS audio, and common drug interaction results
3. **DynamoDB TTL**: Auto-delete raw sensor data after 90 days, keep aggregated summaries indefinitely
4. **Lambda ARM64**: Use Graviton processors for Lambda — 20% cheaper than x84
5. **Kinesis**: Use 1 shard (sufficient for single home's ~100 events/minute peak)
6. **S3 Intelligent-Tiering**: Prescription images and reports auto-tier to cheaper storage after 30 days
7. **Reserved capacity**: For B2B deployments, use provisioned DynamoDB capacity and Savings Plans

### 3.3 Lambda Functions Inventory

| Function | Trigger | Purpose | Runtime | Memory |
|---|---|---|---|---|
| `event_processor` | IoT Core → Kinesis | Processes incoming sensor events, runs triage logic, routes to appropriate handlers | Python 3.12 | 512MB |
| `api_handler` | API Gateway | REST API for dashboard + mobile app CRUD operations | Python 3.12 | 256MB |
| `voice_processor` | API Gateway (WS) | Handles voice interaction pipeline: Transcribe → Bedrock → Polly | Python 3.12 | 512MB |
| `care_navigation` | API Gateway / Agent | RAG-based health Q&A with Bedrock Knowledge Base | Python 3.12 | 512MB |
| `doc_generator` | Schedule / On-demand | Generates clinical summaries, pre-consultation reports, FHIR exports | Python 3.12 | 512MB |
| `prescription_processor` | S3 trigger (Rx upload) | Prescription OCR pipeline: Textract → Comprehend Medical → Bedrock Agent | Python 3.12 | 512MB |
| `ride_booking_agent` | Step Function / Agent | Autonomous ride booking workflow: detect need → book → confirm → track | Python 3.12 | 256MB |
| `analytics_processor` | Schedule (hourly) | Computes drift scores, aggregates metrics, updates baselines | Python 3.12 | 512MB |
| `escalation_handler` | Step Function | Manages triage escalation ladder with timeouts and notifications | Python 3.12 | 256MB |
| `timeline_aggregator` | Schedule (every 15 min) | Aggregates events into human-readable timeline entries | Python 3.12 | 256MB |

### 3.4 DynamoDB Tables

#### Table: `residents`
```
Partition Key: tenant_id (String)
Sort Key: resident_id (String)

Attributes:
- profile: Map (name, age, gender, languages, medical_conditions, allergies)
- contacts: List of Map (name, phone, relationship, notification_preferences)
- medications: List of Map (drug_name, dosage, frequency, timing, prescriber, start_date)
- baselines: Map (activity_baseline, sleep_baseline, voice_baseline, meal_baseline)
- care_plan: Map (acuity_score, visit_frequency, special_instructions)
- consent: Map (monitoring_enabled, voice_enabled, data_sharing_family, data_sharing_doctor)
- cognitive_status: String (normal, mild_impairment, moderate_impairment, advanced_dementia)
- created_at, updated_at: String (ISO 8601)

GSI: by-tenant-status (tenant_id, acuity_score) — for ops dashboard fleet view
```

#### Table: `events`
```
Partition Key: home_id (String)
Sort Key: event_id (String)  — format: {timestamp}#{event_type}#{uuid_short}

Attributes:
- event_type: String (fall, medication, acoustic, drift, temperature, etc.)
- severity: String (log, watch, inform, alert, emergency)
- triage_tier: Number (0-4)
- payload: Map (sensor data, confidence scores, contributing sensors)
- evidence: Map (sensor readings, timeline, context)
- triage_decision: Map (tier, reasoning, agent_invoked, actions_taken)
- outcome: String (auto_resolved, acknowledged, escalated, false_positive)
- outcome_timestamp: String
- ttl: Number (epoch seconds, 90 days for log/watch, never for alert/emergency)

GSI: by-type-time (event_type, created_at) — for analytics queries
GSI: by-severity (severity, created_at) — for alert dashboard
```

#### Table: `medications`
```
Partition Key: resident_id (String)
Sort Key: medication_id (String)

Attributes:
- drug_name: String
- generic_name: String
- dosage: String
- frequency: String (BID, TID, etc.)
- timing: List of String (specific times)
- instructions: String (before meals, with water, etc.)
- prescriber: String
- start_date: String
- end_date: String (optional)
- interactions: List of Map (interacting_drug, severity, description)
- generic_alternative: Map (drug_name, price_original, price_generic, source)
- adherence_log: List of Map (scheduled_time, actual_time, status, confirmation_method)
- prescription_image_s3: String (S3 key for original Rx image)

GSI: by-timing (resident_id, next_dose_time) — for reminder scheduling
```

#### Table: `health_records`
```
Partition Key: resident_id (String)
Sort Key: record_id (String)  — format: {date}#{record_type}#{uuid_short}

Attributes:
- record_type: String (daily_summary, weekly_summary, check_in, drift_report, clinical_note, lab_result, fhir_export)
- content: Map (structured data specific to record type)
- fhir_resources: List of Map (resource_type, resource_json)
- generated_by: String (system, agent:{agent_name}, manual:{user_id})
- source_events: List of String (event_ids that contributed to this record)

GSI: by-type-date (record_type, sort_key) — for report generation
```

#### Table: `care_calendar`
```
Partition Key: resident_id (String)
Sort Key: appointment_id (String)  — format: {datetime}#{type}#{uuid_short}

Attributes:
- appointment_type: String (doctor_visit, lab_test, follow_up, therapy_session)
- provider: Map (name, specialty, clinic, address, phone)
- datetime: String (ISO 8601)
- status: String (scheduled, confirmed, ride_booked, completed, cancelled, no_show)
- preparation: List of String (fasting instructions, medication holds, documents_needed)
- ride_booking: Map (status, provider, pickup_time, vehicle_type, tracking_url)
- pre_consultation_report_s3: String (S3 key for generated report)
- notes: String

GSI: by-date (tenant_id, datetime) — for calendar views
```

### 3.5 S3 Buckets

| Bucket | Purpose | Lifecycle |
|---|---|---|
| `aether-prescriptions-{env}` | Prescription/lab report images + OCR results | Intelligent-Tiering → Glacier after 1 year |
| `aether-knowledge-base-{env}` | Bedrock Knowledge Base source documents (medical Q&A, drug data, dietary, schemes) | Versioned, no expiry |
| `aether-reports-{env}` | Generated clinical reports, FHIR exports, compliance reports, evidence packets | Standard → IA after 90 days |
| `aether-audit-{env}` | Audit logs, agent action logs, guardrail activation logs | Glacier after 30 days, retain 7 years |

---

## 4. Multi-Agent Architecture (Intelligence Layer)

### 4.1 Agent Design Philosophy

AETHER's agents are **autonomous care workers**, not chat assistants. Each agent has:
- A defined **role** and **scope** (what it can and cannot do)
- **Tools** (AWS service integrations, APIs, database access)
- A **knowledge base** (curated domain knowledge via Bedrock KB)
- **Guardrails** (safety constraints)
- **Audit trail** (every decision logged)

Agents collaborate through a **supervisor pattern**: the Event Processor Lambda acts as the supervisor, routing events to the appropriate agent(s) and collecting their outputs.

### 4.2 Agent Inventory

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT SUPERVISOR                             │
│              (event_processor Lambda)                           │
│                                                                 │
│   Routes events to specialized agents based on event type       │
│   Collects agent outputs and orchestrates multi-agent flows     │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬──────────────┐
        ▼             ▼             ▼              ▼
┌──────────────┐ ┌───────────┐ ┌───────────┐ ┌────────────┐
│ TRIAGE       │ │ CLINICAL  │ │ CARE NAV  │ │ POLY-      │
│ AGENT        │ │ SCRIBE    │ │ AGENT     │ │ PHARMACY   │
│              │ │ AGENT     │ │           │ │ AGENT      │
│ • Classifies │ │ • SOAP    │ │ • Health  │ │ • Drug     │
│   events     │ │   notes   │ │   Q&A     │ │   interact │
│ • Determines │ │ • Shift   │ │ • Scheme  │ │ • Generic  │
│   triage tier│ │   reports │ │   discovery│ │   altern.  │
│ • Routes     │ │ • Pre-    │ │ • Cultural│ │ • Food-drug│
│   response   │ │   consult │ │   context │ │   warnings │
└──────────────┘ └───────────┘ └───────────┘ └────────────┘
        
        ┌─────────────┐ ┌───────────────┐
        ▼             ▼                 ▼
┌──────────────┐ ┌───────────────┐ ┌──────────────┐
│ RIDE         │ │ PRESCRIPTION  │ │ DRIFT        │
│ BOOKING      │ │ OCR           │ │ DETECTION    │
│ AGENT        │ │ AGENT         │ │ AGENT        │
│              │ │               │ │              │
│ • Detect     │ │ • Textract    │ │ • Baseline   │
│   transport  │ │ • Comprehend  │ │   comparison │
│   need       │ │   Medical     │ │ • Z-score    │
│ • Book ride  │ │ • Validate    │ │   deviation  │
│ • Confirm    │ │ • Structure   │ │ • Composite  │
│ • Track      │ │ • Add to meds │ │   scoring    │
└──────────────┘ └───────────────┘ └──────────────┘
```

### 4.3 Agent Specifications

#### Agent 1: Intelligent Triage Agent

```yaml
name: aether-triage-agent
role: >
  You are the Triage Agent for AETHER, an elderly care system. Your job is to 
  classify incoming sensor events by severity and determine the appropriate 
  response. You have access to the resident's profile, medical history, 
  medication schedule, and recent event history.
  
  You must be conservative — err on the side of caution for safety events.
  But you must also avoid false alarms that erode trust.

knowledge_bases:
  - aether-medical-kb  # For understanding symptoms and risk factors
  
tools:
  - get_resident_profile  # Fetch resident's medical conditions, medications, baselines
  - get_recent_events     # Fetch last 24h of events for context
  - get_medication_schedule  # Check if event correlates with medication timing
  - classify_event        # Output structured triage decision
  - send_notification     # Send alert to appropriate parties
  - invoke_voice_triage   # Trigger voice check-in with resident

guardrails:
  - Never downgrade an event below WATCH if the resident has a history of falls
  - Never suppress acoustic distress events
  - Always invoke voice triage for ALERT tier before escalating to EMERGENCY
  - Log ALL classification decisions with reasoning

example_reasoning: |
  Event: Accelerometer detected high-G impact (4.2g) at 10:15 AM
  Context: Resident is in bathroom (high-risk zone). No pressure mat data (not in bed).
  Recent history: No falls in last 30 days. Mild arthritis, stable.
  Medication: Took Amlodipine at 8:00 AM (can cause dizziness).
  
  Decision: ALERT tier
  Reasoning: High-G impact in high-risk bathroom zone. Amlodipine taken 2 hours ago 
  may cause orthostatic hypotension. Single-sensor event so not EMERGENCY, but 
  high-risk context warrants voice triage immediately.
  
  Action: Invoke voice triage → "Kamala ji, sab theek hai? Lagta hai kuch gir gaya."
```

#### Agent 2: Clinical Scribe Agent

```yaml
name: aether-clinical-scribe
role: >
  You are the Clinical Scribe Agent. You generate clinical documentation from 
  sensor data, events, and check-in data. You produce SOAP-format notes, 
  shift summaries, pre-consultation reports, and FHIR-compliant records.
  
  Your outputs are used by healthcare professionals. Be precise, concise, 
  and clinically relevant. Use standard medical terminology where appropriate 
  but explain assessments clearly.

knowledge_bases:
  - aether-medical-kb  # For clinical vocabulary and assessment frameworks

tools:
  - get_resident_profile
  - get_events_by_date_range
  - get_health_records
  - get_medication_adherence
  - get_checkin_summaries
  - get_drift_scores
  - generate_fhir_bundle    # Output FHIR R4 resources
  - store_clinical_note     # Save to health_records table

output_formats:
  daily_summary: |
    ## Daily Care Summary — {resident_name}
    **Date**: {date}  |  **Prepared by**: AETHER Clinical Scribe (automated)
    
    ### Activity & Mobility
    - Steps: {steps} (baseline: {baseline_steps})
    - Active hours: {active_hours} | Sedentary: {sedentary_hours}
    - Gait: {gait_assessment}
    
    ### Vital Signs
    - BP: {bp_avg} (trend: {bp_trend})
    - Heart rate: {hr_avg} (range: {hr_range})
    
    ### Medication Adherence
    - Overall: {adherence_pct}%
    - Missed doses: {missed_list}
    
    ### Sleep
    - Duration: {sleep_hours}h (baseline: {baseline_sleep}h)
    - Wake events: {wake_count}
    
    ### Nutrition
    - Meals detected: {meal_count}/3
    - Hydration reminders responded to: {hydration_pct}%
    
    ### Notable Events
    {event_list}
    
    ### Drift Assessment
    - Composite score: {drift_score} (threshold: {drift_threshold})
    - Flagged parameters: {drifting_params}
```

#### Agent 3: Care Navigation Agent

```yaml
name: aether-care-navigator
role: >
  You are the Care Navigation Agent. You help elderly residents and their 
  families navigate healthcare questions, explain medical concepts in simple 
  language, and provide culturally-appropriate health guidance.
  
  You speak in Hindi (or the resident's language). You are warm, respectful,
  and use age-appropriate address forms (ji, aunty, uncle). You NEVER give 
  specific medical treatment advice — you provide information and always 
  direct to the resident's doctor for decisions.

knowledge_bases:
  - aether-medical-kb      # General health information
  - aether-dietary-kb      # Indian dietary guidance, food-drug interactions
  - aether-schemes-kb      # Government healthcare schemes

tools:
  - get_resident_profile
  - get_medication_list
  - search_knowledge_base
  - create_follow_up_task   # Add tasks to care calendar
  - find_nearby_providers   # Find doctors, pharmacies, JanAushadhi kendras

guardrails:
  - NEVER prescribe medication or suggest dosage changes
  - NEVER diagnose conditions
  - ALWAYS include disclaimer: "Yeh jaankari samajhne ke liye hai. Doctor se zaroor baat karein."
  - Use simple, jargon-free language appropriate for elderly
  - Respect cultural dietary practices (vegetarian, fasting days, etc.)
  - Reference ICMR guidelines for Indian-specific recommendations
```

#### Agent 4: Polypharmacy Checker Agent

```yaml
name: aether-polypharmacy-checker
role: >
  You are the Polypharmacy Agent. When medications are added, changed, or 
  queried, you check for drug-drug interactions, food-drug interactions, 
  and suggest generic alternatives from the PMBJP catalog.
  
  You provide information to healthcare providers and families — you do 
  NOT make medication change decisions.

knowledge_bases:
  - aether-drug-interaction-kb  # Drug interaction database
  - aether-pmbjp-kb             # Generic alternatives catalog

tools:
  - get_medication_list
  - check_interactions      # Pairwise drug interaction check
  - find_generic_alternative  # Match to PMBJP catalog
  - check_food_interactions   # Food-drug interaction warnings
  - generate_interaction_report

output_example: |
  ## Medication Interaction Report — Kamala Devi
  **Generated**: 2025-07-13 | **Trigger**: New medication added: Clopidogrel 75mg
  
  ### ⚠️ MAJOR Interactions Found
  1. **Clopidogrel + Aspirin** → Increased bleeding risk
     - Severity: MAJOR
     - Action: Monitor for signs of bleeding. Prescriber should confirm intentional dual antiplatelet therapy.
  
  2. **Amlodipine + Simvastatin** → Increased Simvastatin levels
     - Severity: MODERATE
     - Action: Simvastatin dose should not exceed 20mg when combined with Amlodipine.
  
  ### 🍽️ Food-Drug Interactions
  - **Simvastatin**: Avoid grapefruit (mosambi in some regions)
  - **Metformin**: Take with meals to reduce stomach upset
  
  ### 💊 Generic Alternatives Available (PMBJP)
  | Brand Drug | PMBJP Generic | Monthly Savings |
  |---|---|---|
  | Ecosprin (Aspirin) ₹85 | Aspirin 75mg ₹12 | ₹73 (86%) |
  | Atorva (Atorvastatin) ₹420 | Atorvastatin 20mg ₹38 | ₹382 (91%) |
  | **Total Potential Savings** | | **₹455/month** |
```

#### Agent 5: Prescription OCR Agent

```yaml
name: aether-prescription-ocr
role: >
  You are the Prescription OCR Agent. You process uploaded prescription images
  through an end-to-end pipeline: OCR → entity extraction → validation → 
  structuring → interaction checking.

workflow:
  1. Receive prescription image S3 key from S3 trigger
  2. Call Textract to extract text
  3. Call Comprehend Medical to identify medical entities (drugs, dosages, frequencies)
  4. Validate extracted entities against drug database
  5. Flag low-confidence extractions for human review
  6. For confirmed medications, invoke Polypharmacy Agent for interaction checking
  7. Present structured results to user for confirmation
  8. On confirmation, add medications to resident's medication schedule

tools:
  - textract_analyze_document
  - comprehend_medical_detect_entities
  - validate_drug_name         # Check against known drug database
  - invoke_polypharmacy_agent  # For interaction checking
  - update_medication_schedule
  - notify_user                # Present results for confirmation
```

#### Agent 6: Auto Ride Booking Agent

```yaml
name: aether-ride-booking
role: >
  You are the Ride Booking Agent. You autonomously manage transportation 
  for elderly residents to medical appointments.
  
  You operate as a fully autonomous agent: detect upcoming appointments 
  that need transport → assess mobility needs → book appropriate vehicle → 
  confirm with resident → track arrival → notify family.

workflow:
  1. Triggered by care_calendar event: appointment in next 48 hours
  2. Check if resident can self-transport (profile: mobility_status)
  3. Determine vehicle type based on mobility (auto, cab, wheelchair-accessible)
  4. Calculate pickup time (appointment_time - travel_time - 15min buffer)
  5. Call ride booking API (simulated for demo)
  6. Confirm with resident via voice: "Kamala ji, kal 11 baje doctor ke appointment ke liye 10:15 baje taxi aayegi. Theek hai?"
  7. Send booking details to family via push notification
  8. On ride day: send reminders at T-1hr, T-30min, T-15min
  9. Track ride arrival and notify resident

tools:
  - get_care_calendar
  - get_resident_profile
  - book_ride              # Simulated API call
  - cancel_ride
  - check_ride_status
  - voice_confirm          # Speak to resident and get confirmation
  - notify_family          # Push notification to family members
```

### 4.4 Agent Orchestration Flow

```python
class AgentSupervisor:
    """
    Routes events to appropriate agents and orchestrates multi-agent workflows.
    Runs as the event_processor Lambda function.
    """
    
    AGENT_ROUTING = {
        "fall_detected": ["triage_agent"],
        "acoustic_event": ["triage_agent"],
        "medication_due": ["medication_reminder"],  # Simple rule-based, no agent needed
        "medication_missed": ["triage_agent", "clinical_scribe"],
        "drift_detected": ["triage_agent", "clinical_scribe"],
        "prescription_uploaded": ["prescription_ocr_agent"],
        "appointment_upcoming": ["ride_booking_agent", "clinical_scribe"],
        "health_question": ["care_navigation_agent"],
        "medication_changed": ["polypharmacy_agent"],
        "daily_checkin_completed": ["clinical_scribe"],
        "weekly_summary_due": ["clinical_scribe"],  # Scheduled
    }
    
    async def route_event(self, event: Event):
        """Route an incoming event to the appropriate agent(s)."""
        agents = self.AGENT_ROUTING.get(event.type, [])
        
        if not agents:
            # No agent needed — log and continue
            await self.log_event(event)
            return
        
        results = []
        for agent_name in agents:
            try:
                result = await self.invoke_agent(agent_name, event)
                results.append(result)
                await self.log_agent_action(agent_name, event, result)
            except Exception as e:
                # Agent failure — fall back to rule-based handling
                await self.log_agent_failure(agent_name, event, e)
                await self.rule_based_fallback(event)
        
        return results
    
    async def invoke_agent(self, agent_name: str, event: Event):
        """Invoke a Bedrock Agent with event context."""
        bedrock = boto3.client("bedrock-agent-runtime", region_name="ap-south-1")
        
        response = bedrock.invoke_agent(
            agentId=self.agent_ids[agent_name],
            agentAliasId=self.agent_aliases[agent_name],
            sessionId=f"{event.home_id}-{event.event_id}",
            inputText=self._format_agent_prompt(agent_name, event),
        )
        
        return self._parse_agent_response(response)
```

---

## 5. Agentic Workflow Designs

### 5.1 Prescription OCR Workflow (Step Function)

```json
{
  "Comment": "Prescription OCR → Validation → Interaction Check → User Confirmation",
  "StartAt": "ExtractText",
  "States": {
    "ExtractText": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:*:function:prescription_processor",
      "Parameters": {
        "action": "textract",
        "s3_key.$": "$.prescription_image_key"
      },
      "Next": "ExtractMedicalEntities"
    },
    "ExtractMedicalEntities": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:*:function:prescription_processor",
      "Parameters": {
        "action": "comprehend_medical",
        "raw_text.$": "$.extracted_text"
      },
      "Next": "ValidateAndStructure"
    },
    "ValidateAndStructure": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:*:function:prescription_processor",
      "Parameters": {
        "action": "validate_with_agent",
        "entities.$": "$.medical_entities",
        "resident_id.$": "$.resident_id"
      },
      "Next": "CheckConfidence"
    },
    "CheckConfidence": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.confidence",
          "NumericGreaterThanEquals": 0.85,
          "Next": "CheckInteractions"
        }
      ],
      "Default": "RequestHumanReview"
    },
    "RequestHumanReview": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:*:function:prescription_processor",
      "Parameters": {
        "action": "request_review",
        "medications.$": "$.structured_medications",
        "confidence.$": "$.confidence"
      },
      "Next": "WaitForReview"
    },
    "WaitForReview": {
      "Type": "Wait",
      "TimestampPath": "$.review_deadline",
      "Next": "CheckInteractions"
    },
    "CheckInteractions": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:*:function:prescription_processor",
      "Parameters": {
        "action": "check_interactions",
        "medications.$": "$.confirmed_medications",
        "resident_id.$": "$.resident_id"
      },
      "Next": "PresentResults"
    },
    "PresentResults": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:*:function:prescription_processor",
      "Parameters": {
        "action": "present_results",
        "medications.$": "$.confirmed_medications",
        "interactions.$": "$.interaction_report",
        "generic_alternatives.$": "$.generic_alternatives"
      },
      "End": true
    }
  }
}
```

### 5.2 Escalation Ladder Workflow (Step Function)

```json
{
  "Comment": "Multi-tier escalation with timeouts and voice triage",
  "StartAt": "InitiateVoiceTriage",
  "States": {
    "InitiateVoiceTriage": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:*:function:escalation_handler",
      "Parameters": {
        "action": "voice_triage",
        "event.$": "$.event",
        "resident_id.$": "$.resident_id"
      },
      "Next": "EvaluateVoiceResponse",
      "TimeoutSeconds": 30
    },
    "EvaluateVoiceResponse": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.voice_response.status",
          "StringEquals": "resident_ok",
          "Next": "LogAndResolve"
        },
        {
          "Variable": "$.voice_response.status",
          "StringEquals": "resident_distressed",
          "Next": "EmergencyEscalation"
        },
        {
          "Variable": "$.voice_response.status",
          "StringEquals": "no_response",
          "Next": "NotifyFamily"
        }
      ],
      "Default": "NotifyFamily"
    },
    "LogAndResolve": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:*:function:escalation_handler",
      "Parameters": {
        "action": "log_resolution",
        "event.$": "$.event",
        "resolution": "self_resolved_via_voice"
      },
      "End": true
    },
    "NotifyFamily": {
      "Type": "Parallel",
      "Branches": [
        {
          "StartAt": "SendPushNotification",
          "States": {
            "SendPushNotification": {
              "Type": "Task",
              "Resource": "arn:aws:lambda:ap-south-1:*:function:escalation_handler",
              "Parameters": {
                "action": "notify_family",
                "channel": "push",
                "event.$": "$.event"
              },
              "End": true
            }
          }
        },
        {
          "StartAt": "SendSMS",
          "States": {
            "SendSMS": {
              "Type": "Task",
              "Resource": "arn:aws:states:::sns:publish",
              "Parameters": {
                "TopicArn": "arn:aws:sns:ap-south-1:*:aether-emergency-alerts",
                "Message.$": "$.alert_message"
              },
              "End": true
            }
          }
        }
      ],
      "Next": "WaitForFamilyResponse"
    },
    "WaitForFamilyResponse": {
      "Type": "Wait",
      "Seconds": 300,
      "Next": "CheckFamilyResponse"
    },
    "CheckFamilyResponse": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.family_responded",
          "BooleanEquals": true,
          "Next": "LogFamilyHandled"
        }
      ],
      "Default": "EmergencyEscalation"
    },
    "EmergencyEscalation": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:*:function:escalation_handler",
      "Parameters": {
        "action": "emergency_escalation",
        "event.$": "$.event",
        "evidence_packet.$": "$.evidence_packet"
      },
      "End": true
    },
    "LogFamilyHandled": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:ap-south-1:*:function:escalation_handler",
      "Parameters": {
        "action": "log_resolution",
        "resolution": "family_handled"
      },
      "End": true
    }
  }
}
```

### 5.3 Auto Ride Booking Workflow

```python
class RideBookingWorkflow:
    """
    Fully autonomous ride booking agent workflow.
    
    Trigger: Appointment detected in care_calendar within 48 hours
    
    Steps:
    1. Check if resident needs transportation
    2. Determine vehicle type from mobility profile
    3. Calculate pickup time
    4. Book ride (simulated API)
    5. Confirm with resident via voice
    6. Notify family
    7. Send reminders on ride day
    8. Track ride arrival
    """
    
    async def execute(self, appointment: dict, resident: dict):
        # Step 1: Does resident need transport?
        if resident["profile"]["mobility_status"] == "independent_transport":
            return {"status": "not_needed", "reason": "Resident manages own transport"}
        
        # Step 2: Vehicle type
        vehicle = self._select_vehicle(resident["profile"]["mobility_status"])
        
        # Step 3: Pickup time
        travel_time = await self._estimate_travel(
            resident["profile"]["address"],
            appointment["provider"]["address"]
        )
        pickup_time = appointment["datetime"] - travel_time - timedelta(minutes=15)
        
        # Step 4: Book ride (simulated)
        booking = await self.ride_api.book(
            pickup_address=resident["profile"]["address"],
            dropoff_address=appointment["provider"]["address"],
            pickup_time=pickup_time,
            vehicle_type=vehicle,
            passenger_needs=resident["profile"]["special_needs"],
        )
        
        # Step 5: Voice confirmation
        confirmation = await self.voice_service.confirm(
            resident_id=resident["resident_id"],
            message=f"{resident['profile']['name']} ji, kal {appointment['datetime'].strftime('%I:%M')} baje "
                    f"Dr. {appointment['provider']['name']} ke appointment ke liye "
                    f"{pickup_time.strftime('%I:%M')} baje {vehicle} aayegi. Theek hai?",
            expect_response=True,
        )
        
        if not confirmation.accepted:
            await self.ride_api.cancel(booking["booking_id"])
            return {"status": "cancelled_by_resident"}
        
        # Step 6: Notify family
        await self.notification_service.send(
            recipients=resident["contacts"],
            title=f"Ride booked for {resident['profile']['name']}",
            body=f"Pickup at {pickup_time.strftime('%I:%M %p')} for appointment with "
                 f"Dr. {appointment['provider']['name']}",
        )
        
        # Step 7-8: Schedule reminders and tracking (handled by scheduled Lambda)
        await self.scheduler.create_reminders(booking, resident)
        
        return {"status": "booked", "booking": booking}
```

---

## 6. Client Layer Architecture

### 6.1 Web Dashboard (React + AWS Amplify)

**Tech Stack**: React 18 + TypeScript + Vite + TailwindCSS + Amplify Hosting

```
dashboard/
├── src/
│   ├── App.tsx                    # Router with role-based navigation
│   ├── main.tsx                   # Entry point with Amplify config
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx        # Role-aware navigation sidebar
│   │   │   ├── Header.tsx         # User info, notifications bell, language toggle
│   │   │   └── NotificationCenter.tsx  # Real-time notification panel
│   │   ├── dashboard/
│   │   │   ├── StatusCard.tsx     # Resident status summary card
│   │   │   ├── AlertBanner.tsx    # Active alert banner
│   │   │   ├── ActivityTimeline.tsx  # 24-hour event timeline
│   │   │   ├── DriftGauge.tsx     # Composite drift score gauge
│   │   │   └── MedicationTracker.tsx  # Adherence visual
│   │   ├── charts/
│   │   │   ├── SleepChart.tsx     # Sleep duration + quality over time
│   │   │   ├── ActivityChart.tsx  # Steps + active hours
│   │   │   ├── AdherenceChart.tsx # Medication adherence %
│   │   │   └── DriftTrendChart.tsx  # Multi-parameter drift visualization
│   │   ├── agents/
│   │   │   ├── PrescriptionUpload.tsx  # Camera/upload for Rx OCR
│   │   │   ├── InteractionReport.tsx   # Drug interaction display
│   │   │   ├── ClinicalSummary.tsx     # SOAP note viewer
│   │   │   └── RideBookingStatus.tsx   # Ride booking flow
│   │   └── shared/
│   │       ├── EventIcon.tsx
│   │       ├── StatusBadge.tsx
│   │       └── LoadingSpinner.tsx
│   ├── pages/
│   │   ├── family/
│   │   │   ├── FamilyDashboard.tsx     # Arjun's view of his mother
│   │   │   ├── EventHistory.tsx
│   │   │   └── Settings.tsx
│   │   ├── nurse/
│   │   │   ├── PatientList.tsx         # Sister Priya's patient roster
│   │   │   ├── VisitNotes.tsx
│   │   │   └── ShiftSummary.tsx
│   │   ├── doctor/
│   │   │   ├── DoctorDashboard.tsx     # Dr. Suresh's view
│   │   │   ├── PreConsultReport.tsx
│   │   │   └── FHIRExport.tsx
│   │   └── ops/
│   │       ├── FleetView.tsx           # Meena's operations view
│   │       ├── CaregiverWorkload.tsx
│   │       ├── AnalyticsPanel.tsx
│   │       └── ComplianceReports.tsx
│   ├── hooks/
│   │   ├── useAuth.ts           # Cognito auth hook
│   │   ├── useRealtime.ts       # WebSocket for real-time updates
│   │   ├── useResident.ts       # Resident data fetching
│   │   └── useAlerts.ts         # Alert subscription hook
│   ├── services/
│   │   ├── api.ts               # API Gateway client
│   │   ├── websocket.ts         # WebSocket client for real-time
│   │   └── auth.ts              # Cognito auth service
│   └── types/
│       └── index.ts             # TypeScript interfaces
```

#### Role-Based Views

| Role | Dashboard View | Key Features |
|---|---|---|
| **Family** | Single-resident focused | Status at-a-glance, event timeline, medication adherence, alert notifications, Rx upload, settings |
| **Nurse** | Patient list + individual | Patient roster, visit notes, shift summaries, medication management, voice note transcription |
| **Doctor** | Clinical + analytical | Pre-consultation summaries, drift analysis, FHIR export, trend visualization, medication review |
| **Ops Manager** | Fleet + operational | All-patient grid, caregiver workload, compliance reports, analytics, scheduling |
| **Facility Manager** | Facility-wide | Floor/wing view, night shift monitoring, incident reports, regulatory compliance |

### 6.2 Mobile Application (React Native)

**Tech Stack**: React Native + Expo + TypeScript + React Navigation

```
mobile/
├── src/
│   ├── App.tsx
│   ├── navigation/
│   │   ├── AuthNavigator.tsx      # Login/signup flow
│   │   ├── ElderlyNavigator.tsx   # Simplified elderly view (4 screens)
│   │   ├── FamilyNavigator.tsx    # Full family caregiver view
│   │   └── NurseNavigator.tsx     # Nurse patient management view
│   ├── screens/
│   │   ├── elderly/
│   │   │   ├── HomeScreen.tsx      # Large status display, voice button, SOS
│   │   │   ├── MedicationScreen.tsx  # Visual pill schedule
│   │   │   ├── HelpScreen.tsx      # SOS + care navigation
│   │   │   └── FamilyScreen.tsx    # Voice postcards, calls
│   │   ├── family/
│   │   │   ├── DashboardScreen.tsx  # Mom's status overview
│   │   │   ├── EventsScreen.tsx     # Event timeline + details
│   │   │   ├── MedsScreen.tsx       # Medication management
│   │   │   ├── CameraScreen.tsx     # Prescription photo capture
│   │   │   ├── PostcardScreen.tsx   # Record voice messages
│   │   │   └── SettingsScreen.tsx   # Alert preferences, contacts
│   │   └── nurse/
│   │       ├── PatientListScreen.tsx
│   │       ├── PatientDetailScreen.tsx
│   │       ├── VoiceNoteScreen.tsx
│   │       └── ScheduleScreen.tsx
│   ├── components/
│   │   ├── SOSButton.tsx           # Always-visible emergency button
│   │   ├── VoiceButton.tsx         # Push-to-talk (elderly mode)
│   │   ├── StatusCard.tsx
│   │   ├── MedicationCard.tsx
│   │   └── EventItem.tsx
│   ├── services/
│   │   ├── api.ts                  # API Gateway client
│   │   ├── pushNotifications.ts    # FCM/APNS setup
│   │   ├── voiceRecorder.ts        # Audio recording for postcards
│   │   └── offlineStore.ts         # AsyncStorage for offline
│   └── themes/
│       ├── elderly.ts             # Large fonts, high contrast
│       └── standard.ts            # Normal app theme
```

#### Elderly Mode Design Principles

```typescript
// Elderly mode theme — everything is large, high-contrast, minimal
const elderlyTheme = {
  fonts: {
    body: 22,        // Minimum body text
    header: 28,      // Section headers
    button: 24,      // Button labels
    sectionTitle: 32, // Main titles
  },
  spacing: {
    touchTarget: 56,  // Minimum touch target (px) — Apple says 44, we go bigger
    buttonPadding: 20,
    sectionGap: 24,
  },
  colors: {
    // WCAG AAA contrast ratios for elderly vision
    background: '#FFFFFF',
    text: '#1A1A1A',
    primary: '#1565C0',    // Strong blue — visible even with mild cataracts
    danger: '#C62828',     // Strong red for SOS
    success: '#2E7D32',    // Green for confirmation
    warning: '#E65100',    // Orange for alerts
  },
  maxScreens: 4,  // Maximum 4 screens — Home, Medications, Help, Family
  maxButtonsPerScreen: 6,  // No cluttered screens
};
```

---

## 7. Data Models (TypeScript)

### 7.1 Core Event Model

```typescript
// All events flowing through the system
interface AetherEvent {
  eventId: string;           // UUID v4
  homeId: string;            // Home/facility identifier
  residentId: string;        // Resident this event pertains to
  tenantId: string;          // B2B tenant isolation
  eventType: EventType;
  severity: Severity;
  triageTier: TriageTier;
  timestamp: string;         // ISO 8601
  
  // Sensor evidence
  payload: {
    primarySensor: SensorType;
    sensorReadings: SensorReading[];
    fusionScore: number;      // 0-1, multi-sensor confidence
    contributingSensors: SensorType[];
  };
  
  // AI triage decision
  triageDecision?: {
    tier: TriageTier;
    reasoning: string;        // Agent's explanation
    agentId: string;          // Which agent made the decision
    confidence: number;
    actionsInitiated: string[];  // ["voice_triage", "family_notification"]
  };
  
  // Resolution tracking
  outcome?: {
    resolution: 'auto_resolved' | 'acknowledged' | 'escalated' | 'false_positive' | 'pending';
    resolvedBy: string;       // "system" | "family:{userId}" | "nurse:{userId}"
    resolvedAt: string;
    notes: string;
  };
  
  // Evidence packet (for Alert/Emergency)
  evidencePacket?: EvidencePacket;
  
  ttl?: number;              // DynamoDB TTL (epoch seconds)
}

enum EventType {
  FALL_DETECTED = 'fall_detected',
  POST_FALL_IMMOBILITY = 'post_fall_immobility',
  ACOUSTIC_EVENT = 'acoustic_event',
  MEDICATION_TAKEN = 'medication_taken',
  MEDICATION_MISSED = 'medication_missed',
  MEAL_DETECTED = 'meal_detected',
  MEAL_MISSED = 'meal_missed',
  CHECKIN_COMPLETED = 'checkin_completed',
  DRIFT_ALERT = 'drift_alert',
  ENVIRONMENTAL_ALERT = 'environmental_alert',
  WANDERING_DETECTED = 'wandering_detected',
  SOS_ACTIVATED = 'sos_activated',
  STOVE_UNATTENDED = 'stove_unattended',
  BATHROOM_PROLONGED = 'bathroom_prolonged',
  SOCIAL_WITHDRAWAL = 'social_withdrawal',
}

enum Severity { LOG = 'log', WATCH = 'watch', INFORM = 'inform', ALERT = 'alert', EMERGENCY = 'emergency' }
enum TriageTier { LOG = 0, WATCH = 1, INFORM = 2, ALERT = 3, EMERGENCY = 4 }
```

### 7.2 Resident Profile Model

```typescript
interface ResidentProfile {
  tenantId: string;
  residentId: string;
  
  // Demographics
  profile: {
    name: string;
    age: number;
    gender: 'male' | 'female' | 'other';
    dateOfBirth: string;
    languages: string[];           // ['hindi', 'english']
    preferredLanguage: string;     // 'hindi'
    address: Address;
    photo?: string;                // S3 key
  };
  
  // Medical
  medicalConditions: MedicalCondition[];
  allergies: Allergy[];
  cognitiveStatus: 'normal' | 'mild_impairment' | 'moderate_impairment' | 'advanced_dementia';
  mobilityStatus: 'independent' | 'assisted' | 'wheelchair' | 'bedridden';
  
  // Contacts
  emergencyContacts: Contact[];
  healthcareProviders: HealthcareProvider[];
  
  // Baselines (established after 14-day learning period)
  baselines: {
    activity: { dailySteps: number; activeHours: number; sedentaryHours: number };
    sleep: { avgDuration: number; avgWakeEvents: number; typicalBedtime: string; typicalWakeTime: string };
    voice: { avgPitch: number; avgSpeechRate: number; avgEnergy: number };
    meals: { typicalTimes: string[]; avgMealsPerDay: number };
    bathroom: { avgDailyVisits: number; avgDuration: number };
    medication: { avgAdherenceRate: number; typicalTakeTime: Record<string, string> };
    social: { avgDailyInteractions: number; avgCallDuration: number };
    lastUpdated: string;
    learningComplete: boolean;
  };
  
  // Configuration
  consent: ConsentSettings;
  alertPreferences: AlertPreferences;
  
  // Care plan
  carePlan?: {
    acuityScore: number;          // 1-10
    visitFrequency: string;       // 'daily', '3x_week', 'weekly'
    specialInstructions: string[];
    assignedCaregiver?: string;   // Caregiver user ID
  };
  
  createdAt: string;
  updatedAt: string;
}
```

### 7.3 Evidence Packet Model

```typescript
// Generated automatically for Alert/Emergency events
interface EvidencePacket {
  packetId: string;
  generatedAt: string;
  expiresAt: string;            // Emergency access link expiry
  accessUrl: string;            // Shareable URL (SMS-friendly)
  
  // Patient Info (limited PHI for emergency access)
  patient: {
    name: string;
    age: number;
    bloodType?: string;
    knownConditions: string[];
    knownAllergies: string[];
  };
  
  // Emergency Contacts
  contacts: {
    primary: { name: string; phone: string; relationship: string };
    secondary?: { name: string; phone: string; relationship: string };
    primaryDoctor: { name: string; phone: string; specialty: string };
  };
  
  // Current Medications
  medications: {
    drugName: string;
    dosage: string;
    lastTaken: string;           // When was the last dose
    nextDue: string;
  }[];
  
  // Event Details
  triggeringEvent: {
    type: string;
    severity: string;
    timestamp: string;
    description: string;         // "Fall detected in bathroom with high-G impact"
    sensorData: Record<string, any>;
  };
  
  // Recent Health Context
  recentContext: {
    last24hEvents: { type: string; time: string; description: string }[];
    vitalTrends: { metric: string; values: { time: string; value: number }[] }[];
    medicationAdherenceToday: number;  // Percentage
    lastCheckinSummary: string;
    driftScore: number;
    driftFlags: string[];
  };
  
  // Response Timeline
  responseTimeline: {
    eventDetected: string;
    voiceTriageInitiated?: string;
    voiceResponse?: string;
    familyNotified?: string;
    familyResponded?: string;
    emergencyContacted?: string;
  };
}
```

### 7.4 FHIR Resource Mapping

```typescript
// Maps AETHER data to FHIR R4 resources
interface FHIRMapping {
  // AETHER ResidentProfile → FHIR Patient
  patient: {
    resourceType: 'Patient';
    identifier: [{ system: 'urn:aether:resident', value: string }];
    name: [{ text: string }];
    birthDate: string;
    gender: string;
    address: [Address];
    communication: [{ language: { coding: [{ code: string }] } }];
  };
  
  // AETHER sensor readings → FHIR Observation
  observation: {
    resourceType: 'Observation';
    status: 'final';
    category: [{ coding: [{ system: 'http://terminology.hl7.org/CodeSystem/observation-category', code: string }] }];
    code: { coding: [{ system: 'http://loinc.org', code: string, display: string }] };
    valueQuantity: { value: number; unit: string };
    effectiveDateTime: string;
    device: { reference: string };  // Reference to sensor
  };
  
  // AETHER medication schedule → FHIR MedicationStatement
  medicationStatement: {
    resourceType: 'MedicationStatement';
    status: 'active' | 'completed' | 'stopped';
    medicationCodeableConcept: { text: string };
    dosage: [{ text: string; timing: { repeat: { frequency: number; period: number; periodUnit: string } } }];
    effectivePeriod: { start: string; end?: string };
  };
  
  // AETHER clinical summary → FHIR DiagnosticReport
  diagnosticReport: {
    resourceType: 'DiagnosticReport';
    status: 'final';
    category: [{ coding: [{ code: 'clinical-notes' }] }];
    code: { text: 'AETHER Weekly Health Summary' };
    effectivePeriod: { start: string; end: string };
    conclusion: string;  // The SOAP note text
    presentedForm: [{ contentType: 'application/pdf'; url: string }];
  };
}
```

---

## 8. API Design

### 8.1 REST API (API Gateway)

```yaml
# API Gateway routes — all authenticated via Cognito JWT
base_path: /api/v1

# Resident Management
GET    /residents                        # List residents (tenant-scoped)
GET    /residents/{residentId}           # Get resident profile
PUT    /residents/{residentId}           # Update resident profile
GET    /residents/{residentId}/baselines # Get established baselines

# Events & Timeline
GET    /residents/{residentId}/events    # List events (paginated, filterable)
GET    /residents/{residentId}/events/{eventId}  # Event detail with evidence
POST   /residents/{residentId}/events/{eventId}/outcome  # Mark outcome (true/false positive)
GET    /residents/{residentId}/timeline  # Aggregated timeline

# Medications
GET    /residents/{residentId}/medications  # Current medication list
POST   /residents/{residentId}/medications  # Add medication
PUT    /residents/{residentId}/medications/{medId}  # Update medication
GET    /residents/{residentId}/medications/adherence  # Adherence stats
GET    /residents/{residentId}/medications/interactions  # Interaction report

# Prescriptions
POST   /residents/{residentId}/prescriptions/upload  # Upload Rx image → triggers OCR pipeline
GET    /residents/{residentId}/prescriptions/{rxId}/status  # OCR pipeline status
POST   /residents/{residentId}/prescriptions/{rxId}/confirm  # Confirm OCR results

# Health Records
GET    /residents/{residentId}/records  # List health records (daily summaries, check-ins, reports)
GET    /residents/{residentId}/records/fhir  # FHIR Bundle export
GET    /residents/{residentId}/records/summary  # Pre-consultation summary
GET    /residents/{residentId}/records/drift   # Drift detection report

# Care Calendar
GET    /residents/{residentId}/calendar  # Upcoming appointments
POST   /residents/{residentId}/calendar  # Add appointment
GET    /residents/{residentId}/calendar/{apptId}/ride  # Ride booking status

# Alerts & Notifications
GET    /alerts                           # All active alerts (tenant-scoped)
GET    /alerts/{alertId}                 # Alert detail
POST   /alerts/{alertId}/acknowledge     # Acknowledge alert

# Care Navigation (Agent)
POST   /residents/{residentId}/ask       # Ask health question → Care Navigation Agent
POST   /residents/{residentId}/checkin   # Submit daily check-in data

# Analytics (B2B)
GET    /analytics/overview               # Aggregate metrics
GET    /analytics/alerts                 # Alert analytics
GET    /analytics/adherence              # Medication adherence analytics
GET    /analytics/drift                  # Drift analytics across patients

# Emergency
GET    /emergency/{packetId}             # Emergency evidence packet (no auth required)

# Settings
GET    /settings/profile                 # Current user profile
PUT    /settings/preferences             # Update notification preferences
```

### 8.2 WebSocket API (Real-Time Updates)

```typescript
// WebSocket connection for real-time dashboard updates
// Connect: wss://api.aether.care/ws?token={cognito_jwt}

// Server → Client messages
interface WebSocketMessage {
  type: 'EVENT' | 'ALERT' | 'STATUS_UPDATE' | 'MEDICATION_UPDATE' | 'AGENT_UPDATE';
  payload: {
    residentId: string;
    data: AetherEvent | Alert | StatusUpdate | MedicationUpdate | AgentAction;
    timestamp: string;
  };
}

// Client → Server messages (subscriptions)
interface SubscribeMessage {
  action: 'subscribe';
  channels: string[];  // ['resident:{id}', 'tenant:{id}', 'alerts']
}
```

---

## 9. Drift Detection Engine

### 9.1 Architecture

```python
class DriftDetectionEngine:
    """
    Continuous health baseline monitoring with composite drift scoring.
    
    Runs as the analytics_processor Lambda on an hourly schedule.
    
    For each resident:
    1. Compute Z-scores for all monitored parameters vs. personalized baselines
    2. Calculate composite drift score (weighted multi-parameter deviation)
    3. Check for known clinical patterns (UTI, dehydration, depression onset)
    4. Generate drift alerts when threshold exceeded
    """
    
    # Monitored parameters and their clinical significance weights
    DRIFT_PARAMETERS = {
        "sleep_duration": {"weight": 0.15, "direction": "decrease", "unit": "hours"},
        "sleep_wake_events": {"weight": 0.10, "direction": "increase", "unit": "count"},
        "daily_steps": {"weight": 0.12, "direction": "decrease", "unit": "steps"},
        "active_hours": {"weight": 0.10, "direction": "decrease", "unit": "hours"},
        "medication_adherence": {"weight": 0.15, "direction": "decrease", "unit": "percent"},
        "meal_frequency": {"weight": 0.08, "direction": "decrease", "unit": "meals/day"},
        "bathroom_visits": {"weight": 0.05, "direction": "both", "unit": "visits/day"},
        "voice_energy": {"weight": 0.08, "direction": "decrease", "unit": "dB"},
        "voice_speech_rate": {"weight": 0.07, "direction": "decrease", "unit": "wpm"},
        "social_interactions": {"weight": 0.05, "direction": "decrease", "unit": "count/day"},
        "checkin_mood_score": {"weight": 0.05, "direction": "decrease", "unit": "1-10"},
    }
    
    # Known clinical patterns
    CLINICAL_PATTERNS = {
        "possible_uti": {
            "description": "Possible urinary tract infection",
            "indicators": {
                "bathroom_visits": "increase_30_percent",
                "sleep_wake_events": "increase_50_percent",
                "checkin_mood_score": "decrease_20_percent",
                "voice_energy": "decrease_10_percent",
            },
            "min_indicators": 3,
        },
        "possible_dehydration": {
            "description": "Possible dehydration",
            "indicators": {
                "meal_frequency": "decrease_30_percent",
                "voice_energy": "decrease_15_percent",
                "daily_steps": "decrease_20_percent",
                "bathroom_visits": "decrease_25_percent",
            },
            "min_indicators": 3,
        },
        "possible_depression_onset": {
            "description": "Possible depression onset",
            "indicators": {
                "social_interactions": "decrease_40_percent",
                "daily_steps": "decrease_25_percent",
                "sleep_duration": "change_20_percent",  # Can increase OR decrease
                "checkin_mood_score": "decrease_30_percent",
                "voice_speech_rate": "decrease_15_percent",
            },
            "min_indicators": 3,
        },
    }
    
    def compute_drift(self, resident_id: str) -> DriftReport:
        baselines = self.get_baselines(resident_id)
        current = self.get_current_metrics(resident_id, window_days=7)
        
        z_scores = {}
        for param, config in self.DRIFT_PARAMETERS.items():
            if param in baselines and param in current:
                z = (current[param] - baselines[param].mean) / baselines[param].std
                z_scores[param] = z
        
        # Composite drift score (weighted sum of absolute Z-scores)
        composite = sum(
            abs(z_scores[p]) * self.DRIFT_PARAMETERS[p]["weight"]
            for p in z_scores
        )
        
        # Pattern matching
        matched_patterns = self._match_patterns(z_scores)
        
        # Generate report
        return DriftReport(
            resident_id=resident_id,
            composite_score=composite,
            threshold=1.5,  # Configurable per resident
            alert_triggered=composite > 1.5,
            parameter_scores=z_scores,
            matched_patterns=matched_patterns,
            trending_parameters=[
                p for p, z in z_scores.items() if abs(z) > 1.0
            ],
            generated_at=datetime.utcnow(),
        )
```

---

## 10. Voice Interaction Pipeline

### 10.1 Voice Flow Architecture

```
Resident speaks → Edge Hub Microphone
    │
    ▼
┌──────────────────────┐
│ Wake Word Detection   │  ← On-device, no cloud
│ ("Hey Aether")        │
└──────────┬───────────┘
           │ Wake word detected
           ▼
┌──────────────────────┐
│ Audio Streaming       │  ← Stream to cloud via WebSocket
│ (edge → cloud)        │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ AWS Transcribe        │  ← Streaming STT (Hindi/English)
│ (Speech-to-Text)      │
└──────────┬───────────┘
           │ Transcript
           ▼
┌──────────────────────┐
│ Intent Classification │  ← Bedrock (fast model)
│ + Entity Extraction   │
└──────────┬───────────┘
           │ Intent + entities
           ▼
┌──────────────────────┐
│ Agent Router          │  ← Route to appropriate agent
│                       │
│ Emergency → Direct    │
│ Health Q → Care Nav   │
│ Medication → Med Mgr  │
│ Chat → Companion      │
│ Command → Handler     │
└──────────┬───────────┘
           │ Response text
           ▼
┌──────────────────────┐
│ Bedrock Guardrails    │  ← Safety check on response
└──────────┬───────────┘
           │ Safe response
           ▼
┌──────────────────────┐
│ AWS Polly (Neural)    │  ← Hindi/English TTS
│ + SSML formatting     │
└──────────┬───────────┘
           │ Audio
           ▼
Edge Hub Speaker → Resident hears response
```

### 10.2 Offline Voice Mode

When offline, the edge hub handles basic voice interactions locally:

```python
class OfflineVoiceHandler:
    """
    Handles critical voice commands without cloud connectivity.
    Uses pre-cached TTS audio and simple keyword matching.
    """
    
    OFFLINE_COMMANDS = {
        "emergency": {
            "keywords": ["emergency", "help", "madad", "bachao", "SOS"],
            "response_audio": "tts_cache/emergency_acknowledged.mp3",
            "action": "trigger_local_emergency",
        },
        "medication_query": {
            "keywords": ["medicine", "dawa", "tablet", "goli"],
            "response_audio": "tts_cache/medication_time.mp3",
            "action": "check_local_medication_schedule",
        },
        "time_query": {
            "keywords": ["time", "samay", "baj"],
            "response_audio": None,  # Generated dynamically
            "action": "speak_current_time",
        },
    }
    
    CACHED_TTS_PHRASES = [
        "Kamala ji, sab theek hai? Main yahan hoon.",
        "Aapki dawa ka samay ho gaya hai.",
        "Madad aa rahi hai, aap rukiye.",
        "Abhi internet nahi hai, lekin main aapki baat sun rahi hoon.",
        "Kamala ji, kya aap theek hain? Lagta hai aap gir gayi.",
    ]
```

---

## 11. Security Architecture

### 11.1 Security Layers

```
Layer 1: Network
├── API Gateway with WAF (rate limiting, IP filtering)
├── IoT Core with mutual TLS (device certificates)
├── VPC for internal services (if needed)
└── All traffic encrypted in transit (TLS 1.2+)

Layer 2: Authentication
├── Cognito User Pools (email/password + MFA)
├── Cognito Identity Pools (federated access to AWS resources)
├── JWT token validation on every API call
├── IoT Core device certificate authentication
└── Biometric login support (mobile app)

Layer 3: Authorization
├── Role-based access control (Family, Nurse, Doctor, Admin, Facility)
├── Tenant-scoped policies (B2B isolation)
├── Resource-level permissions (resident-level access grants)
├── API Gateway authorizer with custom claims
└── DynamoDB condition expressions for row-level security

Layer 4: Data Protection
├── DynamoDB encryption at rest (AWS-managed KMS)
├── S3 encryption (SSE-S3 for non-PHI, SSE-KMS for PHI)
├── Field-level encryption for sensitive fields (Cognito ID, medical data)
├── Audit logs encrypted and immutable (S3 Object Lock)
└── Edge hub: SQLite encrypted with device-specific key

Layer 5: Application Security
├── Bedrock Guardrails (LLM output safety)
├── Input validation on all API endpoints
├── OWASP Top 10 mitigations
├── Dependency vulnerability scanning
├── Secrets Manager for API keys and credentials
└── No PHI in logs (CloudWatch log sanitization)
```

### 11.2 Multi-Tenant Isolation

```typescript
// Every DynamoDB operation includes tenant context
const getResident = async (tenantId: string, residentId: string) => {
  const result = await dynamodb.get({
    TableName: 'residents',
    Key: {
      tenant_id: tenantId,      // Partition key includes tenant
      resident_id: residentId,
    },
    // Additional condition: verify caller's tenantId matches
  });
  
  // Belt-and-suspenders: verify tenant match even if DynamoDB returns data
  if (result.Item && result.Item.tenant_id !== callerTenantId) {
    throw new UnauthorizedError('Cross-tenant access attempted');
  }
  
  return result.Item;
};
```

---

## 12. Testing Strategy

### 12.1 Test Pyramid

| Level | Tool | Coverage Target | Focus |
|---|---|---|---|
| **Unit Tests** | pytest / Jest | 80%+ | Individual functions, data transforms, model inference |
| **Integration Tests** | pytest + LocalStack | 70%+ | AWS service interactions, agent invocations, DB operations |
| **E2E Tests** | Cypress (web) / Detox (mobile) | Key flows | Complete user journeys: login → dashboard → event view |
| **Property Tests** | Hypothesis (Python) | Safety-critical | Fall detection accuracy, triage correctness, medication safety |
| **Load Tests** | k6 / Artillery | Scalability targets | API response times under load, event processing throughput |

### 12.2 Safety-Critical Property Tests

```python
# These tests are NON-NEGOTIABLE — they guard patient safety

@given(st.floats(min_value=3.0, max_value=20.0))  # High-G impact
def test_high_impact_always_detected(impact_magnitude):
    """Any accelerometer reading >3G MUST be classified as potential fall."""
    result = fall_detector.evaluate(AccelReading(magnitude=impact_magnitude))
    assert result.detected is True
    assert result.severity != FallSeverity.NONE

@given(st.text(min_size=1, max_size=100))
def test_emergency_keyword_always_triggers(text):
    """Any input containing emergency keywords MUST trigger Emergency tier."""
    for keyword in ["emergency", "help", "madad", "bachao"]:
        if keyword in text.lower():
            result = intent_classifier.classify(text)
            assert result.intent == Intent.EMERGENCY

def test_medication_name_validation():
    """LLM-generated medication names MUST be validated against the drug database."""
    fake_drug = "Nonexistentol 500mg"
    result = medication_validator.validate(fake_drug)
    assert result.valid is False
    assert result.action == "flag_for_review"

def test_raw_audio_never_leaves_edge():
    """Privacy filter MUST strip raw audio before any cloud transmission."""
    raw_reading = SensorReading(sensor_type="microphone", raw_audio=b"audio_data")
    filtered = privacy_filter.apply(raw_reading)
    assert filtered.raw_audio is None
    assert "raw_audio" not in filtered.features
```

### 12.3 Demo Scenario Tests

```python
class TestDemoScenarios:
    """End-to-end tests for demo scenarios that exercise the full system."""
    
    def test_fall_detection_to_resolution(self):
        """Full fall detection pipeline: sensor → triage → voice → family → resolve"""
        # 1. Inject fall sensor data
        # 2. Verify event created with correct severity
        # 3. Verify voice triage initiated
        # 4. Simulate resident response
        # 5. Verify appropriate escalation/resolution
        # 6. Verify event appears on dashboard
        # 7. Verify evidence packet generated
    
    def test_prescription_ocr_pipeline(self):
        """Full Rx pipeline: upload → OCR → validate → interactions → confirm"""
        # 1. Upload prescription image
        # 2. Verify Textract processes it
        # 3. Verify Comprehend Medical extracts entities
        # 4. Verify Bedrock Agent validates
        # 5. Verify interaction checking
        # 6. Verify results presented for confirmation
    
    def test_gradual_decline_detection(self):
        """14-day gradual decline: baseline → drift → alert"""
        # 1. Load 14 days of normal baseline data
        # 2. Inject 7 days of gradually declining data
        # 3. Verify drift scores increase
        # 4. Verify composite drift alert triggered
        # 5. Verify clinical pattern matched
    
    def test_ride_booking_autonomous(self):
        """Full ride booking: appointment → book → confirm → notify"""
        # 1. Create appointment in care calendar
        # 2. Verify ride booking agent triggered
        # 3. Verify appropriate vehicle selected
        # 4. Verify voice confirmation initiated
        # 5. Verify family notified
```

---

## 13. Model Routing Strategy

### 13.1 LLM Model Selection

```python
class ModelRouter:
    """
    Routes LLM requests to the most cost-effective model that meets quality requirements.
    
    Cost hierarchy (cheapest → expensive):
    1. Claude 3 Haiku — fast, cheap, good for classification
    2. Claude 3.5 Sonnet — balanced, good for summarization
    3. Claude 3.5 Sonnet v2 — highest quality, complex reasoning
    """
    
    MODEL_MAP = {
        # Classification tasks — use cheapest model
        "intent_classification": "anthropic.claude-3-haiku-20240307-v1:0",
        "event_triage": "anthropic.claude-3-haiku-20240307-v1:0",
        "sentiment_analysis": "anthropic.claude-3-haiku-20240307-v1:0",
        
        # Generation tasks — use mid-tier
        "daily_summary": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "medication_reminder_text": "anthropic.claude-3-haiku-20240307-v1:0",
        "care_navigation_qa": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        
        # Complex reasoning — use top tier
        "clinical_summarization": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "drug_interaction_analysis": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "drift_pattern_analysis": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "prescription_validation": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    }
    
    def select_model(self, task: str) -> str:
        return self.MODEL_MAP.get(task, "anthropic.claude-3-haiku-20240307-v1:0")
```

---

## 14. Deployment Architecture

### 14.1 Infrastructure as Code (AWS CDK)

```typescript
// CDK Stack Overview
const app = new cdk.App();

// Stack 1: Foundation
const authStack = new AuthStack(app, 'AetherAuth', {
  // Cognito User Pool with custom attributes (role, tenant_id)
  // Identity Pool for AWS resource access
});

// Stack 2: Storage
const storageStack = new StorageStack(app, 'AetherStorage', {
  // DynamoDB tables (5)
  // S3 buckets (4)
  // KMS keys for PHI encryption
});

// Stack 3: IoT
const iotStack = new IoTStack(app, 'AetherIoT', {
  // IoT Core thing types, policies, certificates
  // IoT Rules for routing to Kinesis/Lambda
});

// Stack 4: API + Lambda
const apiStack = new ApiStack(app, 'AetherApi', {
  // API Gateway (REST + WebSocket)
  // Lambda functions (10+)
  // Step Functions (3 state machines)
  // Kinesis Data Stream
});

// Stack 5: Intelligence
const aiStack = new IntelligenceStack(app, 'AetherAI', {
  // Bedrock Agent configurations
  // Knowledge Base setup
  // Guardrail policies
});

// Stack 6: Hosting  
const hostingStack = new HostingStack(app, 'AetherHosting', {
  // Amplify app for web dashboard
  // CloudFront distribution
});
```

### 14.2 Environment Strategy

| Environment | Purpose | Cost | Region |
|---|---|---|---|
| **dev** | Active development, testing | ~$20/month | ap-south-1 |
| **staging** | Pre-demo validation | ~$30/month | ap-south-1 |
| **demo** | Live demo environment | ~$50-60/month | ap-south-1 |

---

## 15. Scalability Plan

### Phase 1: Single Home (Demo) — Month 1-2
- 1 home, 1-2 residents, all simulated sensors
- Single-tenant DynamoDB
- 1 Kinesis shard
- On-demand Lambda

### Phase 2: Multi-Home (Pilot) — Month 3-4
- 5-10 homes, multi-tenant DynamoDB
- Real hardware (some homes)
- Enhanced monitoring

### Phase 3: B2B Clinic (Growth) — Month 5-8
- 50-100 homes per clinic
- Provisioned DynamoDB capacity
- Multi-region consideration
- Staff management features

### Phase 4: Enterprise (Scale) — Month 9+
- 1000+ homes
- DynamoDB Global Tables (multi-region)
- Kinesis Firehose for analytics
- SageMaker for custom models
- Dedicated support tier

---

## 16. Technology Decisions & Tradeoffs

| Decision | Choice | Alternative Considered | Rationale |
|---|---|---|---|
| Edge hardware | Raspberry Pi 5 | Jetson Orin Nano | Cost ($85 vs $500). GPU not needed for demo sensor simulation. Jetson is upgrade path. |
| Primary DB | DynamoDB | RDS PostgreSQL | Serverless, auto-scaling, per-request pricing, schema flexibility for evolving data models |
| LLM Platform | AWS Bedrock | Self-hosted LLM | Managed service, no GPU infra, guardrails built-in, pay-per-token |
| Web Framework | React + Vite | Next.js | Simpler for SPA dashboard. SSR not needed (all data via API). Amplify hosting. |
| Mobile Framework | React Native + Expo | Flutter | Code sharing with web (TypeScript). Expo simplifies builds. Large community. |
| Event Streaming | Kinesis Data Streams | SQS | Real-time stream processing needed for continuous sensor data. Kinesis retains data for replay. |
| Auth | Cognito | Auth0 | AWS-native, free tier covers demo, integrates with all AWS services |
| OCR | Textract + Comprehend Medical | Google Cloud Vision | AWS-native, Comprehend Medical is purpose-built for medical text |
| Voice | Transcribe + Polly | Google Speech / ElevenLabs | AWS-native, Hindi support, neural voices, integrated billing |

---

*End of Technical Design Document — AETHER CareOps Platform v2.0*
