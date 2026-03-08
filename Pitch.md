# AETHER — The Story

## Meet Kamala

Kamala Devi is 78 years old. She lives alone in a small apartment in Bangalore. Her daughter Priya lives two hours away and worries constantly. Kamala takes seven medications, has mild diabetes, and fell in the bathroom three months ago. She never told Priya about the fall.

This is not an unusual story. India will have **194 million elderly citizens by 2030**. Globally, an older adult is treated in the ER for a fall **every 11 seconds**. Over **125,000 people die each year** because they did not take their medications correctly. And the cruel irony of existing monitoring solutions — cameras in the bedroom, pendant alarms that go unanswered, noisy clinical systems drowning nurses in false alerts — is that they fail the very people they are trying to protect.

AETHER was built because elderly care is not one problem. It is twelve interconnected problems — falls, medication chaos, silent health decline, caregiver burnout, social isolation, alert fatigue — and they demand a single, intelligent system that ties everything together.

---

## A Day with AETHER

Let us walk through what one day looks like when Kamala's home is equipped with AETHER.

### 6:30 AM — Kamala Wakes Up

A pressure mat under Kamala's mattress detects she has risen. A PIR motion sensor in the hallway confirms she is moving toward the kitchen. A door sensor logs that the bathroom door opened and closed. None of these are cameras. No video is recorded. No audio is streamed. An edge hub — a **Raspberry Pi 5** sitting quietly on a shelf — processes all this sensor data locally using on-device ML models. Only structured event labels are sent to the cloud through **AWS IoT Core**.

This is AETHER's foundational promise: **privacy-first ambient monitoring**. The sensors know *what* is happening without knowing *what it looks like*.

### 7:15 AM — Medications

Kamala opens her smart pillbox. An NFC sensor logs that she took her morning dose — metformin, amlodipine, and atorvastatin. The event is written to **Amazon DynamoDB** and a **Step Function** (medication adherence workflow) checks it against her prescribed schedule. All seven medications are accounted for.

But what if she had missed a dose? The Step Function would trigger a gentle reminder on her tablet first. If no response after 15 minutes, it escalates — Priya gets a push notification. After 30 minutes, the assigned caregiver is alerted. This four-tier escalation is fully automated through **AWS Lambda** and **Step Functions**, and it means nobody falls through the cracks.

### 9:00 AM — The Caregiver's Morning

Two hours away, Priya opens AETHER on her phone. She logs in as a **Caregiver** and sees the dashboard: three residents she oversees (Kamala plus two neighbors in her care circle), each with a risk score, recent events, and status indicators. She taps on Kamala's card and expands it to see her full health profile — vitals, medications, last 24 hours of activity, sensor data.

She notices Kamala's sleep quality has been declining over the past week. She clicks the sparkle icon — **AI Health Insights** — and within seconds, **Amazon Bedrock** (running the Nova Lite model) analyzes Kamala's sensor data and generates a clinical summary: *"Sleep duration has decreased from 7.2 to 5.1 hours over the past 8 days. Nighttime bathroom visits have increased from 1 to 3. Possible UTI or medication side-effect. Recommend clinical review."*

This is not a canned response. Bedrock is reading Kamala's actual event data from DynamoDB and reasoning over it in real time.

### 10:00 AM — A Question for the AI

Priya wants advice. She navigates to **Care Navigation** — a chat interface — and types: *"Kamala has been waking up three times at night. Could her amlodipine be causing this?"*

**Amazon Bedrock** responds with patient-aware, contextual guidance. It references Kamala's medication list, notes that amlodipine can cause nocturia as a side effect, suggests discussing a dosage adjustment with her doctor, and includes a medical disclaimer. The AI is not a search engine pasting generic answers — it has Kamala's full context.

### 11:30 AM — Checking for Drug Interactions

Priya remembers that Kamala recently started taking an over-the-counter antacid. She goes to **Prescriptions** and clicks **Check Interactions**. Bedrock runs a **polypharmacy analysis** across all seven medications plus the new antacid. It flags that antacids can reduce absorption of amlodipine if taken together, recommends spacing them two hours apart, and additionally surfaces **generic alternatives** from the Indian government's PMBJP (Pradhan Mantri Bhartiya Janaushadhi Pariyojana) program — showing that Kamala could save Rs. 340 per month by switching to Jan Aushadhi branded equivalents.

### 2:00 PM — The Doctor's View

Dr. Rajesh Menon logs in as a **Doctor**. He selects Kamala and navigates to **Clinical Docs**. He chooses "SOAP Note" and clicks **Generate**. In three seconds, **Amazon Bedrock** produces a full clinical document — Subjective complaints derived from recent events, Objective data from sensor readings, Assessment based on pattern analysis, and a recommended Plan. All of it sourced from Kamala's real data in DynamoDB. No typing, no templates — just AI-generated clinical documentation grounded in actual patient data.

### 4:45 PM — Something Goes Wrong

Kamala stumbles in the kitchen. The accelerometer on her wearable detects a sudden impact followed by stillness. The edge hub's **TensorFlow Lite model** classifies this as a probable fall with 94% confidence. It immediately sends a structured event to the cloud.

A **Step Function** (fall detection workflow) kicks in. DynamoDB records the event. A **Lambda function** triggers the escalation chain — Kamala's tablet sounds an alert asking if she is okay. She does not respond within 60 seconds. Priya's phone rings. The caregiver's dashboard turns red. If no one acknowledges within 5 minutes, emergency services are contacted automatically.

On the dashboard, the fall appears instantly in the **Timeline** and **Alerts** views. The entire response — from impact to first human notification — took 8 seconds.

### 7:00 PM — The Voice Companion

It is evening. Kamala is fine — the fall was minor, just a stumble. But she is feeling lonely. She talks to AETHER's **Voice Companion** on her tablet. The AI responds warmly, asks about her day, reminds her to drink water, and gently asks about her mood. Behind the scenes, **Amazon Bedrock** generates the conversational response and **Amazon Polly** converts it to natural speech in her preferred language. The system also runs quiet **sentiment analysis** on her responses, tracking mood trends over time.

### 9:00 PM — Operations at Scale

Meanwhile, at the clinic that manages sensor deployments across 50 homes, Anand from the Ops team logs into the **Operations** dashboard. He sees a fleet management view — every edge gateway's connection status, battery levels, sensor health, firmware versions, and caregiver workload distribution. One hub in another home has been offline for 3 hours. He flags it for a field visit. This is the B2B side of AETHER — the tooling that makes it possible to scale ambient care from 3 homes to 300.

---

## What Powers All of This

Every feature described above runs on real AWS services. Nothing is mocked.

- **Amazon Bedrock** (Nova Lite) powers all five AI capabilities — care navigation, polypharmacy checks, clinical docs, health insights, and voice companion
- **DynamoDB** stores everything — events, timelines, resident profiles, consent, and clinic operations across five tables
- **Lambda** (8 functions) handles event processing, analytics, and AI orchestration
- **Step Functions** (6 workflows) automate medication adherence, fall response, prescription processing, choking triage, daily wellness checks, and health decline prediction
- **IoT Core** connects edge devices to the cloud securely
- **Cognito** manages authentication with four role-based groups (Elder, Caregiver, Doctor, Ops)
- **Polly** provides text-to-speech for the voice companion
- **S3** stores clinical documents
- **CDK** defines the entire infrastructure as code (4 stacks)
- **ECS Fargate** hosts the live production deployment
- **CloudWatch** provides monitoring and logging

The codebase is approximately **40,000 lines** of production-quality code. The React dashboard compiles with **zero TypeScript errors**. The data pipeline is fully live — DynamoDB to FastAPI to React — with no mocked responses in demo mode.

---

## Why AETHER is Different

AETHER does not put cameras in bedrooms. It does not rely on a single wearable that elderly users forget to charge. It does not flood caregivers with false alarms. Instead, it fuses data from ten sensor types at the edge, processes it locally for privacy, sends only meaningful events to the cloud, and lets generative AI do the clinical reasoning that no rule-based system can match. It gives four different people — the elder, the family caregiver, the doctor, and the operations manager — four different views of the same patient, each designed for their workflow. And it works offline for safety-critical features because an internet outage should never mean a fall goes undetected.

---

*Built on AWS for the GenAI Hackathon — March 2026*
