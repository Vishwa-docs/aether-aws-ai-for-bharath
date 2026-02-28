// Event types enum
export enum EventType {
  FALL = "fall",
  FALL_WITH_IMMOBILITY = "fall_with_immobility",
  ACOUSTIC_DISTRESS = "acoustic_distress",
  GLASS_BREAK = "glass_break",
  PROLONGED_SILENCE = "prolonged_silence",
  IMPACT_SOUND = "impact_sound",
  MEDICATION_TAKEN = "medication_taken",
  MEDICATION_MISSED = "medication_missed",
  MEDICATION_CONFUSION = "medication_confusion",
  ROUTINE_DRIFT = "routine_drift",
  DECLINING_HEALTH = "declining_health",
  RESPIRATORY_CONCERN = "respiratory_concern",
  MISSED_DOORBELL = "missed_doorbell",
  SYSTEM_HEALTH = "system_health",
}

export enum Severity {
  CRITICAL = "critical",
  HIGH = "high",
  MEDIUM = "medium",
  LOW = "low",
}

// Source sensor reference
export interface SensorSource {
  sensor_id: string;
  sensor_type: string;
  confidence: number;
}

// Escalation tracking
export interface EscalationInfo {
  tier: number;
  notified: string[];
  acknowledged_by?: string;
  acknowledged_at?: number;
  resolved_at?: number;
}

// Base Event interface — matches DynamoDB schema
export interface AetherEvent {
  event_id: string;
  home_id: string;          // partition key
  timestamp: number;        // sort key (Unix epoch ms)
  event_type: EventType;
  severity: Severity;
  confidence: number;       // 0.0 - 1.0
  resident_id?: string;
  data: Record<string, any>;
  sources: SensorSource[];
  escalation?: EscalationInfo;
  evidence_packet_url?: string;
  created_at: number;
  updated_at: number;
  ttl?: number;
}

// Fall-specific event data
export interface FallEventData {
  imu_impact_force?: number;
  imu_confidence?: number;
  pose_fall_detected?: boolean;
  pose_confidence?: number;
  acoustic_impact?: boolean;
  acoustic_confidence?: number;
  fused_confidence: number;
  immobility_duration?: number;
  voice_check_in_response?: "okay" | "help" | "no_response";
  room?: string;
  coordinates?: { x: number; y: number };
}

// Medication-specific event data
export interface MedicationEventData {
  medication_id: string;
  medication_name: string;
  custom_name?: string;
  scheduled_time: number;
  actual_time?: number;
  status: "taken" | "missed" | "late" | "confused";
  confirmation_method: "voice" | "sensor" | "manual";
  nfc_tag_id?: string;
  removal_detected: boolean;
  critical: boolean;
  escalation_timeout: number;
  escalated: boolean;
}

// Acoustic-specific event data
export interface AcousticEventData {
  acoustic_type: "scream" | "glass_break" | "impact" | "cough" | "doorbell" | "phone_ring" | "silence";
  confidence: number;
  features: {
    mfcc: number[];
    spectral_centroid: number;
    spectral_rolloff: number;
    zero_crossing_rate: number;
    rms_energy: number;
  };
  sentinel_id: string;
  room: string;
  correlated_with?: string[];
}
