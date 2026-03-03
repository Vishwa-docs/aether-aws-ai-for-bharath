/**
 * AETHER Demo Data Service
 * Generates realistic mock data simulating a live elderly care monitoring system.
 * Designed for investor pitch demos — all data is crafted to look convincing and professional.
 */

import type {
  AetherEvent,
  AlertNotification,
  AnalyticsData,
  CalendarEvent,
  CaregiverWorkload,
  CareHandoff,
  CareNavigationQuery,
  ClinicalDocument,
  CommandCenterData,
  ConsentSettings,
  DailyMetrics,
  DailyTrend,
  DashboardStats,
  EdgeGateway,
  EscalationFunnel,
  EscalationTier,
  EventType,
  FalsePositiveRate,
  HealthProfile,
  MedicationConfusionLoop,
  MedicationTrend,
  MicroLesson,
  ModelConfidenceDrift,
  Prescription,
  Resident,
  RespiratoryMetrics,
  ResponseTimeData,
  RiskTrendPoint,
  SensorHealth,
  SensorType,
  ServiceBooking,
  Severity,
  SiteHealth,
  SleepMetrics,
  TimelineEntry,
  User,
} from '../types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function uuid(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

function pick<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function randBetween(min: number, max: number): number {
  return Math.random() * (max - min) + min;
}

function randInt(min: number, max: number): number {
  return Math.floor(randBetween(min, max + 1));
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function dateStr(ts: number): string {
  const d = new Date(ts);
  return d.toISOString().slice(0, 10);
}

function setHour(base: number, hour: number, jitterMin = 30): number {
  const d = new Date(base);
  d.setHours(hour, randInt(0, jitterMin), randInt(0, 59), 0);
  return d.getTime();
}

function daysAgo(n: number): number {
  return Date.now() - n * 24 * 60 * 60 * 1000;
}

function hoursAgo(n: number): number {
  return Date.now() - n * 60 * 60 * 1000;
}

function minutesAgo(n: number): number {
  return Date.now() - n * 60 * 1000;
}

// ─── 0. Demo Users ───────────────────────────────────────────────────────────

export const DEMO_USERS: User[] = [
  {
    id: 'user-elder-001',
    name: 'Margaret Sharma',
    email: 'margaret.sharma@aether.care',
    role: 'elder',
    phone: '+91-98100-45000',
    assignedResidents: ['res-a1b2c3d4'],
  },
  {
    id: 'user-cg-001',
    name: 'Priya Nair',
    email: 'priya.nair@aether.care',
    role: 'caregiver',
    phone: '+91-98765-11111',
    assignedResidents: ['res-a1b2c3d4', 'res-e5f6g7h8', 'res-i9j0k1l2', 'res-m3n4o5p6'],
  },
  {
    id: 'user-doc-001',
    name: 'Dr. Rajesh Menon',
    email: 'rajesh.menon@aether.care',
    role: 'doctor',
    phone: '+91-99000-22222',
    specialization: 'Geriatric Medicine',
    assignedResidents: ['res-a1b2c3d4', 'res-e5f6g7h8', 'res-i9j0k1l2', 'res-m3n4o5p6'],
  },
  {
    id: 'user-ops-001',
    name: 'Anand Kulkarni',
    email: 'anand.kulkarni@aether.care',
    role: 'ops',
    phone: '+91-98450-33333',
    sites: ['site-mumbai', 'site-delhi', 'site-bangalore', 'site-chennai'],
  },
];

// ─── 1. Residents ─────────────────────────────────────────────────────────────

export const RESIDENTS: Resident[] = [
  {
    resident_id: 'res-a1b2c3d4',
    home_id: 'home-001',
    name: 'Margaret Sharma',
    age: 78,
    photo_url: undefined,
    conditions: ['Type 2 Diabetes', 'Mild Hypertension'],
    medications: [
      { name: 'Metformin', dosage: '500 mg', schedule: ['08:00', '20:00'], nfc_tag_id: 'nfc-met-001' },
      { name: 'Amlodipine', dosage: '5 mg', schedule: ['08:00'], nfc_tag_id: 'nfc-aml-001' },
      { name: 'Aspirin', dosage: '75 mg', schedule: ['14:00'], nfc_tag_id: 'nfc-asp-001' },
    ],
    emergency_contacts: [
      { name: 'Vikram Sharma', relationship: 'Son', phone: '+91-98100-45678', is_primary: true },
      { name: 'Priya Sharma', relationship: 'Daughter-in-law', phone: '+91-98100-45679', is_primary: false },
      { name: 'Anita Deshmukh', relationship: 'Neighbour', phone: '+91-98100-99012', is_primary: false },
    ],
    privacy_level: 'standard',
    status: 'active',
    last_activity: Date.now() - 12 * 60 * 1000,
    risk_score: 0.35,
  },
  {
    resident_id: 'res-e5f6g7h8',
    home_id: 'home-002',
    name: 'Rajesh Patel',
    age: 82,
    photo_url: undefined,
    conditions: ['Osteoarthritis', 'COPD'],
    medications: [
      { name: 'Tiotropium Inhaler', dosage: '18 mcg', schedule: ['08:00'], nfc_tag_id: 'nfc-tio-002' },
      { name: 'Diclofenac', dosage: '50 mg', schedule: ['08:00', '20:00'], nfc_tag_id: 'nfc-dic-002' },
      { name: 'Pantoprazole', dosage: '40 mg', schedule: ['08:00'], nfc_tag_id: 'nfc-pan-002' },
      { name: 'Salbutamol Inhaler', dosage: '100 mcg PRN', schedule: ['08:00', '14:00', '20:00'], nfc_tag_id: 'nfc-sal-002' },
    ],
    emergency_contacts: [
      { name: 'Meena Patel', relationship: 'Daughter', phone: '+91-99200-12345', is_primary: true },
      { name: 'Amit Patel', relationship: 'Son', phone: '+91-99200-12346', is_primary: false },
      { name: 'Sunil Joshi', relationship: 'Neighbour', phone: '+91-99200-67890', is_primary: false },
    ],
    privacy_level: 'standard',
    status: 'active',
    last_activity: Date.now() - 45 * 60 * 1000,
    risk_score: 0.52,
  },
  {
    resident_id: 'res-i9j0k1l2',
    home_id: 'home-003',
    name: 'Lakshmi Iyer',
    age: 75,
    photo_url: undefined,
    conditions: ['Atrial Fibrillation', 'Osteoporosis'],
    medications: [
      { name: 'Warfarin', dosage: '2 mg', schedule: ['20:00'], nfc_tag_id: 'nfc-war-003' },
      { name: 'Calcium + Vitamin D3', dosage: '500 mg / 250 IU', schedule: ['08:00', '20:00'], nfc_tag_id: 'nfc-cal-003' },
      { name: 'Atenolol', dosage: '25 mg', schedule: ['08:00'], nfc_tag_id: 'nfc-ate-003' },
    ],
    emergency_contacts: [
      { name: 'Srinivas Iyer', relationship: 'Son', phone: '+91-94440-23456', is_primary: true },
      { name: 'Deepa Iyer', relationship: 'Daughter', phone: '+91-94440-23457', is_primary: false },
      { name: 'Kamala Rao', relationship: 'Neighbour', phone: '+91-94440-78901', is_primary: false },
    ],
    privacy_level: 'elevated',
    status: 'active',
    last_activity: Date.now() - 5 * 60 * 1000,
    risk_score: 0.28,
  },
  {
    resident_id: 'res-m3n4o5p6',
    home_id: 'home-004',
    name: 'Suresh Kumar',
    age: 80,
    photo_url: undefined,
    conditions: ["Parkinson's Disease", 'Mild Cognitive Impairment'],
    medications: [
      { name: 'Levodopa/Carbidopa', dosage: '100/25 mg', schedule: ['08:00', '14:00', '20:00'], nfc_tag_id: 'nfc-lev-004' },
      { name: 'Pramipexole', dosage: '0.5 mg', schedule: ['08:00', '20:00'], nfc_tag_id: 'nfc-pra-004' },
      { name: 'Donepezil', dosage: '5 mg', schedule: ['20:00'], nfc_tag_id: 'nfc-don-004' },
      { name: 'Amantadine', dosage: '100 mg', schedule: ['08:00', '14:00'], nfc_tag_id: 'nfc-ama-004' },
      { name: 'Melatonin', dosage: '3 mg', schedule: ['21:00'], nfc_tag_id: 'nfc-mel-004' },
    ],
    emergency_contacts: [
      { name: 'Anand Kumar', relationship: 'Son', phone: '+91-98450-34567', is_primary: true },
      { name: 'Kavitha Kumar', relationship: 'Daughter', phone: '+91-98450-34568', is_primary: false },
      { name: 'Ramesh Nair', relationship: 'Neighbour', phone: '+91-98450-89012', is_primary: false },
    ],
    privacy_level: 'elevated',
    status: 'active',
    last_activity: Date.now() - 30 * 60 * 1000,
    risk_score: 0.68,
  },
];

// ─── Event Generation Internals ───────────────────────────────────────────────

interface EventTemplate {
  type: EventType;
  weight: number;
  severity: () => Severity;
  confidence: () => number;
  sensors: SensorType[];
  preferredHours?: number[];
  dataPayload: (resident: Resident) => Record<string, unknown>;
}

const EVENT_TEMPLATES: EventTemplate[] = [
  {
    type: 'medication_taken',
    weight: 30,
    severity: () => 'INFO',
    confidence: () => randBetween(0.95, 0.99),
    sensors: ['medication'],
    preferredHours: [8, 14, 20],
    dataPayload: (r) => {
      const med = pick(r.medications);
      return {
        medication_name: med.name,
        dosage: med.dosage,
        nfc_tag_id: med.nfc_tag_id,
        method: 'nfc_verified',
        deviation_minutes: randInt(0, 15),
      };
    },
  },
  {
    type: 'check_in_completed',
    weight: 25,
    severity: () => 'INFO',
    confidence: () => randBetween(0.97, 1.0),
    sensors: ['pose', 'acoustic'],
    preferredHours: [9, 13, 17, 21],
    dataPayload: () => ({
      check_in_type: pick(['scheduled', 'motion_triggered']),
      activity_detected: pick(['sitting', 'walking', 'standing']),
      room: pick(['living_room', 'bedroom', 'kitchen']),
      mood_estimate: pick(['neutral', 'positive', 'calm']),
    }),
  },
  {
    type: 'medication_missed',
    weight: 5,
    severity: () => pick(['MEDIUM', 'HIGH'] as Severity[]),
    confidence: () => randBetween(0.90, 0.98),
    sensors: ['medication'],
    preferredHours: [9, 15, 21],
    dataPayload: (r) => {
      const med = pick(r.medications);
      return {
        medication_name: med.name,
        dosage: med.dosage,
        scheduled_time: pick(med.schedule),
        grace_period_minutes: 60,
        nfc_tag_id: med.nfc_tag_id,
      };
    },
  },
  {
    type: 'medication_late',
    weight: 8,
    severity: () => 'LOW',
    confidence: () => randBetween(0.92, 0.98),
    sensors: ['medication'],
    preferredHours: [9, 15, 21],
    dataPayload: (r) => {
      const med = pick(r.medications);
      return {
        medication_name: med.name,
        dosage: med.dosage,
        scheduled_time: pick(med.schedule),
        actual_delay_minutes: randInt(15, 55),
        nfc_tag_id: med.nfc_tag_id,
      };
    },
  },
  {
    type: 'routine_anomaly',
    weight: 10,
    severity: () => pick(['LOW', 'MEDIUM'] as Severity[]),
    confidence: () => randBetween(0.65, 0.88),
    sensors: ['pose', 'imu'],
    preferredHours: [6, 7, 22, 23, 0, 1, 2, 3],
    dataPayload: () => ({
      anomaly_type: pick(['unusual_hour_activity', 'prolonged_inactivity', 'sleep_disruption', 'deviation_from_pattern']),
      baseline_pattern: 'Last 14-day average',
      deviation_sigma: +(randBetween(1.5, 3.5).toFixed(1)),
      room: pick(['bedroom', 'bathroom', 'hallway', 'kitchen']),
    }),
  },
  {
    type: 'fall_detected',
    weight: 3,
    severity: () => pick(['HIGH', 'CRITICAL'] as Severity[]),
    confidence: () => randBetween(0.75, 0.98),
    sensors: ['imu', 'pose', 'acoustic'],
    preferredHours: [1, 2, 3, 4, 5, 22, 23],
    dataPayload: () => ({
      impact_magnitude_g: +(randBetween(2.5, 8.0).toFixed(2)),
      fall_type: pick(['forward', 'backward', 'lateral', 'from_chair']),
      room: pick(['bathroom', 'bedroom', 'hallway', 'kitchen']),
      post_fall_motion: pick([true, false]),
      response_verbal: pick([true, false, false]),
      pose_confirmation: true,
    }),
  },
  {
    type: 'acoustic_scream',
    weight: 2,
    severity: () => 'HIGH',
    confidence: () => randBetween(0.60, 0.90),
    sensors: ['acoustic'],
    dataPayload: () => ({
      audio_class: 'scream_distress',
      decibel_level: randInt(70, 95),
      duration_ms: randInt(500, 4000),
      room: pick(['bedroom', 'bathroom', 'living_room']),
      privacy_note: 'Audio not stored — classification only',
    }),
  },
  {
    type: 'acoustic_glass_break',
    weight: 2,
    severity: () => 'MEDIUM',
    confidence: () => randBetween(0.70, 0.92),
    sensors: ['acoustic'],
    dataPayload: () => ({
      audio_class: 'glass_break',
      decibel_level: randInt(65, 90),
      duration_ms: randInt(200, 1500),
      room: pick(['kitchen', 'living_room', 'dining_room']),
      privacy_note: 'Audio not stored — classification only',
    }),
  },
  {
    type: 'acoustic_impact',
    weight: 4,
    severity: () => pick(['LOW', 'MEDIUM'] as Severity[]),
    confidence: () => randBetween(0.60, 0.85),
    sensors: ['acoustic'],
    dataPayload: () => ({
      audio_class: pick(['heavy_thud', 'furniture_impact', 'object_drop']),
      decibel_level: randInt(55, 80),
      duration_ms: randInt(100, 1000),
      room: pick(['bedroom', 'living_room', 'kitchen', 'hallway']),
      privacy_note: 'Audio not stored — classification only',
    }),
  },
  {
    type: 'acoustic_silence',
    weight: 6,
    severity: () => 'LOW',
    confidence: () => randBetween(0.80, 0.95),
    sensors: ['acoustic'],
    preferredHours: [10, 11, 12, 13, 14, 15, 16],
    dataPayload: () => ({
      silence_duration_minutes: randInt(45, 180),
      expected_activity: pick(['daytime_ambient', 'tv_radio', 'conversation']),
      room: pick(['living_room', 'bedroom']),
      threshold_minutes: 60,
    }),
  },
  {
    type: 'vital_alert',
    weight: 5,
    severity: () => pick(['MEDIUM', 'HIGH'] as Severity[]),
    confidence: () => randBetween(0.85, 0.96),
    sensors: ['imu', 'vital'],
    dataPayload: () => {
      const vital = pick(['heart_rate', 'spo2', 'blood_pressure', 'temperature']);
      const vals: Record<string, unknown> = { vital_type: vital };
      switch (vital) {
        case 'heart_rate':
          vals.value = randInt(45, 120);
          vals.unit = 'bpm';
          vals.normal_range = '60–100 bpm';
          break;
        case 'spo2':
          vals.value = randInt(88, 94);
          vals.unit = '%';
          vals.normal_range = '95–100%';
          break;
        case 'blood_pressure':
          vals.systolic = randInt(140, 180);
          vals.diastolic = randInt(60, 100);
          vals.unit = 'mmHg';
          vals.normal_range = '120/80 mmHg';
          break;
        case 'temperature':
          vals.value = +(randBetween(37.5, 39.2).toFixed(1));
          vals.unit = '°C';
          vals.normal_range = '36.1–37.2 °C';
          break;
      }
      return vals;
    },
  },
  // ─── New event templates ──────────────────────────────────────────────
  {
    type: 'environmental_alert',
    weight: 4,
    severity: () => pick(['LOW', 'MEDIUM', 'HIGH'] as Severity[]),
    confidence: () => randBetween(0.80, 0.96),
    sensors: ['environmental', 'temperature', 'humidity', 'air_quality'],
    dataPayload: () => {
      const envType = pick(['high_temperature', 'low_humidity', 'poor_air_quality', 'smoke_detected', 'co_detected']);
      const vals: Record<string, unknown> = { alert_type: envType };
      switch (envType) {
        case 'high_temperature':
          vals.value = randInt(35, 42);
          vals.unit = '°C';
          vals.threshold = 34;
          vals.room = pick(['bedroom', 'living_room']);
          break;
        case 'low_humidity':
          vals.value = randInt(15, 25);
          vals.unit = '%';
          vals.threshold = 30;
          vals.room = pick(['bedroom', 'living_room']);
          break;
        case 'poor_air_quality':
          vals.aqi = randInt(150, 300);
          vals.pm25 = randInt(80, 200);
          vals.room = pick(['living_room', 'kitchen']);
          break;
        case 'smoke_detected':
          vals.concentration_ppm = randInt(50, 200);
          vals.room = 'kitchen';
          break;
        case 'co_detected':
          vals.concentration_ppm = randInt(30, 80);
          vals.room = pick(['kitchen', 'bedroom']);
          break;
      }
      return vals;
    },
  },
  {
    type: 'cognitive_decline',
    weight: 2,
    severity: () => pick(['LOW', 'MEDIUM'] as Severity[]),
    confidence: () => randBetween(0.55, 0.82),
    sensors: ['pose', 'acoustic'],
    dataPayload: () => ({
      indicator: pick(['repeated_question', 'confusion_at_door', 'wandering', 'missed_routine_steps', 'disorientation']),
      frequency_increase_pct: randInt(15, 60),
      baseline_period: '30 days',
      room: pick(['living_room', 'hallway', 'kitchen']),
    }),
  },
  {
    type: 'nutrition_concern',
    weight: 3,
    severity: () => pick(['LOW', 'MEDIUM'] as Severity[]),
    confidence: () => randBetween(0.70, 0.90),
    sensors: ['pose', 'environmental'],
    preferredHours: [7, 8, 12, 13, 19, 20],
    dataPayload: () => ({
      concern_type: pick(['skipped_meal', 'reduced_kitchen_activity', 'low_fluid_intake', 'irregular_eating_time']),
      meals_today: randInt(0, 2),
      expected_meals: 3,
      kitchen_visits: randInt(0, 3),
      hydration_events: randInt(1, 5),
    }),
  },
  {
    type: 'scam_alert',
    weight: 1,
    severity: () => 'HIGH',
    confidence: () => randBetween(0.65, 0.88),
    sensors: ['acoustic'],
    dataPayload: () => ({
      call_duration_seconds: randInt(120, 900),
      suspicious_indicators: pick([
        ['urgency_language', 'financial_terms'],
        ['authority_impersonation', 'pressure_tactics'],
        ['unknown_caller_pattern', 'repeated_calls'],
      ]),
      blocked: pick([true, false]),
      privacy_note: 'Content not recorded — pattern analysis only',
    }),
  },
  {
    type: 'emotional_concern',
    weight: 3,
    severity: () => pick(['LOW', 'MEDIUM'] as Severity[]),
    confidence: () => randBetween(0.50, 0.78),
    sensors: ['acoustic', 'pose'],
    dataPayload: () => ({
      indicator: pick(['prolonged_crying', 'social_withdrawal', 'agitation', 'apathy', 'verbal_distress']),
      duration_minutes: randInt(10, 120),
      social_interaction_today: randInt(0, 3),
      baseline_social_avg: 4,
      room: pick(['bedroom', 'living_room']),
    }),
  },
  {
    type: 'bathroom_anomaly',
    weight: 3,
    severity: () => pick(['MEDIUM', 'HIGH'] as Severity[]),
    confidence: () => randBetween(0.72, 0.93),
    sensors: ['toilet', 'pose', 'imu'],
    preferredHours: [0, 1, 2, 3, 4, 5, 22, 23],
    dataPayload: () => ({
      anomaly_type: pick(['prolonged_visit', 'frequent_visits', 'fall_risk_posture', 'no_flush_detected']),
      duration_minutes: randInt(15, 60),
      visits_last_6h: randInt(4, 10),
      baseline_avg_visits_6h: 2,
      time_of_day: pick(['night', 'early_morning']),
    }),
  },
  {
    type: 'choking',
    weight: 1,
    severity: () => 'CRITICAL',
    confidence: () => randBetween(0.70, 0.92),
    sensors: ['acoustic', 'pose'],
    preferredHours: [8, 12, 13, 19, 20],
    dataPayload: () => ({
      audio_class: 'choking_coughing_pattern',
      duration_seconds: randInt(5, 30),
      room: pick(['dining_room', 'kitchen', 'living_room']),
      meal_time: true,
      post_event_breathing: pick(['normal', 'labored', 'unclear']),
      privacy_note: 'Audio not stored — classification only',
    }),
  },
  {
    type: 'gait_degradation',
    weight: 3,
    severity: () => pick(['LOW', 'MEDIUM'] as Severity[]),
    confidence: () => randBetween(0.68, 0.90),
    sensors: ['imu', 'pose'],
    dataPayload: () => ({
      gait_speed_cm_s: randInt(40, 70),
      baseline_speed_cm_s: 85,
      stride_variability_pct: +(randBetween(12, 35).toFixed(1)),
      baseline_variability_pct: 8,
      trend: pick(['declining', 'stable_low']),
      measurement_period: '7 days',
    }),
  },
  {
    type: 'sleep_disruption',
    weight: 4,
    severity: () => pick(['LOW', 'MEDIUM'] as Severity[]),
    confidence: () => randBetween(0.75, 0.92),
    sensors: ['imu', 'pose', 'light'],
    preferredHours: [0, 1, 2, 3, 4, 5],
    dataPayload: () => ({
      disruption_type: pick(['frequent_waking', 'late_sleep_onset', 'early_waking', 'restless_movement']),
      awakenings: randInt(3, 8),
      total_sleep_hours: +(randBetween(3, 5.5).toFixed(1)),
      baseline_sleep_hours: 7,
      sleep_efficiency_pct: randInt(45, 65),
    }),
  },
];

// Build weighted array for selection
const WEIGHTED_TEMPLATES: EventTemplate[] = [];
EVENT_TEMPLATES.forEach((t) => {
  for (let i = 0; i < t.weight; i++) WEIGHTED_TEMPLATES.push(t);
});

// ─── 2. generateEvents ───────────────────────────────────────────────────────

export function generateEvents(count: number, daysBack: number): AetherEvent[] {
  const now = Date.now();
  const start = now - daysBack * 24 * 60 * 60 * 1000;
  const events: AetherEvent[] = [];

  for (let i = 0; i < count; i++) {
    const template = pick(WEIGHTED_TEMPLATES);
    const resident = pick(RESIDENTS);

    // Determine timestamp
    let ts: number;
    if (template.preferredHours && Math.random() < 0.75) {
      // 75 % chance to follow preferred hour pattern
      const day = start + Math.random() * (now - start);
      const hour = pick(template.preferredHours);
      ts = setHour(day, hour);
    } else {
      ts = start + Math.random() * (now - start);
    }
    ts = Math.min(ts, now);

    const isAcknowledged = Math.random() < 0.85 && template.severity() !== 'CRITICAL';
    const ackDelay = randInt(5, 900); // seconds

    const event: AetherEvent = {
      event_id: uuid(),
      home_id: resident.home_id,
      resident_id: resident.resident_id,
      event_type: template.type,
      severity: template.severity(),
      timestamp: ts,
      confidence: +template.confidence().toFixed(3),
      source_sensors: template.sensors,
      privacy_level: resident.privacy_level,
      data: template.dataPayload(resident),
      evidence_packet_id: ['fall_detected', 'acoustic_scream', 'vital_alert', 'choking'].includes(template.type)
        ? `ep-${uuid().slice(0, 8)}`
        : undefined,
    };

    if (isAcknowledged && ts < now - 120_000) {
      event.acknowledged = true;
      event.acknowledged_by = pick(['nurse_priya', 'nurse_arun', 'supervisor_neha', 'system_auto']);
      event.acknowledged_at = ts + ackDelay * 1000;
    }

    events.push(event);
  }

  return events.sort((a, b) => a.timestamp - b.timestamp);
}

// ─── 3. Pre-generated Events ─────────────────────────────────────────────────

export const MOCK_EVENTS: AetherEvent[] = generateEvents(100, 7);

// ─── 4. Dashboard Stats ──────────────────────────────────────────────────────

export const DASHBOARD_STATS: DashboardStats = {
  total_residents: RESIDENTS.length,
  active_alerts: 2,
  events_today: MOCK_EVENTS.filter(
    (e) => dateStr(e.timestamp) === dateStr(Date.now()),
  ).length || 14,
  avg_response_time: 11.4,
  medication_adherence: 91.3,
  system_uptime: 99.97,
  sensors_online: 14,
  sensors_total: 16,
};

// ─── 5. Active Alerts ────────────────────────────────────────────────────────

export function getActiveAlerts(): AlertNotification[] {
  const now = Date.now();

  const alerts: AlertNotification[] = [
    {
      id: uuid(),
      event: {
        event_id: uuid(),
        home_id: 'home-004',
        resident_id: 'res-m3n4o5p6',
        event_type: 'fall_detected',
        severity: 'CRITICAL',
        timestamp: now - 3 * 60 * 1000,
        confidence: 0.92,
        source_sensors: ['imu', 'pose', 'acoustic'],
        privacy_level: 'elevated',
        data: {
          impact_magnitude_g: 5.73,
          fall_type: 'lateral',
          room: 'bathroom',
          post_fall_motion: false,
          response_verbal: false,
          pose_confirmation: true,
        },
        evidence_packet_id: `ep-${uuid().slice(0, 8)}`,
      },
      resident: RESIDENTS[3],
      escalation_tier: 'TIER_3',
      created_at: now - 3 * 60 * 1000,
      is_active: true,
      response_time: undefined,
    },
    {
      id: uuid(),
      event: {
        event_id: uuid(),
        home_id: 'home-002',
        resident_id: 'res-e5f6g7h8',
        event_type: 'medication_missed',
        severity: 'HIGH',
        timestamp: now - 22 * 60 * 1000,
        confidence: 0.97,
        source_sensors: ['medication'],
        privacy_level: 'standard',
        data: {
          medication_name: 'Tiotropium Inhaler',
          dosage: '18 mcg',
          scheduled_time: '08:00',
          grace_period_minutes: 60,
          nfc_tag_id: 'nfc-tio-002',
        },
      },
      resident: RESIDENTS[1],
      escalation_tier: 'TIER_2',
      created_at: now - 22 * 60 * 1000,
      is_active: true,
      response_time: undefined,
    },
    {
      id: uuid(),
      event: {
        event_id: uuid(),
        home_id: 'home-001',
        resident_id: 'res-a1b2c3d4',
        event_type: 'vital_alert',
        severity: 'MEDIUM',
        timestamp: now - 47 * 60 * 1000,
        confidence: 0.89,
        source_sensors: ['vital'],
        privacy_level: 'standard',
        data: {
          vital_type: 'blood_pressure',
          systolic: 158,
          diastolic: 94,
          unit: 'mmHg',
          normal_range: '120/80 mmHg',
        },
        evidence_packet_id: `ep-${uuid().slice(0, 8)}`,
      },
      resident: RESIDENTS[0],
      escalation_tier: 'TIER_1',
      created_at: now - 47 * 60 * 1000,
      is_active: true,
      response_time: 8.2,
    },
  ];

  return alerts;
}

// ─── 6. Daily Trends ─────────────────────────────────────────────────────────

export function getDailyTrends(days: number): DailyTrend[] {
  const trends: DailyTrend[] = [];
  const now = Date.now();

  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now - i * 24 * 60 * 60 * 1000);
    const date = d.toISOString().slice(0, 10);

    const falls = Math.random() < 0.15 ? randInt(1, 2) : 0;
    const medications = randInt(10, 18);
    const acoustic = randInt(1, 6);
    const others = randInt(3, 8);

    trends.push({
      date,
      total_events: falls + medications + acoustic + others,
      falls,
      medications,
      acoustic,
      activity_score: +clamp(randBetween(65, 98), 0, 100).toFixed(1),
    });
  }

  return trends;
}

// ─── 7. Response Times ───────────────────────────────────────────────────────

export function getResponseTimes(days: number): ResponseTimeData[] {
  const data: ResponseTimeData[] = [];
  const now = Date.now();

  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now - i * 24 * 60 * 60 * 1000);
    const date = d.toISOString().slice(0, 10);
    const avg = +randBetween(8, 15).toFixed(1);
    const min = +randBetween(3, avg - 2).toFixed(1);
    const max = +randBetween(avg + 3, 28).toFixed(1);

    data.push({ date, avg_seconds: avg, min_seconds: min, max_seconds: max });
  }

  return data;
}

// ─── 8. Medication Trends ────────────────────────────────────────────────────

export function getMedicationTrends(days: number): MedicationTrend[] {
  const data: MedicationTrend[] = [];
  const now = Date.now();

  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now - i * 24 * 60 * 60 * 1000);
    const date = d.toISOString().slice(0, 10);

    const totalDoses = randInt(14, 20);
    const missed = Math.random() < 0.3 ? randInt(1, 3) : 0;
    const late = Math.random() < 0.4 ? randInt(1, 2) : 0;
    const taken = totalDoses - missed - late;
    const adherence = +((taken / totalDoses) * 100).toFixed(1);

    data.push({
      date,
      adherence_pct: clamp(adherence, 75, 100),
      taken,
      missed,
      late,
    });
  }

  return data;
}

// ─── 9. Sensor Health ────────────────────────────────────────────────────────

const ROOMS = ['living_room', 'bedroom', 'kitchen', 'bathroom', 'hallway'];

function buildSensorsForHome(homeId: string, homeIndex: number): SensorHealth[] {
  const now = Date.now();
  const sensors: SensorHealth[] = [];

  // Edge gateway (virtual — no battery)
  sensors.push({
    sensor_id: `${homeId}-gw-01`,
    type: 'imu' as SensorType,
    room: 'edge_gateway',
    status: 'online',
    battery_pct: undefined,
    last_seen: now - randInt(5, 60) * 1000,
    signal_quality: +randBetween(0.95, 1.0).toFixed(2),
  });

  // 2–3 acoustic sentinels
  const acousticCount = homeIndex === 2 ? 3 : 2;
  for (let a = 0; a < acousticCount; a++) {
    const degraded = homeIndex === 1 && a === 1;
    sensors.push({
      sensor_id: `${homeId}-ac-0${a + 1}`,
      type: 'acoustic',
      room: ROOMS[a],
      status: degraded ? 'degraded' : 'online',
      battery_pct: degraded ? 18 : randInt(55, 100),
      last_seen: now - randInt(10, 300) * 1000,
      signal_quality: +(degraded ? randBetween(0.40, 0.60) : randBetween(0.80, 0.99)).toFixed(2),
    });
  }

  // Environmental sensors
  sensors.push({
    sensor_id: `${homeId}-env-01`,
    type: 'environmental',
    room: 'living_room',
    status: 'online',
    battery_pct: randInt(60, 100),
    last_seen: now - randInt(10, 120) * 1000,
    signal_quality: +randBetween(0.85, 0.99).toFixed(2),
  });

  sensors.push({
    sensor_id: `${homeId}-temp-01`,
    type: 'temperature',
    room: 'bedroom',
    status: 'online',
    battery_pct: randInt(50, 95),
    last_seen: now - randInt(10, 180) * 1000,
    signal_quality: +randBetween(0.88, 0.99).toFixed(2),
  });

  // Toilet sensor
  sensors.push({
    sensor_id: `${homeId}-tlt-01`,
    type: 'toilet',
    room: 'bathroom',
    status: 'online',
    battery_pct: randInt(40, 90),
    last_seen: now - randInt(30, 600) * 1000,
    signal_quality: +randBetween(0.80, 0.97).toFixed(2),
  });

  // Wearable IMU
  const imuOffline = homeIndex === 3;
  sensors.push({
    sensor_id: `${homeId}-imu-01`,
    type: 'imu',
    room: 'wearable',
    status: imuOffline ? 'offline' : 'online',
    battery_pct: imuOffline ? 0 : randInt(40, 95),
    last_seen: imuOffline ? now - 3 * 60 * 60 * 1000 : now - randInt(5, 120) * 1000,
    signal_quality: imuOffline ? 0 : +randBetween(0.85, 0.98).toFixed(2),
  });

  // Medication dock
  sensors.push({
    sensor_id: `${homeId}-med-01`,
    type: 'medication',
    room: 'kitchen',
    status: 'online',
    battery_pct: undefined, // mains-powered
    last_seen: now - randInt(5, 180) * 1000,
    signal_quality: +randBetween(0.92, 1.0).toFixed(2),
  });

  return sensors;
}

export const SENSOR_HEALTH: SensorHealth[] = RESIDENTS.flatMap((r, i) =>
  buildSensorsForHome(r.home_id, i),
);

// ─── 10. Timeline ────────────────────────────────────────────────────────────

export function getTimeline(homeId: string, date: string): TimelineEntry {
  const resident = RESIDENTS.find((r) => r.home_id === homeId) ?? RESIDENTS[0];
  const dayStart = new Date(date).getTime();
  const dayEnd = dayStart + 24 * 60 * 60 * 1000;

  // Filter pre-generated events or create new ones scoped to the day
  let dayEvents = MOCK_EVENTS.filter(
    (e) => e.home_id === homeId && e.timestamp >= dayStart && e.timestamp < dayEnd,
  );

  if (dayEvents.length < 5) {
    // Ensure at least some events for the requested day
    dayEvents = generateEvents(randInt(8, 16), 1).map((e) => ({
      ...e,
      home_id: homeId,
      resident_id: resident.resident_id,
      timestamp: dayStart + Math.random() * (dayEnd - dayStart),
    }));
    dayEvents.sort((a, b) => a.timestamp - b.timestamp);
  }

  const fallCount = dayEvents.filter((e) => e.event_type === 'fall_detected').length;
  const medEvents = dayEvents.filter((e) =>
    ['medication_taken', 'medication_missed', 'medication_late'].includes(e.event_type),
  );
  const medTaken = medEvents.filter((e) => e.event_type === 'medication_taken').length;
  const medAdherence = medEvents.length > 0 ? +((medTaken / medEvents.length) * 100).toFixed(1) : 100;
  const acousticCount = dayEvents.filter((e) => e.event_type.startsWith('acoustic_')).length;

  const metrics: DailyMetrics = {
    total_events: dayEvents.length,
    fall_count: fallCount,
    medication_adherence: medAdherence,
    activity_score: +clamp(randBetween(70, 96), 0, 100).toFixed(1),
    acoustic_events: acousticCount,
    avg_confidence:
      +(dayEvents.reduce((s, e) => s + e.confidence, 0) / dayEvents.length).toFixed(3) || 0,
  };

  const summary =
    fallCount > 0
      ? `${resident.name}: ${fallCount} fall event(s) detected. ${dayEvents.length} total events recorded. Medication adherence ${medAdherence}%.`
      : `${resident.name}: Normal day — ${dayEvents.length} events, medication adherence ${medAdherence}%, activity score ${metrics.activity_score}.`;

  return { home_id: homeId, date, events: dayEvents, summary, metrics };
}

// ─── 11. Recent Events ───────────────────────────────────────────────────────

export function getRecentEvents(homeId?: string, limit = 20): AetherEvent[] {
  let events = [...MOCK_EVENTS];
  if (homeId) {
    events = events.filter((e) => e.home_id === homeId);
  }
  return events.sort((a, b) => b.timestamp - a.timestamp).slice(0, limit);
}

// ─── 12. Live Event Generator ────────────────────────────────────────────────

export function generateLiveEvent(): AetherEvent {
  const template = pick(WEIGHTED_TEMPLATES);
  const resident = pick(RESIDENTS);

  const event: AetherEvent = {
    event_id: uuid(),
    home_id: resident.home_id,
    resident_id: resident.resident_id,
    event_type: template.type,
    severity: template.severity(),
    timestamp: Date.now(),
    confidence: +template.confidence().toFixed(3),
    source_sensors: template.sensors,
    privacy_level: resident.privacy_level,
    data: template.dataPayload(resident),
    evidence_packet_id: ['fall_detected', 'acoustic_scream', 'vital_alert', 'choking'].includes(template.type)
      ? `ep-${uuid().slice(0, 8)}`
      : undefined,
  };

  return event;
}

// ─── Analytics Aggregate ─────────────────────────────────────────────────────

export function getAnalytics(days = 14): AnalyticsData {
  const events = generateEvents(days * 15, days);

  const eventsByType = {} as Record<EventType, number>;
  const eventsBySeverity = {} as Record<Severity, number>;

  events.forEach((e) => {
    eventsByType[e.event_type] = (eventsByType[e.event_type] || 0) + 1;
    eventsBySeverity[e.severity] = (eventsBySeverity[e.severity] || 0) + 1;
  });

  return {
    period: `${days}d`,
    events_by_type: eventsByType,
    events_by_severity: eventsBySeverity,
    daily_trends: getDailyTrends(days),
    response_times: getResponseTimes(days),
    medication_trends: getMedicationTrends(days),
    sensor_health: SENSOR_HEALTH,
  };
}

// ─── 13. Care Navigation Queries ─────────────────────────────────────────────

export const CARE_NAVIGATION_QUERIES: CareNavigationQuery[] = [
  {
    id: uuid(),
    residentId: 'res-a1b2c3d4',
    query: 'Margaret is complaining of burning sensation in her feet. What should we do?',
    response: 'Burning sensation in feet for a diabetic patient like Margaret may indicate diabetic peripheral neuropathy. Ensure blood sugar levels are well-controlled. Apply cool (not cold) compresses for immediate comfort. Schedule a GP consultation within 2–3 days to assess nerve conduction. Monitor for any changes in sensation or color of the feet.',
    actionTier: 'gp_visit',
    sources: ['NICE NG19 — Diabetic Neuropathy', 'AETHER Clinical KB — Diabetic Foot Care'],
    isOffline: false,
    followUpTask: 'Schedule GP visit for neuropathy assessment',
    timestamp: hoursAgo(4),
    language: 'en',
  },
  {
    id: uuid(),
    residentId: 'res-e5f6g7h8',
    query: 'Rajesh has been wheezing more than usual today and his inhaler does not seem to help.',
    response: 'Increased wheezing unresponsive to rescue inhaler in a COPD patient is concerning. Check SpO2 immediately. If SpO2 < 92%, this is urgent. Position upright, ensure calm breathing. If symptoms persist beyond 15 minutes with no improvement, proceed to urgent care. Have a nebulizer session if available at home.',
    actionTier: 'urgent_care',
    sources: ['GOLD 2024 COPD Guidelines', 'AETHER Respiratory Protocol v2.1'],
    isOffline: false,
    followUpTask: 'Monitor SpO2 every 30 minutes; alert if below 92%',
    timestamp: hoursAgo(2),
    language: 'en',
  },
  {
    id: uuid(),
    residentId: 'res-i9j0k1l2',
    query: 'Lakshmi ke ghutne mein bahut dard hai. Kya ice lagaana chahiye?',
    response: 'Haan, ghutne par thanda compress lagaana madad karega (15 minute, din mein 3 baar). Lakshmi ko Warfarin leti hain toh painkiller dene se pehle doctor se zaroor poochein — ibuprofen ya aspirin Warfarin ke saath khatarnaak ho sakta hai. Agar sujan, laalipan ya bukhar ho toh turant GP se milein.',
    actionTier: 'self_care',
    sources: ['AETHER Clinical KB — Joint Pain Management', 'Warfarin Interaction Database'],
    isOffline: true,
    timestamp: hoursAgo(8),
    language: 'hi',
  },
  {
    id: uuid(),
    residentId: 'res-m3n4o5p6',
    query: 'Suresh fell in the bathroom again. He seems okay but is a bit confused.',
    response: 'Post-fall confusion in a Parkinson\'s patient with MCI is a RED FLAG. Do NOT move the patient unless in immediate danger. Check for any head injury — feel for bumps or bleeding. Assess pupil response. Call emergency services immediately if: confusion persists > 5 min, evidence of head trauma, or any loss of consciousness. Meanwhile, keep him warm and still.',
    actionTier: 'emergency',
    sources: ['NICE CG176 — Head Injury', 'Parkinson\'s UK Fall Protocol', 'AETHER Fall Response v3.0'],
    isOffline: false,
    followUpTask: 'Emergency dispatch triggered. Inform family contacts.',
    timestamp: minutesAgo(45),
    language: 'en',
  },
  {
    id: uuid(),
    residentId: 'res-a1b2c3d4',
    query: 'Margaret has a small cut on her hand from chopping vegetables. It is still bleeding slightly after 10 minutes.',
    response: 'For a diabetic patient on low-dose Aspirin, a minor cut may take longer to stop bleeding. Apply firm pressure with a clean cloth for 15 minutes without lifting. Clean with mild soap and water once bleeding stops. Apply antiseptic ointment and a sterile bandage. Watch for signs of infection over next 48 hours (redness, warmth, swelling). If bleeding does not stop in 20 minutes, proceed to GP.',
    actionTier: 'self_care',
    sources: ['AETHER Clinical KB — Wound Care for Diabetics', 'BNF — Aspirin Bleeding Risk'],
    isOffline: false,
    timestamp: hoursAgo(18),
    language: 'en',
  },
  {
    id: uuid(),
    residentId: 'res-e5f6g7h8',
    query: 'Rajesh says he is feeling very dizzy when standing up.',
    response: 'Orthostatic hypotension is common with Diclofenac and in elderly patients with COPD. Have him sit or lie down immediately. Measure blood pressure lying down and standing. If systolic drops > 20 mmHg on standing, this needs medical attention. Ensure adequate hydration. Do not let him walk unassisted until dizziness resolves. Schedule a GP visit to review medication.',
    actionTier: 'gp_visit',
    sources: ['NICE NG136 — Hypertension', 'AETHER Clinical KB — Orthostatic Assessment'],
    isOffline: false,
    followUpTask: 'Schedule GP appointment for orthostatic hypotension evaluation',
    timestamp: hoursAgo(6),
    language: 'en',
  },
];

// ─── 14. Clinical Documents ──────────────────────────────────────────────────

export const CLINICAL_DOCUMENTS: ClinicalDocument[] = [
  {
    id: uuid(),
    residentId: 'res-a1b2c3d4',
    type: 'soap_note',
    status: 'approved',
    content: `S: Margaret reports mild fatigue and occasional dizziness in the morning. Denies chest pain or SOB.\nO: BP 148/88 mmHg, HR 76 bpm, SpO2 97%, BG fasting 142 mg/dL. Medication adherence 94% this week per AETHER NFC tracking.\nA: Suboptimal glycemic control. Mild hypertension — current regimen adequate. Morning dizziness likely orthostatic.\nP: Increase Metformin to 500 mg BID if tolerated. Recheck fasting BG in 1 week. Advise slow position changes. Continue Amlodipine 5 mg and Aspirin 75 mg.`,
    generatedAt: daysAgo(1),
    reviewedBy: 'Dr. Rajesh Menon',
    approvedAt: hoursAgo(18),
    version: 2,
    aiConfidence: 0.94,
  },
  {
    id: uuid(),
    residentId: 'res-e5f6g7h8',
    type: 'soap_note',
    status: 'pending_review',
    content: `S: Rajesh complains of increased joint stiffness in knees this week. Also notes more frequent use of rescue inhaler (3x today vs usual 1x).\nO: SpO2 93%, RR 20/min, mild expiratory wheeze bilaterally. Knee ROM reduced 10° bilaterally. AETHER gait analysis shows 12% speed reduction over 7 days.\nA: COPD exacerbation — mild. OA progression likely contributing to reduced mobility.\nP: Increase Tiotropium monitoring. Consider short course oral prednisolone if wheeze persists. Physiotherapy referral for knee mobility. Continue current OA regimen.`,
    generatedAt: hoursAgo(3),
    version: 1,
    aiConfidence: 0.89,
  },
  {
    id: uuid(),
    residentId: 'res-i9j0k1l2',
    type: 'daily_summary',
    status: 'approved',
    content: `Daily Summary — Lakshmi Iyer — ${dateStr(daysAgo(0))}\n\nVitals: BP 132/78, HR 68 (irregular), SpO2 96%\nMedication Adherence: 100% (Warfarin, Calcium+D3, Atenolol all confirmed via NFC)\nActivity: 4,200 steps, 2 hours seated TV viewing, 45 min kitchen activity\nSleep: 6.8 hours, 2 awakenings, sleep efficiency 82%\nMood: Positive — 3 social interactions (daughter video call, neighbor visit, caregiver check-in)\nNutrition: 3 meals detected, adequate kitchen activity patterns\nAlerts: None\nRisk Score: 0.28 (stable)`,
    generatedAt: hoursAgo(1),
    reviewedBy: 'Priya Nair',
    approvedAt: minutesAgo(30),
    version: 1,
    aiConfidence: 0.96,
  },
  {
    id: uuid(),
    residentId: 'res-m3n4o5p6',
    type: 'incident_report',
    status: 'exported',
    content: `INCIDENT REPORT — Suresh Kumar — Fall Event\n\nDate/Time: ${new Date(hoursAgo(6)).toISOString()}\nLocation: Bathroom\nType: Lateral fall\nSensor Data: IMU impact 5.73g, pose confirmation positive, acoustic correlation confirmed\nConfidence: 92%\n\nPre-incident: Patient was in bathroom for 12 minutes (within normal range). Gait analysis preceding 2 hours showed 15% speed reduction.\nIncident: Lateral fall detected at 03:47 AM. No verbal response detected for 45 seconds.\nPost-incident: Caregiver (Priya Nair) responded in 2 min 18 sec. Patient conscious but disoriented. No visible head injury. Vitals stable — BP 138/82, HR 88.\nActions: Family notified. Dr. Rajesh Menon alerted. Head injury observation protocol initiated.`,
    generatedAt: hoursAgo(5),
    reviewedBy: 'Dr. Rajesh Menon',
    approvedAt: hoursAgo(4),
    exportedAt: hoursAgo(3),
    version: 3,
    aiConfidence: 0.92,
  },
  {
    id: uuid(),
    residentId: 'res-a1b2c3d4',
    type: 'weekly_summary',
    status: 'approved',
    content: `Weekly Summary — Margaret Sharma — Week of ${dateStr(daysAgo(7))} to ${dateStr(daysAgo(0))}\n\nMedication Adherence: 91.3% (2 late doses, 1 missed dose)\nAvg Daily Steps: 3,800 (↓ 5% from previous week)\nSleep Quality: Avg 6.2 hrs/night, efficiency 78%\nVital Trends: BP trending slightly upward (avg 146/86 vs 140/82 prior week)\nGlycemic Control: Fasting BG avg 138 mg/dL (target < 130)\nMood Assessment: Mostly positive, 1 day of noted withdrawal\nFall Risk: Low (0.35)\nKey Observations: Morning dizziness reported 3/7 days — possible orthostatic component.\nRecommendations: GP review of antihypertensive regimen; increase morning hydration.`,
    generatedAt: hoursAgo(12),
    reviewedBy: 'Dr. Rajesh Menon',
    approvedAt: hoursAgo(8),
    version: 2,
    aiConfidence: 0.93,
  },
  {
    id: uuid(),
    residentId: 'res-e5f6g7h8',
    type: 'pre_consult',
    status: 'draft',
    content: `PRE-CONSULTATION BRIEF — Rajesh Patel\nPrepared for: Dr. Rajesh Menon | Upcoming visit: ${dateStr(daysAgo(-2))}\n\nActive Conditions: Osteoarthritis, COPD\nCurrent Medications: Tiotropium 18mcg OD, Diclofenac 50mg BD, Pantoprazole 40mg OD, Salbutamol PRN\n\nKey Observations (14-day AETHER data):\n- Rescue inhaler usage increased 40% (avg 2.1/day → 2.9/day)\n- Gait speed declined 12% (78 cm/s → 69 cm/s)\n- 3 episodes of SpO2 < 94% detected\n- Knee ROM appears reduced based on pose analysis\n- Sleep quality declined — avg 5.4 hrs (from 6.1)\n- Medication adherence 88% (3 late Diclofenac doses)\n\nSuggested Discussion Points:\n1. COPD action plan — step up needed?\n2. OA management — physiotherapy referral\n3. Diclofenac GI risk with ongoing Pantoprazole\n4. Sleep hygiene assessment`,
    generatedAt: hoursAgo(2),
    version: 1,
    aiConfidence: 0.87,
  },
  {
    id: uuid(),
    residentId: 'res-m3n4o5p6',
    type: 'daily_summary',
    status: 'pending_review',
    content: `Daily Summary — Suresh Kumar — ${dateStr(daysAgo(0))}\n\nVitals: BP 134/80, HR 72, SpO2 96%\nMedication Adherence: 80% (1 missed Amantadine dose at 14:00, 1 late Levodopa by 35 min)\nActivity: 1,800 steps (below 2,500 target), significant rest periods\nSleep: 4.8 hours, 5 awakenings, sleep efficiency 58% — Melatonin taken on time\nMood: Low — 1 social interaction only, extended bedroom time\nCognitive Indicators: 2 episodes of repeated questions noted by acoustic analysis\nGait: Speed 52 cm/s (baseline 65 cm/s), stride variability 22% (baseline 10%)\nAlerts: 1 fall event (bathroom, 03:47 AM — see incident report)\nRisk Score: 0.68 → 0.74 (elevated due to fall + gait decline)`,
    generatedAt: minutesAgo(90),
    version: 1,
    aiConfidence: 0.91,
  },
  {
    id: uuid(),
    residentId: 'res-i9j0k1l2',
    type: 'soap_note',
    status: 'draft',
    content: `S: Lakshmi reports feeling well overall. Mentions occasional palpitations, usually lasting < 1 minute. No syncope or chest pain.\nO: HR 68 irregular (consistent with known AF), BP 132/78, SpO2 96%. INR due for check (last: 2.4 three weeks ago). AETHER wearable shows HR variability consistent with paroxysmal AF — 3 episodes > 100 bpm this week.\nA: Atrial fibrillation — rate controlled on Atenolol. INR monitoring overdue. Osteoporosis stable.\nP: Urgent INR check. Continue Warfarin 2mg pending result. Atenolol adequate. Reinforce fall prevention — AF + osteoporosis = high fracture risk. Next calcium/D3 levels at 3-month review.`,
    generatedAt: hoursAgo(1),
    version: 1,
    aiConfidence: 0.88,
  },
];

// ─── 15. Edge Gateways ───────────────────────────────────────────────────────

export const EDGE_GATEWAYS: EdgeGateway[] = [
  {
    id: 'gw-mumbai-01',
    siteId: 'site-mumbai',
    siteName: 'AETHER Mumbai — Andheri West',
    status: 'online',
    uptime: 99.98,
    lastHeartbeat: minutesAgo(1),
    firmwareVersion: '2.4.1',
    connectedSensors: 32,
    totalSensors: 34,
    cpuUsage: 42,
    memoryUsage: 61,
    networkLatency: 12,
  },
  {
    id: 'gw-delhi-01',
    siteId: 'site-delhi',
    siteName: 'AETHER Delhi — Vasant Kunj',
    status: 'online',
    uptime: 99.92,
    lastHeartbeat: minutesAgo(2),
    firmwareVersion: '2.4.1',
    connectedSensors: 28,
    totalSensors: 28,
    cpuUsage: 38,
    memoryUsage: 55,
    networkLatency: 18,
  },
  {
    id: 'gw-bangalore-01',
    siteId: 'site-bangalore',
    siteName: 'AETHER Bangalore — Koramangala',
    status: 'degraded',
    uptime: 98.74,
    lastHeartbeat: minutesAgo(8),
    firmwareVersion: '2.3.9',
    connectedSensors: 22,
    totalSensors: 26,
    cpuUsage: 78,
    memoryUsage: 82,
    networkLatency: 45,
  },
  {
    id: 'gw-chennai-01',
    siteId: 'site-chennai',
    siteName: 'AETHER Chennai — T. Nagar',
    status: 'online',
    uptime: 99.95,
    lastHeartbeat: minutesAgo(1),
    firmwareVersion: '2.4.1',
    connectedSensors: 18,
    totalSensors: 18,
    cpuUsage: 35,
    memoryUsage: 48,
    networkLatency: 15,
  },
];

// ─── 16. Site Health ─────────────────────────────────────────────────────────

export const SITE_HEALTH_DATA: SiteHealth[] = [
  {
    siteId: 'site-mumbai',
    siteName: 'AETHER Mumbai — Andheri West',
    city: 'Mumbai',
    totalResidents: 24,
    activeAlerts: 2,
    gatewayStatus: 'healthy',
    slaResponseTime: 9.2,
    slaTarget: 15,
    sensorCoverage: 94.1,
    lastIncident: daysAgo(3),
  },
  {
    siteId: 'site-delhi',
    siteName: 'AETHER Delhi — Vasant Kunj',
    city: 'Delhi',
    totalResidents: 18,
    activeAlerts: 1,
    gatewayStatus: 'healthy',
    slaResponseTime: 11.8,
    slaTarget: 15,
    sensorCoverage: 100,
  },
  {
    siteId: 'site-bangalore',
    siteName: 'AETHER Bangalore — Koramangala',
    city: 'Bangalore',
    totalResidents: 16,
    activeAlerts: 4,
    gatewayStatus: 'degraded',
    slaResponseTime: 18.5,
    slaTarget: 15,
    sensorCoverage: 84.6,
    lastIncident: hoursAgo(6),
  },
  {
    siteId: 'site-chennai',
    siteName: 'AETHER Chennai — T. Nagar',
    city: 'Chennai',
    totalResidents: 12,
    activeAlerts: 0,
    gatewayStatus: 'healthy',
    slaResponseTime: 8.4,
    slaTarget: 15,
    sensorCoverage: 100,
  },
];

// ─── 17. Health Profiles ─────────────────────────────────────────────────────

export const HEALTH_PROFILES: HealthProfile[] = [
  {
    residentId: 'res-a1b2c3d4',
    overallScore: 72,
    domains: [
      { name: 'Cardiovascular', score: 68, trend: 'stable', lastUpdated: hoursAgo(2) },
      { name: 'Metabolic', score: 62, trend: 'declining', lastUpdated: hoursAgo(2) },
      { name: 'Mobility', score: 78, trend: 'stable', lastUpdated: hoursAgo(4) },
      { name: 'Cognitive', score: 85, trend: 'stable', lastUpdated: daysAgo(1) },
      { name: 'Sleep', score: 65, trend: 'declining', lastUpdated: hoursAgo(6) },
      { name: 'Nutrition', score: 80, trend: 'improving', lastUpdated: hoursAgo(3) },
    ],
    riskFactors: ['Uncontrolled blood sugar', 'Morning orthostatic dizziness', 'Suboptimal sleep'],
    recommendations: ['Review antihypertensive regimen', 'Increase morning hydration', 'Fasting BG recheck in 1 week'],
  },
  {
    residentId: 'res-e5f6g7h8',
    overallScore: 58,
    domains: [
      { name: 'Respiratory', score: 48, trend: 'declining', lastUpdated: hoursAgo(1) },
      { name: 'Musculoskeletal', score: 52, trend: 'declining', lastUpdated: hoursAgo(3) },
      { name: 'Mobility', score: 55, trend: 'declining', lastUpdated: hoursAgo(2) },
      { name: 'Cognitive', score: 82, trend: 'stable', lastUpdated: daysAgo(1) },
      { name: 'Sleep', score: 55, trend: 'declining', lastUpdated: hoursAgo(6) },
      { name: 'Nutrition', score: 70, trend: 'stable', lastUpdated: hoursAgo(4) },
    ],
    riskFactors: ['COPD exacerbation risk', 'Gait speed decline 12%', 'Increased rescue inhaler usage', 'OA progression'],
    recommendations: ['COPD action plan review', 'Physiotherapy referral', 'Sleep hygiene assessment', 'Consider Diclofenac alternatives'],
  },
  {
    residentId: 'res-i9j0k1l2',
    overallScore: 79,
    domains: [
      { name: 'Cardiovascular', score: 72, trend: 'stable', lastUpdated: hoursAgo(2) },
      { name: 'Musculoskeletal', score: 65, trend: 'stable', lastUpdated: daysAgo(1) },
      { name: 'Mobility', score: 82, trend: 'improving', lastUpdated: hoursAgo(3) },
      { name: 'Cognitive', score: 90, trend: 'stable', lastUpdated: daysAgo(1) },
      { name: 'Sleep', score: 82, trend: 'stable', lastUpdated: hoursAgo(5) },
      { name: 'Nutrition', score: 85, trend: 'improving', lastUpdated: hoursAgo(2) },
    ],
    riskFactors: ['AF — fracture risk with osteoporosis', 'INR monitoring overdue'],
    recommendations: ['Urgent INR check', 'Reinforce fall prevention', 'Continue calcium + D3'],
  },
  {
    residentId: 'res-m3n4o5p6',
    overallScore: 45,
    domains: [
      { name: 'Neurological', score: 38, trend: 'declining', lastUpdated: hoursAgo(1) },
      { name: 'Mobility', score: 35, trend: 'declining', lastUpdated: hoursAgo(2) },
      { name: 'Cognitive', score: 42, trend: 'declining', lastUpdated: hoursAgo(3) },
      { name: 'Sleep', score: 38, trend: 'declining', lastUpdated: hoursAgo(4) },
      { name: 'Nutrition', score: 55, trend: 'stable', lastUpdated: hoursAgo(6) },
      { name: 'Emotional', score: 48, trend: 'declining', lastUpdated: hoursAgo(2) },
    ],
    riskFactors: ['Recurrent falls', 'Rapid gait degradation', 'Cognitive decline progression', 'Social withdrawal', 'Poor sleep'],
    recommendations: ['Neurology review — medication adjustment', 'Increase social engagement', 'Bathroom safety modifications', 'Night-time monitoring protocol'],
  },
];

// ─── 18. Prescriptions ──────────────────────────────────────────────────────

export const PRESCRIPTIONS: Prescription[] = [
  {
    id: uuid(),
    residentId: 'res-a1b2c3d4',
    doctorName: 'Dr. Rajesh Menon',
    date: daysAgo(5),
    medications: [
      { name: 'Metformin', dosage: '500 mg', frequency: 'Twice daily', duration: '90 days', notes: 'Take with food' },
      { name: 'Amlodipine', dosage: '5 mg', frequency: 'Once daily (morning)', duration: '90 days' },
      { name: 'Aspirin', dosage: '75 mg', frequency: 'Once daily (afternoon)', duration: '90 days', notes: 'Enteric coated' },
    ],
    interactions: [],
    status: 'approved',
    ocrConfidence: 0.97,
  },
  {
    id: uuid(),
    residentId: 'res-e5f6g7h8',
    doctorName: 'Dr. Sanjay Kapoor',
    date: daysAgo(2),
    medications: [
      { name: 'Prednisolone', dosage: '20 mg', frequency: 'Once daily (morning)', duration: '5 days', notes: 'Short course for COPD exacerbation' },
      { name: 'Diclofenac', dosage: '50 mg', frequency: 'Twice daily', duration: '14 days' },
      { name: 'Pantoprazole', dosage: '40 mg', frequency: 'Once daily (before breakfast)', duration: '14 days' },
    ],
    interactions: [
      {
        drugA: 'Prednisolone',
        drugB: 'Diclofenac',
        severity: 'severe',
        description: 'Combined use of corticosteroids and NSAIDs significantly increases the risk of GI bleeding and peptic ulceration.',
        recommendation: 'Consider gastroprotective agent (Pantoprazole already prescribed). Monitor for GI symptoms. Limit concurrent use duration.',
      },
    ],
    status: 'flagged',
    ocrConfidence: 0.91,
    sourceDocUrl: '/documents/rx-patel-20260302.pdf',
  },
  {
    id: uuid(),
    residentId: 'res-i9j0k1l2',
    doctorName: 'Dr. Rajesh Menon',
    date: daysAgo(14),
    medications: [
      { name: 'Warfarin', dosage: '2 mg', frequency: 'Once daily (evening)', duration: 'Ongoing' },
      { name: 'Calcium + Vitamin D3', dosage: '500 mg / 250 IU', frequency: 'Twice daily', duration: '90 days' },
      { name: 'Atenolol', dosage: '25 mg', frequency: 'Once daily (morning)', duration: '90 days' },
    ],
    interactions: [
      {
        drugA: 'Warfarin',
        drugB: 'Calcium + Vitamin D3',
        severity: 'minor',
        description: 'High-dose Vitamin D may slightly affect Warfarin metabolism. At current dosage (250 IU), interaction is minimal.',
        recommendation: 'Monitor INR as scheduled. No dose adjustment needed at current Vitamin D level.',
      },
    ],
    status: 'approved',
    ocrConfidence: 0.95,
  },
  {
    id: uuid(),
    residentId: 'res-m3n4o5p6',
    doctorName: 'Dr. Anita Desai',
    date: daysAgo(7),
    medications: [
      { name: 'Levodopa/Carbidopa', dosage: '100/25 mg', frequency: 'Three times daily', duration: '90 days', notes: 'Take 30 min before meals' },
      { name: 'Pramipexole', dosage: '0.5 mg', frequency: 'Twice daily', duration: '90 days' },
      { name: 'Donepezil', dosage: '5 mg', frequency: 'Once daily (bedtime)', duration: '90 days' },
      { name: 'Amantadine', dosage: '100 mg', frequency: 'Twice daily', duration: '90 days' },
      { name: 'Melatonin', dosage: '3 mg', frequency: 'Once daily (21:00)', duration: '90 days' },
    ],
    interactions: [
      {
        drugA: 'Amantadine',
        drugB: 'Donepezil',
        severity: 'moderate',
        description: 'Amantadine has anticholinergic properties that may oppose the cholinergic effects of Donepezil, potentially reducing cognitive benefit.',
        recommendation: 'Monitor cognitive function closely. Discuss with neurologist whether Amantadine dose reduction is appropriate.',
      },
      {
        drugA: 'Pramipexole',
        drugB: 'Levodopa/Carbidopa',
        severity: 'minor',
        description: 'Pramipexole may potentiate the dopaminergic effects of Levodopa, increasing risk of dyskinesia.',
        recommendation: 'Monitor for involuntary movements. May need Levodopa dose adjustment.',
      },
    ],
    status: 'pending_review',
    ocrConfidence: 0.88,
    sourceDocUrl: '/documents/rx-kumar-20260225.pdf',
  },
];

// ─── 19. Service Bookings ────────────────────────────────────────────────────

export const SERVICE_BOOKINGS: ServiceBooking[] = [
  {
    id: uuid(),
    residentId: 'res-a1b2c3d4',
    type: 'transport',
    status: 'confirmed',
    details: {
      pickup: 'AETHER Mumbai — Andheri West',
      destination: 'Kokilaben Dhirubhai Ambani Hospital',
      purpose: 'Endocrinology follow-up',
      wheelchair: false,
      escort: 'Priya Nair (Caregiver)',
    },
    requestedAt: hoursAgo(12),
    estimatedTime: hoursAgo(-4), // 4 hours from now
    cost: 450,
    isDemoOnly: true,
  },
  {
    id: uuid(),
    residentId: 'res-e5f6g7h8',
    type: 'food_order',
    status: 'in_progress',
    details: {
      restaurant: 'Swiggy — Shree Krishna Veg',
      items: ['Dal Khichdi (soft)', 'Dahi', 'Banana'],
      dietaryNotes: 'COPD patient — soft food preferred, no spicy',
      specialInstructions: 'Extra dahi on the side',
    },
    requestedAt: minutesAgo(35),
    estimatedTime: minutesAgo(-15), // 15 min from now
    cost: 180,
    isDemoOnly: true,
  },
  {
    id: uuid(),
    residentId: 'res-m3n4o5p6',
    type: 'appointment',
    status: 'confirmed',
    details: {
      doctor: 'Dr. Anita Desai',
      specialization: 'Neurology',
      hospital: 'Manipal Hospital, Bangalore',
      purpose: 'Parkinson\'s medication review',
      telemedicine: false,
    },
    requestedAt: daysAgo(3),
    estimatedTime: daysAgo(-2), // 2 days from now
    isDemoOnly: true,
  },
  {
    id: uuid(),
    residentId: 'res-i9j0k1l2',
    type: 'shopping',
    status: 'completed',
    details: {
      store: 'BigBasket',
      items: ['Ragi flour', 'Oats', 'Almonds', 'Dates', 'Turmeric milk powder'],
      deliveryNotes: 'Leave at reception — Lakshmi will collect',
    },
    requestedAt: daysAgo(1),
    estimatedTime: daysAgo(1) + 3 * 60 * 60 * 1000,
    cost: 620,
    isDemoOnly: true,
  },
  {
    id: uuid(),
    residentId: 'res-a1b2c3d4',
    type: 'transport',
    status: 'completed',
    details: {
      pickup: 'AETHER Mumbai — Andheri West',
      destination: 'Lilavati Hospital — Pathology Lab',
      purpose: 'Fasting blood sugar test',
      wheelchair: false,
      escort: 'Vikram Sharma (Son)',
    },
    requestedAt: daysAgo(4),
    estimatedTime: daysAgo(4) + 2 * 60 * 60 * 1000,
    cost: 380,
    isDemoOnly: true,
  },
];

// ─── 20. Calendar Events ─────────────────────────────────────────────────────

export const CALENDAR_EVENTS: CalendarEvent[] = [
  {
    id: uuid(),
    title: 'Metformin — Morning Dose',
    type: 'medication',
    datetime: setHour(Date.now(), 8, 0),
    participants: ['res-a1b2c3d4'],
    recurrence: 'daily',
    reminders: [15, 5],
    notes: 'Take with breakfast',
  },
  {
    id: uuid(),
    title: 'Metformin — Evening Dose',
    type: 'medication',
    datetime: setHour(Date.now(), 20, 0),
    participants: ['res-a1b2c3d4'],
    recurrence: 'daily',
    reminders: [15, 5],
  },
  {
    id: uuid(),
    title: 'Dr. Rajesh Menon — Endocrinology Follow-up',
    type: 'appointment',
    datetime: daysAgo(-2) + 10 * 60 * 60 * 1000,
    duration: 30,
    participants: ['res-a1b2c3d4', 'user-doc-001'],
    reminders: [60, 30, 15],
    notes: 'Bring fasting BG report from Lilavati',
  },
  {
    id: uuid(),
    title: 'Cab to Kokilaben Hospital',
    type: 'transport',
    datetime: daysAgo(-2) + 9 * 60 * 60 * 1000,
    duration: 45,
    participants: ['res-a1b2c3d4', 'user-cg-001'],
    reminders: [60, 30],
  },
  {
    id: uuid(),
    title: 'Vikram Sharma — Family Visit',
    type: 'visit',
    datetime: daysAgo(-1) + 16 * 60 * 60 * 1000,
    duration: 120,
    participants: ['res-a1b2c3d4'],
    recurrence: 'weekly',
    reminders: [60],
    notes: 'Son visits every Sunday',
  },
  {
    id: uuid(),
    title: 'Levodopa/Carbidopa — Morning',
    type: 'medication',
    datetime: setHour(Date.now(), 8, 0),
    participants: ['res-m3n4o5p6'],
    recurrence: 'daily',
    reminders: [15, 5],
    notes: '30 min before breakfast',
  },
  {
    id: uuid(),
    title: 'Physiotherapy Session — Rajesh',
    type: 'activity',
    datetime: daysAgo(-1) + 11 * 60 * 60 * 1000,
    duration: 45,
    participants: ['res-e5f6g7h8'],
    recurrence: 'weekly',
    reminders: [30, 15],
    notes: 'Focus on knee mobility exercises',
  },
  {
    id: uuid(),
    title: 'Dr. Anita Desai — Neurology Review',
    type: 'appointment',
    datetime: daysAgo(-3) + 14 * 60 * 60 * 1000,
    duration: 45,
    participants: ['res-m3n4o5p6', 'user-doc-001'],
    reminders: [120, 60, 30],
    notes: 'Discuss Amantadine/Donepezil interaction and gait decline',
  },
  {
    id: uuid(),
    title: 'Warfarin INR Check — Lakshmi',
    type: 'appointment',
    datetime: daysAgo(-1) + 9 * 60 * 60 * 1000,
    duration: 15,
    participants: ['res-i9j0k1l2'],
    reminders: [60, 30],
    notes: 'Overdue — last INR was 3 weeks ago',
  },
  {
    id: uuid(),
    title: 'Morning Yoga — Group Activity',
    type: 'activity',
    datetime: setHour(Date.now(), 7, 0),
    duration: 30,
    participants: ['res-a1b2c3d4', 'res-i9j0k1l2'],
    recurrence: 'daily',
    reminders: [15],
    notes: 'Chair yoga for mobility-limited residents',
  },
];

// ─── 21. Care Handoffs ───────────────────────────────────────────────────────

export const CARE_HANDOFFS: CareHandoff[] = [
  {
    id: uuid(),
    fromCaregiver: 'Priya Nair',
    toCaregiver: 'Arun Mathew',
    timestamp: hoursAgo(2),
    checklist: [
      { task: 'Suresh fall incident — head injury observation ongoing', completed: true, priority: 'high' },
      { task: 'Rajesh rescue inhaler count check', completed: true, priority: 'high' },
      { task: 'Margaret evening Metformin — remind at 20:00', completed: false, priority: 'medium' },
      { task: 'Lakshmi — 2 PM Aspirin verification', completed: true, priority: 'medium' },
      { task: 'Environmental sensor check — living rooms', completed: true, priority: 'low' },
    ],
    notes: 'Suresh had a fall at 03:47 AM. Currently stable but confused off and on. Dr. Menon has been informed. Keep close watch tonight — bathroom escort mandatory. Rajesh was wheezy earlier, improved after nebulizer session at 14:30.',
    pendingTasks: [
      'Margaret 20:00 Metformin reminder',
      'Suresh head observation — check at 22:00',
      'Rajesh SpO2 check at 21:00',
    ],
  },
  {
    id: uuid(),
    fromCaregiver: 'Arun Mathew',
    toCaregiver: 'Neha Gupta',
    timestamp: hoursAgo(10),
    checklist: [
      { task: 'Morning medication round — all 4 residents', completed: true, priority: 'high' },
      { task: 'Margaret fasting BG check', completed: true, priority: 'high' },
      { task: 'Suresh morning Levodopa — 30 min before breakfast', completed: true, priority: 'high' },
      { task: 'Environmental comfort check — AC/humidity', completed: true, priority: 'low' },
      { task: 'Update family portal — daily summaries', completed: false, priority: 'medium' },
    ],
    notes: 'Quiet morning shift. Margaret fasting BG was 142 — slightly above target. All morning meds administered on time. Suresh was slow to wake but mood reasonable. Lakshmi in good spirits — daughter called at 09:30.',
    pendingTasks: [
      'Update family portal with morning summaries',
      'Rajesh 14:00 Salbutamol reminder',
    ],
  },
];

// ─── 22. Micro-Lessons ──────────────────────────────────────────────────────

export const MICRO_LESSONS: MicroLesson[] = [
  {
    id: uuid(),
    title: 'Recognizing Diabetic Foot Complications',
    category: 'Diabetes Management',
    content: 'Learn to identify early signs of diabetic foot complications: tingling, numbness, color changes, and temperature differences between feet. Daily foot inspections are critical for diabetic residents.',
    duration: 5,
    completedBy: ['user-cg-001'],
    teachBackRequired: true,
    teachBackCompleted: true,
  },
  {
    id: uuid(),
    title: 'COPD Emergency Response Protocol',
    category: 'Respiratory Care',
    content: 'When a COPD patient shows signs of acute exacerbation: 1) Position upright, 2) Administer rescue inhaler, 3) Check SpO2, 4) If SpO2 < 92% — call emergency, 5) Document event in AETHER system.',
    duration: 8,
    completedBy: ['user-cg-001'],
    teachBackRequired: true,
    teachBackCompleted: false,
  },
  {
    id: uuid(),
    title: 'Safe Patient Transfer Techniques',
    category: 'Physical Safety',
    content: 'Proper body mechanics for transferring elderly patients from bed to wheelchair. Includes pivot transfer, stand-pivot, and sliding board techniques with emphasis on Parkinson\'s patients.',
    duration: 12,
    completedBy: [],
    teachBackRequired: true,
    teachBackCompleted: false,
  },
  {
    id: uuid(),
    title: 'Understanding Warfarin and Dietary Interactions',
    category: 'Medication Safety',
    content: 'Warfarin interacts with Vitamin K-rich foods. Educate residents about consistent intake of leafy greens rather than avoidance. Key foods: spinach, broccoli, kale, green tea.',
    duration: 6,
    completedBy: ['user-cg-001'],
    teachBackRequired: false,
    teachBackCompleted: false,
  },
  {
    id: uuid(),
    title: 'Detecting Elder Scam Calls',
    category: 'Safety & Security',
    content: 'Common patterns in elder-targeted scam calls: urgency tactics, authority impersonation (bank/police), requests for OTPs or account details. AETHER acoustic analysis flags suspicious call patterns automatically.',
    duration: 7,
    completedBy: [],
    teachBackRequired: false,
    teachBackCompleted: false,
  },
  {
    id: uuid(),
    title: 'Post-Fall Assessment Checklist',
    category: 'Emergency Response',
    content: 'After a fall: 1) Do not move patient, 2) Check consciousness, 3) Assess for head injury, 4) Check limb deformity, 5) Measure vitals, 6) Document in AETHER, 7) Notify doctor if any red flags.',
    duration: 10,
    completedBy: ['user-cg-001'],
    teachBackRequired: true,
    teachBackCompleted: true,
  },
];

// ─── 23. Consent Settings ────────────────────────────────────────────────────

export const CONSENT_SETTINGS: ConsentSettings[] = [
  {
    residentId: 'res-a1b2c3d4',
    dataTypes: [
      { type: 'Motion & Activity', allowedViewers: ['caregiver', 'doctor', 'ops'], enabled: true },
      { type: 'Medication Tracking', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Audio Classification', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Vital Signs', allowedViewers: ['doctor'], enabled: true },
      { type: 'Environmental Data', allowedViewers: ['caregiver', 'doctor', 'ops'], enabled: true },
      { type: 'Sleep Patterns', allowedViewers: ['doctor'], enabled: true },
      { type: 'Location (Room-level)', allowedViewers: ['caregiver'], enabled: true },
    ],
    retentionDays: 90,
    exportRequests: [
      { id: uuid(), requestedAt: daysAgo(10), status: 'completed', format: 'pdf' },
    ],
  },
  {
    residentId: 'res-e5f6g7h8',
    dataTypes: [
      { type: 'Motion & Activity', allowedViewers: ['caregiver', 'doctor', 'ops'], enabled: true },
      { type: 'Medication Tracking', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Audio Classification', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Vital Signs', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Environmental Data', allowedViewers: ['caregiver', 'doctor', 'ops'], enabled: true },
      { type: 'Sleep Patterns', allowedViewers: ['doctor'], enabled: true },
      { type: 'Location (Room-level)', allowedViewers: ['caregiver'], enabled: true },
    ],
    retentionDays: 90,
    exportRequests: [],
  },
  {
    residentId: 'res-i9j0k1l2',
    dataTypes: [
      { type: 'Motion & Activity', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Medication Tracking', allowedViewers: ['doctor'], enabled: true },
      { type: 'Audio Classification', allowedViewers: ['doctor'], enabled: true },
      { type: 'Vital Signs', allowedViewers: ['doctor'], enabled: true },
      { type: 'Environmental Data', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Sleep Patterns', allowedViewers: ['doctor'], enabled: false },
      { type: 'Location (Room-level)', allowedViewers: ['caregiver'], enabled: false },
    ],
    retentionDays: 60,
    exportRequests: [
      { id: uuid(), requestedAt: daysAgo(5), status: 'completed', format: 'json' },
      { id: uuid(), requestedAt: daysAgo(1), status: 'pending', format: 'csv' },
    ],
  },
  {
    residentId: 'res-m3n4o5p6',
    dataTypes: [
      { type: 'Motion & Activity', allowedViewers: ['caregiver', 'doctor', 'ops'], enabled: true },
      { type: 'Medication Tracking', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Audio Classification', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Vital Signs', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Environmental Data', allowedViewers: ['caregiver', 'doctor', 'ops'], enabled: true },
      { type: 'Sleep Patterns', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Location (Room-level)', allowedViewers: ['caregiver', 'doctor'], enabled: true },
      { type: 'Cognitive Indicators', allowedViewers: ['doctor'], enabled: true },
    ],
    retentionDays: 180,
    exportRequests: [
      { id: uuid(), requestedAt: daysAgo(2), status: 'processing', format: 'pdf' },
    ],
  },
];

// ─── 24. Caregiver Workload ──────────────────────────────────────────────────

export const CAREGIVER_WORKLOAD: CaregiverWorkload[] = [
  {
    caregiverId: 'user-cg-001',
    name: 'Priya Nair',
    shift: 'Day (07:00–15:00)',
    alertsHandled: 12,
    avgResponseTime: 8.4,
    hoursWorked: 7.5,
    burnoutScore: 42,
    lastBreak: hoursAgo(3),
  },
  {
    caregiverId: 'cg-002',
    name: 'Arun Mathew',
    shift: 'Evening (15:00–23:00)',
    alertsHandled: 8,
    avgResponseTime: 11.2,
    hoursWorked: 6,
    burnoutScore: 35,
    lastBreak: hoursAgo(1),
  },
  {
    caregiverId: 'cg-003',
    name: 'Neha Gupta',
    shift: 'Night (23:00–07:00)',
    alertsHandled: 4,
    avgResponseTime: 14.8,
    hoursWorked: 8,
    burnoutScore: 58,
    lastBreak: hoursAgo(5),
  },
  {
    caregiverId: 'cg-004',
    name: 'Deepak Reddy',
    shift: 'Day (07:00–15:00)',
    alertsHandled: 15,
    avgResponseTime: 7.1,
    hoursWorked: 7.8,
    burnoutScore: 72,
    lastBreak: hoursAgo(4),
  },
  {
    caregiverId: 'cg-005',
    name: 'Sunita Rajan',
    shift: 'Evening (15:00–23:00)',
    alertsHandled: 6,
    avgResponseTime: 9.5,
    hoursWorked: 5.5,
    burnoutScore: 28,
    lastBreak: hoursAgo(2),
  },
];

// ─── 25. Escalation Funnel ───────────────────────────────────────────────────

export const ESCALATION_FUNNEL: EscalationFunnel = {
  detected: 847,
  verified: 312,
  caregiverAcknowledged: 289,
  resolved: 274,
  autoEscalated: 38,
};

// ─── 26. Risk Trend Data ─────────────────────────────────────────────────────

export function generateRiskTrends(residentId: string, days = 30): RiskTrendPoint[] {
  const data: RiskTrendPoint[] = [];
  const now = Date.now();

  // Base profiles per resident for realistic trends
  const profiles: Record<string, { mobility: number; sleep: number; hydration: number; medAdherence: number; mood: number; cognitive: number; respiratory: number; driftRate: number }> = {
    'res-a1b2c3d4': { mobility: 78, sleep: 65, hydration: 72, medAdherence: 91, mood: 75, cognitive: 85, respiratory: 88, driftRate: 0.3 },
    'res-e5f6g7h8': { mobility: 55, sleep: 55, hydration: 68, medAdherence: 88, mood: 70, cognitive: 82, respiratory: 48, driftRate: 0.8 },
    'res-i9j0k1l2': { mobility: 82, sleep: 82, hydration: 78, medAdherence: 100, mood: 85, cognitive: 90, respiratory: 90, driftRate: 0.1 },
    'res-m3n4o5p6': { mobility: 45, sleep: 38, hydration: 60, medAdherence: 80, mood: 48, cognitive: 42, respiratory: 85, driftRate: 1.2 },
  };

  const p = profiles[residentId] || profiles['res-a1b2c3d4'];

  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now - i * 24 * 60 * 60 * 1000);
    const dayFactor = (days - i) / days; // 0→1 as we approach today
    const noise = () => randBetween(-4, 4);

    data.push({
      date: d.toISOString().slice(0, 10),
      mobility: clamp(p.mobility - dayFactor * p.driftRate * 10 + noise(), 10, 100),
      sleep: clamp(p.sleep - dayFactor * p.driftRate * 5 + noise(), 10, 100),
      hydration: clamp(p.hydration + noise(), 30, 100),
      medicationAdherence: clamp(p.medAdherence + noise() * 0.5, 60, 100),
      mood: clamp(p.mood - dayFactor * p.driftRate * 3 + noise(), 10, 100),
      cognitive: clamp(p.cognitive - dayFactor * p.driftRate * 4 + noise(), 10, 100),
      respiratory: clamp(p.respiratory - dayFactor * p.driftRate * 6 + noise(), 10, 100),
    });
  }

  return data;
}

// Pre-generate for all residents
export const RISK_TRENDS: Record<string, RiskTrendPoint[]> = {
  'res-a1b2c3d4': generateRiskTrends('res-a1b2c3d4'),
  'res-e5f6g7h8': generateRiskTrends('res-e5f6g7h8'),
  'res-i9j0k1l2': generateRiskTrends('res-i9j0k1l2'),
  'res-m3n4o5p6': generateRiskTrends('res-m3n4o5p6'),
};

// ─── 27. Environmental Sensor Data ───────────────────────────────────────────

export interface EnvironmentalReading {
  sensorId: string;
  homeId: string;
  room: string;
  timestamp: number;
  temperature: number; // °C
  humidity: number; // %
  aqi: number;
  lightLevel: number; // lux
  noiseLevel: number; // dB
}

export function getEnvironmentalReadings(): EnvironmentalReading[] {
  const now = Date.now();
  const readings: EnvironmentalReading[] = [];

  RESIDENTS.forEach((r) => {
    ROOMS.forEach((room) => {
      readings.push({
        sensorId: `${r.home_id}-env-${room}`,
        homeId: r.home_id,
        room,
        timestamp: now - randInt(1, 5) * 60 * 1000,
        temperature: +(randBetween(24, 30).toFixed(1)),
        humidity: randInt(40, 65),
        aqi: randInt(30, 120),
        lightLevel: room === 'bedroom' ? randInt(10, 80) : randInt(100, 400),
        noiseLevel: randInt(25, 55),
      });
    });
  });

  return readings;
}

// ─── 28. Command Center ──────────────────────────────────────────────────────

export function getCommandCenterData(): CommandCenterData {
  const criticalEvents = MOCK_EVENTS.filter((e) => e.severity === 'CRITICAL' && !e.acknowledged);
  const unresolvedMeds = MOCK_EVENTS.filter(
    (e) => e.event_type === 'medication_missed' && !e.acknowledged,
  ).length;

  return {
    criticalAlerts: criticalEvents.length > 0 ? criticalEvents.slice(-3) : [
      {
        event_id: uuid(),
        home_id: 'home-004',
        resident_id: 'res-m3n4o5p6',
        event_type: 'fall_detected',
        severity: 'CRITICAL',
        timestamp: minutesAgo(3),
        confidence: 0.92,
        source_sensors: ['imu', 'pose', 'acoustic'],
        privacy_level: 'elevated',
        data: { room: 'bathroom', fall_type: 'lateral', post_fall_motion: false },
        evidence_packet_id: `ep-${uuid().slice(0, 8)}`,
      },
    ],
    unresolvedMeds: unresolvedMeds || 3,
    pendingApprovals: CLINICAL_DOCUMENTS.filter((d) => d.status === 'pending_review').length,
    connectivityIncidents: EDGE_GATEWAYS.filter((g) => g.status !== 'online').length,
    lastUpdated: Date.now(),
  };
}

// ─── 29. False Positive Rates ────────────────────────────────────────────────

export function getFalsePositiveRates(): FalsePositiveRate[] {
  const data: FalsePositiveRate[] = [];
  for (let i = 30; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000);
    const fallBase = 8 + Math.sin(i * 0.3) * 3;
    const medBase = 5 + Math.cos(i * 0.2) * 2;
    const acBase = 12 + Math.sin(i * 0.25) * 4;
    const envBase = 6 + Math.cos(i * 0.15) * 2;
    data.push({
      date: d.toISOString().split('T')[0],
      fallDetection: +(Math.max(1, fallBase + randBetween(-2, 2)).toFixed(1)),
      medicationAlert: +(Math.max(1, medBase + randBetween(-1, 1)).toFixed(1)),
      acousticAlert: +(Math.max(1, acBase + randBetween(-2, 2)).toFixed(1)),
      environmentalAlert: +(Math.max(1, envBase + randBetween(-1, 1)).toFixed(1)),
      overallRate: +(Math.max(1, (fallBase + medBase + acBase + envBase) / 4 + randBetween(-1, 1)).toFixed(1)),
    });
  }
  return data;
}

// ─── 30. Model Confidence Drift ──────────────────────────────────────────────

export function getModelConfidenceDrift(): ModelConfidenceDrift[] {
  const data: ModelConfidenceDrift[] = [];
  for (let i = 30; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000);
    const fallModel = 92 - i * 0.15 + randBetween(-1, 1);
    const acousticModel = 89 - i * 0.1 + randBetween(-1, 1);
    const activityModel = 94 - i * 0.08 + randBetween(-1, 1);
    const medicationModel = 91 - i * 0.05 + randBetween(-1, 1);
    const avg = (fallModel + acousticModel + activityModel + medicationModel) / 4;
    data.push({
      date: d.toISOString().split('T')[0],
      fallModel: +fallModel.toFixed(1),
      acousticModel: +acousticModel.toFixed(1),
      activityModel: +activityModel.toFixed(1),
      medicationModel: +medicationModel.toFixed(1),
      avgConfidence: +avg.toFixed(1),
      driftAlert: avg < 85,
    });
  }
  return data;
}

// ─── 31. Medication Confusion Loops ──────────────────────────────────────────

export function getMedicationConfusionLoops(): MedicationConfusionLoop[] {
  const loops: MedicationConfusionLoop[] = [];
  const meds = ['Metformin 500mg', 'Lisinopril 10mg', 'Atorvastatin 20mg', 'Aspirin 75mg'];
  RESIDENTS.forEach((r) => {
    const count = randInt(0, 4);
    for (let i = 0; i < count; i++) {
      loops.push({
        date: new Date(Date.now() - randInt(0, 7) * 86400000).toISOString().split('T')[0],
        residentId: r.resident_id,
        residentName: r.name,
        openCloseCycles: randInt(2, 6),
        durationSeconds: randInt(30, 180),
        medicationName: meds[randInt(0, meds.length - 1)],
        resolved: Math.random() > 0.3,
      });
    }
  });
  return loops.sort((a, b) => b.date.localeCompare(a.date));
}

// ─── 32. Sleep Metrics ───────────────────────────────────────────────────────

export function getSleepMetrics(residentId?: string): SleepMetrics[] {
  const data: SleepMetrics[] = [];
  for (let i = 14; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000);
    const quality = randInt(40, 95);
    const deep = +(randBetween(10, 30).toFixed(1));
    const rem = +(randBetween(15, 28).toFixed(1));
    data.push({
      date: d.toISOString().split('T')[0],
      qualityScore: quality,
      totalSleepMinutes: randInt(300, 540),
      deepSleepPct: deep,
      remSleepPct: rem,
      lightSleepPct: +(Math.max(0, 100 - deep - rem - randBetween(5, 15)).toFixed(1)),
      bedExits: randInt(0, 5),
      apneaEvents: randInt(0, 12),
      sleepEfficiency: +(randBetween(65, 95).toFixed(1)),
      fragmentationIndex: +(randBetween(0.05, 0.4).toFixed(3)),
    });
  }
  return data;
}

// ─── 33. Respiratory Metrics ─────────────────────────────────────────────────

export function getRespiratoryMetrics(residentId?: string): RespiratoryMetrics[] {
  const data: RespiratoryMetrics[] = [];
  for (let i = 14; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000);
    data.push({
      date: d.toISOString().split('T')[0],
      respiratoryScore: randInt(60, 100),
      coughCount: randInt(0, 20),
      coughPerHour: +(randBetween(0, 4).toFixed(1)),
      wheezingEpisodes: randInt(0, 5),
      avgBreathingRate: +(randBetween(12, 22).toFixed(1)),
      avgSpO2: +(randBetween(93, 99).toFixed(1)),
      minSpO2: +(randBetween(88, 97).toFixed(1)),
    });
  }
  return data;
}
