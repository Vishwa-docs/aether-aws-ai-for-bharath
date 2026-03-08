# AETHER CareOps Platform — 2-Month Sprint Plan

> **Version**: 2.0 — Full CareOps Platform  
> **Timeline**: 8 Weeks (2 Months)  
> **Developer**: Single senior full-stack dev with AI assistance  
> **Last Updated**: 2025-07-13  
> **Status**: Planning & Architecture Phase

---

## Sprint Philosophy

This sprint produces a **demo-ready CareOps platform** that proves ALL 12 pain points with simulated hardware and real AI agents. Every week builds on the previous one. Each week has a **demo checkpoint** — a tangible, showable milestone.

**Key Principle**: Build the thinnest possible vertical slice through ALL layers (edge → cloud → client) first, then widen each layer.

---

## Phase 1: Foundation & Infrastructure (Week 1-2)

> **Checkpoint**: CDK deploys, API returns data, dashboard renders, edge hub runs simulators

### Task 1.1: Project Scaffolding & Monorepo Setup 🔴 DEMO
- [ ] Initialize monorepo structure: `/edge` (Python), `/cloud` (Python Lambda), `/dashboard` (React), `/mobile` (React Native), `/infrastructure` (CDK TypeScript)
- [ ] Set up Python virtual environments (edge, cloud) with shared models
- [ ] Set up Node/TypeScript for dashboard and infrastructure
- [ ] Configure linting (ruff for Python, ESLint for TypeScript), formatting (black, prettier)
- [ ] Create shared TypeScript interfaces in `/infrastructure/lib/models/` (Event, Resident, Medication, etc.)
- [ ] Create shared Python models in `/cloud/lambdas/shared/models.py` aligned with TypeScript types
- [ ] Initialize Git repository with branching strategy (main, develop, feature/*)
- **Output**: Clean monorepo with all packages, shared types, build/lint scripts

### Task 1.2: AWS CDK Infrastructure — Core Stacks 🔴 DEMO
- [ ] **Auth Stack**: Cognito User Pool (email+password, custom attributes: role, tenant_id), Identity Pool, App Client for dashboard + mobile
- [ ] **Storage Stack**: DynamoDB tables (residents, events, medications, health_records, care_calendar) with GSIs + TTL. S3 buckets (prescriptions, knowledge-base, reports, audit)
- [ ] **IoT Stack**: IoT Core thing type, policy, rule (route MQTT → Kinesis), test certificate generation
- [ ] **API Stack**: API Gateway (REST) with Cognito authorizer, Lambda functions (stub handlers), Kinesis Data Stream (1 shard)
- [ ] Configure CDK environments (dev). Deploy and verify all resources created.
- [ ] Set up CloudWatch dashboards for cost monitoring
- **Output**: `cdk deploy` creates all resources. API Gateway returns 200. DynamoDB tables exist.

### Task 1.3: Seed Data & Mock Profiles 🔴 DEMO
- [ ] Create Kamala Devi resident profile with full medical history (diabetes, hypertension, arthritis), 8 medications, baselines, contacts (Arjun as primary)
- [ ] Create Arjun Mehta family caregiver user account with permissions
- [ ] Create Sister Priya Nair nurse account with 3-patient roster (including Kamala)
- [ ] Create Dr. Suresh Iyer doctor account
- [ ] Create seed medication schedules with realistic Indian medications (Metformin, Amlodipine, Atorvastatin, Aspirin, Pantoprazole, etc.)
- [ ] Create seed event history (2 weeks of simulated normal data + 2 fall events + 5 missed medications)
- [ ] Create DynamoDB seed script that populates all tables
- **Output**: Running seed script populates DynamoDB with realistic demo data for all personas

### Task 1.4: Edge Hub Bootstrap 🔴 DEMO
- [ ] Set up edge hub Python project with asyncio event loop
- [ ] Implement local MQTT broker (using `asyncio-mqtt` or `hbmqtt`)
- [ ] Implement basic sensor data aggregation (receive MQTT, normalize, timestamp)
- [ ] Implement connectivity monitor (check IoT Core reachability, track online/offline state)
- [ ] Implement SQLite event queue (enqueue, dequeue, sync on reconnect)
- [ ] Implement AWS IoT Core client (MQTT publish with certificates)
- [ ] Test: edge hub receives simulated sensor data via local MQTT, queues events, publishes to IoT Core when online
- **Output**: Edge hub binary that connects to sensors (simulated) and forwards events to AWS

### Task 1.5: Sensor Simulators — Core Set 🔴 DEMO
- [ ] Implement accelerometer simulator (walking, sitting, sleeping, falling profiles)
- [ ] Implement pressure mat simulator (bed occupancy, sudden unloading)
- [ ] Implement PIR motion simulator (room transitions, activity patterns)
- [ ] Implement door/window sensor simulator (open/close events)
- [ ] Implement temperature/humidity simulator (normal + extreme scenarios)
- [ ] Implement gas sensor simulator (cooking gas detected, leak scenario)
- [ ] Implement pillbox simulator (compartment opened at scheduled time, missed dose)
- [ ] Implement daily routine scenario manager (Kamala Devi's day: wake, pray, cook, eat, medicate, rest, sleep)
- [ ] Implement accelerated replay mode (compress 24h into 5 minutes for demo)
- **Output**: Run `python simulate.py --scenario morning_routine` and see realistic sensor data flowing through MQTT

### Task 1.6: Web Dashboard — Shell & Auth 🔴 DEMO
- [ ] Set up React 18 + TypeScript + Vite + TailwindCSS project
- [ ] Integrate AWS Amplify for auth (Cognito login/signup)
- [ ] Implement role-based routing (Family, Nurse, Doctor, OpsMgr → different dashboard layouts)
- [ ] Build sidebar navigation component with role-aware menu items
- [ ] Build header with user info, notification bell (placeholder), language toggle
- [ ] Create placeholder pages for all views (Dashboard, Events, Medications, Calendar, Analytics, Settings)
- [ ] Deploy to Amplify Hosting (CI/CD from Git)
- **Output**: Login as Arjun → see Family Dashboard shell. Login as Sister Priya → see Nurse view shell.

---

## Phase 2: Core Monitoring & Events (Week 3)

> **Checkpoint**: Fall detection works end-to-end, events appear on dashboard in real-time

### Task 2.1: Fall Detection Pipeline (Edge) 🔴 DEMO
- [ ] Implement fall detection fusion algorithm (accelerometer + pressure mat + acoustic)
- [ ] Implement severity classification (minor/moderate/severe) with multi-sensor confidence scoring
- [ ] Implement post-fall immobility detection (prolonged floor-level presence)
- [ ] Wire fall detection into edge hub main loop
- [ ] Test with fall simulator scenario: inject fall data → detect → classify → queue
- **Output**: Simulate a fall → edge hub detects it within 2 seconds with correct severity

### Task 2.2: Acoustic Event Detection (Edge) 🔴 DEMO
- [ ] Implement acoustic classifier (scream/distress, glass break, sustained cough, impact sounds, prolonged silence)
- [ ] Implement privacy filter — extract acoustic features only, discard raw audio
- [ ] Wire acoustic detection into edge hub
- [ ] Test: simulate scream event → detected with >85% confidence → event queued (no raw audio in event)
- **Output**: Acoustic events detected on-device with only labels/confidence transmitted

### Task 2.3: Event Processing Pipeline (Cloud) 🔴 DEMO
- [ ] Implement `event_processor` Lambda triggered by Kinesis
- [ ] Parse incoming IoT events, validate schema, enrich with resident profile data
- [ ] Store events in DynamoDB `events` table with appropriate severity and TTL
- [ ] Implement WebSocket API (API Gateway) for real-time event push to dashboard
- [ ] Test: IoT Core receives event → Kinesis → Lambda processes → DynamoDB stores → WebSocket pushes to dashboard
- **Output**: Full event pipeline from edge to dashboard working end-to-end

### Task 2.4: Dashboard — Real-Time Events & Timeline 🔴 DEMO
- [ ] Implement resident status card (current state, last event, medication adherence today)
- [ ] Implement 24-hour activity timeline with event markers (fall, medication, meal, alert)
- [ ] Implement WebSocket connection for real-time event updates (events appear immediately)
- [ ] Implement event detail panel (click event → see evidence, sensor data, triage decision)
- [ ] Implement alert banner for active Alert/Emergency events
- [ ] Style with AETHER branding and color-coded severity indicators
- **Output**: Dashboard shows Kamala's live timeline. Simulate a fall → it appears on dashboard within 5 seconds.

### Task 2.5: Environmental Monitoring 🔴 DEMO
- [ ] Wire temperature/humidity data to event processor (extreme temp alerts)
- [ ] Implement stove safety monitoring: "stove on + no kitchen motion for 15 min" → alert
- [ ] Add environmental status to dashboard (current temp, gas status)
- [ ] Test: simulate stove left on → verbal reminder (logged) → caregiver alert on dashboard
- **Output**: Environmental alerts working on dashboard

---

## Phase 3: Medication & Voice (Week 4)

> **Checkpoint**: Voice interaction works, medication reminders delivered, check-in completed

### Task 3.1: Medication Management System 🔴 DEMO
- [ ] Implement medication CRUD API (add, update, remove medications per resident)
- [ ] Implement medication schedule engine (compute next dose times from frequency/timing)
- [ ] Implement reminder trigger (Lambda scheduled check every 5 min → due reminders → push to edge)
- [ ] Implement medication adherence tracking (pillbox sensor confirms → log taken/missed)
- [ ] Implement escalation for missed meds: reminder at T+0 → second at T+15min → caregiver alert at T+30min
- [ ] Dashboard: medication schedule view, adherence percentage, missed dose highlighting
- **Output**: Kamala's 8-medication schedule managed with voice reminders and adherence tracking

### Task 3.2: Voice Interaction — Online Pipeline 🔴 DEMO
- [ ] Implement wake word detection on edge hub (keyword spotting for "Hey Aether")
- [ ] Implement streaming audio pipeline: edge → WebSocket → Lambda → Transcribe (streaming)
- [ ] Implement intent classification using Bedrock (Haiku) — categorize: emergency, medication, companion, health_question, command
- [ ] Implement response generation (Bedrock Sonnet for open-ended, rule-based for commands)
- [ ] Implement TTS response delivery (Polly neural → audio → edge → speaker)
- [ ] End-to-end test: "Hey Aether, meri dawa ka samay ho gaya kya?" → check schedule → "Haan Kamala ji, aapki Metformin leni hai. Khane ke baad, paani ke saath."
- **Output**: Full voice conversation in Hindi working end-to-end

### Task 3.3: Voice Interaction — Offline Mode 🔴 DEMO
- [ ] Implement offline command handler (keyword matching for: emergency, medication, time)
- [ ] Pre-cache common TTS phrases on edge hub (20+ Hindi phrases for reminders, greetings, medication names)
- [ ] Implement graceful degradation: if cloud unavailable → local keyword processing → cached audio response
- [ ] Test: disconnect internet → "Hey Aether, emergency!" → local emergency response triggered
- **Output**: Basic voice commands work without internet

### Task 3.4: Daily Health Check-In 🔴 DEMO
- [ ] Implement check-in conversation flow using Bedrock Agent with guided dialogue
- [ ] Conversation covers: sleep quality, pain levels, mood, appetite, hydration, specific complaints
- [ ] Implement structured data extraction from natural conversation (Bedrock NLU → numeric scores)
- [ ] Store check-in results in health_records table
- [ ] Display check-in history on dashboard with mood/pain/sleep trend charts
- [ ] Test: full check-in conversation in Hindi → structured data extracted → visible on dashboard
- **Output**: "Kamala ji, kal raat neend kaisi rahi?" → natural conversation → structured health data

### Task 3.5: Medication Dashboard & Calendar View 🔴 DEMO
- [ ] Build medication schedule page on dashboard (visual timeline, pill identification)
- [ ] Build adherence chart (daily/weekly/monthly adherence percentage)
- [ ] Build missed dose log with timestamps and escalation actions taken
- [ ] Build care calendar page with upcoming appointments, medication reminders
- **Output**: Dashboard shows complete medication management view

---

## Phase 4: Agentic AI & Intelligence (Week 5)

> **Checkpoint**: 3+ Bedrock Agents working autonomously, prescription OCR pipeline functional

### Task 4.1: Bedrock Agent — Intelligent Triage 🔴 DEMO
- [ ] Create Triage Agent in AWS Bedrock with: role/instructions, tools (get_resident_profile, get_recent_events, get_medication_schedule), knowledge base connection
- [ ] Implement action groups: classify_event, invoke_voice_triage, send_notification
- [ ] Configure Bedrock Guardrails for triage agent output safety
- [ ] Wire triage agent into event_processor Lambda (route incoming events to agent for classification)
- [ ] Implement adaptive threshold learning: store triage outcomes, adjust confidence thresholds per resident
- [ ] Test: simulate 10 events (mix of real alerts and false alarms) → agent classifies correctly → suppresses false alarms → logs reasoning
- **Output**: Events are triaged by AI with <10% false positive rate. Dashboard shows "Why this alert?" explanations.

### Task 4.2: Bedrock Agent — Clinical Scribe 🔴 DEMO
- [ ] Create Clinical Scribe Agent with: tools (get_events, get_health_records, get_medication_adherence, get_checkin_data, get_drift_scores)
- [ ] Implement daily summary generation (automated, runs at end of day)
- [ ] Implement weekly SOAP note generation for each resident
- [ ] Implement pre-consultation report generation (triggered 24h before appointment)
- [ ] Store generated reports in health_records table + S3 (PDF rendering)
- [ ] Dashboard: clinical summary view for doctors, downloadable reports
- [ ] Test: run Scribe Agent on Kamala's 2-week data → generates comprehensive summary with trends and recommendations
- **Output**: Dr. Suresh sees auto-generated pre-consultation report on dashboard

### Task 4.3: Prescription OCR Pipeline (Agentic Workflow) 🔴 DEMO
- [ ] Implement S3 trigger: prescription image uploaded → Lambda invoked
- [ ] Implement Textract document analysis (handwritten + printed text extraction)
- [ ] Implement Comprehend Medical entity extraction (drug names, dosages, frequencies)
- [ ] Create Prescription Validation Agent in Bedrock (validates extracted meds against known drug database, resolves ambiguities)
- [ ] Implement Step Function workflow: Textract → Comprehend → Agent → Confidence Check → Human Review (if needed) → Confirm
- [ ] Build prescription upload UI in mobile app (camera capture) and dashboard (file upload)
- [ ] Build results display UI: extracted medications, confidence scores, "Confirm" button
- [ ] Test: upload sample handwritten Rx → structured medication list extracted → confidence displayed → user confirms → meds added to schedule
- **Output**: Photo of handwritten prescription → structured medication list in <30 seconds

### Task 4.4: Bedrock Agent — Polypharmacy Checker 🔴 DEMO
- [ ] Build drug interaction knowledge base (S3 documents with common drug-drug and food-drug interactions)
- [ ] Create Polypharmacy Agent in Bedrock with KB access + interaction checking tools
- [ ] Implement interaction checking flow: triggered on any medication add/change
- [ ] Implement PMBJP generic alternative lookup (knowledge base with generic medicine catalog)
- [ ] Build interaction report display on dashboard and mobile app
- [ ] Wire into Prescription OCR pipeline: after extraction → auto-check interactions
- [ ] Test: add Clopidogrel to Kamala's medications → immediate interaction report → Clopidogrel+Aspirin flagged as MAJOR → generic alternatives shown
- **Output**: Automated drug interaction checking with generic alternatives and cost savings

### Task 4.5: Bedrock Agent — Care Navigation 🔴 DEMO
- [ ] Build medical Q&A knowledge base (S3: general health info, condition management guides, Indian-specific dietary guidance)
- [ ] Create Care Navigation Agent with KB, guardrails (no medical advice, disclaimers required), culturally-aware system prompt
- [ ] Implement voice-based health Q&A: resident asks → agent searches KB → responds in Hindi → follow-up tasks created
- [ ] Implement task creation from navigation: "I have knee pain" → agent responds + creates "Discuss knee pain with Dr. Iyer" task
- [ ] Dashboard: view navigator interactions, task list
- [ ] Test: "Aether, mujhe blood sugar badhne par kya karna chahiye?" → culturally-appropriate Hindi response with dietary tips + disclaimer
- **Output**: Health Q&A in Hindi with RAG-grounded responses

### Task 4.6: Drift Detection Engine 🔴 DEMO
- [ ] Implement baseline computation (14-day rolling averages + standard deviations per parameter)
- [ ] Implement Z-score computation for all drift parameters (sleep, activity, adherence, voice, meals, bathroom, social, mood)
- [ ] Implement composite drift score (weighted sum of absolute Z-scores)
- [ ] Implement clinical pattern matching (UTI pattern, dehydration pattern, depression onset)
- [ ] Run as scheduled Lambda (hourly)
- [ ] Generate drift alerts in events table when composite score exceeds threshold
- [ ] Dashboard: drift gauge visualization, parameter-level trend charts, pattern match display
- [ ] Test: inject 14 days gradual decline data → drift score rises → alert triggered with pattern match → visible on dashboard
- **Output**: Simulate 2-week gradual decline → system detects and alerts with "Possible UTI" pattern match

---

## Phase 5: Auto Ride Booking & Advanced Agents (Week 6)

> **Checkpoint**: Ride booking works autonomously, FHIR export functional, escalation ladder complete

### Task 5.1: Auto Ride Booking Agent 🔴 DEMO
- [ ] Create mock ride booking API (Lambda simulating Ola/Uber Health: book, cancel, status, track)
- [ ] Create Ride Booking Agent in Bedrock with tools: get_care_calendar, get_resident_profile, book_ride, cancel_ride, voice_confirm, notify_family
- [ ] Implement trigger: appointment in care_calendar within 48h + resident needs transport → agent invoked
- [ ] Implement vehicle selection based on mobility status (auto-rickshaw, cab, wheelchair-accessible)
- [ ] Implement voice confirmation with resident
- [ ] Implement family notification on booking
- [ ] Implement ride-day reminders (T-1h, T-30min, T-15min)
- [ ] Dashboard: ride booking status card, booking history
- [ ] Test: create appointment for Kamala → agent books ride → confirms via voice → Arjun notified → reminders sent
- **Output**: Fully autonomous ride booking from appointment detection to confirmation

### Task 5.2: Escalation Ladder (Step Function) 🔴 DEMO
- [ ] Implement Step Function: VoiceTriage → EvaluateResponse → NotifyFamily → WaitForResponse → EmergencyEscalation
- [ ] Implement voice triage initiation (edge hub speaks to resident, records response quality)
- [ ] Implement family notification (push notification, SMS via SNS)
- [ ] Implement configurable timeouts per tier (voice: 30s, family: 5min)
- [ ] Implement de-escalation (resident says "I'm fine" → resolve and log)
- [ ] Implement emergency evidence packet generation on Emergency escalation
- [ ] Test: fall detected → voice triage → no response → Arjun notified → Arjun doesn't respond → emergency escalation with evidence packet
- **Output**: Complete escalation workflow from event to resolution with evidence packets

### Task 5.3: Emergency Evidence Packet 🔴 DEMO
- [ ] Implement evidence packet generator Lambda: collects patient info, medications, recent events, vital trends, response timeline
- [ ] Generate shareable URL (API Gateway endpoint, no auth required, time-limited)
- [ ] Generate QR code for physical display on edge hub screen (if display connected)
- [ ] Mobile-friendly HTML rendering of evidence packet
- [ ] Test: emergency event → evidence packet generated in <10 seconds → accessible via URL → shows complete patient context
- **Output**: Shareable emergency packet URL with complete patient context

### Task 5.4: FHIR Data Export 🔴 DEMO
- [ ] Implement FHIR R4 resource generators: Patient, Observation, MedicationStatement, MedicationAdministration, DiagnosticReport, AllergyIntolerance
- [ ] Implement FHIR Bundle composition (collection of resources per resident)
- [ ] Build API endpoint: GET /residents/{id}/records/fhir → returns FHIR Bundle JSON
- [ ] Build human-readable PDF rendering of FHIR data (wkhtmltopdf or similar)
- [ ] Dashboard: "Export FHIR" button on doctor view, "Download PDF Report" on all views
- [ ] Test: export Kamala's data as FHIR → validate against FHIR R4 schema → valid bundle with all resource types
- **Output**: One-click FHIR export of patient health records

### Task 5.5: Voice Companion & Social Features 🔴 DEMO
- [ ] Implement AI companion persona in Bedrock (warm, Hindi-speaking, remembers past conversations)
- [ ] Implement scheduled companion interactions (morning greeting, afternoon chat, evening wind-down)
- [ ] Implement conversation context persistence (DynamoDB: store last 10 conversation summaries per resident)
- [ ] Implement social engagement tracking (interaction count, duration, sentiment analysis)
- [ ] Build social engagement display on dashboard
- [ ] Test: "Hey Aether, kuch baat karo" → warm Hindi conversation → references previous conversations → companion persona maintained
- **Output**: Natural companion conversations in Hindi with memory

---

## Phase 6: Web Dashboard Complete & Mobile App (Week 7)

> **Checkpoint**: Dashboard fully functional with all views, mobile app running on device

### Task 6.1: Dashboard — Family View Complete 🔴 DEMO
- [ ] Real-time status card with all metrics (activity, sleep, medication, drift, mood)
- [ ] Weekly trend charts (Chart.js or Recharts): sleep duration, activity, adherence, drift score, mood
- [ ] Event history page with filtering (by type, severity, date range) and pagination
- [ ] Medication management page (view schedule, see adherence history, upload Rx)
- [ ] Care calendar page (appointments, ride bookings)
- [ ] Settings page (alert preferences, emergency contacts, notification channels)
- [ ] Notification center (bell icon → recent notifications with mark-read)
- **Output**: Arjun can manage his mother's care entirely from the dashboard

### Task 6.2: Dashboard — Clinic/Doctor Views 🔴 DEMO
- [ ] **Nurse View**: Patient list with status indicators, click-to-detail, shift summary view, voice note transcription display
- [ ] **Doctor View**: Pre-consultation report view, FHIR export, drift analysis, medication review, clinical summary timeline
- [ ] **Ops Manager View (Fleet)**: Grid of all patients with color-coded status (green/yellow/orange/red), aggregate analytics, caregiver workload, compliance metric cards
- [ ] Alert management: acknowledge from dashboard, mark false positive, add notes
- [ ] Export functionality: PDF reports, CSV data export
- **Output**: All 5 dashboard roles fully functional with realistic data

### Task 6.3: Mobile App — Foundation 🔴 DEMO
- [ ] Initialize React Native + Expo project with TypeScript
- [ ] Implement Cognito auth integration (login, signup, biometric)
- [ ] Implement role-based navigation (Elderly / Family / Nurse)
- [ ] Build API client service (shared types with dashboard)
- [ ] Implement push notification setup (Expo Notifications → SNS)
- [ ] Implement offline data caching (AsyncStorage for essential data)
- **Output**: App builds, authenticates, and navigates based on role

### Task 6.4: Mobile App — Elderly View 🔴 DEMO
- [ ] Build Home screen (extra-large UI, status summary, voice button, SOS button)
- [ ] Build Medication screen (visual pill schedule with color-coded compartments, time-of-day grouping)
- [ ] Build Help screen (SOS button, "Call family" button, Care Navigation voice button)
- [ ] Build Family screen (voice postcard playback, "Call Arjun" button)
- [ ] Apply elderly theme (28pt+ fonts, high contrast, max 4 screens, 56px touch targets)
- [ ] Hindi language support throughout
- **Output**: Kamala can see her medications, press SOS, and interact via voice on a tablet

### Task 6.5: Mobile App — Family View 🔴 DEMO
- [ ] Build Dashboard screen (status overview, latest events, medication adherence)
- [ ] Build Events screen (timeline with event details, evidence viewer)
- [ ] Build Medications screen (view schedule, adherence chart)
- [ ] Build Camera/Rx screen (capture prescription photo → upload → OCR pipeline)
- [ ] Build Settings screen (preferences, contacts, alert configuration)
- [ ] Implement push notification handling (tap notification → navigate to relevant event)
- **Output**: Arjun manages his mother's care from his phone with push notifications

---

## Phase 7: Integration, Polish & Demo Prep (Week 8)

> **Checkpoint**: Full demo scenario runs end-to-end with all 12 pain points demonstrated

### Task 7.1: Integration Testing 🔴 DEMO
- [ ] End-to-end test: Fall detection → triage → voice triage → escalation → notification → dashboard → evidence packet
- [ ] End-to-end test: Prescription upload → OCR → interaction checking → generic alternatives → medication schedule update
- [ ] End-to-end test: Gradual decline simulation (14 days) → drift detection → alert → clinical summary
- [ ] End-to-end test: Appointment → ride booking → voice confirm → reminder → ride tracking
- [ ] End-to-end test: Daily check-in → structured data → health record → pre-consultation summary
- [ ] End-to-end test: Voice companion conversation → sentiment tracking → social engagement metrics
- [ ] Offline mode test: disconnect → fall detection works → events queue → reconnect → sync
- [ ] Multi-user test: Arjun, Sister Priya, and Dr. Suresh all see appropriate data based on role
- **Output**: All critical paths verified end-to-end

### Task 7.2: Demo Scenarios & Scripts 🔴 DEMO
- [ ] **Scenario 1: Morning Routine** — Kamala wakes up, takes medication (voice reminder), has breakfast, does morning check-in
- [ ] **Scenario 2: Fall & Response** — Kamala slips in bathroom → detection → voice triage → she says she's okay → logged and resolved
- [ ] **Scenario 3: Serious Fall** — Fall with no voice response → Arjun notified → Arjun takes 6 minutes → emergency escalation → evidence packet
- [ ] **Scenario 4: New Prescription** — Arjun photographs new Rx → OCR extracts 2 new meds → interaction found with existing Aspirin → generic alternatives shown
- [ ] **Scenario 5: Gradual Decline** — Accelerated 2-week data showing UTI-like pattern → drift alert → clinical summary shows pattern
- [ ] **Scenario 6: Care Navigation** — Kamala asks in Hindi about diabetes management → RAG-grounded response → follow-up task created
- [ ] **Scenario 7: Ride Booking** — Appointment detected → agent books ride → confirms with Kamala → notifies Arjun
- [ ] **Scenario 8: Clinic Operations** — Meena views fleet dashboard → sees high-priority patients → reviews compliance metrics
- [ ] **Scenario 9: Kitchen Safety** — Stove left on → 15-min warning → no response → Arjun alerted
- [ ] **Scenario 10: Companion Chat** — Kamala initiates conversation → warm Hindi exchange → system references yesterday's chat
- [ ] Create demo runner script that orchestrates scenarios with appropriate timing
- [ ] Create demo narration guide (what to show, what to explain at each step)
- **Output**: 10 demo scenarios scripted and rehearsed

### Task 7.3: Performance & Cost Optimization 🔴 DEMO
- [ ] Profile Lambda cold start times — ensure <3 second warm, <5 second cold
- [ ] Verify API response times <500ms (95th percentile)
- [ ] Verify event processing latency <5 seconds end-to-end
- [ ] Verify dashboard load time <2 seconds
- [ ] Review and optimize Bedrock model usage (Haiku for classification, Sonnet for generation)
- [ ] Review DynamoDB capacity (on-demand is sufficient for demo)
- [ ] Generate AWS cost report — verify <$60/month projection
- [ ] Clean up unused resources, remove dev artifacts
- **Output**: Performance meets targets, cost under budget

### Task 7.4: Documentation & Cleanup 🔴 DEMO
- [ ] Update README.md with project overview, setup instructions, architecture diagram
- [ ] Document all API endpoints with request/response examples
- [ ] Document demo script (step-by-step what to show)
- [ ] Document Bedrock Agent configurations and prompt patterns
- [ ] Clean up code: remove TODOs, debug logging, unused imports
- [ ] Create environment setup guide (AWS credentials, CDK bootstrap, local dev)
- **Output**: Anyone can clone, set up, and run the demo following documentation

### Task 7.5: Final Demo Run & Recording 🔴 DEMO
- [ ] Full dry run of all 10 demo scenarios
- [ ] Fix any issues discovered during dry run
- [ ] Screen record complete demo (15-20 minutes)
- [ ] Prepare 5-minute highlight reel for quick presentations
- [ ] Deploy final version to `demo` environment
- **Output**: Polished, recorded demo ready for presentation

---

## Weekly Checkpoints & Deliverables

| Week | Phase | Deliverable | Demo Proof |
|---|---|---|---|
| 1-2 | Foundation | Infrastructure deployed, simulators running, dashboard shell | CDK deploy → API works → dashboard renders → sensors stream |
| 3 | Core Monitoring | Fall detection + event pipeline | Simulate fall → appears on dashboard in <5 seconds |
| 4 | Medication & Voice | Voice interaction + medication management | Hindi voice command → correct response → medication reminder works |
| 5 | Agentic AI | 5 Bedrock Agents + Rx OCR + drift detection | Upload Rx → extracted → interactions checked → drift alert shown |
| 6 | Advanced Agents | Ride booking + escalation + FHIR + companion | Appointment → ride booked → confirmed via voice → FHIR exported |
| 7 | Full Client | Dashboard complete + mobile app functional | All 5 dashboard roles working, mobile app on device |
| 8 | Demo Ready | 10 scenarios polished, performance optimized | Full demo runs smoothly, <$60/month cost confirmed |

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Bedrock model not available in ap-south-1 | Medium | High | Use us-east-1 as fallback (higher latency acceptable for non-real-time) |
| Textract poor on handwritten Hindi Rx | High | Medium | Implement confidence scoring + human review path. Use printed Rx for demo. |
| Lambda cold starts affect voice latency | Medium | Medium | Use provisioned concurrency for voice Lambda ($25/month additional) |
| React Native + Expo limitations | Low | Medium | Use bare workflow if Expo constraints hit. Most features are API calls. |
| Cost exceeds $60/month during development | Medium | Low | Monitor CloudWatch billing. Use dev environment with minimal data. Tear down nightly. |
| Knowledge base quality for Care Navigation | Medium | High | Curate KB manually with verified medical sources. Start small, expand. |
| Single developer bottleneck | High | High | Use AI coding assistants aggressively. Prioritize ruthlessly. Cut stretch features if behind. |

---

## Definition of Done — 2-Month Sprint

The sprint is complete when:

1. ✅ **ALL 12 pain points** are demonstrated with working features
2. ✅ **6+ Bedrock Agents** working autonomously (Triage, Scribe, Care Nav, Polypharmacy, Ride Booking, Rx OCR)
3. ✅ **Web dashboard** with 5 role-based views rendering real data
4. ✅ **Mobile app** with elderly and family views running on device
5. ✅ **Voice interaction** in Hindi working end-to-end (wake word → response)
6. ✅ **Prescription OCR** pipeline from photo to structured medication list
7. ✅ **Drift detection** shows gradual decline detection with clinical pattern matching
8. ✅ **Offline operation** demonstrated for safety-critical features
9. ✅ **10 demo scenarios** scripted and rehearsed
10. ✅ **AWS cost** < ₹5,000/month ($60 USD) confirmed with billing data
11. ✅ **Documentation** sufficient for setup and demo by another person
12. ✅ **Screen recording** of complete demo (15-20 min) available

---

*End of Sprint Plan — AETHER CareOps Platform v2.0*
