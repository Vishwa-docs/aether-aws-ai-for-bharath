# AETHER — Project Summary

## Autonomous Elderly Ecosystem for Total Health Emergency Response & Optimization

---

## What is AETHER?

AETHER is a **production-grade elderly care operating system** that prevents health emergencies, detects them instantly, and coordinates real-world response — all powered by AWS and GenAI.

Unlike fragmented monitoring solutions, AETHER provides a **unified platform** spanning edge devices, cloud AI, and 4 persona-specific dashboards serving elders, caregivers, doctors, and operations teams.

---

## The Problem

**150+ million elderly people** worldwide live independently, facing cascading risks:

- **Falls** — #1 cause of injury deaths in 65+ population
- **Medication errors** — 125,000 deaths/year from non-adherence
- **Dehydration & malnutrition** — often undetected for days
- **Cognitive decline** — wandering, confusion, delayed care
- **Caregiver burnout** — 40% of family caregivers report depression

Current solutions are either **invasive** (cameras), **fragmented** (single-purpose devices), or **too noisy** (false alarms erode trust).

---

## Our Solution

### End-to-End Architecture on AWS

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Edge** | Raspberry Pi + ESP32 mesh | Privacy-first local processing, no raw video/audio leaves device |
| **Cloud** | DynamoDB, Lambda, Step Functions, IoT Core | Scalable event pipeline with serverless compute |
| **AI** | Amazon Bedrock (Nova Lite) | Clinical reasoning, polypharmacy analysis, document generation |
| **Frontend** | React + TypeScript PWA | 4-persona responsive dashboard with mobile support |
| **Auth** | AWS Cognito | Role-based access with 4 user groups |

### 15+ AI Features

1. Care Navigation AI (Bedrock clinical Q&A)
2. Polypharmacy Checker (drug interactions + Beers Criteria)
3. Clinical Document Generator (SOAP notes, summaries)
4. Health Insights Engine (risk scoring, drift detection)
5. Voice Companion (sentiment + mood tracking)
6. Fall Detection (edge ML pose estimation)
7. Medication Adherence (NFC-verified + Step Functions)
8. Choking Triage (acoustic anomaly detection)
9. Wandering Detection (geofence + motion patterns)
10. Vital Anomaly Detection (HR, SpO2, temperature)
11. Sleep Quality Analysis (respiratory metrics)
12. Predictive Health Decline (multi-signal analysis)
13. Prescription OCR (text extraction)
14. Emergency Escalation (4-tier automated response)
15. Analytics & Trend AI (confidence drift, false positive analysis)

---

## AWS Services Used

- **Amazon Bedrock** — Core AI engine (Nova Lite model for all GenAI features)
- **DynamoDB** — 5 tables handling events, timeline, residents, consent, clinic ops
- **Lambda** — 8 serverless functions for processing
- **Step Functions** — 6 workflows (medication adherence, fall detection, prescription, choking, wellness, health decline)
- **Cognito** — Authentication with elder/caregiver/doctor/ops roles
- **IoT Core** — Edge device communication
- **S3** — Document and asset storage
- **CloudWatch** — Operational monitoring
- **CDK** — Infrastructure as Code (4 stacks)
- **Polly** — Voice synthesis for AI companion

---

## Key Differentiators

### 1. Privacy-First by Design
No raw video or audio ever leaves the edge device. All sensor data is processed locally using TFLite models, and only structured events (fall_detected, medication_taken, etc.) are transmitted to the cloud.

### 2. Multi-Persona Experience
Four distinct dashboard experiences tailored to each user type:
- **Elder** — Simplified health view with AI companion
- **Caregiver** — Full monitoring with real-time alerts
- **Doctor** — Clinical documents and prescriptions
- **Ops** — Fleet management and analytics

### 3. Real AI, Real Data
Every AI feature calls Amazon Bedrock in real-time. No hardcoded responses. The system reads actual patient data from DynamoDB, constructs contextual prompts, and returns clinician-grade analysis.

### 4. Offline-First Edge
The edge gateway operates independently when connectivity is lost, caching events locally and syncing when the connection is restored.

### 5. 4-Tier Emergency Escalation
Automated escalation from local caregiver notification → remote family alert → telehealth activation → emergency services dispatch.

---

## Technical Metrics

| Metric | Value |
|--------|-------|
| Total codebase | ~40,000 lines |
| Dashboard pages | 12+ |
| Lambda functions | 8 |
| Step Functions | 6 |
| DynamoDB tables | 5 |
| CDK stacks | 4 |
| AI features | 15+ |
| Edge test coverage | Unit tests for all modules |
| TypeScript compilation | Zero errors |

---

## Demo Highlights

**Live Demo:** http://65.1.180.56:8080 — Login with any persona card (password: `demo123`)

1. **Live DynamoDB data** — Real residents, events, and timeline entries
2. **Real-time Bedrock AI** — Ask care questions, generate documents, check drug interactions
3. **Scenario simulation** — Trigger fall/choking/wandering/medication events that write to DynamoDB
4. **Mobile PWA** — Install on phone, bottom tab navigation
5. **Role switching** — Login as elder/caregiver/doctor/ops for different experiences
6. **Guided Tour** — First-time login shows a step-by-step walkthrough of key features

---

## Deployment

Deployed on **AWS ECS Fargate** (Mumbai region) with a Docker multi-stage build serving the FastAPI backend and React dashboard as a single container on port 8080.

---

## Future Roadmap

- Real hardware deployment (Raspberry Pi + ESP32 mesh kit)
- Apple Watch / Wear OS integration
- Multi-language support (Hindi, Tamil, Telugu)
- Telehealth video integration
- Community health worker module
- Insurance API integration for claim automation
- Regional dialect voice companion (Bedrock + Polly)

---

*Built for the GenAI Hackathon — March 2026*
