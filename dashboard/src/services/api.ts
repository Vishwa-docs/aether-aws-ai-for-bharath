/**
 * AETHER CareOps — API Service Layer
 * ====================================
 * Connects the dashboard to the FastAPI backend via Vite proxy.
 * All /api/* calls are proxied to the backend server.
 */

const API_BASE = '/api';

// ─── Generic API caller ────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  timeoutMs = 10000,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
    });

    clearTimeout(timer);

    if (!res.ok) {
      throw new Error(`API error: ${res.status} ${res.statusText}`);
    }

    return (await res.json()) as T;
  } catch (err) {
    clearTimeout(timer);
    throw err;
  }
}

// ─── Residents ─────────────────────────────────────────────────────────

export interface ApiResident {
  resident_id: string;
  home_id: string;
  name: string;
  age: number;
  gender: string;
  photo_url?: string;
  medical_conditions: string[];
  medications: Array<{
    name: string;
    dosage: string;
    timing: string[];
    frequency: string;
  }>;
  emergency_contacts: Array<{
    name: string;
    relationship: string;
    phone: string;
    is_primary: boolean;
  }>;
  mobility_level: string;
  cognitive_status: string;
  fall_risk_score: number;
  privacy_level: string;
  status: string;
  created_at: string;
}

export async function fetchResidents(): Promise<ApiResident[]> {
  const data = await apiFetch<{ residents: ApiResident[] }>('/residents');
  return data.residents;
}

export async function fetchResident(id: string): Promise<ApiResident> {
  return apiFetch<ApiResident>(`/residents/${id}`);
}

// ─── Events ────────────────────────────────────────────────────────────

export interface ApiEvent {
  event_id: string;
  home_id: string;
  resident_id: string;
  event_type: string;
  severity: string;
  timestamp: number;
  timestamp_iso: string;
  confidence: number | string;
  source_sensors: string[];
  privacy_level: string;
  data: Record<string, unknown>;
}

export async function fetchEvents(homeId: string, limit = 50): Promise<ApiEvent[]> {
  const data = await apiFetch<{ events: ApiEvent[] }>(`/events?home_id=${homeId}&limit=${limit}`);
  return data.events;
}

export async function createEvent(event: {
  home_id: string;
  resident_id: string;
  event_type: string;
  severity: string;
  data?: Record<string, unknown>;
  confidence?: number;
  source_sensors?: string[];
}): Promise<{ event_id: string }> {
  return apiFetch<{ event_id: string }>('/events', {
    method: 'POST',
    body: JSON.stringify(event),
  });
}

// ─── Timeline ──────────────────────────────────────────────────────────

export interface ApiTimelineEntry {
  home_id: string;
  date: string;
  total_events: number;
  fall_count: number;
  medication_adherence_pct: number;
  sleep_hours: number;
  steps: number;
  mood_score: number;
  daily_summary: string;
}

export async function fetchTimeline(homeId: string, days = 14): Promise<ApiTimelineEntry[]> {
  const data = await apiFetch<{ entries: ApiTimelineEntry[] }>(`/timeline/${homeId}?days=${days}`);
  return data.entries;
}

// ─── Dashboard Stats ───────────────────────────────────────────────────

export interface ApiDashboardStats {
  total_residents: number;
  residents: ApiResident[];
  active_alerts: number;
  pending_tasks: number;
  sensor_health: number;
  generated_at: string;
}

export async function fetchDashboardStats(): Promise<ApiDashboardStats> {
  return apiFetch<ApiDashboardStats>('/dashboard');
}

// ─── Analytics ─────────────────────────────────────────────────────────

export interface ApiAnalytics {
  home_id: string;
  period: string;
  total_events: number;
  total_falls: number;
  avg_adherence: number;
  daily: ApiTimelineEntry[];
}

export async function fetchAnalytics(homeId: string, period = '7d'): Promise<ApiAnalytics> {
  return apiFetch<ApiAnalytics>(`/analytics?home_id=${homeId}&period=${period}`);
}

// ─── Care Navigation (Bedrock AI) ──────────────────────────────────────

export interface CareNavResponse {
  response: string;
  action_tier: 'self_care' | 'gp_visit' | 'urgent_care' | 'emergency';
  citations: string[];
  follow_up_tasks: string[];
  confidence: number;
  safety_note: string;
  ai_model: string;
  source: string;
}

export async function queryCareNavigation(params: {
  query: string;
  resident_id?: string;
  language?: string;
}): Promise<CareNavResponse> {
  return apiFetch<CareNavResponse>('/care-navigation/query', {
    method: 'POST',
    body: JSON.stringify(params),
  }, 30000);
}

// ─── Clinical Document Generation (Bedrock AI) ────────────────────────

export interface DocGenResponse {
  document_id: string;
  doc_type: string;
  content: string;
  generated_at: string;
  ai_model: string;
  review_status: string;
  resident_id: string;
  source: string;
}

export async function generateDocument(params: {
  doc_type: 'soap_note' | 'daily_summary' | 'weekly_report' | 'pre_consult' | 'incident_report';
  resident_id: string;
}): Promise<DocGenResponse> {
  return apiFetch<DocGenResponse>('/documents/generate', {
    method: 'POST',
    body: JSON.stringify(params),
  }, 30000);
}

// ─── Voice / AI Companion ──────────────────────────────────────────────

export interface VoiceSessionResponse {
  session_id: string;
  response_text: string;
  sentiment: string;
  mood_score: number;
  follow_up_needed: boolean;
  insights: string[];
  session_type: string;
  ai_model: string;
  source: string;
}

export async function voiceSession(params: {
  resident_id: string;
  session_type: 'daily_checkin' | 'companion' | 'medication_reminder' | 'emergency_check';
  message?: string;
  language?: string;
}): Promise<VoiceSessionResponse> {
  return apiFetch<VoiceSessionResponse>('/voice/session', {
    method: 'POST',
    body: JSON.stringify(params),
  }, 30000);
}

// ─── Polypharmacy Check (Bedrock AI) ───────────────────────────────────

export interface PolypharmacyResponse {
  interactions: Array<{
    drug1: string;
    drug2: string;
    severity: string;
    description: string;
  }>;
  beers_criteria_flags: string[];
  risk_score: number;
  recommendations: string[];
  contraindications: string[];
  summary: string;
  ai_model: string;
  source: string;
}

export async function checkPolypharmacy(params: {
  medications: Array<{ name: string; dosage: string; frequency: string }>;
  conditions: string[];
  age: number;
}): Promise<PolypharmacyResponse> {
  return apiFetch<PolypharmacyResponse>('/polypharmacy/check', {
    method: 'POST',
    body: JSON.stringify(params),
  }, 30000);
}

// ─── Health Insights (Bedrock AI) ──────────────────────────────────────

export interface HealthInsightsResponse {
  overall_status: 'green' | 'yellow' | 'red';
  risk_score: number;
  domain_scores?: Record<string, number>;
  trends?: Record<string, string>;
  insights: string[];
  alerts?: string[];
  recommendations: string[];
  drift_detection?: { detected: boolean; patterns: string[] };
  ai_model: string;
  source: string;
  resident_id: string;
}

export async function fetchHealthInsights(params: {
  resident_id: string;
  domains?: string[];
}): Promise<HealthInsightsResponse> {
  return apiFetch<HealthInsightsResponse>('/health-insights', {
    method: 'POST',
    body: JSON.stringify(params),
  }, 30000);
}

// ─── Escalation ────────────────────────────────────────────────────────

export interface EscalationResponse {
  escalation_id: string;
  tier: number;
  action: string;
  response_time: string;
  contact: string;
  reason: string;
  status: string;
  triggered_at: string;
}

export async function triggerEscalation(params: {
  event_id: string;
  home_id: string;
  tier: number;
  reason: string;
}): Promise<EscalationResponse> {
  return apiFetch<EscalationResponse>('/escalation/trigger', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ─── Alerts ────────────────────────────────────────────────────────────

export async function acknowledgeAlert(params: {
  event_id: string;
  acknowledged_by: string;
}): Promise<{ message: string }> {
  return apiFetch<{ message: string }>('/alerts/acknowledge', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ─── Simulation (Demo) ────────────────────────────────────────────────

export interface SimulationResponse {
  message: string;
  event_id: string;
  event_type: string;
  severity: string;
  resident_id: string;
  home_id: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export async function simulateEvent(params: {
  scenario: 'fall_detection' | 'medication_missed' | 'choking_detected' | 'wandering' | 'vital_anomaly';
  resident_id?: string;
}): Promise<SimulationResponse> {
  return apiFetch<SimulationResponse>('/simulate/event', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ─── Health Check ──────────────────────────────────────────────────────

export async function healthCheck(): Promise<{ status: string; service: string; region: string }> {
  return apiFetch<{ status: string; service: string; region: string }>('/health');
}
