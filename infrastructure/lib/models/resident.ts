export interface Medication {
  medication_id: string;
  name: string;
  custom_name?: string;
  dosage: string;
  schedule: {
    times: string[];  // ["08:00", "20:00"]
    days: string[];   // ["mon", "tue", ...]
  };
  critical: boolean;
  escalation_timeout: number;
  nfc_tag_id?: string;
}

export interface Contact {
  contact_id: string;
  name: string;
  relationship: string;
  phone: string;
  email?: string;
  escalation_tier: number;
  availability_schedule?: {
    [day: string]: { start: string; end: string }[];
  };
  notification_preferences: {
    sms: boolean;
    push: boolean;
    email: boolean;
    call: boolean;
  };
}

export type Language = "en" | "es" | "hi" | "kn" | "zh";

export interface BaselinePattern {
  mean: number;
  std_dev: number;
}

export interface ResidentProfile {
  resident_id: string;
  home_id: string;
  name: string;
  date_of_birth: string;
  language: Language;
  conditions: string[];
  medications: Medication[];
  allergies: string[];
  emergency_contacts: Contact[];
  baseline: {
    wake_time: BaselinePattern;
    sleep_time: BaselinePattern;
    meal_times: BaselinePattern[];
    activity_level: BaselinePattern;
    established_at: number;
    observation_days: number;
  };
  privacy: {
    acoustic_monitoring: boolean;
    camera_enabled: boolean;
    raw_audio_recording: boolean;
    data_retention_days: number;
    sensor_toggles: { [sensor_type: string]: boolean };
  };
  voice_profile?: {
    voice_id: string;
    trained_at: number;
    samples_count: number;
  };
  created_at: number;
  updated_at: number;
}
