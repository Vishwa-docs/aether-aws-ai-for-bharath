import { useMemo, useState } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  Users,
  Bell,
  Activity,
  Timer,
  Pill,
  Cpu,
  TrendingUp,
  TrendingDown,
  ShieldCheck,
  Clock,
  ChevronRight,
  Sun,
  Phone,
  MessageCircle,
  Heart,
  Moon,
  Smile,
  Thermometer,
  Wind,
  Stethoscope,
  FileText,
  Video,
  AlertTriangle,
  Server,
  Wifi,
  BarChart3,
  DollarSign,
  ClipboardList,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  CheckCircle,
} from 'lucide-react';
import { formatDistanceToNow, format, parseISO } from 'date-fns';

import {
  DASHBOARD_STATS,
  RESIDENTS,
  MOCK_EVENTS,
  ESCALATION_FUNNEL,
  RISK_TRENDS,
  HEALTH_PROFILES,
  CLINICAL_DOCUMENTS,
  PRESCRIPTIONS,
  CALENDAR_EVENTS,
  EDGE_GATEWAYS,
  SITE_HEALTH_DATA,
  CAREGIVER_WORKLOAD,
  getRecentEvents,
  getActiveAlerts,
  getDailyTrends,
  getEnvironmentalReadings,
  getMedicationConfusionLoops,
} from '../data/mockData';
import StatusBadge from '../components/StatusBadge';
import EventIcon from '../components/EventIcon';
import { useAuth } from '../contexts/AuthContext';
import type { AetherEvent, AlertNotification, Resident, RiskTrendPoint } from '../types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtEventType(type: string): string {
  return type.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

function residentById(id: string): Resident | undefined {
  return RESIDENTS.find((r) => r.resident_id === id);
}

function timeAgo(ts: number): string {
  return formatDistanceToNow(new Date(ts), { addSuffix: true });
}

function riskBarColor(score: number): string {
  if (score < 0.3) return 'bg-emerald-500';
  if (score <= 0.6) return 'bg-amber-400';
  return 'bg-red-500';
}

function riskText(score: number): string {
  if (score < 0.3) return 'text-emerald-600';
  if (score <= 0.6) return 'text-amber-600';
  return 'text-red-600';
}

const PIE_COLORS = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6'];

// ─── Shared Components ────────────────────────────────────────────────────────

interface StatCardProps {
  label: string;
  value: string | number;
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  subtitle?: string;
  pulse?: boolean;
  trend?: 'up' | 'down' | 'flat';
  children?: React.ReactNode;
}

function StatCard({ label, value, icon: Icon, iconBg, iconColor, subtitle, pulse, trend, children }: StatCardProps) {
  return (
    <div className="relative overflow-hidden rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200/60 transition-all duration-200 hover:shadow-md hover:ring-gray-300/80">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-gray-500 truncate">{label}</p>
          <div className="mt-1.5 flex items-baseline gap-2">
            <p className="text-2xl font-bold tracking-tight text-gray-900">{value}</p>
            {trend === 'up' && <ArrowUpRight size={16} className="text-emerald-500" />}
            {trend === 'down' && <ArrowDownRight size={16} className="text-red-500" />}
            {trend === 'flat' && <Minus size={14} className="text-gray-400" />}
          </div>
          {subtitle && <p className="mt-0.5 text-[11px] text-gray-400">{subtitle}</p>}
          {children}
        </div>
        <div className="relative ml-3">
          {pulse && <span className="absolute -inset-1 rounded-xl animate-ping opacity-20 bg-red-400" />}
          <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconBg}`}>
            <Icon className={iconColor} size={20} strokeWidth={2} />
          </div>
        </div>
      </div>
    </div>
  );
}

function MiniProgress({ value, max = 100, color = 'bg-blue-500' }: { value: number; max?: number; color?: string }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="mt-1.5 h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
      <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function SectionCard({ title, subtitle, children, className = '' }: { title: string; subtitle?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60 ${className}`}>
      <div className="mb-4">
        <h2 className="text-base font-semibold text-gray-900">{title}</h2>
        {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const isDate = typeof label === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(label);
  return (
    <div className="rounded-xl border border-gray-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur-sm">
      <p className="mb-2 text-xs font-semibold text-gray-500">
        {isDate ? format(parseISO(label), 'EEE, MMM d') : label}
      </p>
      {payload.map((entry: any) => (
        <div key={entry.name} className="flex items-center gap-2 text-sm">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-gray-600">{entry.name}:</span>
          <span className="font-semibold text-gray-900">{typeof entry.value === 'number' ? entry.value.toFixed(1) : entry.value}</span>
        </div>
      ))}
    </div>
  );
}

function EventRow({ event }: { event: AetherEvent }) {
  const resident = residentById(event.resident_id);
  return (
    <div className="group flex items-center gap-4 rounded-xl px-4 py-3 transition-colors hover:bg-gray-50 cursor-pointer">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-50 ring-1 ring-gray-200/80 group-hover:ring-gray-300">
        <EventIcon eventType={event.event_type} size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800 truncate">{fmtEventType(event.event_type)}</span>
          <StatusBadge severity={event.severity} size="sm" />
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-gray-400">
          <span className="truncate font-medium text-gray-500">{resident?.name ?? 'Unknown'}</span>
          <span>·</span>
          <span>{timeAgo(event.timestamp)}</span>
        </div>
      </div>
      <div className="hidden sm:flex flex-col items-end gap-0.5 shrink-0">
        <span className="text-[10px] font-medium text-gray-400">{(event.confidence * 100).toFixed(0)}%</span>
        <div className="h-1 w-16 rounded-full bg-gray-100 overflow-hidden">
          <div className="h-full rounded-full bg-blue-500 transition-all" style={{ width: `${event.confidence * 100}%` }} />
        </div>
      </div>
      <ChevronRight size={16} className="shrink-0 text-gray-300 group-hover:text-gray-500 transition-colors" />
    </div>
  );
}

function AlertCard({ alert, onAcknowledge }: { alert: AlertNotification; onAcknowledge: (id: string) => void }) {
  const tierColors: Record<string, string> = {
    TIER_1: 'bg-yellow-100 text-yellow-700', TIER_2: 'bg-orange-100 text-orange-700',
    TIER_3: 'bg-red-100 text-red-700', TIER_4: 'bg-red-200 text-red-800',
  };
  return (
    <div className="relative rounded-xl border border-red-200/60 bg-gradient-to-br from-red-50/60 to-white p-4 shadow-sm">
      <span className="absolute top-4 right-4 flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
        <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-red-500" />
      </span>
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100 text-sm font-bold text-red-600">
          {alert.resident.name.charAt(0)}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900 truncate">{alert.resident.name}</p>
          <p className="mt-0.5 text-xs text-gray-500">{fmtEventType(alert.event.event_type)}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${tierColors[alert.escalation_tier] ?? 'bg-gray-100 text-gray-600'}`}>
              {alert.escalation_tier.replace('_', ' ')}
            </span>
            <span className="text-[11px] text-gray-400 flex items-center gap-1"><Clock size={11} />{timeAgo(alert.created_at)}</span>
          </div>
          <button onClick={() => onAcknowledge(alert.id)} className="mt-3 w-full rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-red-700 active:scale-[0.98]">
            Acknowledge
          </button>
        </div>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
//  ELDER VIEW
// ═════════════════════════════════════════════════════════════════════════════

function ElderDashboard({ userName }: { userName: string }) {
  const firstName = userName.split(' ')[0];
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';

  const myResident = RESIDENTS[0]; // Elder's own profile
  const profile = HEALTH_PROFILES.find((h) => h.residentId === myResident.resident_id) ?? HEALTH_PROFILES[0];
  const envReadings = useMemo(() => getEnvironmentalReadings(), []);
  const myEnv = envReadings.find((r) => r.homeId === myResident.home_id && r.room === 'living_room');
  const myEvents = useMemo(() => getRecentEvents(myResident.home_id, 5), [myResident.home_id]);
  const todayCalendar = CALENDAR_EVENTS.filter((c) => {
    const d = new Date(c.datetime);
    const now = new Date();
    return d.toDateString() === now.toDateString();
  });

  const domainIcons: Record<string, React.ElementType> = {
    Mobility: Activity, Sleep: Moon, Mood: Smile,
    'Medication Adherence': Pill, Cognitive: Heart, Respiratory: Wind,
  };
  const trendIcon = (t: string) => t === 'improving' ? <ArrowUpRight size={14} className="text-emerald-500" /> : t === 'declining' ? <ArrowDownRight size={14} className="text-red-500" /> : <Minus size={12} className="text-gray-400" />;

  return (
    <>
      {/* Welcome */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">{greeting}, {firstName}!</h1>
        <p className="text-sm text-gray-500 mt-1">Here's your day · {format(new Date(), 'EEEE, MMM d, yyyy')}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Schedule + Quick Actions */}
        <div className="lg:col-span-2 space-y-6">
          {/* Today's Schedule */}
          <SectionCard title="Today's Schedule" subtitle={`${todayCalendar.length} items planned`}>
            {todayCalendar.length === 0 ? (
              <p className="text-sm text-gray-400 py-4 text-center">No scheduled events for today.</p>
            ) : (
              <div className="space-y-3">
                {todayCalendar.slice(0, 6).map((cal) => {
                  const calIcons: Record<string, React.ElementType> = { medication: Pill, appointment: Stethoscope, transport: Sun, visit: Users, activity: Activity };
                  const CalIcon = calIcons[cal.type] ?? Clock;
                  return (
                    <div key={cal.id} className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-gray-50 transition-colors">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50"><CalIcon size={16} className="text-blue-600" /></div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 truncate">{cal.title}</p>
                        <p className="text-xs text-gray-400">{format(new Date(cal.datetime), 'h:mm a')}{cal.duration ? ` · ${cal.duration} min` : ''}</p>
                      </div>
                      <span className="text-[10px] font-medium rounded-full px-2 py-0.5 bg-gray-100 text-gray-500 capitalize">{cal.type}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>

          {/* Health Summary */}
          <SectionCard title="My Health Summary" subtitle="Current wellness indicators">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
              {profile.domains.map((d) => {
                const DIcon = domainIcons[d.name] ?? Heart;
                const scoreColor = d.score >= 75 ? 'text-emerald-600' : d.score >= 50 ? 'text-amber-600' : 'text-red-600';
                const barColor = d.score >= 75 ? 'bg-emerald-500' : d.score >= 50 ? 'bg-amber-400' : 'bg-red-500';
                return (
                  <div key={d.name} className="rounded-xl border border-gray-100 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <DIcon size={18} className="text-gray-400" />
                      {trendIcon(d.trend)}
                    </div>
                    <p className="text-xs font-medium text-gray-500">{d.name}</p>
                    <p className={`text-xl font-bold ${scoreColor}`}>{d.score}<span className="text-xs font-normal text-gray-400">/100</span></p>
                    <div className="mt-2 h-1.5 w-full rounded-full bg-gray-100">
                      <div className={`h-full rounded-full ${barColor}`} style={{ width: `${d.score}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </SectionCard>

          {/* Recent Alerts */}
          <SectionCard title="Recent Activity" subtitle="Your latest events">
            <div className="divide-y divide-gray-50">
              {myEvents.map((ev) => <EventRow key={ev.event_id} event={ev} />)}
            </div>
          </SectionCard>
        </div>

        {/* Right Column: Quick Actions + Environmental + Chat */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <SectionCard title="Quick Actions">
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Check In', icon: CheckCircle, bg: 'bg-emerald-50 hover:bg-emerald-100', color: 'text-emerald-600' },
                { label: 'Take Medication', icon: Pill, bg: 'bg-violet-50 hover:bg-violet-100', color: 'text-violet-600' },
                { label: 'Call for Help', icon: Phone, bg: 'bg-red-50 hover:bg-red-100', color: 'text-red-600' },
                { label: 'Talk to Companion', icon: MessageCircle, bg: 'bg-blue-50 hover:bg-blue-100', color: 'text-blue-600' },
              ].map((a) => (
                <button key={a.label} className={`flex flex-col items-center gap-2 rounded-xl p-4 ${a.bg} transition-all active:scale-95`}>
                  <a.icon size={24} className={a.color} />
                  <span className={`text-xs font-semibold ${a.color}`}>{a.label}</span>
                </button>
              ))}
            </div>
          </SectionCard>

          {/* Environmental */}
          <SectionCard title="My Home" subtitle="Environmental readings">
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-gray-100 p-3 text-center">
                <Thermometer size={20} className="mx-auto text-orange-500 mb-1" />
                <p className="text-lg font-bold text-gray-900">{myEnv?.temperature ?? 26}°C</p>
                <p className="text-[10px] text-gray-400">Temperature</p>
              </div>
              <div className="rounded-xl border border-gray-100 p-3 text-center">
                <Wind size={20} className="mx-auto text-sky-500 mb-1" />
                <p className="text-lg font-bold text-gray-900">{myEnv?.aqi ?? 45}</p>
                <p className="text-[10px] text-gray-400">Air Quality</p>
              </div>
            </div>
          </SectionCard>

          {/* Companion Chat */}
          <SectionCard title="Companion Chat" subtitle="AI wellness companion">
            <div className="space-y-3">
              <div className="rounded-lg bg-blue-50 p-3">
                <p className="text-xs text-blue-800"><span className="font-semibold">AETHER:</span> Good morning, {firstName}! You slept 7.2 hours last night — that's great! Don't forget your Metformin at 8 AM. Would you like me to remind you?</p>
              </div>
              <div className="rounded-lg bg-gray-50 p-3">
                <p className="text-xs text-gray-700"><span className="font-semibold">You:</span> Yes please, and can you call Vikram later today?</p>
              </div>
              <div className="rounded-lg bg-blue-50 p-3">
                <p className="text-xs text-blue-800"><span className="font-semibold">AETHER:</span> Absolutely! I've set a reminder for your Metformin and I'll remind you to call Vikram at 4 PM. Have a wonderful day!</p>
              </div>
            </div>
            <button className="mt-3 w-full rounded-lg border border-blue-200 px-3 py-2 text-xs font-medium text-blue-600 hover:bg-blue-50 transition-colors">
              Open Companion Chat
            </button>
          </SectionCard>
        </div>
      </div>
    </>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
//  CAREGIVER VIEW
// ═════════════════════════════════════════════════════════════════════════════

function CaregiverDashboard() {
  const stats = DASHBOARD_STATS;
  const [trendWindow, setTrendWindow] = useState<7 | 30>(7);
  const trendData = useMemo(() => getDailyTrends(trendWindow), [trendWindow]);
  const recentEvents = useMemo(() => getRecentEvents(undefined, 10), []);
  const [alerts, setAlerts] = useState<AlertNotification[]>(() => getActiveAlerts());
  const handleAcknowledge = (id: string) => setAlerts((prev) => prev.filter((a) => a.id !== id));

  // Risk trend — aggregate average across all residents
  const riskTrendData = useMemo(() => {
    const allTrends = Object.values(RISK_TRENDS);
    if (allTrends.length === 0) return [];
    const len = Math.min(...allTrends.map((t) => t.length));
    const sliceStart = trendWindow === 7 ? Math.max(0, len - 7) : 0;
    const result: RiskTrendPoint[] = [];
    for (let i = sliceStart; i < len; i++) {
      const points = allTrends.map((t) => t[i]);
      result.push({
        date: points[0].date,
        mobility: +(points.reduce((s, p) => s + p.mobility, 0) / points.length).toFixed(1),
        sleep: +(points.reduce((s, p) => s + p.sleep, 0) / points.length).toFixed(1),
        hydration: +(points.reduce((s, p) => s + p.hydration, 0) / points.length).toFixed(1),
        medicationAdherence: +(points.reduce((s, p) => s + p.medicationAdherence, 0) / points.length).toFixed(1),
        mood: +(points.reduce((s, p) => s + p.mood, 0) / points.length).toFixed(1),
        cognitive: +(points.reduce((s, p) => s + p.cognitive, 0) / points.length).toFixed(1),
        respiratory: +(points.reduce((s, p) => s + p.respiratory, 0) / points.length).toFixed(1),
      });
    }
    return result;
  }, [trendWindow]);

  // Escalation funnel data
  const funnelData = useMemo(() => [
    { name: 'Detected', value: ESCALATION_FUNNEL.detected, fill: '#6366f1' },
    { name: 'Verified', value: ESCALATION_FUNNEL.verified, fill: '#8b5cf6' },
    { name: 'Acknowledged', value: ESCALATION_FUNNEL.caregiverAcknowledged, fill: '#f59e0b' },
    { name: 'Resolved', value: ESCALATION_FUNNEL.resolved, fill: '#22c55e' },
    { name: 'Auto-escalated', value: ESCALATION_FUNNEL.autoEscalated, fill: '#ef4444' },
  ], []);

  // Medication reliability per resident
  const medReliability = useMemo(() => {
    const confusionLoops = getMedicationConfusionLoops();
    return RESIDENTS.map((r) => {
      const resEvents = MOCK_EVENTS.filter((e) => e.resident_id === r.resident_id);
      const taken = resEvents.filter((e) => e.event_type === 'medication_taken').length;
      const missed = resEvents.filter((e) => e.event_type === 'medication_missed').length;
      const late = resEvents.filter((e) => e.event_type === 'medication_late').length;
      const loops = confusionLoops.filter((l) => l.residentId === r.resident_id).length;
      const total = taken + missed + late || 1;
      return {
        name: r.name.split(' ')[0],
        'On-time': +((taken / total) * 100).toFixed(0),
        Late: +((late / total) * 100).toFixed(0),
        Missed: +((missed / total) * 100).toFixed(0),
        'Confusion Loops': loops,
      };
    });
  }, []);

  // Event distribution for pie
  const eventDistribution = useMemo(() => {
    const counts: Record<string, number> = {};
    MOCK_EVENTS.forEach((e) => {
      const label = fmtEventType(e.event_type);
      counts[label] = (counts[label] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([name, value]) => ({ name, value }));
  }, []);

  const sensorPct = Math.round((stats.sensors_online / stats.sensors_total) * 100);

  return (
    <>
      {/* Header */}
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 shadow-sm">
          <ShieldCheck className="text-white" size={20} />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">AETHER Dashboard</h1>
          <p className="text-sm text-gray-500">Real-time elderly care monitoring · {format(new Date(), 'EEEE, MMM d, yyyy · h:mm a')}</p>
        </div>
      </div>

      {/* KPI Row (8 cards) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-4 gap-4">
        <StatCard label="Active Residents" value={stats.total_residents} icon={Users} iconBg="bg-blue-50" iconColor="text-blue-600" subtitle="Monitored homes" trend="up" />
        <StatCard label="Critical Alerts" value={alerts.length} icon={Bell} iconBg={alerts.length > 0 ? 'bg-red-50' : 'bg-emerald-50'} iconColor={alerts.length > 0 ? 'text-red-500' : 'text-emerald-500'} pulse={alerts.length > 0} subtitle={alerts.length > 0 ? 'Requires attention' : 'All clear'} />
        <StatCard label="Events Today" value={stats.events_today} icon={Activity} iconBg="bg-purple-50" iconColor="text-purple-600" subtitle="Across all homes" trend="flat" />
        <StatCard label="Avg Response (MTTA)" value={`${stats.avg_response_time}s`} icon={Timer} iconBg="bg-emerald-50" iconColor="text-emerald-600" subtitle="Last 24 hours" trend="down" />
      </div>
      <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-4 gap-4">
        <StatCard label="Medication Adherence" value={`${stats.medication_adherence}%`} icon={Pill} iconBg="bg-violet-50" iconColor="text-violet-600" subtitle="7-day average" trend="up">
          <MiniProgress value={stats.medication_adherence} color={stats.medication_adherence >= 90 ? 'bg-emerald-500' : 'bg-amber-400'} />
        </StatCard>
        <StatCard label="System Uptime" value={`${stats.system_uptime}%`} icon={Cpu} iconBg="bg-sky-50" iconColor="text-sky-600" subtitle="Current period" trend="flat" />
        <StatCard label="Sensors Online" value={`${stats.sensors_online}/${stats.sensors_total}`} icon={Wifi} iconBg="bg-teal-50" iconColor="text-teal-600" subtitle={`${sensorPct}% coverage`} trend={sensorPct >= 90 ? 'up' : 'down'}>
          <MiniProgress value={stats.sensors_online} max={stats.sensors_total} color={sensorPct >= 90 ? 'bg-emerald-500' : 'bg-amber-400'} />
        </StatCard>
        <StatCard label="Pending Tasks" value={CAREGIVER_WORKLOAD.reduce((s, w) => s + w.alertsHandled, 0)} icon={ClipboardList} iconBg="bg-orange-50" iconColor="text-orange-600" subtitle="Team total today" />
      </div>

      {/* Risk Trend Chart */}
      <div className="mt-6">
        <SectionCard title="Risk Trend Analysis" subtitle="Average health domain scores across residents">
          <div className="flex justify-end mb-2">
            <div className="inline-flex rounded-lg bg-gray-100 p-0.5">
              {([7, 30] as const).map((w) => (
                <button key={w} onClick={() => setTrendWindow(w)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${trendWindow === w ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
                  {w}D
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={riskTrendData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} tickFormatter={(v: string) => format(parseISO(v), 'MMM d')} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} domain={[0, 100]} />
              <Tooltip content={<ChartTooltip />} />
              <Legend verticalAlign="top" align="right" iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, paddingBottom: 8 }} />
              <Line type="monotone" dataKey="mobility" name="Mobility" stroke="#6366f1" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="sleep" name="Sleep" stroke="#8b5cf6" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="hydration" name="Hydration" stroke="#06b6d4" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="medicationAdherence" name="Medication" stroke="#22c55e" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="mood" name="Mood" stroke="#f59e0b" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </SectionCard>
      </div>

      {/* Row: Escalation Funnel + Medication Reliability */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SectionCard title="Escalation Funnel" subtitle="Event lifecycle — last 30 days">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={funnelData} layout="vertical" margin={{ top: 0, right: 20, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
              <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <YAxis dataKey="name" type="category" tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false} width={110} />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="value" name="Events" radius={[0, 6, 6, 0]}>
                {funnelData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>

        <SectionCard title="Medication Reliability" subtitle="By resident — on-time vs late vs missed (⟳ = confusion loops)">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={medReliability} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <YAxis yAxisId="pct" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} domain={[0, 100]} unit="%" />
              <YAxis yAxisId="loops" orientation="right" tick={{ fontSize: 11, fill: '#a855f7' }} tickLine={false} axisLine={false} domain={[0, 'auto']} />
              <Tooltip content={<ChartTooltip />} />
              <Legend verticalAlign="top" align="right" iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, paddingBottom: 8 }} />
              <Bar yAxisId="pct" dataKey="On-time" stackId="a" fill="#22c55e" radius={[0, 0, 0, 0]} />
              <Bar yAxisId="pct" dataKey="Late" stackId="a" fill="#f59e0b" />
              <Bar yAxisId="pct" dataKey="Missed" stackId="a" fill="#ef4444" radius={[4, 4, 0, 0]} />
              <Bar yAxisId="loops" dataKey="Confusion Loops" fill="#a855f7" radius={[4, 4, 0, 0]} barSize={14} />
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      </div>

      {/* Row: Activity Trend + Event Distribution Pie */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <SectionCard title="Activity Trends" subtitle={`Event breakdown — ${trendWindow}-day window`} className="lg:col-span-2">
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={trendData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="gTotal" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} /><stop offset="95%" stopColor="#6366f1" stopOpacity={0} /></linearGradient>
                <linearGradient id="gFalls" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#ef4444" stopOpacity={0.15} /><stop offset="95%" stopColor="#ef4444" stopOpacity={0} /></linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} tickFormatter={(v: string) => format(parseISO(v), 'MMM d')} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} allowDecimals={false} />
              <Tooltip content={<ChartTooltip />} />
              <Legend verticalAlign="top" align="right" iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, paddingBottom: 8 }} />
              <Area type="monotone" dataKey="total_events" name="Total Events" stroke="#6366f1" strokeWidth={2} fill="url(#gTotal)" dot={false} />
              <Area type="monotone" dataKey="medications" name="Medications" stroke="#22c55e" strokeWidth={1.5} fill="transparent" dot={false} />
              <Area type="monotone" dataKey="falls" name="Falls" stroke="#ef4444" strokeWidth={1.5} fill="url(#gFalls)" dot={false} />
              <Area type="monotone" dataKey="acoustic" name="Acoustic" stroke="#f59e0b" strokeWidth={1.5} fill="transparent" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </SectionCard>

        <SectionCard title="Event Distribution" subtitle="By type — last 7 days">
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={eventDistribution} cx="50%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={3} dataKey="value" nameKey="name" label={({ name, percent }) => `${name.split(' ')[0]} ${(percent * 100).toFixed(0)}%`} labelLine={false} style={{ fontSize: 10 }}>
                {eventDistribution.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </SectionCard>
      </div>

      {/* Row: Events Feed + Active Alerts */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60">
          <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
            <div>
              <h2 className="text-base font-semibold text-gray-900">Recent Events</h2>
              <p className="text-xs text-gray-400">Latest activity across all homes</p>
            </div>
            <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
              Live<span className="ml-1.5 h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            </span>
          </div>
          <div className="divide-y divide-gray-50 px-2 py-2">{recentEvents.map((ev) => <EventRow key={ev.event_id} event={ev} />)}</div>
        </div>
        <div className="space-y-4">
          <SectionCard title="Active Alerts" subtitle={`${alerts.length} requiring action`}>
            {alerts.length === 0 ? (
              <div className="flex flex-col items-center py-8 text-center">
                <ShieldCheck size={36} className="text-emerald-400 mb-2" />
                <p className="text-sm font-medium text-gray-600">All clear</p>
              </div>
            ) : (
              <div className="space-y-3">{alerts.map((a) => <AlertCard key={a.id} alert={a} onAcknowledge={handleAcknowledge} />)}</div>
            )}
          </SectionCard>
          <SectionCard title="Quick Links">
            <div className="space-y-2">
              {[
                { label: 'Residents', path: '/residents' },
                { label: 'Alerts', path: '/alerts' },
                { label: 'Analytics', path: '/analytics' },
                { label: 'Clinical Docs', path: '/clinical-docs' },
                { label: 'Care Navigation', path: '/care-navigation' },
              ].map((link) => (
                <a key={link.path} href={link.path} className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors">
                  {link.label}
                  <ChevronRight size={14} className="text-gray-400" />
                </a>
              ))}
            </div>
          </SectionCard>
        </div>
      </div>
    </>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
//  DOCTOR VIEW
// ═════════════════════════════════════════════════════════════════════════════

function DoctorDashboard() {
  const pendingReviews = CLINICAL_DOCUMENTS.filter((d) => d.status === 'pending_review');
  const todayConsults = CALENDAR_EVENTS.filter((c) => {
    const d = new Date(c.datetime);
    return d.toDateString() === new Date().toDateString() && c.type === 'appointment';
  });
  const flaggedPrescriptions = PRESCRIPTIONS.filter((p) => p.status === 'flagged' || p.interactions.some((i) => i.severity === 'severe' || i.severity === 'contraindicated'));
  const allInteractions = PRESCRIPTIONS.flatMap((p) => p.interactions.filter((i) => i.severity === 'severe' || i.severity === 'contraindicated'));

  return (
    <>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Clinical Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Patient overview · {format(new Date(), 'EEEE, MMM d, yyyy')}</p>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Assigned Patients" value={RESIDENTS.length} icon={Users} iconBg="bg-blue-50" iconColor="text-blue-600" subtitle="Active" />
        <StatCard label="Pending Reviews" value={pendingReviews.length} icon={FileText} iconBg="bg-amber-50" iconColor="text-amber-600" subtitle="Clinical docs" pulse={pendingReviews.length > 0} />
        <StatCard label="Today's Consults" value={todayConsults.length} icon={Video} iconBg="bg-indigo-50" iconColor="text-indigo-600" subtitle="Telehealth" />
        <StatCard label="Drug Interactions" value={allInteractions.length} icon={AlertTriangle} iconBg="bg-red-50" iconColor="text-red-500" subtitle="Severe/Contraindicated" pulse={allInteractions.length > 0} />
      </div>

      <div className="mt-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Patient Summary Cards */}
        <div className="lg:col-span-2 space-y-6">
          <SectionCard title="Patient Summary" subtitle="Key vitals and risk scores">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {RESIDENTS.map((r) => {
                const profile = HEALTH_PROFILES.find((h) => h.residentId === r.resident_id);
                const riskScore = r.risk_score ?? 0;
                return (
                  <div key={r.resident_id} className="rounded-xl border border-gray-100 p-4 hover:shadow-sm transition-all">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="relative">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-sm font-bold text-white shadow-sm">{r.name.charAt(0)}</div>
                        <span className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white ${r.status === 'active' ? 'bg-emerald-400' : 'bg-gray-300'}`} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-gray-900 truncate">{r.name}</p>
                        <p className="text-xs text-gray-400">Age {r.age} · {r.conditions.join(', ')}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <p className={`text-lg font-bold ${riskText(riskScore)}`}>{(riskScore * 100).toFixed(0)}%</p>
                        <p className="text-[10px] text-gray-400">Risk</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-gray-900">{profile?.overallScore ?? '—'}</p>
                        <p className="text-[10px] text-gray-400">Health</p>
                      </div>
                      <div>
                        <p className="text-lg font-bold text-gray-900">{r.medications.length}</p>
                        <p className="text-[10px] text-gray-400">Meds</p>
                      </div>
                    </div>
                    <div className="mt-2 h-1.5 w-full rounded-full bg-gray-100">
                      <div className={`h-full rounded-full ${riskBarColor(riskScore)}`} style={{ width: `${riskScore * 100}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </SectionCard>

          {/* Clinical Insights */}
          <SectionCard title="Clinical Insights" subtitle="AI-generated trends (via Amazon Bedrock)">
            <div className="space-y-3">
              {[
                { text: 'Margaret Sharma\'s fasting glucose trending upward (142 mg/dL today). Consider Metformin dose adjustment at next review.', severity: 'text-amber-600', bg: 'bg-amber-50' },
                { text: 'Rajesh Patel shows progressive gait degradation over 14 days — correlates with increased COPD exacerbation frequency. Refer to physiotherapy.', severity: 'text-red-600', bg: 'bg-red-50' },
                { text: 'Suresh Kumar\'s Levodopa response windows are narrowing (motor fluctuation increase detected by IMU). Consider CR formulation switch.', severity: 'text-amber-600', bg: 'bg-amber-50' },
                { text: 'Lakshmi Iyer maintaining excellent Warfarin adherence (100% 30-day). INR stable at 2.3 — no adjustment needed.', severity: 'text-emerald-600', bg: 'bg-emerald-50' },
              ].map((insight, i) => (
                <div key={i} className={`rounded-lg ${insight.bg} p-3`}>
                  <p className={`text-xs ${insight.severity}`}>{insight.text}</p>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* Pending Reviews */}
          <SectionCard title="Pending Reviews" subtitle={`${pendingReviews.length} documents`}>
            {pendingReviews.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">All caught up!</p>
            ) : (
              <div className="space-y-2">
                {pendingReviews.slice(0, 5).map((doc) => {
                  const resident = residentById(doc.residentId);
                  return (
                    <div key={doc.id} className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-gray-50 transition-colors cursor-pointer">
                      <FileText size={16} className="text-amber-500 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-800 truncate capitalize">{doc.type.replace(/_/g, ' ')}</p>
                        <p className="text-xs text-gray-400">{resident?.name ?? 'Unknown'} · AI conf: {(doc.aiConfidence * 100).toFixed(0)}%</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>

          {/* Today's Teleconsults */}
          <SectionCard title="Today's Teleconsults" subtitle="Scheduled telehealth">
            {todayConsults.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-4">No consults scheduled today</p>
            ) : (
              <div className="space-y-2">
                {todayConsults.map((c) => (
                  <div key={c.id} className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-gray-50 transition-colors">
                    <Video size={16} className="text-indigo-500 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{c.title}</p>
                      <p className="text-xs text-gray-400">{format(new Date(c.datetime), 'h:mm a')}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          {/* Drug Interaction Alerts */}
          <SectionCard title="Drug Interaction Alerts" subtitle="Flagged interactions">
            {allInteractions.length === 0 ? (
              <div className="flex flex-col items-center py-6"><CheckCircle size={28} className="text-emerald-400 mb-1" /><p className="text-sm text-gray-500">No severe interactions</p></div>
            ) : (
              <div className="space-y-2">
                {allInteractions.map((inter, i) => (
                  <div key={i} className="rounded-lg border border-red-100 bg-red-50/50 p-3">
                    <div className="flex items-center gap-2 mb-1">
                      <AlertTriangle size={14} className="text-red-500" />
                      <span className="text-xs font-bold text-red-700 uppercase">{inter.severity}</span>
                    </div>
                    <p className="text-xs text-gray-700"><span className="font-semibold">{inter.drugA}</span> + <span className="font-semibold">{inter.drugB}</span></p>
                    <p className="text-[11px] text-gray-500 mt-1">{inter.description}</p>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          {/* Recent Prescriptions */}
          <SectionCard title="Recent Prescriptions" subtitle={`${flaggedPrescriptions.length} flagged`}>
            <div className="space-y-2">
              {PRESCRIPTIONS.slice(0, 4).map((rx) => {
                const resident = residentById(rx.residentId);
                const statusColors: Record<string, string> = { pending_review: 'bg-amber-100 text-amber-700', approved: 'bg-emerald-100 text-emerald-700', flagged: 'bg-red-100 text-red-700' };
                return (
                  <div key={rx.id} className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-gray-50">
                    <Pill size={16} className="text-violet-500 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{resident?.name ?? 'Unknown'}</p>
                      <p className="text-xs text-gray-400">{rx.medications.length} medications · OCR {(rx.ocrConfidence * 100).toFixed(0)}%</p>
                    </div>
                    <span className={`text-[10px] font-bold rounded-full px-2 py-0.5 ${statusColors[rx.status] ?? 'bg-gray-100 text-gray-600'}`}>{rx.status.replace(/_/g, ' ').toUpperCase()}</span>
                  </div>
                );
              })}
            </div>
          </SectionCard>
        </div>
      </div>
    </>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
//  OPS / B2B VIEW
// ═════════════════════════════════════════════════════════════════════════════

function OpsDashboard() {
  const [alertWindow, setAlertWindow] = useState<7 | 30>(30);
  const trendData = useMemo(() => getDailyTrends(alertWindow), [alertWindow]);

  const totalGateways = EDGE_GATEWAYS.length;
  const onlineGateways = EDGE_GATEWAYS.filter((g) => g.status === 'online').length;
  const avgUptime = +(EDGE_GATEWAYS.reduce((s, g) => s + g.uptime, 0) / totalGateways).toFixed(1);
  const slaCompliance = SITE_HEALTH_DATA.filter((s) => s.slaResponseTime <= s.slaTarget).length;
  const avgMTTA = +(CAREGIVER_WORKLOAD.reduce((s, w) => s + w.avgResponseTime, 0) / CAREGIVER_WORKLOAD.length).toFixed(1);
  const avgMTTR = +(avgMTTA * 2.3).toFixed(1); // Simulated MTTR
  const avgBurnout = +(CAREGIVER_WORKLOAD.reduce((s, w) => s + w.burnoutScore, 0) / CAREGIVER_WORKLOAD.length).toFixed(0);

  // Sensor coverage by modality
  const sensorCoverage = useMemo(() => {
    const modalities = ['IMU', 'Acoustic', 'Pose', 'Medication', 'Vital', 'Environmental'];
    return modalities.map((m) => ({
      name: m,
      coverage: Math.round(75 + Math.random() * 25),
      target: 95,
    }));
  }, []);

  // Response time trend
  const responseTimeTrend = useMemo(() => {
    return trendData.map((d) => ({
      date: d.date,
      mtta: +(8 + Math.random() * 8).toFixed(1),
      mttr: +(18 + Math.random() * 15).toFixed(1),
    }));
  }, [trendData]);

  // Cost data (demo)
  const costData = useMemo(() => {
    const months = ['Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb'];
    return months.map((m) => ({
      month: m,
      costPerResident: +(2200 + Math.random() * 400).toFixed(0),
      revenue: +(3500 + Math.random() * 600).toFixed(0),
    }));
  }, []);

  return (
    <>
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Operations Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Fleet & platform overview · {format(new Date(), 'EEEE, MMM d, yyyy')}</p>
      </div>

      {/* Fleet KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <StatCard label="Total Sites" value={SITE_HEALTH_DATA.length} icon={Server} iconBg="bg-indigo-50" iconColor="text-indigo-600" subtitle="Active deployments" />
        <StatCard label="Gateways Online" value={`${onlineGateways}/${totalGateways}`} icon={Wifi} iconBg="bg-teal-50" iconColor="text-teal-600" subtitle={`${Math.round((onlineGateways / totalGateways) * 100)}% online`} trend="up" />
        <StatCard label="Avg Uptime" value={`${avgUptime}%`} icon={TrendingUp} iconBg="bg-emerald-50" iconColor="text-emerald-600" subtitle="Across all gateways" trend="up" />
        <StatCard label="SLA Compliance" value={`${slaCompliance}/${SITE_HEALTH_DATA.length}`} icon={ShieldCheck} iconBg="bg-blue-50" iconColor="text-blue-600" subtitle="Response time target" />
      </div>

      {/* Site Health Map */}
      <div className="mt-6">
        <SectionCard title="Site Health Map" subtitle="Status across all deployment sites">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {SITE_HEALTH_DATA.map((site) => {
              const statusColors: Record<string, { bg: string; dot: string; text: string }> = {
                healthy: { bg: 'border-emerald-200 bg-emerald-50/30', dot: 'bg-emerald-400', text: 'text-emerald-700' },
                degraded: { bg: 'border-amber-200 bg-amber-50/30', dot: 'bg-amber-400', text: 'text-amber-700' },
                critical: { bg: 'border-red-200 bg-red-50/30', dot: 'bg-red-500', text: 'text-red-700' },
              };
              const sc = statusColors[site.gatewayStatus] ?? statusColors.healthy;
              return (
                <div key={site.siteId} className={`rounded-xl border p-4 ${sc.bg} transition-all hover:shadow-sm`}>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-sm font-semibold text-gray-900">{site.siteName}</p>
                    <span className={`flex h-2.5 w-2.5 rounded-full ${sc.dot}`} />
                  </div>
                  <p className="text-xs text-gray-400 mb-3">{site.city} · {site.totalResidents} residents</p>
                  <div className="grid grid-cols-2 gap-2 text-center">
                    <div>
                      <p className="text-sm font-bold text-gray-900">{site.slaResponseTime}s</p>
                      <p className="text-[10px] text-gray-400">Response</p>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-gray-900">{site.sensorCoverage}%</p>
                      <p className="text-[10px] text-gray-400">Coverage</p>
                    </div>
                  </div>
                  {site.activeAlerts > 0 && (
                    <div className="mt-2 rounded-md bg-red-100 px-2 py-1 text-center">
                      <p className="text-[10px] font-bold text-red-700">{site.activeAlerts} active alerts</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </SectionCard>
      </div>

      {/* Row: Sensor Coverage + Care Team KPIs */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SectionCard title="Sensor Coverage by Modality" subtitle="Deployment quality per sensor type">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={sensorCoverage} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} domain={[0, 100]} unit="%" />
              <Tooltip content={<ChartTooltip />} />
              <Bar dataKey="coverage" name="Coverage %" fill="#6366f1" radius={[6, 6, 0, 0]} />
              <Bar dataKey="target" name="Target" fill="#e2e8f0" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>

        <SectionCard title="Care Team KPIs" subtitle="Caregiver performance metrics">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="rounded-xl border border-gray-100 p-3 text-center">
              <p className="text-xl font-bold text-gray-900">{avgMTTA}s</p>
              <p className="text-[10px] text-gray-400">Avg MTTA</p>
            </div>
            <div className="rounded-xl border border-gray-100 p-3 text-center">
              <p className="text-xl font-bold text-gray-900">{avgMTTR}s</p>
              <p className="text-[10px] text-gray-400">Avg MTTR</p>
            </div>
            <div className="rounded-xl border border-gray-100 p-3 text-center">
              <p className={`text-xl font-bold ${Number(avgBurnout) >= 60 ? 'text-red-600' : 'text-amber-600'}`}>{avgBurnout}</p>
              <p className="text-[10px] text-gray-400">Burnout Proxy</p>
            </div>
            <div className="rounded-xl border border-gray-100 p-3 text-center">
              <p className="text-xl font-bold text-gray-900">{CLINICAL_DOCUMENTS.filter((d) => d.status === 'pending_review').length}</p>
              <p className="text-[10px] text-gray-400">Doc Pending</p>
            </div>
          </div>
          <div className="space-y-2">
            {CAREGIVER_WORKLOAD.slice(0, 4).map((cg) => (
              <div key={cg.caregiverId} className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-gray-50">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-600">{cg.name.charAt(0)}</div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{cg.name}</p>
                  <p className="text-[10px] text-gray-400">{cg.shift} · {cg.alertsHandled} alerts</p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-semibold text-gray-700">{cg.avgResponseTime}s</p>
                  <div className="mt-0.5 h-1 w-12 rounded-full bg-gray-100">
                    <div className={`h-full rounded-full ${cg.burnoutScore >= 60 ? 'bg-red-500' : cg.burnoutScore >= 40 ? 'bg-amber-400' : 'bg-emerald-500'}`} style={{ width: `${cg.burnoutScore}%` }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>

      {/* Row: Alert Volume Trend + Response Time Trend */}
      <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SectionCard title="Alert Volume Trend" subtitle={`${alertWindow}-day event volume`}>
          <div className="flex justify-end mb-2">
            <div className="inline-flex rounded-lg bg-gray-100 p-0.5">
              {([7, 30] as const).map((w) => (
                <button key={w} onClick={() => setAlertWindow(w)}
                  className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${alertWindow === w ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
                  {w}D
                </button>
              ))}
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={trendData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="gradAlert" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.15} /><stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} /></linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} tickFormatter={(v: string) => format(parseISO(v), 'MMM d')} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Area type="monotone" dataKey="total_events" name="Events" stroke="#8b5cf6" strokeWidth={2} fill="url(#gradAlert)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </SectionCard>

        <SectionCard title="Response Time Trend" subtitle="MTTA / MTTR over time">
          <ResponsiveContainer width="100%" height={252}>
            <LineChart data={responseTimeTrend} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} tickFormatter={(v: string) => format(parseISO(v), 'MMM d')} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} unit="s" />
              <Tooltip content={<ChartTooltip />} />
              <Legend verticalAlign="top" align="right" iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, paddingBottom: 8 }} />
              <Line type="monotone" dataKey="mtta" name="MTTA" stroke="#6366f1" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="mttr" name="MTTR" stroke="#f59e0b" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </SectionCard>
      </div>

      {/* Revenue/Cost Metrics */}
      <div className="mt-6">
        <SectionCard title="Revenue & Cost Metrics" subtitle="Monthly cost per resident vs revenue (demo data)">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={costData} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} tickFormatter={(v: number) => `₹${(v / 1000).toFixed(0)}k`} />
              <Tooltip content={<ChartTooltip />} />
              <Legend verticalAlign="top" align="right" iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, paddingBottom: 8 }} />
              <Bar dataKey="costPerResident" name="Cost/Resident" fill="#ef4444" radius={[4, 4, 0, 0]} />
              <Bar dataKey="revenue" name="Revenue" fill="#22c55e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </SectionCard>
      </div>
    </>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
//  MAIN PAGE — ROLE DISPATCHER
// ═════════════════════════════════════════════════════════════════════════════

export default function DashboardPage() {
  const { user, role } = useAuth();

  return (
    <div className="min-h-screen bg-gray-50/60">
      <div className="mx-auto max-w-[1440px] px-6 py-8 lg:px-10">
        {role === 'elder' && <ElderDashboard userName={user?.name ?? 'Resident'} />}
        {role === 'caregiver' && <CaregiverDashboard />}
        {role === 'doctor' && <DoctorDashboard />}
        {role === 'ops' && <OpsDashboard />}
        {!role && <CaregiverDashboard />}

        {/* Footer */}
        <div className="mt-12 border-t border-gray-200/60 pt-6 pb-8 text-center">
          <p className="text-xs text-gray-300">
            AETHER · Adaptive Elderly Tracking & Home Emergency Response · Privacy-first edge AI monitoring
          </p>
        </div>
      </div>
    </div>
  );
}
