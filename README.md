# AETHER CareOps Platform

> **Autonomous Elderly ecosystem for Total Health, Engagement & Response**
> AI-powered elder care operating system built on AWS

[![AWS](https://img.shields.io/badge/AWS-Powered-FF9900?logo=amazon-aws)](https://aws.amazon.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?logo=typescript)](https://typescriptlang.org)

**Live Demo:** http://13.201.85.165:8080

---

## Overview

AETHER is an end-to-end elderly care operating system that combines **ambient sensing**, **edge AI**, and **agentic GenAI** (Amazon Bedrock) to prevent health emergencies, detect them instantly, and coordinate real-world response across caregivers, medical staff, and emergency services.

The platform provides 4 persona-based dashboards (Elder, Caregiver, Doctor, Operations) with 15+ AI-powered features, all running on AWS infrastructure. All AI features hit real AWS services — nothing is mocked.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AETHER Architecture                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐ │
│  │  Edge     │───▶│  AWS IoT     │───▶│  DynamoDB Tables      │ │
│  │  Devices  │    │  Core        │    │  (Events/Timeline/    │ │
│  │  (Hub +   │    │              │    │   Residents/Consent)  │ │
│  │  Sensors) │    └──────────────┘    └───────────┬───────────┘ │
│  └──────────┘                                     │             │
│                                                   ▼             │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐ │
│  │ Dashboard │◀──▶│  FastAPI     │───▶│  Amazon Bedrock       │ │
│  │ (React)   │    │  Backend     │    │  (Nova Lite)          │ │
│  │ PWA       │    │  (boto3)     │    │  AI Analysis          │ │
│  └──────────┘    └──────────────┘    └───────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │  Lambda Functions (8) · Step Functions (6) · Cognito Auth │ │
│  │  S3 Storage · CloudWatch · IAM Roles · CDK Stacks (4)    │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## AWS Services Used

| Service | Purpose |
|---------|---------|
| **Amazon Bedrock** | AI inference (Nova Lite) — care navigation, polypharmacy checks, document generation, health insights, voice companion |
| **DynamoDB** | 5 tables — events, timeline, residents, consent, clinic-ops |
| **Lambda** | 8 serverless functions for event processing, analytics, care navigation, etc. |
| **Step Functions** | 6 state machines for workflows (medication adherence, fall detection, prescription, choking triage, wellness, health decline) |
| **Cognito** | User authentication with 4 role-based groups |
| **IoT Core** | Edge device communication and telemetry ingestion |
| **S3** | Document storage, clinical documents |
| **CloudWatch** | Monitoring and logging |
| **CDK** | Infrastructure as Code (4 stacks) |
| **Polly** | Text-to-speech for voice companion |

## AI Features (15+)

1. **Care Navigation AI** — Bedrock-powered clinical Q&A with patient context
2. **Polypharmacy Checker** — Drug interaction analysis + Beers Criteria for elderly
3. **Clinical Document Generator** — SOAP notes, daily summaries, incident reports
4. **Health Insights Engine** — Risk scoring, trend analysis, drift detection
5. **Voice Companion** — AI check-in with sentiment analysis + mood tracking
6. **Fall Detection** — Edge ML pose estimation (no video leaves device)
7. **Medication Adherence** — NFC-verified dose tracking with escalation
8. **Choking Triage** — Acoustic anomaly detection + emergency workflow
9. **Wandering Detection** — Geofence + motion pattern analysis
10. **Vital Anomaly Detection** — Heart rate, SpO2, temperature monitoring
11. **Sleep Quality Analysis** — Pattern tracking with respiratory metrics
12. **Predictive Health Decline** — Multi-signal drift detection
13. **Prescription OCR** — Text extraction from uploaded prescriptions
14. **Emergency Escalation** — 4-tier automated response coordination
15. **Analytics & Trend AI** — Model confidence drift + false positive analysis

## 4 Persona Dashboards

| Persona | Features |
|---------|----------|
| **Elder** | Simplified health view, AI companion, medication reminders, family portal |
| **Caregiver** | Full monitoring, alerts, timeline, care navigation, prescriptions, handoffs |
| **Doctor** | Clinical docs, prescriptions, patient analytics, health insights |
| **Operations** | Fleet management, sensor health, analytics, site monitoring |

## Project Structure

```
├── api/                    # FastAPI backend server (boto3 → AWS)
│   └── server.py           # All API endpoints
├── cloud/
│   ├── lambdas/            # 8 Lambda functions
│   │   ├── analytics_processor/
│   │   ├── api_handler/
│   │   ├── care_navigation/
│   │   ├── clinic_ops/
│   │   ├── doc_generator/
│   │   ├── escalation_handler/
│   │   ├── event_processor/
│   │   └── ...
│   └── step_functions/     # 6 ASL state machines
├── dashboard/              # React + TypeScript + Tailwind
│   ├── src/
│   │   ├── components/     # Layout, DemoPanel, StatusBadge...
│   │   ├── contexts/       # AuthContext, LiveDataContext
│   │   ├── pages/          # 12+ page components
│   │   ├── services/       # API service layer
│   │   └── types/          # TypeScript interfaces
│   └── public/             # PWA manifest
├── edge/                   # Edge device code (Python)
│   ├── src/aether/         # Sensor fusion, ML models, gateway
│   └── tests/              # Unit tests
├── infrastructure/         # AWS CDK (TypeScript)
│   ├── lib/                # 4 CDK stacks
│   └── api/                # OpenAPI spec
└── scripts/                # DynamoDB seeder, utilities
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- AWS CLI configured with credentials
- AWS region: `ap-south-1`

### 1. Start the Backend API

```bash
cd api
pip install fastapi uvicorn boto3
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Start the Dashboard

```bash
cd dashboard
npm install
npm run dev
```

The dashboard starts on `http://localhost:3001` with API proxy to the backend.

### 3. Login

Use any of the demo accounts (password: `demo123`):

| User | Role | Features |
|------|------|----------|
| Priya Sharma | Caregiver | Full access |
| Dr. Arjun Mehta | Doctor | Clinical focus |
| Kamala Devi | Elder | Simplified view |
| Ravi Kumar | Operations | Fleet & analytics |

### 4. Seed Demo Data (Optional)

```bash
cd scripts
python seed_dynamodb.py
```

Seeds 3 residents, 544 events, 42 timeline entries to DynamoDB.

## Demo Guide

### Quick Access

Open **http://13.201.85.165:8080** in your browser. You'll see the login page with 4 persona cards. Click any card to log in instantly — password is `demo123`.

### Recommended Demo Flow

1. **Login as Caregiver** (Priya Nair, green card) → See the full operations dashboard
2. **Residents** → Expand a resident card → Click "AI Health Insights" (sparkle icon) → Watch Bedrock generate analysis
3. **Care Navigation** → Type "What diet should Kamala follow for diabetes?" → Real Bedrock AI response
4. **Prescriptions** → Click "Check Interactions" → See polypharmacy analysis with generic alternatives
5. **Demo Panel** (⚡ lightning bolt in sidebar) → Trigger a "Fall Detected" scenario → See it appear on Timeline/Alerts
6. **Login as Doctor** (Dr. Rajesh, blue card) → **Clinical Docs** → Select resident → Generate a SOAP Note with Bedrock
7. **Login as Ops** (Anand Kulkarni, amber card) → **Fleet Ops** → See fleet management, sensor health, workload

### Key AI Features to Demo

- **Care Navigation** → Ask any health question → Bedrock responds with patient context
- **Clinical Docs** → Generate SOAP notes, discharge summaries, care plans from real data
- **Polypharmacy** → Drug interaction analysis + PMBJP generic alternatives with cost savings
- **Health Insights** → AI pattern analysis across sensor data for drift detection
- **Voice Companion** → AI-generated responses using Amazon Polly text-to-speech

## Deployment

The platform is deployed on **AWS ECS Fargate** in the `ap-south-1` (Mumbai) region.

- **Container:** Docker multi-stage build (Node.js 20 + Python 3.11)
- **Registry:** ECR `aether-careops`
- **Cluster:** ECS `aether-cluster`
- **Port:** 8080

To redeploy after changes:
```bash
./deploy.sh
```

## Tech Stack

- **Frontend:** React 18, TypeScript 5.5, TailwindCSS 3.4, Recharts, Vite 5
- **Backend:** FastAPI, Python 3.11, boto3
- **AI/ML:** Amazon Bedrock (Nova Lite), Edge ML (TFLite)
- **Database:** DynamoDB (5 tables)
- **Auth:** AWS Cognito (4 user groups)
- **Infrastructure:** AWS CDK (TypeScript), 4 stacks
- **Edge:** Python, ESP32/Raspberry Pi compatible
- **Mobile:** Progressive Web App (PWA) with installable manifest

## Privacy & Safety

- **Privacy-First:** No raw video/audio leaves the edge device
- **Edge Processing:** Sensor data processed locally, only events sent to cloud
- **Encryption:** All data encrypted at rest (DynamoDB) and in transit (TLS)
- **Role-Based Access:** 4 Cognito groups with granular permissions
- **Consent Management:** Per-resident privacy levels and data sharing controls
- **Audit Trail:** All AI-generated content includes model attribution and timestamps

## Team

Built for the GenAI Hackathon — March 2026

## License

Proprietary — Hackathon Submission
