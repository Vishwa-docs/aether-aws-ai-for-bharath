# Implementation Plan: AETHER Elderly Care System

## Overview

This implementation plan breaks down the AETHER MVP into discrete coding tasks following the 2-week hackathon timeline. The MVP focuses on demonstrating core safety features: fall detection with multi-sensor fusion, voice-first interaction, acoustic event detection, emergency escalation, and privacy-preserving edge processing.

The implementation uses Python for AWS Lambda functions and edge processing, TypeScript for data models and API contracts, and React Native for the mobile app. All tasks build incrementally toward a working end-to-end demo.

## Tasks

### Phase 1: Project Setup and Infrastructure (Days 1-2)

- [ ] 1. Set up AWS infrastructure and project repositories
  - [ ] 1.1 Create AWS account and configure IAM roles for services
    - Create IAM roles for Lambda, IoT Core, Step Functions with least-privilege policies
    - Configure KMS keys for encryption
    - Set up CloudWatch log groups
    - _Requirements: 73.1, 73.2, 73.3, 73.4_
  
  - [ ] 1.2 Create DynamoDB tables with indexes
    - Create `aether-events` table with GSIs (event-type-index, resident-index, severity-index)
    - Create `aether-timeline` table
    - Create `aether-residents` table with home-index GSI
    - Create `aether-consent` table
    - Enable point-in-time recovery and TTL
    - _Requirements: 86.1, 86.2, 86.3, 86.4_
  
  - [ ] 1.3 Create S3 buckets with lifecycle policies
    - Create evidence packets bucket with 30-day Glacier transition
    - Create model artifacts bucket with versioning
    - Configure bucket policies and encryption
    - _Requirements: 73.5, 73.6_
  
  - [ ] 1.4 Set up AWS IoT Core for device management
    - Create IoT thing types and thing groups
    - Configure IoT Core rules for event routing to Lambda
    - Set up device certificates and policies
    - _Requirements: 72.1, 72.2, 72.3_
  
  - [ ] 1.5 Initialize project repositories with structure
    - Create `aether-edge` repository (Python) with modules: sensors, fusion, privacy, mqtt
    - Create `aether-cloud` repository (Python) with Lambda functions and IaC
    - Create `aether-mobile` repository (React Native)
    - Create `aether-simulator` repository (Python) for synthetic data
    - Set up .gitignore, README, and basic CI/CD with GitHub Actions
    - _Requirements: 85.6_

- [ ] 2. Define data models and API contracts
  - [ ] 2.1 Create TypeScript interfaces for all data models
    - Define Event, FallEventData, MedicationEventData, AcousticEventData interfaces
    - Define TimelineEntry, ResidentProfile, EvidencePacket interfaces
    - Add JSON schema validation
    - _Requirements: 86.1, 86.2, 86.3, 86.4, 86.5_
  
  - [ ] 2.2 Write property test for data model serialization
    - **Property 1: Event serialization round-trip consistency**
    - **Validates: Requirements 86.1, 86.2**
    - Test that Event objects serialize to JSON and deserialize without data loss
    - Test all event types (fall, medication, acoustic, routine)
  
  - [ ] 2.3 Create OpenAPI specification for REST API
    - Define endpoints: POST /events, GET /timeline/{home_id}, GET /residents/{resident_id}
    - Define request/response schemas with validation rules
    - Document authentication requirements
    - _Requirements: 72.4, 72.5_

### Phase 2: Edge Gateway and Sensor Simulation (Days 3-4)

- [ ] 3. Implement sensor simulators for testing
  - [ ] 3.1 Create IMU sensor simulator
    - Generate realistic accelerometer/gyroscope data for normal activity
    - Generate fall patterns (impact, orientation change, immobility)
    - Use SisFall dataset patterns for validation
    - _Requirements: 1.1, 1.2, 1.3, 85.3_
  
  - [ ] 3.2 Create acoustic event simulator
    - Generate MFCC features for scream, glass break, impact, silence events
    - Simulate background noise and normal household sounds
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ] 3.3 Create pose estimation simulator
    - Generate 17-point skeleton keypoints for normal movement
    - Generate fall sequences (standing → falling → ground)
    - _Requirements: 1.4, 1.5_
  
  - [ ] 3.4 Create medication event simulator
    - Simulate NFC tag scans with timestamps
    - Generate adherence and non-adherence patterns
    - _Requirements: 10.1, 10.2, 10.3_

- [ ] 4. Build Edge Gateway core processing
  - [ ] 4.1 Implement MQTT broker and sensor communication
    - Set up local Mosquitto MQTT broker on Edge Gateway
    - Implement MQTT client for receiving sensor data
    - Add message validation and error handling
    - _Requirements: 72.1, 72.2_
  
  - [ ] 4.2 Implement privacy filtering layer
    - Extract MFCC features from audio (no raw audio transmission)
    - Extract pose keypoints from video (no frame storage)
    - Filter IMU data to acceleration patterns only
    - _Requirements: 68.1, 68.2, 68.3, 68.4, 68.5_
  
  - [ ] 4.3 Write property test for privacy preservation
    - **Property 3: Privacy preservation - no raw audio/video in output**
    - **Validates: Requirements 68.1, 68.2, 68.3**
    - Test that privacy filter never outputs raw audio samples or video frames
    - Test that only features (MFCC, keypoints) are transmitted
  
  - [ ] 4.4 Implement fall detection fusion engine
    - Combine IMU, pose, and acoustic signals with confidence scoring
    - Implement weighted fusion algorithm (IMU: 0.4, Pose: 0.4, Acoustic: 0.2)
    - Add confidence thresholds (0.90 for immediate alert, 0.70 for monitoring)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  
  - [ ] 4.5 Write property test for fall detection fusion
    - **Property 4: Confidence-based escalation correctness**
    - **Validates: Requirements 1.6, 1.7**
    - Test that confidence >= 0.90 triggers immediate escalation
    - Test that confidence 0.70-0.89 triggers monitoring mode
    - Test that confidence < 0.70 logs but doesn't escalate
  
  - [ ] 4.6 Implement local event queue for offline resilience
    - Create SQLite database for event storage
    - Implement queue with retry logic and exponential backoff
    - Add connectivity monitoring and automatic sync when online
    - _Requirements: 69.1, 69.2, 69.3, 69.4, 69.5_
  
  - [ ] 4.7 Write property test for offline event queue
    - **Property 5: Offline event queue preserves order**
    - **Validates: Requirements 69.1, 69.2**
    - Test that events queued offline are transmitted in correct order when online
    - Test that no events are lost during connectivity transitions

- [ ] 5. Checkpoint - Test edge gateway with simulated sensors
  - Ensure all tests pass, verify multi-sensor fusion produces correct confidence scores, ask the user if questions arise.

### Phase 3: Cloud Backend and Event Processing (Days 5-7)

- [ ] 6. Implement AWS Lambda event processing functions
  - [ ] 6.1 Create event-processor Lambda function
    - Parse incoming MQTT events from IoT Core
    - Validate event schema and extract metadata
    - Generate triage card using AWS Bedrock (Nemotron model)
    - Store event in DynamoDB with TTL
    - Store evidence packet in S3
    - _Requirements: 86.1, 86.2, 86.3, 86.4, 86.5, 86.6_
  
  - [ ] 6.2 Create escalation-handler Lambda function
    - Implement escalation ladder logic (local siren → caregiver → nurse → 911)
    - Send notifications via SNS (SMS) and SES (email)
    - Track escalation state in DynamoDB
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_
  
  - [ ] 6.3 Write property test for escalation ladder
    - **Property 6: Escalation ladder progression**
    - **Validates: Requirements 15.1, 15.2, 15.3**
    - Test that escalation progresses through tiers if not acknowledged
    - Test that acknowledgment stops escalation
    - Test that critical events skip to appropriate tier
  
  - [ ] 6.4 Create timeline-aggregator Lambda function
    - Aggregate events into daily timeline summaries
    - Generate daily metrics (fall count, medication adherence, activity level)
    - Store timeline in DynamoDB
    - _Requirements: 86.3, 86.4_
  
  - [ ] 6.5 Implement AWS Bedrock integration with Guardrails
    - Configure Bedrock client with Nemotron model
    - Set up Guardrails for content filtering (no medical diagnosis, no unsafe advice)
    - Implement prompt templates for triage card generation
    - Add error handling and fallback responses
    - _Requirements: 50.1, 50.2, 50.3, 50.4, 50.5, 50.6_
  
  - [ ] 6.6 Write property test for LLM safety guardrails
    - **Property 7: LLM safety - no medical diagnosis in output**
    - **Validates: Requirements 50.1, 50.2, 50.3**
    - Test that LLM never provides medical diagnosis
    - Test that adversarial prompts are rejected
    - Test that output contains appropriate disclaimers

- [ ] 7. Implement AWS Step Functions for workflow orchestration
  - [ ] 7.1 Create fall detection workflow state machine
    - Define states: DetectFall → GenerateTriage → Escalate → NotifyCaregiver
    - Add error handling and retry logic
    - Implement timeout handling (20-second SLA for notifications)
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 85.1_
  
  - [ ] 7.2 Create medication adherence workflow
    - Define states: DetectMedEvent → CheckAdherence → NotifyIfMissed
    - Implement scheduled checks for missed medications
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 8. Set up API Gateway for client access
  - [ ] 8.1 Create REST API with endpoints
    - POST /events - Submit event from Edge Gateway
    - GET /timeline/{home_id} - Retrieve timeline
    - GET /residents/{resident_id} - Get resident profile
    - PUT /residents/{resident_id} - Update resident profile
    - POST /alerts/acknowledge - Acknowledge alert
    - _Requirements: 72.4, 72.5_
  
  - [ ] 8.2 Configure API Gateway authentication
    - Set up AWS Cognito user pool for caregivers
    - Configure API Gateway authorizer
    - Add API key authentication for Edge Gateway
    - _Requirements: 73.1, 73.2_
  
  - [ ] 8.3 Write integration tests for API endpoints
    - Test event submission flow
    - Test timeline retrieval with pagination
    - Test authentication and authorization

- [ ] 9. Checkpoint - Test end-to-end event flow
  - Ensure all tests pass, verify events flow from edge to cloud to storage, test escalation ladder, ask the user if questions arise.

### Phase 4: Voice Interaction System (Days 8-9)

- [ ] 10. Implement wake-word detection
  - [ ] 10.1 Integrate Porcupine wake-word engine
    - Set up Porcupine SDK on Edge Gateway
    - Configure wake-word: "Hey Sentinel" or "Hey AETHER"
    - Implement audio streaming from microphone
    - _Requirements: 5.1, 5.2_
  
  - [ ] 10.2 Write property test for wake-word latency
    - **Property 2: Wake word detection latency < 500ms**
    - **Validates: Requirements 5.2**
    - Test that wake-word detection completes within 500ms
    - Test with various background noise levels
  
  - [ ] 10.3 Implement voice activity detection (VAD)
    - Detect start and end of speech after wake-word
    - Buffer audio for ASR processing
    - _Requirements: 5.3_

- [ ] 11. Implement voice command processing
  - [ ] 11.1 Integrate AWS Transcribe for speech recognition
    - Set up Transcribe streaming API
    - Support English and Hindi languages
    - Handle transcription errors and low confidence
    - _Requirements: 5.3, 5.4, 6.1, 6.2_
  
  - [ ] 11.2 Create voice command parser and intent classifier
    - Parse commands: "cancel alert", "I'm okay", "call my son", "what's my medication"
    - Implement intent classification using keyword matching
    - Add fallback to LLM for complex queries
    - _Requirements: 5.5, 5.6, 5.7, 5.8_
  
  - [ ] 11.3 Write property test for voice command cancellation
    - **Property 8: Voice command cancellation within 30 seconds**
    - **Validates: Requirements 5.7**
    - Test that "cancel alert" command stops escalation within 30 seconds
    - Test that cancellation is logged in event timeline
  
  - [ ] 11.4 Integrate AWS Polly for text-to-speech
    - Set up Polly client with neural voices
    - Support English (Joanna) and Hindi (Aditi) voices
    - Implement audio playback on Edge Gateway
    - _Requirements: 5.9, 6.3_
  
  - [ ] 11.5 Implement daily check-in dialogue system
    - Create dialogue flow: greeting → mood → pain → sleep → hydration → summary
    - Generate questions using LLM with personalization
    - Parse responses and extract structured data
    - Store check-in results in DynamoDB
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  
  - [ ] 11.6 Write unit tests for daily check-in dialogue
    - Test dialogue flow progression
    - Test response parsing for mood, pain, sleep, hydration
    - Test error handling for unclear responses

- [ ] 12. Implement care navigation assistant
  - [ ] 12.1 Create knowledge pack with vetted medical content
    - Curate medical knowledge base (common conditions, first aid, when to seek care)
    - Convert to JSON format with embeddings
    - Upload to S3 and configure Bedrock Knowledge Base
    - _Requirements: 52.1, 52.2, 52.3_
  
  - [ ] 12.2 Implement RAG query processing
    - Integrate Amazon Q for care navigation
    - Implement query routing to Bedrock Knowledge Base
    - Add citation tracking for responses
    - _Requirements: 52.4, 52.5, 52.6_
  
  - [ ] 12.3 Write property test for care navigation safety
    - **Property 9: Care navigation never provides diagnosis**
    - **Validates: Requirements 50.1, 52.1**
    - Test that responses contain disclaimers
    - Test that diagnosis-seeking queries are redirected to healthcare provider

- [ ] 13. Checkpoint - Test voice interaction end-to-end
  - Ensure all tests pass, verify wake-word detection, test voice commands, test daily check-in dialogue, ask the user if questions arise.

### Phase 5: Caregiver Mobile App (Days 10-11)

- [ ] 14. Build React Native mobile app foundation
  - [ ] 14.1 Initialize React Native project with navigation
    - Set up React Navigation with stack and tab navigators
    - Create screen structure: Login, Home, Timeline, Alerts, Profile
    - Configure TypeScript and ESLint
    - _Requirements: 85.2_
  
  - [ ] 14.2 Implement authentication with AWS Cognito
    - Create login and registration screens
    - Integrate AWS Amplify for Cognito authentication
    - Implement secure token storage
    - Add biometric authentication (fingerprint/face)
    - _Requirements: 73.1, 73.2_
  
  - [ ] 14.3 Set up push notification infrastructure
    - Configure Firebase Cloud Messaging (FCM) for Android
    - Configure Apple Push Notification Service (APNS) for iOS
    - Integrate with AWS SNS for notification delivery
    - _Requirements: 15.5, 15.6_

- [ ] 15. Implement timeline view and event cards
  - [ ] 15.1 Create timeline screen with event list
    - Fetch timeline data from API Gateway
    - Implement pull-to-refresh and pagination
    - Display events in chronological order with timestamps
    - _Requirements: 86.3, 86.4_
  
  - [ ] 15.2 Create event card components
    - Design cards for fall events, medication events, acoustic events
    - Show confidence scores, severity, and evidence
    - Add expand/collapse for detailed view
    - _Requirements: 86.1, 86.2_
  
  - [ ] 15.3 Implement evidence packet viewer
    - Display sensor data visualizations (IMU graphs, pose keypoints)
    - Show AI-generated triage card
    - Add download option for evidence packets
    - _Requirements: 86.5, 86.6_

- [ ] 16. Implement alert notification and response system
  - [ ] 16.1 Create alert notification handler
    - Display high-priority notifications with sound and vibration
    - Show alert details with resident name, event type, confidence
    - Implement notification tap to open alert details
    - _Requirements: 15.5, 15.6_
  
  - [ ] 16.2 Create alert response screen
    - Add "Acknowledge" button to confirm alert received
    - Add "Respond" button to indicate caregiver is responding
    - Add "False Alarm" button to dismiss
    - Send acknowledgment to backend via API
    - _Requirements: 15.3, 15.4_
  
  - [ ] 16.3 Write integration tests for alert flow
    - Test notification delivery and display
    - Test acknowledgment submission
    - Test alert state updates in timeline

- [ ] 17. Implement resident profile management
  - [ ] 17.1 Create resident profile screen
    - Display resident information (name, age, conditions, medications)
    - Show baseline metrics and recent trends
    - _Requirements: 86.4_
  
  - [ ] 17.2 Implement profile editing
    - Add forms for updating medications, emergency contacts
    - Validate input and submit updates to API
    - _Requirements: 86.4_

- [ ] 18. Checkpoint - Test mobile app with backend
  - Ensure all tests pass, verify authentication, test timeline display, test alert notifications, ask the user if questions arise.

### Phase 6: LLM Safety and Integration Testing (Days 12-13)

- [ ] 19. Implement LLM safety layer with red-team testing
  - [ ] 19.1 Configure AWS Bedrock Guardrails
    - Set up content filters: hate speech, violence, sexual content, profanity
    - Configure topic filters: medical diagnosis, legal advice, financial advice
    - Set up PII redaction for sensitive data
    - _Requirements: 50.1, 50.2, 50.3, 50.4_
  
  - [ ] 19.2 Create red-team test harness
    - Compile adversarial prompts (jailbreak attempts, prompt injection, diagnosis requests)
    - Implement automated testing against LLM endpoints
    - Log all failures for analysis
    - _Requirements: 50.5, 50.6_
  
  - [ ] 19.3 Write property test for LLM refusal behavior
    - **Property 10: LLM refuses unsafe requests**
    - **Validates: Requirements 50.1, 50.2, 50.3**
    - Test that diagnosis requests are refused
    - Test that jailbreak attempts are detected
    - Test that refusals include helpful alternative suggestions
  
  - [ ] 19.4 Implement audit logging for LLM interactions
    - Log all LLM queries with timestamps, user context, and responses
    - Store logs in CloudWatch with structured JSON
    - Add alerting for suspicious patterns
    - _Requirements: 50.6, 73.7_

- [ ] 20. Implement acoustic event detection
  - [ ] 20.1 Create acoustic event classifier
    - Implement MFCC feature extraction
    - Train or load pre-trained classifier for scream, glass break, impact, silence
    - Add confidence thresholding
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ] 20.2 Write property test for acoustic event thresholds
    - **Property 11: Acoustic event detection thresholds**
    - **Validates: Requirements 7.1, 7.2, 7.3**
    - Test that scream detection triggers at correct dB threshold
    - Test that silence detection triggers after 4+ hours
    - Test that glass break detection has low false positive rate

- [ ] 21. Implement medication adherence tracking
  - [ ] 21.1 Create medication schedule manager
    - Store medication schedules in DynamoDB
    - Implement scheduled reminders via voice prompts
    - Track adherence events (taken, missed, late)
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  
  - [ ] 21.2 Implement voice confirmation for medication
    - Prompt: "Did you take your [medication name]?"
    - Parse yes/no responses
    - Log confirmation in timeline
    - _Requirements: 10.5, 10.6_
  
  - [ ] 21.3 Write property test for medication adherence
    - **Property 12: Medication adherence tracking accuracy**
    - **Validates: Requirements 10.1, 10.2, 10.3**
    - Test that missed medications trigger alerts
    - Test that adherence percentage is calculated correctly

- [ ] 22. End-to-end integration testing
  - [ ] 22.1 Create integration test suite
    - Test fall detection → escalation → mobile notification flow
    - Test voice command → LLM processing → response flow
    - Test offline event queue → sync when online flow
    - _Requirements: 85.7_
  
  - [ ] 22.2 Write property test for end-to-end latency
    - **Property 13: Alert delivery latency < 20 seconds**
    - **Validates: Requirements 15.1, 85.2**
    - Test that fall detection to mobile notification completes within 20 seconds
    - Test across different network conditions
  
  - [ ] 22.3 Performance testing and optimization
    - Load test API Gateway with 100 concurrent requests
    - Test Lambda cold start times and optimize
    - Test DynamoDB query performance with large datasets
    - _Requirements: 72.6, 72.7_

- [ ] 23. Checkpoint - Verify all integration tests pass
  - Ensure all tests pass, verify end-to-end flows work correctly, test performance under load, ask the user if questions arise.

### Phase 7: Demo Preparation and Documentation (Day 14)

- [ ] 24. Create demo scenarios and synthetic data
  - [ ] 24.1 Implement Digital Twin simulator
    - Generate 24 hours of synthetic sensor data
    - Include normal activities and 2-3 fall events
    - Include medication events and daily check-ins
    - _Requirements: 85.3, 85.4_
  
  - [ ] 24.2 Create demo script with scenarios
    - Scenario 1: Fall detection with multi-sensor fusion
    - Scenario 2: Voice command to cancel false alarm
    - Scenario 3: Daily check-in dialogue
    - Scenario 4: Care navigation query
    - Scenario 5: Offline event queue and sync
    - _Requirements: 85.7_

- [ ] 25. Deploy to demo environment
  - [ ] 25.1 Deploy Edge Gateway to Raspberry Pi 5 or Jetson Orin Nano
    - Install dependencies and configure services
    - Set up systemd services for auto-start
    - Test connectivity to AWS IoT Core
    - _Requirements: 85.6_
  
  - [ ] 25.2 Deploy Lambda functions to AWS
    - Package Lambda functions with dependencies
    - Deploy using AWS SAM or Terraform
    - Configure environment variables and permissions
    - _Requirements: 85.6_
  
  - [ ] 25.3 Deploy mobile app to test devices
    - Build iOS and Android APKs
    - Install on test devices
    - Configure push notifications
    - _Requirements: 85.6_

- [ ] 26. Create documentation and demo materials
  - [ ] 26.1 Write setup and deployment guide
    - Document AWS account setup steps
    - Document Edge Gateway installation
    - Document mobile app installation
    - _Requirements: 85.6_
  
  - [ ] 26.2 Create architecture diagram and system overview
    - Diagram showing edge, cloud, and mobile components
    - Data flow diagrams for key scenarios
    - _Requirements: 85.7_
  
  - [ ] 26.3 Record demo video
    - 5-minute video showing all key features
    - Narrate architecture and design decisions
    - Show live demo of fall detection and response
    - _Requirements: 85.7_

- [ ] 27. Final testing and bug fixes
  - [ ] 27.1 Execute full demo rehearsal
    - Run through all demo scenarios
    - Identify and fix any issues
    - _Requirements: 85.7_
  
  - [ ] 27.2 Final bug fixes and polish
    - Fix any critical bugs discovered during rehearsal
    - Improve error messages and user feedback
    - _Requirements: 85.7_

- [ ] 28. Final checkpoint - Demo ready
  - Ensure all demo scenarios work reliably, verify documentation is complete, confirm deployment is stable, ready for presentation.

## Notes

- Tasks marked with `*` are optional property-based tests and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability (e.g., _Requirements: 1.1, 1.2_)
- Checkpoints ensure incremental validation and provide opportunities for user feedback
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation follows the 2-week timeline from the design document
- Focus is on demonstrating core safety features with working end-to-end flows
- Synthetic data is used throughout (no physical hardware required for MVP)
- Python 3.11 is used for Lambda functions and edge processing
- TypeScript is used for data models and API contracts
- React Native is used for the mobile app

## Success Criteria

The MVP is complete when:
1. Fall detection works with 90% accuracy on simulated data
2. Alerts reach mobile app within 20 seconds of fall detection
3. Voice interaction works for wake-word, commands, and daily check-in
4. Offline event queue preserves events and syncs when connectivity restored
5. LLM safety layer blocks unsafe requests and provides appropriate refusals
6. End-to-end demo runs reliably for all scenarios
7. Documentation and demo video are complete
