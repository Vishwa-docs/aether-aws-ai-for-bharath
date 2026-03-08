# AETHER — Pitch Guide

## What is AETHER?

AETHER stands for Autonomous Elderly ecosystem for Total Health, Engagement & Response. It is an end-to-end care operating system that monitors elderly residents through ambient sensors, processes data locally on edge devices for privacy, and uses Amazon Bedrock's generative AI for clinical reasoning, document generation, and care navigation. The platform coordinates response across families, nurses, doctors, and emergency services — all from a single unified dashboard.

The core insight behind AETHER is simple: elderly care is not a single problem, it is twelve interconnected problems — falls, medication chaos, caregiver burnout, silent health decline, social isolation, alert fatigue, and more. AETHER addresses all twelve with a combination of multi-sensor fusion at the edge and agentic AI in the cloud. Nothing is mocked. Every AI feature hits real AWS services.

---

## The Problem We Solve

Every 11 seconds, an older adult is treated in the ER for a fall. Over 125,000 people die annually from medication non-adherence alone. More than 150 million elderly people worldwide live independently, facing cascading health risks that current monitoring solutions simply cannot handle.

Existing solutions fall into three broken categories. Camera-based systems are invasive and strip dignity. Single-purpose devices like pendant alarms are fragmented — they do not talk to each other or learn from patterns. And clinical monitoring systems are so noisy with false alarms that families stop trusting them within weeks. AETHER was built to change all of that.

---

## How It Works — The Architecture

AETHER runs on a three-tier architecture. At the edge, a Raspberry Pi 5 hub collects data from 10+ sensors (accelerometer, pressure mat, acoustic, PIR motion, door sensors, temperature, gas, pillbox) and runs local AI models for fall detection and acoustic event classification. No raw audio or video ever leaves the home — only structured event labels and extracted features are sent to the cloud.

In the cloud, events flow through AWS IoT Core into DynamoDB, where Lambda functions and Step Functions process them. Amazon Bedrock (Nova Lite model) powers five AI endpoints: care navigation, polypharmacy checking, clinical document generation, health insights, and voice companion responses. The entire infrastructure is defined as code using CDK with four stacks.

On the client side, a React + TypeScript dashboard serves four persona-based views (Elder, Caregiver, Doctor, Operations), each showing role-appropriate data and features. The dashboard is also a PWA that works on mobile devices with a bottom tab navigation bar.

---

## How to Demo — Step by Step

Open the live deployment URL in your browser. You will see the AETHER login page with four persona cards. Each persona reveals a different view of the platform. The password for all accounts is **demo123**. Simply click any persona card to log in instantly.

### Start with the Caregiver View

Click the **Caregiver** card (Priya Nair, the green one). This is the most feature-rich view. After logging in, you will land on the main dashboard showing all residents with status cards, risk scores, and the escalation funnel. Notice the Command Center strip at the top showing real-time system status.

Now open the sidebar and navigate to **Residents**. Click on any resident card to expand it. You will see their full health profile, medications, recent events, and sensor data. Click the sparkle icon labeled **AI Health Insights** — this calls Amazon Bedrock in real time and generates a clinical analysis of the resident's health patterns. Wait a few seconds for the AI response to appear.

### Try the AI Features

Navigate to **Care Navigation** in the sidebar. This is a chat interface powered by Amazon Bedrock. Type a question like "What diet should Kamala follow for her diabetes?" or "Is it safe for Kamala to take aspirin with her current medications?" The AI responds with patient-aware, culturally appropriate guidance using knowledge of the resident's health profile. Every response includes a medical disclaimer.

Next, go to **Prescriptions**. You will see the medication lists for each resident. Click the **Check Interactions** button on any resident. Bedrock will analyze all their medications for drug-drug interactions, food-drug warnings, and suggest generic alternatives from the Indian government's PMBJP program with cost savings.

### Generate Clinical Documents

If you log in as the **Doctor** persona (Dr. Rajesh Menon, the blue card), navigate to **Clinical Docs**. Select a resident, choose a document type (SOAP Note, Discharge Summary, Care Plan, or Incident Report), and click **Generate**. Amazon Bedrock will create a comprehensive clinical document in 3 to 5 seconds, complete with subjective findings, objective data, assessment, and plan — all derived from the resident's actual event and sensor data.

### Simulate Live Events

Look for the lightning bolt icon in the bottom-left of the sidebar — this opens the **Demo Panel**. From here, you can trigger live scenarios: simulate a fall, medication miss, vital alert, or choking event. After triggering an event, navigate to the **Timeline** or **Alerts** page to watch it appear in real-time. The event flows through DynamoDB and appears on the dashboard within seconds.

### Explore Fleet Operations

Log in as the **Ops / B2B** persona (Anand Kulkarni, the amber card). Navigate to **Fleet Ops** to see the fleet management view — edge gateway status, site health metrics, caregiver workload distribution, and sensor health across all monitored homes. This is the view a clinic operations manager would use to oversee 50 to 100 homes at once.

Also check the **Family Portal** (available under the Ops view) to see what a remote family caregiver sees — a simplified status dashboard with medication adherence, recent events, and the ability to communicate.

### Check the Analytics

Navigate to **Analytics** from any role. This page shows deep operational metrics: event distribution by type and severity, response time trends, false positive rates, sensor health, and AI model confidence tracking. Toggle between 7-day, 14-day, 30-day, and 90-day views to see how trends evolve.

---

## The AI — What Amazon Bedrock Does

AETHER uses Amazon Bedrock with the Nova Lite model for five distinct AI capabilities. First, the Care Navigation Agent answers health questions in natural language with patient context, grounded in medical knowledge and filtered through safety guardrails. Second, the Polypharmacy Checker analyzes medication lists for drug-drug interactions, food-drug warnings, and suggests cheaper generic alternatives. Third, the Clinical Document Generator creates SOAP notes, discharge summaries, and care plans from real patient data. Fourth, the Health Insights Engine analyzes patterns across sensor data to detect drift — gradual health decline that is invisible to periodic checkups but clear in continuous monitoring. Fifth, the Voice Companion generates warm, contextual responses for elderly residents in their preferred language using Amazon Polly for text-to-speech.

Beyond Bedrock, AETHER uses six Step Functions for workflow orchestration (medication adherence, fall detection, prescription processing, choking triage, daily wellness, and health decline prediction), eight Lambda functions for event processing, and DynamoDB with five tables for the complete data model.

---

## AWS Services Used

The platform runs on over 10 AWS services. Amazon Bedrock provides all generative AI capabilities. DynamoDB stores events, timeline entries, resident profiles, consent records, and clinic operations data across five tables. Lambda handles event processing, analytics, care navigation, document generation, and polypharmacy analysis. Step Functions orchestrate complex multi-step workflows. IoT Core handles edge device communication. Cognito manages authentication with four role-based groups. S3 stores clinical documents. CloudWatch provides monitoring and logging. Polly generates speech for the voice companion. CDK defines the entire infrastructure as code across four stacks. ECS Fargate hosts the production deployment.

---

## Technical Highlights

The codebase is approximately 40,000 lines of production-quality code. The React dashboard has zero TypeScript compilation errors. The data pipeline is fully live — DynamoDB to FastAPI to React with no mocks in demo mode. The edge system is designed for offline-first operation with a Raspberry Pi 5 and ESP32 sensor mesh. The CDK infrastructure is fully reproducible. The dashboard is a PWA installable on any mobile device with responsive design and safe area support for notched phones.

---

## Market Opportunity

The global elderly care market is projected to reach 1.32 trillion dollars by 2030. Remote patient monitoring alone will be a 175 billion dollar market by 2028. India's elderly population will reach 194 million by 2030. The average cost of a single fall hospitalization is 35,000 dollars in the US, and medication non-adherence costs the US healthcare system over 300 billion dollars annually. AETHER's approach of early detection through continuous ambient monitoring can reduce cost-per-incident by an estimated 60 percent through automated coordination and faster response.

---

## Why AETHER Wins

Unlike competitors, AETHER is privacy-first — no cameras, no raw audio leaves the home. It uses multi-sensor fusion instead of relying on a single device. It has generative AI clinical reasoning that no competitor offers. It provides four distinct persona dashboards instead of a one-size-fits-all interface. It operates in a hybrid edge-plus-cloud architecture that works offline for safety-critical features. And it is built on an open, extensible architecture rather than a proprietary black box.

---

*Built on AWS for the GenAI Hackathon — March 2026*
