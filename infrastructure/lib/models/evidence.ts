import { Severity, AetherEvent } from "./events";

export interface PoseKeypoint {
  x: number;
  y: number;
  confidence: number;
  keypoint_type: string;
}

export interface CheckInResponse {
  timestamp: number;
  question: string;
  response: string;
  sentiment: number;
  extracted_data: {
    pain_score?: number;
    sleep_quality?: number;
    mood?: string;
    hydration?: boolean;
  };
}

export interface EvidencePacket {
  packet_id: string;
  event_id: string;
  home_id: string;
  resident_id: string;
  timestamp: number;
  event_summary: string;
  severity: Severity;
  sensor_data: {
    imu?: {
      acceleration: { x: number; y: number; z: number }[];
      gyroscope: { x: number; y: number; z: number }[];
      sampling_rate: number;
      duration: number;
    };
    acoustic?: {
      features: {
        mfcc: number[];
        spectral_centroid: number;
        spectral_rolloff: number;
        zero_crossing_rate: number;
        rms_energy: number;
      };
      ambient_level: number;
      event_type: string;
    };
    pose?: {
      keypoints: PoseKeypoint[][];
      fall_pattern: boolean;
      confidence: number;
    };
  };
  recent_events: AetherEvent[];
  recent_check_ins: CheckInResponse[];
  medication_adherence_24h: number;
  activity_summary_24h: string;
  ai_insights: {
    triage_card: string;
    recommended_actions: string[];
    risk_assessment: "low" | "medium" | "high" | "critical";
    confidence: number;
  };
  device_status: {
    battery_levels: { [device_id: string]: number };
    signal_quality: { [device_id: string]: number };
    last_seen: { [device_id: string]: number };
  };
  created_at: number;
  s3_url: string;
}
