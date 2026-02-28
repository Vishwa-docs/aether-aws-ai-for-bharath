import { AetherEvent } from "./events";

export interface TimelineMetrics {
  total_events: number;
  falls: number;
  medication_adherence_rate: number;
  activity_level: number;
  sleep_duration: number;
  check_in_mood_score: number;
}

export interface TimelineEntry {
  home_id: string;
  date: string;  // YYYY-MM-DD
  events: AetherEvent[];
  metrics: TimelineMetrics;
  summary: string;
  concerns: string[];
  created_at: number;
  updated_at: number;
}
