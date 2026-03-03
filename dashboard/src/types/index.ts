// ──────────────────────────────────────────────
// AETHER Type Definitions
// ──────────────────────────────────────────────

// ─── User / Auth ──────────────────────────────

export type UserRole = 'elder' | 'caregiver' | 'doctor' | 'ops';

export interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  avatar?: string;
  phone?: string;
  assignedResidents?: string[];
  specialization?: string; // for doctors
  sites?: string[]; // for ops
}

// ─── Core Enums ───────────────────────────────

export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

export type EventType =
  | 'fall_detected'
  | 'medication_taken'
  | 'medication_missed'
  | 'medication_late'
  | 'acoustic_scream'
  | 'acoustic_glass_break'
  | 'acoustic_impact'
  | 'acoustic_silence'
  | 'routine_anomaly'
  | 'vital_alert'
  | 'check_in_completed'
  | 'environmental_alert'
  | 'cognitive_decline'
  | 'nutrition_concern'
  | 'scam_alert'
  | 'emotional_concern'
  | 'bathroom_anomaly'
  | 'choking'
  | 'gait_degradation'
  | 'sleep_disruption';

export type EscalationTier = 'TIER_1' | 'TIER_2' | 'TIER_3' | 'TIER_4';

export type SensorType =
  | 'imu'
  | 'acoustic'
  | 'pose'
  | 'medication'
  | 'vital'
  | 'environmental'
  | 'toilet'
  | 'temperature'
  | 'humidity'
  | 'air_quality'
  | 'smoke'
  | 'co'
  | 'light'
  | 'noise';

// ─── Core Event / Resident ────────────────────

export interface AetherEvent {
  event_id: string;
  home_id: string;
  resident_id: string;
  event_type: EventType;
  severity: Severity;
  timestamp: number;
  confidence: number;
  source_sensors: SensorType[];
  privacy_level: string;
  data: Record<string, unknown>;
  evidence_packet_id?: string;
  acknowledged?: boolean;
  acknowledged_by?: string;
  acknowledged_at?: number;
}

export interface Resident {
  resident_id: string;
  home_id: string;
  name: string;
  age: number;
  photo_url?: string;
  conditions: string[];
  medications: Medication[];
  emergency_contacts: EmergencyContact[];
  privacy_level: string;
  status: 'active' | 'inactive';
  last_activity?: number;
  risk_score?: number;
}

export interface Medication {
  name: string;
  dosage: string;
  schedule: string[];
  nfc_tag_id?: string;
}

export interface EmergencyContact {
  name: string;
  relationship: string;
  phone: string;
  is_primary: boolean;
}

// ─── Timeline ─────────────────────────────────

export interface TimelineEntry {
  home_id: string;
  date: string;
  events: AetherEvent[];
  summary: string;
  metrics: DailyMetrics;
}

export interface DailyMetrics {
  total_events: number;
  fall_count: number;
  medication_adherence: number;
  activity_score: number;
  acoustic_events: number;
  avg_confidence: number;
}

// ─── Dashboard / Alerts ───────────────────────

export interface DashboardStats {
  total_residents: number;
  active_alerts: number;
  events_today: number;
  avg_response_time: number;
  medication_adherence: number;
  system_uptime: number;
  sensors_online: number;
  sensors_total: number;
}

export interface AlertNotification {
  id: string;
  event: AetherEvent;
  resident: Resident;
  escalation_tier: EscalationTier;
  created_at: number;
  is_active: boolean;
  response_time?: number;
}

// ─── Analytics ────────────────────────────────

export interface AnalyticsData {
  period: string;
  events_by_type: Record<EventType, number>;
  events_by_severity: Record<Severity, number>;
  daily_trends: DailyTrend[];
  response_times: ResponseTimeData[];
  medication_trends: MedicationTrend[];
  sensor_health: SensorHealth[];
}

export interface DailyTrend {
  date: string;
  total_events: number;
  falls: number;
  medications: number;
  acoustic: number;
  activity_score: number;
}

export interface ResponseTimeData {
  date: string;
  avg_seconds: number;
  min_seconds: number;
  max_seconds: number;
}

export interface MedicationTrend {
  date: string;
  adherence_pct: number;
  taken: number;
  missed: number;
  late: number;
}

export interface SensorHealth {
  sensor_id: string;
  type: SensorType;
  room: string;
  status: 'online' | 'offline' | 'degraded';
  battery_pct?: number;
  last_seen: number;
  signal_quality: number;
}

// ─── Escalation ───────────────────────────────

export interface EscalationState {
  event_id: string;
  current_tier: EscalationTier;
  started_at: number;
  history: EscalationStep[];
}

export interface EscalationStep {
  tier: EscalationTier;
  timestamp: number;
  action: string;
  result?: string;
}

// ─── Care Navigation ─────────────────────────

export interface CareNavigationQuery {
  id: string;
  residentId: string;
  query: string;
  response: string;
  actionTier: 'self_care' | 'gp_visit' | 'urgent_care' | 'emergency';
  sources: string[];
  isOffline: boolean;
  followUpTask?: string;
  timestamp: number;
  language: string;
}

// ─── Clinical Documents ──────────────────────

export interface ClinicalDocument {
  id: string;
  residentId: string;
  type: 'soap_note' | 'daily_summary' | 'weekly_summary' | 'incident_report' | 'pre_consult';
  status: 'draft' | 'pending_review' | 'approved' | 'exported';
  content: string;
  generatedAt: number;
  reviewedBy?: string;
  approvedAt?: number;
  exportedAt?: number;
  version: number;
  aiConfidence: number;
}

// ─── Fleet / Ops ──────────────────────────────

export interface EdgeGateway {
  id: string;
  siteId: string;
  siteName: string;
  status: 'online' | 'offline' | 'degraded';
  uptime: number;
  lastHeartbeat: number;
  firmwareVersion: string;
  connectedSensors: number;
  totalSensors: number;
  cpuUsage: number;
  memoryUsage: number;
  networkLatency: number;
}

export interface SiteHealth {
  siteId: string;
  siteName: string;
  city: string;
  totalResidents: number;
  activeAlerts: number;
  gatewayStatus: 'healthy' | 'degraded' | 'critical';
  slaResponseTime: number; // seconds
  slaTarget: number;
  sensorCoverage: number; // percentage
  lastIncident?: number;
}

// ─── Health Profile ───────────────────────────

export interface HealthDomain {
  name: string;
  score: number; // 0-100
  trend: 'improving' | 'stable' | 'declining';
  lastUpdated: number;
}

export interface HealthProfile {
  residentId: string;
  overallScore: number;
  domains: HealthDomain[];
  riskFactors: string[];
  recommendations: string[];
}

// ─── Prescriptions ────────────────────────────

export interface Prescription {
  id: string;
  residentId: string;
  doctorName: string;
  date: number;
  medications: PrescribedMedication[];
  interactions: DrugInteraction[];
  status: 'pending_review' | 'approved' | 'flagged';
  ocrConfidence: number;
  sourceDocUrl?: string;
}

export interface PrescribedMedication {
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  notes?: string;
}

export interface DrugInteraction {
  drugA: string;
  drugB: string;
  severity: 'minor' | 'moderate' | 'severe' | 'contraindicated';
  description: string;
  recommendation: string;
}

// ─── Service Bookings ─────────────────────────

export interface ServiceBooking {
  id: string;
  residentId: string;
  type: 'transport' | 'food_order' | 'appointment' | 'shopping';
  status: 'requested' | 'confirmed' | 'in_progress' | 'completed' | 'cancelled';
  details: Record<string, any>;
  requestedAt: number;
  estimatedTime?: number;
  cost?: number;
  isDemoOnly: boolean;
}

// ─── Family / Calendar ────────────────────────

export interface CalendarEvent {
  id: string;
  title: string;
  type: 'medication' | 'appointment' | 'transport' | 'visit' | 'activity';
  datetime: number;
  duration?: number;
  participants: string[];
  recurrence?: 'daily' | 'weekly' | 'monthly';
  reminders: number[]; // minutes before
  notes?: string;
}

export interface CareHandoff {
  id: string;
  fromCaregiver: string;
  toCaregiver: string;
  timestamp: number;
  checklist: HandoffItem[];
  notes: string;
  pendingTasks: string[];
}

export interface HandoffItem {
  task: string;
  completed: boolean;
  priority: 'high' | 'medium' | 'low';
}

// ─── Education ────────────────────────────────

export interface MicroLesson {
  id: string;
  title: string;
  category: string;
  content: string;
  duration: number; // minutes
  completedBy: string[];
  teachBackRequired: boolean;
  teachBackCompleted: boolean;
}

// ─── Consent ──────────────────────────────────

export interface ConsentSettings {
  residentId: string;
  dataTypes: ConsentDataType[];
  retentionDays: number;
  exportRequests: ExportRequest[];
}

export interface ConsentDataType {
  type: string;
  allowedViewers: string[];
  enabled: boolean;
}

export interface ExportRequest {
  id: string;
  requestedAt: number;
  status: 'pending' | 'processing' | 'completed';
  format: 'pdf' | 'json' | 'csv';
}

// ─── Caregiver Burnout ────────────────────────

export interface CaregiverWorkload {
  caregiverId: string;
  name: string;
  shift: string;
  alertsHandled: number;
  avgResponseTime: number;
  hoursWorked: number;
  burnoutScore: number; // 0-100
  lastBreak?: number;
}

// ─── Escalation Funnel ───────────────────────

export interface EscalationFunnel {
  detected: number;
  verified: number;
  caregiverAcknowledged: number;
  resolved: number;
  autoEscalated: number;
}

// ─── Risk Trends ──────────────────────────────

export interface RiskTrendPoint {
  date: string;
  mobility: number;
  sleep: number;
  hydration: number;
  medicationAdherence: number;
  mood: number;
  cognitive: number;
  respiratory: number;
}

// ─── Command Center ──────────────────────────

export interface CommandCenterData {
  criticalAlerts: AetherEvent[];
  unresolvedMeds: number;
  pendingApprovals: number;
  connectivityIncidents: number;
  lastUpdated: number;
}

// ─── False Positive Rates ────────────────────

export interface FalsePositiveRate {
  date: string;
  fallDetection: number;
  medicationAlert: number;
  acousticAlert: number;
  environmentalAlert: number;
  overallRate: number;
}

// ─── Model Confidence Drift ──────────────────

export interface ModelConfidenceDrift {
  date: string;
  fallModel: number;
  acousticModel: number;
  activityModel: number;
  medicationModel: number;
  avgConfidence: number;
  driftAlert: boolean;
}

// ─── Medication Confusion Loop ───────────────

export interface MedicationConfusionLoop {
  date: string;
  residentId: string;
  residentName: string;
  openCloseCycles: number;
  durationSeconds: number;
  medicationName: string;
  resolved: boolean;
}

// ─── Sleep Metrics ───────────────────────────

export interface SleepMetrics {
  date: string;
  qualityScore: number;
  totalSleepMinutes: number;
  deepSleepPct: number;
  remSleepPct: number;
  lightSleepPct: number;
  bedExits: number;
  apneaEvents: number;
  sleepEfficiency: number;
  fragmentationIndex: number;
}

// ─── Respiratory Metrics ─────────────────────

export interface RespiratoryMetrics {
  date: string;
  respiratoryScore: number;
  coughCount: number;
  coughPerHour: number;
  wheezingEpisodes: number;
  avgBreathingRate: number;
  avgSpO2: number;
  minSpO2: number;
}
