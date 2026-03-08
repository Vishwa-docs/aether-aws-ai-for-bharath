# AETHER CareOps Platform — Requirements Specification

> **Version**: 2.0 — Full CareOps Platform Vision  
> **Sprint**: 2-Month (8-Week) Development Sprint  
> **Last Updated**: 2025-07-13  
> **Status**: Planning & Architecture Phase

---

## 1. Introduction

AETHER (Autonomous Elderly Technology for Health, Engagement & Response) is a **comprehensive CareOps Platform** — the complete operating system for elderly care. It combines ambient sensors, wearable devices, edge AI processing, agentic GenAI workflows, and care coordination into a unified system that addresses the **12 most critical pain points** in elderly care.

This is not a simple fall detection gadget or a medication reminder app. AETHER is an **enterprise-grade autonomous care ecosystem** that works across three tiers:

- **Edge Layer** — Sensors + edge AI on Raspberry Pi 5 (or Jetson Orin Nano) for real-time, private, offline-capable processing
- **Cloud Layer** — AWS-native backend with multi-agent AI orchestration, clinical intelligence, and predictive analytics
- **Client Layer** — Web dashboard for caregivers/clinics + AI-powered mobile app for elderly and families

### 1.1 Key Differentiators

| Differentiator | Description |
|---|---|
| **Agentic AI Workflows** | Autonomous multi-agent system that ACTS, not just alerts — books rides, checks drug interactions, generates clinical reports |
| **Predictive, Not Reactive** | Drift detection engine identifies health decline weeks before crisis through personalized baselines |
| **Privacy-First Edge AI** | Raw sensor data never leaves the home — only features and events are transmitted |
| **Voice-First UX** | Natural Hindi/English/Tamil/Kannada voice interaction for elderly who can't use touchscreens |
| **India-Optimized** | Built for India's realities — paper prescriptions, caregiver gap, government schemes (PMBJP, Ayushman Bharat), multi-language |
| **CareOps, Not Just Monitoring** | Complete workflow automation — scheduling, documentation, navigation, coordination |

### 1.2 Cost Target

Total AWS infrastructure cost: **< ₹5,000/month (~$60 USD)** for a single-home deployment. B2B multi-tenant deployments scale sub-linearly.

---

## 2. Problem Definition

### 2.1 India's Elderly Care Crisis

India's elderly population (60+) is projected to reach **319 million by 2050** (from 149 million in 2022). The country faces a unique convergence of challenges:

- **Caregiver Gap**: India has ~0.5 geriatricians per 100,000 elderly (vs. 7.6 in the US). Home health workers are scarce and undertrained.
- **Nuclear Family Transition**: Joint families are dissolving. 35% of elderly in urban India live alone or with only a spouse. Adult children are in different cities (often Bangalore, Hyderabad, Mumbai) while parents age in Tier-2/3 towns.
- **Paper-Based Healthcare**: 80%+ of prescriptions in India are handwritten. Medical records exist in plastic bags and folders. No continuity of care data.
- **Digital Divide**: Most elderly are not smartphone-literate. Hindi/regional language barriers exclude them from English-only health tech.
- **Financial Vulnerability**: Many elderly are unaware of government schemes (PMBJP for cheap generics, Ayushman Bharat for insurance, pension programs). They overpay for branded medications.
- **Alert Fatigue**: Existing monitoring systems generate too many false alarms. Caregivers disable them or ignore real emergencies.
- **Delayed Intervention**: Health decline is gradual — UTIs, dehydration, cognitive decline, depression — and detectable weeks before crisis, but current systems only react to acute events.

### 2.2 The Cost of Inaction

- Falls are the #1 cause of injury-related death in elderly. A hip fracture has 30% one-year mortality.
- Medication errors cause 125,000+ deaths annually in the US alone. India's numbers are likely comparable per capita.
- Loneliness increases mortality risk by 26% — equivalent to smoking 15 cigarettes per day.
- 40% of hospital readmissions in elderly are preventable with proper monitoring and medication adherence.

---

## 3. The 12 Core Pain Points

AETHER is organized around **12 critical pain points** in elderly care. Every feature, every agent, every sensor maps to solving one or more of these problems.

### Pain Point 1: Falls & Mobility Degradation

**The Problem**: Falls are the leading cause of injury death in the elderly. Current solutions only detect AFTER a fall has occurred. Gait deterioration — the strongest predictor of future falls — goes unmonitored.

**AETHER Solution**: Multi-sensor fusion (accelerometer + pressure mat + camera + acoustic) detects falls in real-time with <2 second latency. More critically, the **Gait Degradation Engine** tracks walking patterns over weeks, detecting subtle changes (shorter stride, increased sway, asymmetry) that predict falls 2-4 weeks before they occur.

**Key Innovation**: Post-fall voice triage — instead of immediately calling 911, AETHER verbally asks the resident if they're okay, assesses consciousness and pain, and makes an intelligent routing decision (self-recovery vs. family call vs. emergency).

---

### Pain Point 2: Medication Chaos & Polypharmacy

**The Problem**: The average elderly Indian on chronic medications takes 6-12 pills daily from multiple specialists who don't coordinate. Drug interactions go undetected. Branded drugs cost 3-10x more than generic equivalents. Handwritten prescriptions are illegible.

**AETHER Solution**: Smart pillbox with LED-guided compartments + voice reminders + NFC medication identification. The **Polypharmacy Checker Agent** cross-references all medications for interactions, contraindications, and food-drug conflicts. The **Generic Alternative Agent** finds PMBJP (Pradhan Mantri Bhartiya Janaushadhi Pariyojana) equivalents that can save 60-80% on drug costs.

**Key Innovation**: Prescription OCR pipeline — photograph a handwritten prescription → Textract extracts text → Comprehend Medical identifies drug names/dosages → Bedrock Agent validates and structures → automatically adds to medication schedule with interaction checking.

---

### Pain Point 3: The "Paper Wall" — Medical Records Gap

**The Problem**: India's elderly have decades of medical history trapped in paper files, plastic bags, and fading memories. Doctors in consultations have no longitudinal data. Hospital → home transitions lose critical information.

**AETHER Solution**: Progressive digitization through prescription OCR, lab report scanning, and clinical summarization. FHIR-compliant health records built incrementally. The **Clinical Summarization Agent** generates weekly SOAP-style notes from sensor data, creating a continuous digital health narrative.

**Key Innovation**: The system builds a medical record over time from ambient data — even without manual entry. Sleep patterns, activity levels, medication adherence, voice biomarkers — all contribute to a comprehensive health profile that grows richer each week.

---

### Pain Point 4: Caregiver Burnout & Staff Shortage

**The Problem**: Professional caregivers manage 15-25 patients with paper-based workflows. Documentation alone takes 30-40% of their time. Burnout rate exceeds 50%. Facilities can't hire enough staff.

**AETHER Solution**: Automated clinical documentation from sensor data. Dynamic scheduling that adjusts based on patient acuity. The **Burnout Detection Engine** monitors caregiver workload, overtime, patient complexity, and response times to flag early burnout signals before they lead to errors or resignation.

**Key Innovation**: Every sensor reading, every interaction, every medication event automatically generates clinical documentation — shift summaries, progress notes, incident reports — freeing caregivers to provide actual care instead of paperwork.

---

### Pain Point 5: Alert Fatigue & False Alarms

**The Problem**: Traditional monitoring systems alert on every threshold breach. A dropped phone triggers a fall alert. Sitting down quickly triggers an activity alert. Caregivers receive 50-100 alerts/day and start ignoring all of them — including the real emergencies.

**AETHER Solution**: The **Intelligent Triage Agent** cross-references multiple data streams before alerting. A possible fall is validated against: accelerometer data + camera confirmation + acoustic analysis + voice response + historical patterns. Alerts are classified into 5 tiers (Log → Watch → Inform → Alert → Emergency) with adaptive thresholds that learn each resident's patterns.

**Key Innovation**: "Silent validation" — the system resolves 70%+ of potential alerts without ever bothering a caregiver, but logs them with full evidence for later review. Only confirmed, contextually-significant events generate notifications.

---

### Pain Point 6: Silent Health Decline ("Shadow Sickness")

**The Problem**: The most dangerous health events in elderly care are the ones that develop gradually. UTIs cause confusion over days. Dehydration builds over a week. Depression manifests as subtle activity reduction. By the time someone notices, the patient is in crisis.

**AETHER Solution**: The **Drift Detection Engine** maintains personalized baselines for every measurable parameter — activity levels, sleep quality, voice characteristics, meal patterns, social engagement, medication timing. When multiple parameters drift simultaneously, the system generates a **Drift Alert** with a composite risk score and evidence summary.

**Key Innovation**: "Composite Drift Score" — individual parameter changes might be insignificant, but when sleep quality drops 15% AND meal frequency decreases AND voice energy reduces AND bathroom visits increase — the system recognizes this as a UTI pattern and alerts proactively, potentially days before clinical symptoms.

---

### Pain Point 7: Social Isolation & Loneliness

**The Problem**: 35% of urban elderly in India live alone. Nuclear families mean children visit once a month or less. Loneliness is a clinical-grade health risk (26% increased mortality) but has no medical treatment.

**AETHER Solution**: AI Voice Companion for daily conversation and engagement. Reminiscence Therapy sessions that guide elderly through memory exercises and life story recording. Weekly health check-in conversations that feel natural, not clinical. **Family Voice Postcards** — short audio messages family can record and send, played to the elderly during quiet moments.

**Key Innovation**: "Passive Social Phenotyping" — the system tracks social engagement metrics (call frequency, conversation duration, voice sentiment, interaction initiation vs. response) and detects social withdrawal patterns that predict depression onset, enabling early intervention.

---

### Pain Point 8: Nutrition & Hydration Neglect

**The Problem**: Elderly lose the sensation of thirst. They forget meals. They eat the same nutritionally-poor food daily. Dehydration — the #1 preventable cause of elderly hospitalization — builds silently. Food-drug interactions (grapefruit + statins, dairy + certain antibiotics) go unmonitored.

**AETHER Solution**: Smart meal detection (from kitchen activity sensors) + hydration tracking (smart bottle/cup sensors) + voice-prompted meal/water reminders with escalation. **Dietary Guidance Agent** that provides culturally-appropriate nutrition advice (dal-rice-sabzi vs. Western diet plans). Food-drug interaction warnings before meals.

**Key Innovation**: "Dehydration Prediction Model" — combining bathroom visit frequency, meal patterns, ambient temperature, activity level, and voice dryness analysis to predict dehydration risk 24-48 hours before clinical symptoms.

---

### Pain Point 9: Delayed Emergency Response

**The Problem**: When an emergency occurs, the response chain is broken at every link. The elderly person can't explain their condition. Family far away can't assess severity. Wrong triage sends an ambulance for a minor fall or misses a stroke. Paramedics arrive with zero patient context.

**AETHER Solution**: **Intelligent Response Router** that classifies events into self-recovery, family-assist, clinic visit, or emergency based on multi-modal evidence. **Auto Ride Booking Agent** that books transportation for non-emergency medical visits. **Emergency Evidence Packet** auto-generated with vital signs, medication list, recent health data, and contact information for first responders.

**Key Innovation**: The ride booking agent is fully autonomous — it detects an upcoming appointment, checks if the resident needs transportation (based on mobility assessment), picks an appropriate transport type (auto-rickshaw, cab, wheelchair-accessible vehicle), books it, confirms with the resident, and tracks arrival — all via agentic AI without human intervention.

---

### Pain Point 10: Home-to-Hospital Data Gap (EMR Disconnect)

**The Problem**: Home monitoring data is trapped in proprietary silos. When a resident visits a doctor, the doctor has no access to weeks of continuous data — sleep patterns, medication adherence, activity trends. Hospital discharge instructions are ignored because there's no system to track compliance.

**AETHER Solution**: FHIR-compliant data export. **Pre-Consultation Report Agent** that generates a doctor-ready summary before each appointment: "In the past 2 weeks, Mrs. Devi's blood pressure averaged 142/88 (trending up from 135/82), medication adherence was 87% (missed evening Amlodipine 3 times), sleep duration decreased to 5.2 hours from 6.5 hour baseline, and she reported increased knee pain during check-ins."

**Key Innovation**: Bidirectional EMR bridge — not just exporting data OUT but importing prescriptions and care plans IN after hospital visits, closing the loop between home and clinical settings.

---

### Pain Point 11: Home Safety & Environmental Hazards

**The Problem**: Gas stoves left on. Bathroom floors wet and slippery. Wandering by dementia patients. Extreme temperatures. Water leaks. These environmental hazards cause as many injuries as medical conditions but are largely unmonitored.

**AETHER Solution**: Environmental sensor network — gas/smoke detectors, water presence sensors, door/window sensors, temperature/humidity monitors. **Contextual Safety Engine** that understands behavioral context: door opening at 3 AM by a dementia patient is an emergency, but at 3 PM it's normal. Kitchen activity without the stove turning off after 30 minutes triggers a verbal reminder, then an alert.

**Key Innovation**: "Dementia-Aware Safety Mode" — when cognitive decline is detected, the system automatically escalates safety thresholds, enables geo-fencing, increases verbal reminders, and activates wandering detection without requiring manual configuration changes.

---

### Pain Point 12: Healthcare Navigation & Access

**The Problem**: Elderly don't know which specialist to see. They can't read prescriptions. They overpay for medications. They don't know about government health schemes they qualify for. Appointment booking is phone-call-only and daunting.

**AETHER Solution**: **Care Navigation Agent** with RAG over a medical knowledge base that answers health questions in Hindi/regional languages with culturally appropriate context. **Scheme Optimizer** that matches resident profiles to eligible government programs (PMBJP, Ayushman Bharat, pension schemes). Appointment booking assistance. Pre-visit preparation (fasting requirements, medication hold instructions).

**Key Innovation**: The Care Navigator doesn't just answer questions — it creates action items. "Based on your symptoms, you should see a urologist. I've found Dr. Patel at City Hospital who speaks Hindi and has an opening next Thursday. Shall I prepare your medical summary and book a ride?"

---

## 4. Target Users

### Persona 1: Kamala Devi, 75 — The Independent Senior

- **Location**: Lucknow, Uttar Pradesh (Tier-2 city)
- **Living**: Alone in family home, son in Bangalore
- **Health**: Type-2 diabetes, hypertension, mild arthritis, early cataracts
- **Tech**: Feature phone, no smartphone literacy, fluent Hindi speaker
- **Medications**: 8 pills/day from 3 doctors — cardiologist, endocrinologist, ophthalmologist
- **Pain Points**: Forgets evening medications, no one to talk to most days, afraid of falling in bathroom, can't read small text on medicine strips, overpays for branded drugs
- **Primary Interaction**: Voice-first — talks to AETHER like a companion
- **Goal**: "I want to stay in my home, not go to a retirement facility. I just need a little help remembering things and someone to talk to."

### Persona 2: Arjun Mehta, 48 — The Remote Family Caregiver

- **Location**: Bangalore, Karnataka
- **Role**: Only son, IT manager, wife and two school-age children
- **Care Situation**: Mother (Kamala) lives alone in Lucknow, 2000 km away
- **Tech**: Smartphone-savvy, uses apps for everything
- **Pain Points**: Constant anxiety about mother's safety, can't verify medication adherence remotely, only visits every 2-3 months, feels guilty about not being there, wastes leave days on false alarms
- **Primary Interaction**: Mobile app — dashboard view, push notifications, video check-in
- **Goal**: "I want to know my mother is safe without calling her 5 times a day. And when something real happens, I want to know immediately with enough context to make decisions."

### Persona 3: Sister Priya Nair, 42 — The Home Health Nurse

- **Location**: Kochi, Kerala
- **Role**: Home health nurse managing 20 elderly patients across the city
- **Work Pattern**: 6 home visits/day, paper-based documentation, manages medications for non-compliant patients
- **Tech**: Android smartphone, WhatsApp-heavy workflow
- **Pain Points**: Spends 40% of time on paperwork, can't monitor patients between visits, families demand constant updates, medication change coordination is nightmare, no clinical decision support
- **Primary Interaction**: Mobile app — patient list, auto-generated visit notes, medication management
- **Goal**: "I want to walk into a patient's home already knowing what happened since my last visit. And I want my notes done before I leave the house."

### Persona 4: Dr. Suresh Iyer, 55 — The Telehealth Geriatrician

- **Location**: Chennai, Tamil Nadu
- **Role**: Consulting geriatrician, runs telehealth practice for elderly
- **Practice**: 15-20 consultations/day, mostly follow-ups
- **Tech**: Laptop, EMR system (basic)
- **Pain Points**: Patients can't describe symptoms accurately, no objective data between visits, medication lists are always wrong, families overreact to minor issues, no time to read through raw sensor data
- **Primary Interaction**: Web dashboard — pre-consultation summaries, FHIR exports, trend visualization
- **Goal**: "Give me a 2-minute summary of what happened since the last visit with the data that matters. Don't make me dig through 500 sensor readings."

### Persona 5: Meena Sharma, 40 — The Clinic Operations Manager (B2B)

- **Location**: Pune, Maharashtra
- **Role**: Manages a geriatric care clinic with 80 home-care patients
- **Responsibilities**: Staff scheduling, quality metrics, compliance reporting, family communication
- **Tech**: Desktop computer, Excel-based operations
- **Pain Points**: Can't see all patients at once, scheduling is manual and reactive, incident reporting is delayed, families complain about communication, audit compliance is manual
- **Primary Interaction**: Web dashboard — fleet view, scheduling, analytics, compliance reports
- **Goal**: "I need a single screen that shows me which patients need attention right now, which staff are overloaded, and whether we're meeting our care standards."

### Persona 6: Rajesh Kumar, 52 — The Assisted Living Facility Manager (B2B)

- **Location**: Coimbatore, Tamil Nadu
- **Role**: Manages a 60-bed assisted living facility
- **Responsibilities**: Resident safety, staff management, regulatory compliance, family satisfaction
- **Tech**: Basic desktop, WhatsApp for family updates
- **Pain Points**: Night shift coverage gaps, can't monitor all residents simultaneously, incident documentation is retrospective, high staff turnover requires constant retraining, families want real-time updates
- **Primary Interaction**: Web dashboard — facility-wide monitoring, alerting, analytics, reporting
- **Goal**: "At 2 AM with 3 staff for 60 residents, I need the system to be my extra set of eyes and ears. And if SEBI or health inspectors visit, I need reports ready."

---

## 5. Deployment Scenarios

### 5.1 B2C: Single Home Deployment

- **Scale**: 1-4 residents per home
- **Hardware**: Raspberry Pi 5 hub + sensor kit (simulated for demo)
- **Users**: Resident (voice interaction) + Family members (mobile app)
- **Connectivity**: WiFi primary, 4G failover, fully offline-capable for safety features
- **Cost**: ₹5,000/month AWS + ₹15,000 one-time hardware

### 5.2 B2B: Clinic Operations (Home Care Network)

- **Scale**: 10-100 homes managed by a clinic/nursing service
- **Hardware**: Hub per home, centralized dashboard
- **Users**: Nurses (mobile app) + Doctors (web dashboard) + Operations manager (web dashboard) + Families (mobile app)
- **Multi-Tenancy**: Shared infrastructure, isolated data per patient, role-based access
- **Cost**: ₹25,000-50,000/month AWS (shared), per-home hardware costs

### 5.3 B2B: Assisted Living Facility

- **Scale**: 50-200 residents in a single facility
- **Hardware**: Central hub per floor, shared sensors, individual wearables
- **Users**: Staff (mobile app + dashboard) + Management (web dashboard) + Families (mobile app)
- **Cost**: ₹40,000-80,000/month AWS, facility-wide hardware investment

---

## 6. Glossary

| Term | Definition |
|---|---|
| **AETHER** | Autonomous Elderly Technology for Health, Engagement & Response — the platform name |
| **Agentic AI** | AI systems that autonomously take multi-step actions (not just generate text) to accomplish goals |
| **Bedrock Agent** | An AWS Bedrock Agent configured with tools and knowledge bases to perform autonomous tasks |
| **CareOps** | Care Operations — the operational workflow layer of elderly care (scheduling, documentation, coordination, triage) |
| **Composite Drift Score** | A weighted aggregate of multiple health parameter deviations from personalized baselines |
| **Edge Hub** | Raspberry Pi 5 (or Jetson Orin Nano) device that runs local AI inference and sensor aggregation |
| **Evidence Packet** | A structured data bundle generated during events containing all relevant sensor data, history, and context for decision-making |
| **FHIR** | Fast Healthcare Interoperability Resources — the standard for healthcare data exchange |
| **Knowledge Pack** | A versioned bundle of model weights, thresholds, and configuration deployed to edge devices |
| **MQTT** | Message Queuing Telemetry Transport — lightweight IoT messaging protocol used between sensors and edge hub |
| **PMBJP** | Pradhan Mantri Bhartiya Janaushadhi Pariyojana — Indian government generic medicine program |
| **RAG** | Retrieval-Augmented Generation — technique for grounding LLM responses in specific knowledge bases |
| **Shadow Sickness** | Silent, gradual health decline that is detectable through continuous monitoring but invisible to periodic check-ups |
| **SOAP Note** | Subjective-Objective-Assessment-Plan — standard clinical documentation format |
| **Triage Tier** | Classification level (Log/Watch/Inform/Alert/Emergency) assigned to detected events based on severity and context |
| **Voice Biomarker** | Acoustic features of speech (pitch, rate, energy, clarity) that correlate with health conditions |
| **Wake Word** | A spoken trigger phrase ("Hey Aether") that activates the voice interaction system |

---

## 7. Requirements

Requirements are organized by the **12 Core Pain Points**. Each requirement includes a User Story and measurable Acceptance Criteria.

**Priority Tags**:
- 🔴 **DEMO** — Must be implemented and working in the 2-month sprint
- 🟡 **STRETCH** — Implement if time permits, simplified version acceptable
- 🟢 **VISION** — Full roadmap feature, not required for 2-month demo

---

### 7.1 Pain Point 1: Falls & Mobility Degradation

#### REQ-1: Real-Time Fall Detection 🔴 DEMO

**User Story**: As Kamala Devi, when I fall in my home, I want the system to detect it within seconds and initiate an appropriate response so that I get help quickly.

**Acceptance Criteria**:
1. SHALL detect falls using accelerometer + pressure mat sensor fusion within 2 seconds of impact
2. SHALL classify fall severity into 3 levels: minor (stumble/controlled sit), moderate (fall with recovery attempt), severe (fall with no movement)
3. SHALL initiate voice triage within 5 seconds of fall detection: "Kamala ji, are you okay? I noticed you may have fallen."
4. SHALL escalate to family notification if no voice response within 30 seconds
5. SHALL escalate to emergency services if no response within 60 seconds or if voice analysis indicates distress
6. SHALL log all fall events with full sensor evidence packet including timestamp, location, severity, response timeline, and outcome
7. SHALL operate fully offline — fall detection and voice triage must work without internet connectivity

#### REQ-2: Post-Fall Immobility Detection 🔴 DEMO

**User Story**: As Arjun, I want the system to detect if my mother is lying on the floor unable to get up, even if she didn't trigger a "fall" event, so that prolonged immobility doesn't go unnoticed.

**Acceptance Criteria**:
1. SHALL detect prolonged floor-level presence (>3 minutes in unexpected location) using pressure mat and accelerometer data
2. SHALL distinguish between intentional floor-sitting (yoga, prayer) and unintentional immobility using time-of-day context and activity patterns
3. SHALL initiate voice check-in after 3 minutes of unexpected floor-level position
4. SHALL escalate through standard triage tier if no satisfactory response
5. SHALL include immobility duration in the evidence packet

#### REQ-3: Gait Degradation Prediction 🟡 STRETCH

**User Story**: As Dr. Suresh, I want to see trends in my patient's walking patterns over time so that I can predict fall risk before a fall occurs.

**Acceptance Criteria**:
1. SHALL track gait metrics (stride length, gait speed, cadence, symmetry) from daily activity via accelerometer data
2. SHALL establish personalized gait baseline within the first 14 days of deployment
3. SHALL detect statistically significant deviation from baseline (>15% change in any metric over 7-day rolling window)
4. SHALL generate a Gait Degradation Alert with trend visualization when deviation is detected
5. SHALL correlate gait changes with other drift parameters (sleep, medication adherence) for composite risk assessment
6. SHALL present gait trend data in the pre-consultation report for Dr. Suresh

#### REQ-4: Fall Location Mapping 🟡 STRETCH

**User Story**: As Sister Priya, I want to know where falls most frequently occur in a patient's home so I can recommend safety modifications.

**Acceptance Criteria**:
1. SHALL map fall and near-fall events to room locations using sensor zone identification
2. SHALL generate a fall heatmap showing high-risk areas (bathroom, kitchen, stairs)
3. SHALL recommend specific safety interventions based on location patterns (grab bars, non-slip mats, lighting)
4. SHALL make location data available on the caregiver web dashboard

---

### 7.2 Pain Point 2: Medication Chaos & Polypharmacy

#### REQ-5: Smart Medication Reminders 🔴 DEMO

**User Story**: As Kamala Devi, I want the system to remind me to take my medicines at the right times in Hindi, so I don't miss doses.

**Acceptance Criteria**:
1. SHALL store complete medication schedule per resident including drug name, dosage, timing, and special instructions (before/after meals, with water)
2. SHALL deliver voice reminders in the resident's preferred language at scheduled times: "Kamala ji, it's time for your evening Amlodipine — the white round tablet, second compartment. Take it after dinner with water."
3. SHALL confirm medication intake through voice acknowledgment or pill compartment sensor
4. SHALL escalate missed medication: reminder at T+0, second reminder at T+15min, caregiver notification at T+30min
5. SHALL track medication adherence percentage per drug and overall
6. SHALL never give medical advice about changing medication — only remind, track, and report

#### REQ-6: Drug Interaction Checking (Polypharmacy Agent) 🔴 DEMO

**User Story**: As Dr. Suresh, I want the system to automatically check for drug-drug and food-drug interactions whenever a medication list changes, so I can prevent adverse reactions.

**Acceptance Criteria**:
1. SHALL maintain a drug interaction knowledge base using AWS Bedrock Knowledge Base with curated pharmaceutical data
2. SHALL automatically check all pairwise interactions when any medication is added or modified
3. SHALL classify interactions by severity: Contraindicated, Major, Moderate, Minor
4. SHALL generate an interaction report with specific risks: "Warfarin + Aspirin: Major interaction — increased bleeding risk"
5. SHALL flag critical food-drug interactions: "Amlodipine: avoid grapefruit or grapefruit juice"
6. SHALL notify the prescribing doctor's dashboard for Major/Contraindicated interactions
7. SHALL present interaction information in both technical (for doctors) and plain language (for families)

#### REQ-7: Prescription OCR & Digitization Agent 🔴 DEMO

**User Story**: As Arjun, I want to photograph my mother's handwritten prescriptions and have the system automatically extract and structure the medication information, so we have an accurate digital medication list.

**Acceptance Criteria**:
1. SHALL accept prescription images via mobile app camera or upload
2. SHALL use AWS Textract to extract text from handwritten and printed prescriptions
3. SHALL use Amazon Comprehend Medical to identify drug names, dosages, frequencies, and route of administration
4. SHALL use a Bedrock Agent to validate extracted information against known drug databases and resolve ambiguities
5. SHALL present extracted information to the user for confirmation before adding to the medication schedule
6. SHALL achieve >85% accuracy on printed prescriptions and >70% on handwritten prescriptions (with human-in-the-loop for low-confidence extractions)
7. SHALL store original prescription image linked to the digital medication entry for audit trail

#### REQ-8: Generic Alternative Suggestions (PMBJP) 🟡 STRETCH

**User Story**: As Kamala Devi's family, when a branded drug is prescribed, I want the system to suggest cheaper generic alternatives available through government programs, so we can reduce medication costs.

**Acceptance Criteria**:
1. SHALL maintain a PMBJP drug catalog in the Bedrock Knowledge Base
2. SHALL automatically match branded medications to generic equivalents when available
3. SHALL show cost comparison: "Atorvastatin 20mg — Branded: ₹350/month → PMBJP Generic: ₹45/month (87% savings)"
4. SHALL only suggest alternatives for the same molecule, dosage, and formulation
5. SHALL clearly state that generic alternatives must be approved by the prescribing doctor before switching
6. SHALL identify nearest Janaushadhi Kendra (generic pharmacy) locations

---

### 7.3 Pain Point 3: The "Paper Wall" — Medical Records Gap

#### REQ-9: Lab Report Digitization 🟡 STRETCH

**User Story**: As Sister Priya, I want to scan a patient's printed lab reports and have the results automatically extracted and tracked, so I can see trends over time.

**Acceptance Criteria**:
1. SHALL accept lab report images/PDFs via mobile app or web dashboard upload
2. SHALL extract key values (blood glucose, HbA1c, creatinine, CBC, lipid panel, etc.) using Textract + Comprehend Medical
3. SHALL track lab values over time with trend visualization
4. SHALL flag values outside normal ranges with severity indication
5. SHALL include lab trends in the pre-consultation summary

#### REQ-10: Continuous Health Record Building 🔴 DEMO

**User Story**: As Dr. Suresh, I want the system to automatically build a longitudinal health record from daily sensor data and interactions, even without manual entry, so I have objective data for consultations.

**Acceptance Criteria**:
1. SHALL automatically generate daily health summaries from sensor data: activity level, sleep quality, medication adherence, voice biomarker trends, meal patterns
2. SHALL aggregate daily summaries into weekly and monthly health narratives
3. SHALL structure all health data in FHIR-compatible format (Patient, Observation, MedicationStatement, Condition resources)
4. SHALL enable export of health records as FHIR bundles or human-readable PDF reports
5. SHALL maintain data provenance — every data point traceable to its sensor/interaction source

#### REQ-11: Clinical Summarization Agent 🔴 DEMO

**User Story**: As Dr. Suresh, before a telehealth consultation, I want a concise clinical summary of the patient's status since the last visit, so I can use my 15-minute slot effectively.

**Acceptance Criteria**:
1. SHALL generate a SOAP-format pre-consultation summary using Bedrock Agent with RAG over the patient's health record
2. SHALL include: vital sign trends, medication adherence stats, notable events/alerts, drift detection findings, patient-reported symptoms from check-ins
3. SHALL highlight clinically significant changes from the previous visit
4. SHALL generate the summary automatically 24 hours before a scheduled appointment
5. SHALL allow the doctor to request an on-demand summary via dashboard
6. SHALL be concise (1-2 pages) with links to detailed data for drill-down

---

### 7.4 Pain Point 4: Caregiver Burnout & Staff Shortage

#### REQ-12: Automated Documentation 🔴 DEMO

**User Story**: As Sister Priya, I want the system to automatically generate visit notes, shift summaries, and incident reports from sensor data and my voice input, so I spend less time on paperwork.

**Acceptance Criteria**:
1. SHALL auto-generate daily care summaries per patient from sensor data and events
2. SHALL allow nurses to add voice notes during visits that are transcribed and integrated into documentation
3. SHALL generate shift handoff reports summarizing key events, pending tasks, and upcoming medication schedules
4. SHALL auto-generate incident reports when Alert or Emergency tier events occur
5. SHALL structure all documentation for regulatory compliance
6. SHALL reduce documentation time by >50% compared to manual processes

#### REQ-13: Caregiver Workload Analytics 🟡 STRETCH

**User Story**: As Meena (clinic ops manager), I want to see caregiver workload distribution and burnout risk indicators, so I can adjust scheduling before burnout occurs.

**Acceptance Criteria**:
1. SHALL track caregiver metrics: patients per caregiver, visit frequency, response times, overtime hours, high-acuity patient ratio
2. SHALL calculate a burnout risk score per caregiver based on workload patterns
3. SHALL generate scheduling recommendations to balance workload
4. SHALL alert management when a caregiver's burnout risk exceeds threshold
5. SHALL show workload analytics on the ops manager web dashboard

#### REQ-14: Dynamic Scheduling 🟢 VISION

**User Story**: As Meena, I want the system to suggest optimal visit schedules based on patient acuity and caregiver availability, so that high-risk patients get more frequent visits.

**Acceptance Criteria**:
1. SHALL input caregiver availability, patient locations, and patient acuity scores
2. SHALL generate optimized daily visit schedules minimizing travel time while prioritizing high-acuity patients
3. SHALL automatically adjust schedules when emergencies or cancellations occur
4. SHALL consider travel distance, traffic patterns, and visit duration
5. SHALL allow manual overrides with audit trail

---

### 7.5 Pain Point 5: Alert Fatigue & False Alarms

#### REQ-15: Intelligent Alert Triage Agent 🔴 DEMO

**User Story**: As Arjun, I only want to be notified about events that actually matter, not every time my mother sits down heavily or drops a book, so I can trust that every notification deserves attention.

**Acceptance Criteria**:
1. SHALL classify all detected events into 5 tiers: Log (record only), Watch (monitor for progression), Inform (non-urgent notification), Alert (immediate notification), Emergency (auto-escalation)
2. SHALL use multi-modal validation: cross-reference at least 2 sensor modalities before generating Alert or Emergency tier events
3. SHALL maintain per-resident adaptive thresholds that learn from confirmed vs. false-positive events
4. SHALL suppress duplicate alerts for the same ongoing event (no repeated notifications for the same fall)
5. SHALL include a confidence score and evidence summary with every alert
6. SHALL achieve <10% false positive rate for Alert tier events after 14-day learning period
7. SHALL provide a "Why this alert?" explanation accessible from the notification

#### REQ-16: Alert History & Analytics 🔴 DEMO

**User Story**: As Dr. Suresh, I want to review a patient's alert history with outcome tracking, so I can understand patterns and adjust care plans.

**Acceptance Criteria**:
1. SHALL log all detected events including suppressed/auto-resolved events
2. SHALL allow caregivers to mark alert outcomes: true positive, false positive, expected behavior
3. SHALL show alert frequency trends by type, time of day, and tier
4. SHALL use outcome labels to retrain adaptive thresholds (feedback loop)
5. SHALL include alert analytics in the pre-consultation report

---

### 7.6 Pain Point 6: Silent Health Decline ("Shadow Sickness")

#### REQ-17: Personalized Baseline Engine 🔴 DEMO

**User Story**: As a system, I need to establish unique health baselines for each resident, so that I can detect "unusual for this person" rather than "outside generic normal range."

**Acceptance Criteria**:
1. SHALL collect and analyze 14 days of data to establish initial baselines per resident
2. SHALL track baselines for: daily activity level (steps, movement hours), sleep metrics (duration, wake events, sleep/wake times), medication adherence pattern, voice characteristics (pitch, rate, energy, clarity), meal frequency and timing, bathroom visit frequency and pattern, social interaction frequency
3. SHALL update baselines using rolling 30-day windows with seasonal adjustment
4. SHALL handle expected variations (weekends vs. weekdays, seasonal changes, post-illness recovery periods)
5. SHALL flag when insufficient data prevents reliable baseline establishment

#### REQ-18: Drift Detection & Composite Risk 🔴 DEMO

**User Story**: As Sister Priya, I want the system to detect when a patient is gradually declining across multiple parameters, even if no single reading is alarming, so I can intervene early.

**Acceptance Criteria**:
1. SHALL compute deviation-from-baseline scores for each monitored parameter (normalized Z-scores)
2. SHALL calculate a Composite Drift Score that weights multiple parameter deviations
3. SHALL trigger Drift Alerts when Composite Drift Score exceeds configurable threshold
4. SHALL include in the Drift Alert: which parameters are drifting, magnitude and direction, historical trend visualization, possible cause patterns (e.g., "This pattern matches early UTI indicators")
5. SHALL generate weekly Drift Reports per patient for proactive review
6. SHALL allow clinicians to acknowledge Drift Alerts and mark them for follow-up or dismiss with reason

#### REQ-19: Predictive Health Analytics 🟡 STRETCH

**User Story**: As Dr. Suresh, I want the system to predict which patients are likely to need hospitalization in the next 2 weeks, so I can intervene proactively.

**Acceptance Criteria**:
1. SHALL use a trained model (SageMaker) to compute 14-day hospitalization risk scores
2. SHALL identify the top contributing factors for each patient's risk score
3. SHALL present high-risk patients in a prioritized list on the clinician dashboard
4. SHALL track prediction accuracy over time for model improvement

---

### 7.7 Pain Point 7: Social Isolation & Loneliness

#### REQ-20: AI Voice Companion 🔴 DEMO

**User Story**: As Kamala Devi, I want someone to talk to during the day — not clinical questions but real conversation — so I feel less lonely.

**Acceptance Criteria**:
1. SHALL initiate conversational interactions at configurable times (morning greeting, afternoon check-in, evening wind-down)
2. SHALL engage in natural, warm conversation in Hindi (or resident's preferred language) using Bedrock LLM with a companion persona
3. SHALL remember previous conversations and reference them: "You told me yesterday that your friend Savita visited. How was the visit?"
4. SHALL use Bedrock Guardrails to prevent inappropriate, medical-advice, or harmful responses
5. SHALL detect emotional distress in conversation (sadness, anxiety, confusion) and log it as a mental health observation
6. SHALL seamlessly transition between companion mode and functional mode: "While we're chatting, I should remind you — it's time for your afternoon medicine."

#### REQ-21: Daily Health Check-In 🔴 DEMO

**User Story**: As the system, I need to conduct a natural-feeling daily check-in conversation that captures subjective health data (pain, mood, sleep quality, appetite) in a way that feels like chatting, not like filling a form.

**Acceptance Criteria**:
1. SHALL conduct voice-based check-in covering: sleep quality, pain levels, mood/emotional state, appetite, hydration, any specific complaints
2. SHALL use conversational flow — not a questionnaire: "How did you sleep last night, Kamala ji?" → follow-up based on response
3. SHALL extract structured health data from natural conversation using Bedrock NLU
4. SHALL generate a standardized check-in summary (numeric scores + free text) stored in the health record
5. SHALL adapt questions based on health history: ask about joint pain if arthritis is documented, ask about dizziness if blood pressure medication was recently changed
6. SHALL complete check-in in <5 minutes to avoid fatigue
7. SHALL allow elderly to skip or defer check-in without repeated nagging

#### REQ-22: Reminiscence Therapy & Life Memoir 🟡 STRETCH

**User Story**: As Kamala Devi, I want the system to help me remember and share stories from my life, so I stay mentally engaged and my grandchildren can hear my stories someday.

**Acceptance Criteria**:
1. SHALL conduct weekly guided reminiscence sessions using therapeutic protocol: "Tell me about your wedding day" → follow-up questions that deepen the story
2. SHALL record and transcribe life stories with consent
3. SHALL compile stories into a "Life Memoir" accessible to family members
4. SHALL track cognitive engagement metrics during sessions (narrative coherence, detail richness, temporal orientation) for passive cognitive assessment
5. SHALL use culturally appropriate prompts (festivals, family traditions, regional landmarks)

#### REQ-23: Family Voice Postcards 🟡 STRETCH

**User Story**: As Arjun, I want to record short voice messages for my mother that the system plays during quiet moments, so she hears from family even when we can't call.

**Acceptance Criteria**:
1. SHALL allow family members to record voice messages (30-120 seconds) via mobile app
2. SHALL play voice postcards at appropriate times (morning, after meals) or on-demand: "You have a message from Arjun beta"
3. SHALL allow the elderly to replay messages and respond with a voice reply
4. SHALL track which messages have been played and the resident's emotional response (voice sentiment analysis)

#### REQ-24: Social Engagement Tracking 🟡 STRETCH

**User Story**: As Sister Priya, I want to see metrics on each patient's social engagement and detect social withdrawal patterns, so I can arrange visitor programs or activities.

**Acceptance Criteria**:
1. SHALL track: phone call frequency and duration, visitors (door sensor + voice detection), conversational interactions with AETHER, family app engagement
2. SHALL compute a daily Social Engagement Score
3. SHALL detect social withdrawal patterns (declining engagement over 7+ days) and generate alerts
4. SHALL correlate social engagement with other health metrics in the drift detection engine
5. SHALL present social engagement trends on caregiver dashboard

---

### 7.8 Pain Point 8: Nutrition & Hydration Neglect

#### REQ-25: Meal Detection & Tracking 🔴 DEMO

**User Story**: As Sister Priya, I want to know whether my patient ate breakfast, lunch, and dinner today and approximately when, so I can track nutritional patterns.

**Acceptance Criteria**:
1. SHALL detect meal events using kitchen activity sensors (stove, microwave, fridge door) and time-of-day context
2. SHALL distinguish between meal preparation (stove on for cooking) and non-meal kitchen activity (getting water)
3. SHALL track meal times and regularity per day
4. SHALL generate alerts for missed meals: no detected meal activity for >6 hours during waking hours
5. SHALL present meal pattern data on caregiver dashboard with weekly summary

#### REQ-26: Hydration Monitoring & Nudging 🟡 STRETCH

**User Story**: As Kamala Devi, I sometimes forget to drink water all day. I want the system to gently remind me throughout the day so I stay hydrated.

**Acceptance Criteria**:
1. SHALL track water intake via smart bottle/cup sensors or verbal confirmation after reminders
2. SHALL deliver voice-based hydration reminders at configurable intervals (default: every 2 hours during waking hours)
3. SHALL adjust reminder frequency based on: ambient temperature, activity level, medication requirements (diuretics need more water)
4. SHALL track daily hydration intake and present cumulative progress: "You've had 4 glasses today. Try to have 2 more before dinner."
5. SHALL include hydration data in the Dehydration Prediction Model

#### REQ-27: Dietary Guidance Agent 🟡 STRETCH

**User Story**: As Kamala Devi, I want culturally-appropriate dietary suggestions that work with my Indian vegetarian diet and consider my diabetes, so I can eat better without feeling like I'm on a "Western diet plan."

**Acceptance Criteria**:
1. SHALL provide dietary recommendations that are culturally appropriate for Indian regional cuisines
2. SHALL consider medical conditions: diabetic-friendly, heart-healthy, kidney-friendly options
3. SHALL flag food-drug interactions before meals: "Kamala ji, you're having dal-chawal today. A reminder — avoid having the Metformin with very heavy meals. Take it 30 minutes before."
4. SHALL suggest meal ideas based on nutritional gaps detected from eating patterns
5. SHALL use Bedrock Agent with a nutrition knowledge base for personalized recommendations

---

### 7.9 Pain Point 9: Delayed Emergency Response

#### REQ-28: Emergency Evidence Packet 🔴 DEMO

**User Story**: As a first responder arriving at Kamala Devi's home, I want a comprehensive information packet instantly available so I can provide informed care without delay.

**Acceptance Criteria**:
1. SHALL auto-generate an Emergency Evidence Packet when an Emergency tier event is triggered
2. SHALL include: patient demographics, emergency contacts, current medications (with last dose times), known allergies, relevant medical conditions, vital sign trends (last 24 hours), event timeline (what triggered the emergency, sensor data, response timeline), current consciousness/response status
3. SHALL be shareable via URL link (SMS/WhatsApp) and printable QR code displayed on the edge hub screen
4. SHALL be generated within 10 seconds of emergency tier classification
5. SHALL be accessible without authentication (emergency access with limited PHI)

#### REQ-29: Intelligent Response Router 🔴 DEMO

**User Story**: As the system, when an event occurs, I need to route the response appropriately based on severity, context, and available resources — from self-resolution logging up to emergency dispatch.

**Acceptance Criteria**:
1. SHALL implement a 5-tier routing escalation: (1) Log-only → (2) Watch-and-wait → (3) Family notification → (4) Caregiver alert → (5) Emergency services
2. SHALL use the Triage Agent to classify events considering: sensor data, resident history, time of day, recent events, voice response quality
3. SHALL allow each tier to escalate to the next if no satisfactory response within configurable timeouts
4. SHALL support de-escalation: an Alert can be downgraded to Inform if the resident verbally confirms they are okay
5. SHALL log the complete routing decision chain for audit and improvement
6. SHALL enable emergency override by the resident via SOS button or voice command: "Aether, emergency!"

#### REQ-30: Auto Ride Booking Agent 🔴 DEMO

**User Story**: As Kamala Devi, when I have a doctor's appointment, I want the system to book a ride for me without me having to figure out apps, so I actually get to my appointments.

**Acceptance Criteria**:
1. SHALL detect upcoming appointments from the care calendar and medication instructions
2. SHALL assess resident's transportation needs: can they take an auto-rickshaw or need a wheelchair-accessible vehicle?
3. SHALL book appropriate transportation via simulated ride-booking API (modeled after Ola/Uber Health)
4. SHALL confirm ride details with the resident via voice: "Kamala ji, your appointment with Dr. Patel is tomorrow at 11 AM. I've booked a cab for 10:15 AM. Is that okay?"
5. SHALL send ride details to family members via push notification
6. SHALL track ride status and alert if the ride is late or doesn't arrive
7. SHALL handle cancellations and rebooking autonomously

---

### 7.10 Pain Point 10: Home-to-Hospital Data Gap

#### REQ-31: FHIR Data Export 🔴 DEMO

**User Story**: As Dr. Suresh, I want to receive my patient's home monitoring data in FHIR format so I can import it into my EMR system and see all data in one place.

**Acceptance Criteria**:
1. SHALL generate FHIR R4 compliant resources: Patient, Observation (vitals, activity), MedicationStatement, MedicationAdministration, Condition, AllergyIntolerance, DiagnosticReport
2. SHALL support FHIR Bundle export via API and downloadable file
3. SHALL update FHIR resources in near real-time as new data flows in
4. SHALL provide a human-readable HTML/PDF rendering alongside the FHIR JSON
5. SHALL comply with FHIR India profile extensions where applicable

#### REQ-32: Pre-Consultation Report Agent 🔴 DEMO

**User Story**: As Dr. Suresh, before each appointment, I want a concise report showing what has changed since the last visit with actionable insights, so I can make the most of a short consultation.

**Acceptance Criteria**:
1. SHALL auto-generate report 24 hours before any scheduled appointment
2. SHALL include: medication adherence summary (% and specific misses), vital sign trends with baselines, notable events/alerts since last visit, drift detection findings, patient-reported symptoms from daily check-ins, any new prescriptions or medication changes
3. SHALL present data as trends and summaries — not raw data dumps
4. SHALL highlight top 3 items requiring doctor attention
5. SHALL be accessible on the web dashboard in the doctor view
6. SHALL be shareable as a PDF or FHIR DocumentReference

#### REQ-33: Post-Discharge Compliance Tracking 🟡 STRETCH

**User Story**: As Sister Priya, when my patient comes home from the hospital with new medications and instructions, I want the system to automatically track compliance with the discharge plan.

**Acceptance Criteria**:
1. SHALL accept hospital discharge summaries (manual entry or document scan)
2. SHALL extract care instructions: new medications, activity restrictions, follow-up appointments, wound care schedule
3. SHALL create automated tracking for each instruction with reminders and compliance monitoring
4. SHALL generate a discharge compliance report showing which instructions are being followed
5. SHALL alert the nurse when critical instructions are not being followed

---

### 7.11 Pain Point 11: Home Safety & Environmental Hazards

#### REQ-34: Kitchen Safety Monitoring 🔴 DEMO

**User Story**: As Arjun, I want to know if my mother left the stove on unattended, so I can remind her or alert a neighbor before there's a fire.

**Acceptance Criteria**:
1. SHALL monitor stove/gas activity via temperature and gas sensors
2. SHALL detect "stove on but no kitchen activity" condition after configurable timeout (default: 15 minutes)
3. SHALL deliver voice reminder first: "Kamala ji, the stove has been on for 15 minutes. Are you still cooking?"
4. SHALL escalate to family notification if no response within 5 minutes
5. SHALL log kitchen safety events with duration and outcome

#### REQ-35: Bathroom Safety Monitoring 🟡 STRETCH

**User Story**: As Sister Priya, I want to detect when a patient has been in the bathroom too long or may have slipped, so I can check on them.

**Acceptance Criteria**:
1. SHALL detect bathroom occupancy via door sensor and motion/humidity changes
2. SHALL trigger voice check-in for prolonged bathroom visits (>20 minutes, configurable per resident)
3. SHALL detect potential slip events via acoustic analysis (impact sounds) and accelerometer data
4. SHALL escalate through standard triage tiers if no satisfactory response
5. SHALL maintain bathroom visit frequency data for health analysis (polyuria tracking)

#### REQ-36: Wandering Detection (Dementia Safety) 🟡 STRETCH

**User Story**: As Rajesh (facility manager), I want to detect when a dementia patient leaves their designated area or opens exterior doors at unusual times, so I can intervene before they get lost.

**Acceptance Criteria**:
1. SHALL define safe zones per resident (room, floor, building) based on cognitive status
2. SHALL detect zone boundary breaches using door sensors and optional BLE beacons
3. SHALL distinguish between normal exits (scheduled walks, accompanied) and concerning exits (alone, unusual time, unfamiliar pattern)
4. SHALL generate immediate Alert tier notification for after-hours exits by dementia patients
5. SHALL track wandering frequency and time-of-day patterns for behavioral assessment

#### REQ-37: Environmental Monitoring 🔴 DEMO

**User Story**: As the system, I need to monitor environmental conditions in the home to ensure they are safe and comfortable for the resident.

**Acceptance Criteria**:
1. SHALL monitor ambient temperature, humidity, air quality (if sensor available)
2. SHALL alert for extreme temperature conditions: >35°C or <15°C in living areas
3. SHALL detect smoke/gas anomalies via sensor integration
4. SHALL correlate environmental data with health events (e.g., high heat + low hydration → heat stroke risk)
5. SHALL present environmental dashboard on caregiver web view

---

### 7.12 Pain Point 12: Healthcare Navigation & Access

#### REQ-38: Care Navigation Agent (RAG) 🔴 DEMO

**User Story**: As Kamala Devi, when I have a health question, I want to ask AETHER in Hindi and get a clear, trustworthy, culturally-appropriate answer with guidance on what to do next.

**Acceptance Criteria**:
1. SHALL accept health questions via voice in Hindi, English, Tamil, and Kannada
2. SHALL use Bedrock Agent with RAG over a curated medical knowledge base to generate responses
3. SHALL provide culturally-appropriate explanations without medical jargon: not "myocardial infarction" but "heart attack — dil ka daura"
4. SHALL always include appropriate caveats: "This is general information. For your specific situation, please consult Dr. Iyer."
5. SHALL recognizing symptom descriptions and recommend urgency level: "This sounds like it could be serious. Would you like me to contact your doctor?"
6. SHALL create follow-up tasks from navigation queries: "I've added 'discuss knee pain with Dr. Iyer' to your next appointment preparation."
7. SHALL use Bedrock Guardrails to prevent hallucinated or dangerous medical advice

#### REQ-39: Government Scheme Discovery 🟡 STRETCH

**User Story**: As Arjun, I want to know which government healthcare and welfare schemes my mother qualifies for, so she can access benefits she's entitled to.

**Acceptance Criteria**:
1. SHALL maintain a knowledge base of relevant government schemes: PMBJP (generic medicines), Ayushman Bharat (health insurance), National Pension Scheme, Rashtriya Vayoshri Yojana (assistive devices), state-specific schemes
2. SHALL match resident profile (age, income, health conditions) to eligible schemes
3. SHALL provide application guidance: required documents, application process, nearest office
4. SHALL estimate potential savings: "PMBJP could save ₹2,400/month on your current medications"
5. SHALL track scheme application status if user opts in

#### REQ-40: Appointment Management 🔴 DEMO

**User Story**: As Sister Priya, I want a unified view of all my patients' upcoming appointments and the ability to manage appointment logistics, so I can ensure patients actually show up for their consultations.

**Acceptance Criteria**:
1. SHALL maintain a care calendar per resident with all scheduled appointments (doctor visits, lab tests, follow-ups)
2. SHALL send voice reminders to residents 24 hours and 2 hours before appointments
3. SHALL generate pre-visit preparation instructions: "Kamala ji, your blood test is tomorrow morning. Remember to not eat anything after 10 PM tonight."
4. SHALL show consolidated appointment calendar on caregiver dashboard
5. SHALL trigger the Auto Ride Booking Agent when transportation is needed
6. SHALL track appointment attendance and flag no-shows for follow-up

---

### 7.13 Cross-Cutting: Voice Interaction Platform

#### REQ-41: Wake Word Detection 🔴 DEMO

**User Story**: As Kamala Devi, I want to activate the system by saying "Hey Aether" (or a Hindi equivalent) without pressing any buttons.

**Acceptance Criteria**:
1. SHALL detect wake word "Hey Aether" (or "Aether" or "aye-ther") within 2 seconds on-device (edge processing, no cloud dependency)
2. SHALL work in noisy environments (TV on, fan running) with >90% detection rate
3. SHALL distinguish the resident's voice from TV/radio using voice activity detection
4. SHALL provide audible acknowledgment (chime or voice: "Haan, Kamala ji?")
5. SHALL support configurable wake words in Hindi: "Suniye" or custom name

#### REQ-42: Voice Command Processing 🔴 DEMO

**User Story**: As Kamala Devi, I want to give voice commands for common tasks without needing complex phrases.

**Acceptance Criteria**:
1. SHALL process voice commands using AWS Transcribe (streaming) with Hindi and English language support
2. SHALL support command categories: medication queries ("Kya medicine leni hai?"), emergency ("Mujhe madad chahiye!"), companion ("Kuch baat karo"), appointments ("Mera doctor appointment kab hai?"), family ("Arjun ka message sunao")
3. SHALL use Bedrock to understand intent from natural language (not fixed command syntax)
4. SHALL respond in the same language the command was given in
5. SHALL handle multi-turn conversations: follow-up questions, clarifications
6. SHALL function in degraded mode offline: basic commands (emergency, medication time) work without cloud

#### REQ-43: Text-to-Speech Output 🔴 DEMO

**User Story**: As Kamala Devi, I want the system to speak to me in natural, warm Hindi — not robotic text-to-speech.

**Acceptance Criteria**:
1. SHALL use AWS Polly neural voices for Hindi and English text-to-speech
2. SHALL support SSML for natural speech patterns: appropriate pausing, emphasis, and speed for elderly listeners
3. SHALL speak at a pace configurable per resident (default: 80% normal speed for elderly comprehension)
4. SHALL use respectful address forms appropriate to the language: "Kamala ji" in Hindi, "Aunty" in English-Indian context
5. SHALL support adjustable volume that matches ambient noise level

#### REQ-44: Acoustic Event Detection 🔴 DEMO

**User Story**: As the system, I need to detect critical acoustic events (screams, glass breaking, prolonged coughing, silence) in the home for safety monitoring.

**Acceptance Criteria**:
1. SHALL detect acoustic events on-device (edge processing) without transmitting raw audio to cloud
2. SHALL classify: scream/distress call, glass breaking, sustained coughing (>30 seconds), impact sounds (fall-related), prolonged silence (>2 hours during waking, indicating possible unconsciousness)
3. SHALL extract only event labels and confidence scores — NOT raw audio — for privacy
4. SHALL cross-reference acoustic events with other sensor data via the Triage Agent for contextual assessment
5. SHALL achieve >85% accuracy on scream/distress detection and >75% on glass breaking
6. SHALL have <5% false positive rate for each event category

#### REQ-45: Voice Biomarker Analysis 🟡 STRETCH

**User Story**: As Dr. Suresh, I want the system to track changes in my patient's voice over time that might indicate health decline, so I can detect conditions like cognitive impairment, depression, dehydration, or respiratory issues early.

**Acceptance Criteria**:
1. SHALL extract voice biomarker features during every voice interaction: pitch (fundamental frequency), speech rate (words per minute), voice energy/volume, pause patterns, verbal fluency, articulation clarity
2. SHALL establish personalized voice baselines within 14 days
3. SHALL detect significant deviations from baseline (voice becoming more monotone, slower, less articulate)
4. SHALL correlate voice biomarker changes with known clinical indicators: cognitive decline, depression, dehydration, respiratory distress, medication side effects
5. SHALL include voice biomarker trends in the drift detection engine and pre-consultation reports

---

### 7.14 Cross-Cutting: Web Dashboard

#### REQ-46: Caregiver Dashboard 🔴 DEMO

**User Story**: As Arjun, I want a web dashboard where I can see my mother's status at a glance, review recent events, and manage her care settings.

**Acceptance Criteria**:
1. SHALL display real-time resident status: current activity state, last known location (room), medication adherence today, most recent check-in summary, any active alerts
2. SHALL show a 24-hour activity timeline with event markers
3. SHALL display weekly trend charts: sleep, activity, medication adherence, mood scores, drift composite
4. SHALL provide event history with filtering by type, severity, and date range
5. SHALL support push notifications via browser for Alert and Emergency events
6. SHALL be responsive and work on tablet and desktop screens
7. SHALL authenticate via Cognito with role-based access (family, nurse, doctor, admin)

#### REQ-47: Clinic Operations Dashboard (B2B) 🔴 DEMO

**User Story**: As Meena (ops manager), I want a fleet view showing all patients across my clinic with status indicators, so I can see who needs attention.

**Acceptance Criteria**:
1. SHALL display a grid/list of all patients with color-coded status indicators: Green (stable), Yellow (drift detected/watch), Orange (active alert), Red (emergency)
2. SHALL allow filtering and sorting by status, acuity score, caregiver, last event
3. SHALL show aggregate analytics: total patients, active alerts, medication adherence rates, upcoming appointments
4. SHALL provide drill-down from fleet view to individual patient dashboard
5. SHALL display caregiver workload distribution and scheduling
6. SHALL generate exportable compliance/quality reports (weekly, monthly)
7. SHALL support multi-tenant access — each clinic sees only their patients

#### REQ-48: Analytics & Reporting Dashboard 🔴 DEMO

**User Story**: As Rajesh (facility manager), I want analytics on care quality metrics, incident trends, and operational efficiency, so I can demonstrate value and compliance.

**Acceptance Criteria**:
1. SHALL display aggregate metrics: average response time, false alarm rate, medication adherence, fall incident rate, hospitalization rate
2. SHALL show trend analysis over configurable time periods (7-day, 30-day, 90-day)
3. SHALL compare metrics against benchmarks and previous periods
4. SHALL generate downloadable PDF reports for regulatory review
5. SHALL allow custom date range selection for all visualizations

---

### 7.15 Cross-Cutting: Mobile Application

#### REQ-49: Elderly Mobile App (Simplified UI) 🔴 DEMO

**User Story**: As Kamala Devi, I need a simple mobile app (if I use one at all) with very large buttons, minimal screens, and voice-first interaction for when my son sets it up on a tablet.

**Acceptance Criteria**:
1. SHALL have a maximum of 4 main screens — Home, Medications, Help, Family
2. SHALL use extra-large fonts (minimum 18pt body, 24pt headers), high-contrast colors, and minimal visual clutter
3. SHALL support voice activation from any screen
4. SHALL show medication schedule with visual pill identification (photos and colors)
5. SHALL have a prominent SOS button on every screen
6. SHALL support Hindi and English (switchable)
7. SHALL work offline with cached data and sync when connectivity returns

#### REQ-50: Family Caregiver Mobile App 🔴 DEMO

**User Story**: As Arjun, I want a mobile app on my phone with real-time status, notifications, and the ability to remotely configure and interact with my mother's AETHER system.

**Acceptance Criteria**:
1. SHALL show real-time resident status summary on the home screen
2. SHALL receive push notifications for Inform, Alert, and Emergency tier events
3. SHALL allow viewing event details, evidence packets, and timeline
4. SHALL support prescription photo upload for OCR digitization
5. SHALL allow recording and sending voice postcards
6. SHALL show medication adherence dashboard and schedule
7. SHALL allow configuring care settings: reminder times, escalation contacts, alert preferences
8. SHALL authenticate via Cognito and support biometric login

#### REQ-51: Nurse Mobile App 🟡 STRETCH

**User Story**: As Sister Priya, I need a mobile app optimized for patient visits — quick access to patient info, voice note capture, and medication management on the go.

**Acceptance Criteria**:
1. SHALL show prioritized patient list with status indicators
2. SHALL provide quick patient summary accessible per visit
3. SHALL support voice note capture during visits (auto-transcription)
4. SHALL allow medication schedule updates and administration logging
5. SHALL display visit schedule with navigation/route optimization
6. SHALL work offline and sync notes/updates when connectivity returns

---

### 7.16 Cross-Cutting: Edge Computing & IoT

#### REQ-52: Edge Hub Offline Operation 🔴 DEMO

**User Story**: As the system, I must continue all safety-critical functions even when internet connectivity is lost, because elderly safety cannot depend on WiFi uptime.

**Acceptance Criteria**:
1. SHALL run fall detection, acoustic event detection, medication reminders, and basic voice commands entirely on the edge hub without cloud connectivity
2. SHALL queue events locally (SQLite) during offline periods and sync when connectivity resumes
3. SHALL maintain FIFO queue with a minimum 72-hour event buffer
4. SHALL indicate connectivity status to caregivers via the dashboard (online/offline/degraded)
5. SHALL process sensor data at full fidelity offline — no quality degradation
6. SHALL respond to wake word and basic commands offline with locally cached TTS responses

#### REQ-53: Sensor Data Fusion 🔴 DEMO

**User Story**: As the system, I need to combine data from multiple sensors to make accurate assessments, because no single sensor is reliable enough alone.

**Acceptance Criteria**:
1. SHALL aggregate data from all configured sensors via MQTT on the edge hub
2. SHALL support sensor types: accelerometer/IMU (wearable), pressure mat (bed/chair), PIR motion sensor, door/window contact sensors, temperature/humidity, gas/smoke sensor, microphone (acoustic processing only — no raw audio storage)
3. SHALL timestamps all sensor readings with synchronized clocks (<100ms tolerance)
4. SHALL handle sensor failures gracefully — continue operation with reduced sensor set and flag degraded accuracy
5. SHALL perform sensor fusion on-device for latency-sensitive events (fall detection: <2 second end-to-end)

#### REQ-54: Sensor Simulators 🔴 DEMO

**User Story**: As a developer, I need realistic sensor simulators that generate representative data streams for developing and demoing without physical hardware.

**Acceptance Criteria**:
1. SHALL provide software simulators for all sensor types that generate realistic data streams via MQTT
2. SHALL support scenario-based simulation: "morning routine," "fall event," "medication time," "nocturnal wandering," "cooking forgotten," "gradual decline over 2 weeks"
3. SHALL generate time-series data with realistic noise, drift, and variation
4. SHALL support real-time streaming (simulating live sensors) and accelerated replay (compress 24 hours into 5 minutes for demo)
5. SHALL be configurable: adjust event frequency, severity distribution, noise level

#### REQ-55: MQTT Communication Layer 🔴 DEMO

**User Story**: As the system, sensor-to-hub and hub-to-cloud communication must use MQTT for lightweight, reliable IoT messaging.

**Acceptance Criteria**:
1. SHALL use MQTT v3.1.1+ for all sensor-to-hub communication
2. SHALL use AWS IoT Core for hub-to-cloud communication with certificate-based authentication
3. SHALL implement QoS Level 1 (at least once delivery) for all safety-critical events
4. SHALL support topic hierarchy: `aether/{home_id}/sensors/{sensor_type}/data` and `aether/{home_id}/events/{event_type}`
5. SHALL encrypt all MQTT payloads in transit using TLS 1.2+

---

### 7.17 Cross-Cutting: AI & LLM Platform

#### REQ-56: Multi-Agent Orchestration 🔴 DEMO

**User Story**: As the system, I need a multi-agent architecture where specialized AI agents handle different care domains and collaborate to deliver holistic care.

**Acceptance Criteria**:
1. SHALL implement agents using AWS Bedrock Agents with action groups and knowledge bases
2. SHALL support at minimum these agents: Triage Agent (event classification), Clinical Scribe Agent (documentation), Care Navigation Agent (health Q&A), Polypharmacy Agent (drug interaction), Ride Booking Agent (transportation), Report Agent (pre-consultation summaries)
3. SHALL enable agent-to-agent communication: Triage Agent can invoke Clinical Scribe Agent to document an event it triaged
4. SHALL log all agent actions, decisions, and tool invocations for audit trail
5. SHALL enforce Bedrock Guardrails across all agent responses to prevent hallucination, harmful content, and unauthorized medical advice
6. SHALL gracefully degrade when agent invocation fails — fall back to rule-based defaults

#### REQ-57: Knowledge Base Management 🔴 DEMO

**User Story**: As the system, I need curated, versioned knowledge bases that ground AI agent responses in verified medical and pharmaceutical information.

**Acceptance Criteria**:
1. SHALL use Bedrock Knowledge Bases with S3-hosted document collections
2. SHALL maintain separate knowledge bases for: medical Q&A (general health info, condition management), pharmaceutical data (drug interactions, generic alternatives, PMBJP catalog), dietary guidance (Indian-specific nutrition, food-drug interactions), government schemes (eligibility, application process)
3. SHALL support knowledge base versioning and updates without downtime
4. SHALL track knowledge base source citations in agent responses: "Based on PMBJP catalog updated June 2025"
5. SHALL include Indian-specific medical guidelines (ICMR, IMA) alongside WHO/CDC guidelines

#### REQ-58: LLM Safety & Guardrails 🔴 DEMO

**User Story**: As the system, all LLM-generated content must be safe, accurate, and appropriate for elderly healthcare use — no hallucinated drug names, no dangerous advice, no inappropriate content.

**Acceptance Criteria**:
1. SHALL use Bedrock Guardrails to block: fabricated drug names or dosages, medical treatment recommendations (only information, not advice), content that could cause panic or anxiety, personally identifiable information in logs, culturally inappropriate or disrespectful content
2. SHALL implement response validation: if LLM mentions a drug, validate it exists in the knowledge base before presenting to user
3. SHALL always include safety disclaimers for health information: "Yeh jaankari kewal samajhne ke liye hai. Apne doctor se zaroor baat karein."
4. SHALL log all guardrail activations for safety review
5. SHALL have a human-reviewable safety audit trail for all medical-adjacent AI outputs
6. SHALL support emergency-aware mode: in Emergency tier events, switch from conversational to directive: "Kamala ji, stay still. Help is on the way. I have called Arjun."

---

### 7.18 Cross-Cutting: Data & Privacy

#### REQ-59: Privacy-First Architecture 🔴 DEMO

**User Story**: As Kamala Devi, I need assurance that my private conversations, health data, and home activities are protected and that raw sensor data never leaves my home.

**Acceptance Criteria**:
1. SHALL process all raw audio, video (if any), and sensor streams on the edge hub — only extracted features, events, and anonymized metrics transit to cloud
2. SHALL never store raw audio recordings — only acoustic event labels and voice biomarker features
3. SHALL encrypt all data at rest (AES-256) and in transit (TLS 1.2+)
4. SHALL implement field-level encryption for PHI (Protected Health Information) using AWS KMS
5. SHALL maintain comprehensive audit logs for all data access
6. SHALL support consent management: residents can opt-in/out of specific monitoring features
7. SHALL comply with India's Digital Personal Data Protection Act (DPDP) 2023

#### REQ-60: Multi-Tenant Data Isolation 🔴 DEMO

**User Story**: As Meena (clinic ops), I need assurance that our patient data is completely isolated from other clinics using the same AETHER platform.

**Acceptance Criteria**:
1. SHALL implement tenant isolation at the DynamoDB partition level using composite keys
2. SHALL enforce tenant-scoped IAM policies — no cross-tenant data access
3. SHALL ensure API Gateway authorization checks tenant context on every request
4. SHALL support tenant-specific encryption keys via KMS
5. SHALL provide audit logs filterable by tenant

#### REQ-61: Consent Management 🟡 STRETCH

**User Story**: As Kamala Devi, I want to control what data is collected and who can see it, and be able to change my mind at any time.

**Acceptance Criteria**:
1. SHALL provide granular consent options: activity monitoring, voice interaction recording, health data sharing with family, health data sharing with doctors, emergency data sharing with first responders
2. SHALL allow consent changes via voice command or mobile app
3. SHALL immediately enforce consent changes — if voice interaction consent is withdrawn, voice companion ceases
4. SHALL maintain a consent audit trail with timestamps
5. SHALL default to minimum-necessary data collection for safety features

---

## 8. Safety Constraints

These are non-negotiable safety requirements that apply across the entire system.

### SC-1: Fail-Safe Defaults
- All safety features MUST default to the MORE protective setting
- If uncertain whether an event is a fall, treat it as a fall
- If uncertain whether a medication was taken, treat it as missed
- If connectivity status is unknown, assume offline and activate local safeguards

### SC-2: No Medical Treatment Decisions
- AETHER MUST NOT recommend specific treatments, modify medication dosages, or override clinical decisions
- The system provides information and monitoring — medical decisions remain with licensed healthcare providers
- Every medical-adjacent response includes a disclaimer directing users to their healthcare provider

### SC-3: Emergency Override
- SOS button and "Emergency" voice command MUST bypass ALL other processing and immediately trigger Emergency tier response
- Emergency functions MUST work offline
- Emergency evidence packets MUST be generated and accessible within 10 seconds

### SC-4: Data Safety
- Raw audio MUST NOT leave the edge device
- PHI MUST be encrypted at rest and in transit
- System MUST operate with minimal data collection if consent is restricted
- All LLM responses involving health data MUST go through guardrails

### SC-5: Graceful Degradation
- Loss of any single sensor MUST NOT disable the entire monitoring system
- Loss of internet MUST NOT disable safety-critical features
- Loss of cloud services MUST NOT prevent local event detection and recording
- Battery backup (if available) MUST maintain critical functions for 4+ hours

### SC-6: Cultural Safety
- Voice interactions MUST use respectful, age-appropriate language
- Cultural sensitivities (dietary restrictions, religious practices, family hierarchy) MUST be respected
- The system MUST NOT make assumptions about family dynamics or caregiving arrangements

---

## 9. Non-Functional Requirements

### 9.1 Performance

| Metric | Target |
|---|---|
| Fall detection latency (sensor → event) | < 2 seconds |
| Wake word detection latency | < 1 second |
| Voice command response latency | < 3 seconds (online), < 1 second (offline basic) |
| Dashboard load time | < 2 seconds |
| API response time (95th percentile) | < 500ms |
| Event processing pipeline (edge → cloud) | < 5 seconds |
| LLM agent response (complex query) | < 10 seconds |
| Push notification delivery | < 5 seconds from event classification |

### 9.2 Reliability & Availability

| Metric | Target |
|---|---|
| Edge hub uptime | 99.9% (< 8.76 hours downtime/year) |
| Cloud services uptime | 99.95% (AWS SLA) |
| Offline operation guarantee | Minimum 72 hours without cloud |
| Data durability (S3) | 99.999999999% (11 nines) |
| Event delivery guarantee | At-least-once for all Safety and Emergency events |

### 9.3 Scalability

| Metric | Target |
|---|---|
| Single-hub sensor throughput | 100+ messages/second |
| Cloud event processing | 10,000 events/minute per tenant |
| DynamoDB read/write capacity | Auto-scaling, on-demand |
| Concurrent dashboard users | 500+ per tenant |
| Multi-tenant homes supported | 10,000+ homes on shared infrastructure |

### 9.4 Cost

| Item | Target |
|---|---|
| Single-home AWS monthly cost | < ₹5,000 (~$60 USD) |
| Per-additional-home marginal cost (B2B) | < ₹500 (~$6 USD) |
| Edge hardware one-time cost (BoM) | < ₹15,000 (~$180 USD) |
| LLM inference cost per home/month | < ₹1,000 (~$12 USD) |

---

## 10. 2-Month Demo Scope

### 10.1 What the Demo Proves

The 2-month demo is designed to prove that AETHER can address ALL 12 pain points in a compelling, realistic manner. It uses **simulated hardware** (sensor simulators) with **real AI processing** (actual Bedrock agents, actual ML models, actual voice interaction).

### 10.2 Demo Priority Features (Must Be Working)

| # | Feature | Pain Point | User Experience |
|---|---|---|---|
| 1 | Fall detection + voice triage | PP1 | Simulate fall → system detects → asks "are you okay?" → escalates appropriately |
| 2 | Medication reminders + adherence tracking | PP2 | Voice reminder at scheduled time → confirm/miss → adherence dashboard |
| 3 | Prescription OCR | PP2, PP3 | Photo of handwritten Rx → structured medication list → drug interactions flagged |
| 4 | Drug interaction checking | PP2 | Add new medication → immediate interaction warning with explanation |
| 5 | Clinical summarization | PP4, PP10 | Generate SOAP-style weekly summary from sensor data |
| 6 | Intelligent alert triage | PP5 | Simulate multiple events → show how system triages (some suppressed, some escalated) |
| 7 | Drift detection | PP6 | Show 2-week simulated decline → drift alert with composite score |
| 8 | Voice companion + daily check-in | PP7 | Natural Hindi conversation → check-in data extracted → mood tracked |
| 9 | Meal tracking | PP8 | Kitchen sensor activity → meal detected/missed → alert for missed meal |
| 10 | Emergency evidence packet | PP9 | Emergency event → auto-generated packet with all patient data |
| 11 | Auto ride booking | PP9 | Appointment detected → ride booked → confirmed with resident |
| 12 | FHIR export + pre-consultation report | PP10 | Doctor dashboard shows formatted patient summary before appointment |
| 13 | Kitchen/environmental safety | PP11 | Stove left on → voice warning → caregiver alert |
| 14 | Care navigation Q&A | PP12 | Hindi health question → culturally-appropriate RAG response |
| 15 | Web dashboard (family + clinic) | All | Real-time status, event timeline, analytics |
| 16 | Mobile app (elderly + family) | All | Simplified elderly view, full caregiver view |
| 17 | Offline mode | All | Demonstrate safety features working without internet |
| 18 | Sensor simulators | All | Realistic multi-sensor data generation with demo scenarios |

### 10.3 Stretch Features (If Time Permits)

| # | Feature | Pain Point |
|---|---|---|
| 1 | Gait degradation prediction (ML model) | PP1 |
| 2 | Generic alternative suggestions (PMBJP) | PP2 |
| 3 | Lab report digitization | PP3 |
| 4 | Caregiver burnout predictor | PP4 |
| 5 | Voice biomarker analysis | PP6 |
| 6 | Reminiscence therapy & life memoir | PP7 |
| 7 | Family voice postcards | PP7 |
| 8 | Hydration tracking & prediction | PP8 |
| 9 | Dietary guidance agent | PP8 |
| 10 | Post-discharge compliance | PP10 |
| 11 | Bathroom safety / wandering detection | PP11 |
| 12 | Government scheme discovery | PP12 |
| 13 | WhatsApp integration for alerts | All |
| 14 | Scam call interceptor | PP7 |
| 15 | NFC medication identification | PP2 |

### 10.4 Vision Features (Future Roadmap, Not in 2-Month Sprint)

- Dynamic caregiver scheduling optimization
- Video-based activity recognition (Jetson Orin Nano + DeepStream)
- Digital Health Passport for elderly
- Community matching for social engagement
- Bedsore risk prediction from bed pressure patterns
- Multi-facility fleet management for large B2B deployments
- NVIDIA Omniverse digital twin of the home
- Integration with hospital EMR systems (real FHIR endpoints)
- Wearable vital sign monitoring (SpO2, ECG) with medical-grade devices
- Telehealth video consultation integration

---

## 11. Assumptions

1. **Hardware is simulated**: The 2-month demo uses software sensor simulators, not physical hardware. The system architecture supports real hardware through the same MQTT interfaces.
2. **AWS Bedrock models available in ap-south-1**: Claude, Titan, and configured models are accessible in the Mumbai region. If model availability is limited, us-east-1 is used as fallback.
3. **Single-developer sprint**: The 2-month timeline assumes a single senior full-stack developer working full-time with AI assistance.
4. **Internet connectivity**: For development and demo, reliable internet is available. Offline capability is demonstrated but not the primary operating mode.
5. **English/Hindi primary**: Voice interaction supports Hindi and English in the demo. Tamil and Kannada are architecture-ready but not implemented in the 2-month sprint.
6. **Medical knowledge base is curated, not generated**: The RAG knowledge base content is manually curated from verified medical sources, not AI-generated.
7. **Ride booking is simulated**: The ride booking agent demonstrates the agentic workflow with a mock API, not actual Ola/Uber integration.

---

## 12. Out of Scope (2-Month Sprint)

1. Real hardware procurement, assembly, and field testing
2. Clinical trial validation or regulatory approval (CE/FDA)
3. Integration with real hospital EMR systems
4. Real-time video analytics on edge devices
5. Multi-language voice (beyond Hindi + English)
6. Real payment processing or insurance claims
7. HIPAA compliance certification (architecture supports it, not certified)
8. Real ride-hailing API integration (simulated only)
9. Mobile app store deployment (development builds only)
10. Load testing at production scale (>1000 homes)

---

## 13. Success Metrics (2-Month Demo)

### Technical Metrics
| Metric | Target |
|---|---|
| Fall detection accuracy (simulated) | > 95% |
| False alarm suppression rate | > 70% of raw alerts silenced with context |
| Prescription OCR accuracy (printed) | > 85% |
| Voice command recognition (Hindi) | > 90% |
| API uptime during demo period | > 99% |
| Edge-to-cloud event latency | < 5 seconds |
| Offline operation uptime | 72+ hours demonstrated |

### User Experience Metrics
| Metric | Target |
|---|---|
| Dashboard page load time | < 2 seconds |
| Voice response time | < 3 seconds |
| Daily check-in completion rate (simulated) | 100% |
| Agent workflow completion rate | > 95% |
| Pre-consultation report generation | Automated, < 30 seconds |

### Business Metrics (for Demo Narrative)
| Metric | Target |
|---|---|
| Pain points demonstrated | 12/12 |
| Working agentic AI agents | ≥ 6 |
| Documentation automation potential | > 50% time savings demonstrated |
| Cost per home (AWS) | < ₹5,000/month |
| Generic medication savings identified | > 50% on sample prescription |

---

*End of Requirements Specification — AETHER CareOps Platform v2.0*
