import { useMemo, useState } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from 'recharts';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  AlertTriangle,
  Pill,
  Timer,
  Cpu,
  Wifi,
  WifiOff,
  BatteryMedium,
  BatteryLow,
  BatteryWarning,
  BatteryFull,
  Signal,
  SignalLow,
  SignalZero,
  Brain,
  Sparkles,
  Lightbulb,
  Mic,
  Move,
  Radio,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';

import { getAnalytics, RESIDENTS, DASHBOARD_STATS, SENSOR_HEALTH, getFalsePositiveRates, getModelConfidenceDrift } from '../data/mockData';
import { useLiveData } from '../contexts/LiveDataContext';
import type {
  AnalyticsData,
  DailyTrend,
  ResponseTimeData,
  MedicationTrend,
  SensorHealth,
  EventType,
  Severity,
  FalsePositiveRate,
  ModelConfidenceDrift,
} from '../types';

// ─── Constants ────────────────────────────────────────────────────────────────

const PERIOD_OPTIONS = [
  { label: '7 days', value: 7 },
  { label: '14 days', value: 14 },
  { label: '30 days', value: 30 },
  { label: '90 days', value: 90 },
] as const;

const SEVERITY_COLORS: Record<Severity, string> = {
  CRITICAL: '#ef4444',
  HIGH: '#f97316',
  MEDIUM: '#eab308',
  LOW: '#22c55e',
  INFO: '#6b7280',
};

const EVENT_TYPE_COLORS: Record<string, string> = {
  fall_detected: '#ef4444',
  medication_taken: '#22c55e',
  medication_missed: '#f97316',
  medication_late: '#eab308',
  acoustic_scream: '#dc2626',
  acoustic_glass_break: '#b91c1c',
  acoustic_impact: '#ea580c',
  acoustic_silence: '#9ca3af',
  routine_anomaly: '#a855f7',
  vital_alert: '#ec4899',
  check_in_completed: '#06b6d4',
};

const SENSOR_TYPE_ICONS: Record<string, React.ElementType> = {
  imu: Move,
  acoustic: Mic,
  pose: Activity,
  medication: Pill,
  vital: Activity,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatEventType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function formatRoom(room: string): string {
  return room
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function fmtDate(dateStr: string): string {
  try {
    return format(parseISO(dateStr), 'MMM d');
  } catch {
    return dateStr;
  }
}

function fmtDateLong(dateStr: string): string {
  try {
    return format(parseISO(dateStr), 'EEE, MMM d');
  } catch {
    return dateStr;
  }
}

// ─── KPI Card ─────────────────────────────────────────────────────────────────

interface KPICardProps {
  title: string;
  value: string | number;
  suffix?: string;
  change?: number;
  changeLabel?: string;
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  children?: React.ReactNode;
}

function KPICard({
  title,
  value,
  suffix,
  change,
  changeLabel,
  icon: Icon,
  iconBg,
  iconColor,
  children,
}: KPICardProps) {
  const isPositive = change !== undefined && change >= 0;
  const TrendIcon = isPositive ? TrendingUp : TrendingDown;

  return (
    <div className="relative overflow-hidden rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200/60 transition-all duration-200 hover:shadow-md hover:ring-gray-300/80">
      {/* Decorative gradient */}
      <div className={`absolute top-0 right-0 h-24 w-24 rounded-full blur-3xl opacity-10 ${iconBg}`} />

      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-500 truncate">{title}</p>
          <div className="mt-2 flex items-baseline gap-1">
            <span className="text-3xl font-bold tracking-tight text-gray-900">{value}</span>
            {suffix && <span className="text-sm font-medium text-gray-400">{suffix}</span>}
          </div>
          {change !== undefined && (
            <div className="mt-2 flex items-center gap-1.5">
              <div
                className={`flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-semibold ${
                  isPositive
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-red-50 text-red-700'
                }`}
              >
                <TrendIcon size={12} />
                <span>{Math.abs(change).toFixed(1)}%</span>
              </div>
              {changeLabel && (
                <span className="text-xs text-gray-400">{changeLabel}</span>
              )}
            </div>
          )}
          {children}
        </div>
        <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${iconBg}`}>
          <Icon className={iconColor} size={22} strokeWidth={2} />
        </div>
      </div>
    </div>
  );
}

// ─── Section Wrapper ──────────────────────────────────────────────────────────

function Section({
  title,
  subtitle,
  children,
  className = '',
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60 ${className}`}
    >
      <div className="mb-5">
        <h3 className="text-lg font-bold text-gray-900">{title}</h3>
        {subtitle && <p className="mt-0.5 text-sm text-gray-400">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

// ─── Custom Tooltips ──────────────────────────────────────────────────────────

function TrendTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-gray-200/80 bg-white/95 px-4 py-3 shadow-xl backdrop-blur-sm">
      <p className="mb-2 text-xs font-semibold text-gray-500">{fmtDateLong(label)}</p>
      {payload.map((entry: any) => (
        <div key={entry.name} className="flex items-center gap-2 text-sm">
          <span
            className="inline-block h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-gray-600">{entry.name}:</span>
          <span className="font-semibold text-gray-900">{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

function ResponseTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload as ResponseTimeData | undefined;
  if (!data) return null;
  return (
    <div className="rounded-xl border border-gray-200/80 bg-white/95 px-4 py-3 shadow-xl backdrop-blur-sm">
      <p className="mb-2 text-xs font-semibold text-gray-500">{fmtDateLong(label)}</p>
      <div className="space-y-1 text-sm">
        <div className="flex justify-between gap-6">
          <span className="text-gray-500">Average</span>
          <span className="font-semibold text-blue-600">{data.avg_seconds}s</span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-gray-500">Minimum</span>
          <span className="font-semibold text-emerald-600">{data.min_seconds}s</span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-gray-500">Maximum</span>
          <span className="font-semibold text-orange-600">{data.max_seconds}s</span>
        </div>
      </div>
    </div>
  );
}

function MedTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload as MedicationTrend | undefined;
  if (!data) return null;
  return (
    <div className="rounded-xl border border-gray-200/80 bg-white/95 px-4 py-3 shadow-xl backdrop-blur-sm">
      <p className="mb-2 text-xs font-semibold text-gray-500">{fmtDateLong(label)}</p>
      <div className="space-y-1 text-sm">
        <div className="flex justify-between gap-6">
          <span className="text-gray-500">Adherence</span>
          <span className="font-bold text-emerald-600">{data.adherence_pct}%</span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-gray-500">Taken</span>
          <span className="font-semibold text-green-600">{data.taken}</span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-gray-500">Missed</span>
          <span className="font-semibold text-red-600">{data.missed}</span>
        </div>
        <div className="flex justify-between gap-6">
          <span className="text-gray-500">Late</span>
          <span className="font-semibold text-yellow-600">{data.late}</span>
        </div>
      </div>
    </div>
  );
}

// ─── Pie Center Label ─────────────────────────────────────────────────────────

function PieCenterLabel({ viewBox, total }: any) {
  const { cx, cy } = viewBox;
  return (
    <g>
      <text x={cx} y={cy - 6} textAnchor="middle" className="fill-gray-900 text-2xl font-bold">
        {total}
      </text>
      <text x={cx} y={cy + 14} textAnchor="middle" className="fill-gray-400 text-xs">
        total
      </text>
    </g>
  );
}

// ─── Battery bar ──────────────────────────────────────────────────────────────

function BatteryBar({ pct }: { pct?: number }) {
  if (pct === undefined) return <span className="text-xs text-gray-400">AC</span>;
  const color =
    pct > 60 ? 'bg-emerald-500' : pct > 25 ? 'bg-yellow-500' : 'bg-red-500';
  const BattIcon =
    pct > 60 ? BatteryFull : pct > 25 ? BatteryMedium : pct > 5 ? BatteryLow : BatteryWarning;
  return (
    <div className="flex items-center gap-1.5">
      <BattIcon size={14} className={pct > 60 ? 'text-emerald-500' : pct > 25 ? 'text-yellow-500' : 'text-red-500'} />
      <div className="h-1.5 w-12 rounded-full bg-gray-100 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-medium text-gray-500">{pct}%</span>
    </div>
  );
}

// ─── Signal bars ──────────────────────────────────────────────────────────────

function SignalBars({ quality }: { quality: number }) {
  const bars = quality > 0.8 ? 3 : quality > 0.5 ? 2 : quality > 0 ? 1 : 0;
  return (
    <div className="flex items-end gap-0.5 h-4">
      {[1, 2, 3].map((level) => (
        <div
          key={level}
          className={`w-1 rounded-t-sm transition-all ${
            level <= bars ? 'bg-emerald-500' : 'bg-gray-200'
          }`}
          style={{ height: `${(level / 3) * 100}%` }}
        />
      ))}
    </div>
  );
}

// ─── Sensor Card ──────────────────────────────────────────────────────────────

function SensorCard({ sensor }: { sensor: SensorHealth }) {
  const SensorIcon = SENSOR_TYPE_ICONS[sensor.type] || Radio;
  const statusDot =
    sensor.status === 'online'
      ? 'bg-emerald-500'
      : sensor.status === 'degraded'
      ? 'bg-yellow-500'
      : 'bg-red-500';
  const statusLabel =
    sensor.status === 'online'
      ? 'text-emerald-700 bg-emerald-50'
      : sensor.status === 'degraded'
      ? 'text-yellow-700 bg-yellow-50'
      : 'text-red-700 bg-red-50';

  const timeSince = Date.now() - sensor.last_seen;
  const minsAgo = Math.floor(timeSince / 60000);
  const lastSeenStr =
    minsAgo < 1 ? 'Just now' : minsAgo < 60 ? `${minsAgo}m ago` : `${Math.floor(minsAgo / 60)}h ago`;

  return (
    <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-gray-50/50 px-4 py-3 transition-all hover:bg-white hover:shadow-sm">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white ring-1 ring-gray-200/60">
        <SensorIcon size={16} className="text-gray-600" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800 truncate">{sensor.sensor_id}</span>
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusLabel}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${statusDot}`} />
            {sensor.status}
          </span>
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-gray-400">
          <span>{formatRoom(sensor.room)}</span>
          <span>·</span>
          <span>{lastSeenStr}</span>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <BatteryBar pct={sensor.battery_pct} />
        <SignalBars quality={sensor.signal_quality} />
      </div>
    </div>
  );
}

// ─── Insight Card ─────────────────────────────────────────────────────────────

function InsightCard({
  icon: Icon,
  iconColor,
  iconBg,
  title,
  description,
  tag,
  tagColor,
}: {
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
  title: string;
  description: string;
  tag: string;
  tagColor: string;
}) {
  return (
    <div className="group relative overflow-hidden rounded-2xl border border-gray-100 bg-gradient-to-br from-white to-gray-50/50 p-5 transition-all duration-200 hover:shadow-md hover:border-gray-200">
      <div className="absolute top-0 right-0 h-20 w-20 rounded-full blur-3xl opacity-[0.07]" style={{ background: iconBg }} />
      <div className="flex gap-4">
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${iconBg}`}>
          <Icon className={iconColor} size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-sm font-bold text-gray-900">{title}</h4>
            <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${tagColor}`}>
              {tag}
            </span>
          </div>
          <p className="text-sm text-gray-600 leading-relaxed">{description}</p>
        </div>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═════════════════════════════════════════════════════════════════════════════

export default function AnalyticsPage() {
  const { apiConnected } = useLiveData();
  const [period, setPeriod] = useState(14);

  const analytics: AnalyticsData = useMemo(() => getAnalytics(period), [period]);

  // Compute KPIs
  const totalEvents = analytics.daily_trends.reduce((s, d) => s + d.total_events, 0);
  const totalFalls = analytics.daily_trends.reduce((s, d) => s + d.falls, 0);
  const avgAdherence =
    analytics.medication_trends.length > 0
      ? +(
          analytics.medication_trends.reduce((s, d) => s + d.adherence_pct, 0) /
          analytics.medication_trends.length
        ).toFixed(1)
      : 0;
  const avgResponseTime =
    analytics.response_times.length > 0
      ? +(
          analytics.response_times.reduce((s, d) => s + d.avg_seconds, 0) /
          analytics.response_times.length
        ).toFixed(1)
      : 0;

  // Simulated previous-period comparison
  const eventChange = 12.3;
  const fallChange = -8.5;
  const adherenceChange = 3.2;
  const responseChange = -18.7;

  // Events by type for bar chart
  const eventsByTypeData = Object.entries(analytics.events_by_type)
    .map(([type, count]) => ({
      name: formatEventType(type),
      value: count,
      fill: EVENT_TYPE_COLORS[type] || '#6b7280',
    }))
    .sort((a, b) => b.value - a.value);

  const eventsByTypeTotal = eventsByTypeData.reduce((s, d) => s + d.value, 0);

  // Events by severity for donut chart
  const eventsBySeverityData = Object.entries(analytics.events_by_severity)
    .map(([severity, count]) => ({
      name: severity,
      value: count,
      fill: SEVERITY_COLORS[severity as Severity] || '#6b7280',
    }))
    .sort((a, b) => {
      const order: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
      return order.indexOf(a.name as Severity) - order.indexOf(b.name as Severity);
    });

  const severityTotal = eventsBySeverityData.reduce((s, d) => s + d.value, 0);

  // Sensor health summary
  const sensors = analytics.sensor_health;
  const sensorsOnline = sensors.filter((s) => s.status === 'online').length;
  const sensorsDegraded = sensors.filter((s) => s.status === 'degraded').length;
  const sensorsOffline = sensors.filter((s) => s.status === 'offline').length;

  // Group sensors by home
  const sensorsByHome = sensors.reduce<Record<string, SensorHealth[]>>((acc, s) => {
    const homeId = s.sensor_id.split('-').slice(0, 2).join('-');
    if (!acc[homeId]) acc[homeId] = [];
    acc[homeId].push(s);
    return acc;
  }, {});

  // False-positive rate trends
  const falsePositiveData: FalsePositiveRate[] = useMemo(() => getFalsePositiveRates(), []);

  // Model confidence drift
  const confidenceDriftData: ModelConfidenceDrift[] = useMemo(() => getModelConfidenceDrift(), []);

  return (
    <div className="animate-fade-in space-y-6">
      {/* ─── Header ───────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics &amp; Insights</h1>
          <p className="mt-1 text-sm text-gray-500 flex items-center gap-2">
            Performance metrics, trends, and AI-powered insights
            {apiConnected && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                <Wifi size={10} /> AWS Live
              </span>
            )}
          </p>
        </div>
        <div className="flex rounded-xl bg-gray-100 p-1">
          {PERIOD_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setPeriod(opt.value)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition-all ${
                period === opt.value
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* ─── KPI Cards ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <KPICard
          title="Total Events"
          value={totalEvents.toLocaleString()}
          change={eventChange}
          changeLabel="vs prev period"
          icon={Activity}
          iconBg="bg-blue-100"
          iconColor="text-blue-600"
        />
        <KPICard
          title="Fall Incidents"
          value={totalFalls}
          change={fallChange}
          changeLabel="vs prev period"
          icon={AlertTriangle}
          iconBg="bg-red-100"
          iconColor="text-red-600"
        />
        <KPICard
          title="Medication Adherence"
          value={`${avgAdherence}%`}
          change={adherenceChange}
          changeLabel="vs prev period"
          icon={Pill}
          iconBg="bg-emerald-100"
          iconColor="text-emerald-600"
        >
          <div className="mt-2 h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-700"
              style={{ width: `${avgAdherence}%` }}
            />
          </div>
        </KPICard>
        <KPICard
          title="Avg Response Time"
          value={avgResponseTime}
          suffix="sec"
          change={responseChange}
          changeLabel="vs prev period"
          icon={Timer}
          iconBg="bg-violet-100"
          iconColor="text-violet-600"
        />
        <KPICard
          title="System Uptime"
          value={`${DASHBOARD_STATS.system_uptime}%`}
          change={0.02}
          changeLabel="vs prev period"
          icon={Cpu}
          iconBg="bg-cyan-100"
          iconColor="text-cyan-600"
        >
          <div className="mt-2 h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
            <div
              className="h-full rounded-full bg-cyan-500 transition-all duration-700"
              style={{ width: `${DASHBOARD_STATS.system_uptime}%` }}
            />
          </div>
        </KPICard>
      </div>

      {/* ─── Section 1: Event Trends ──────────────────────────────── */}
      <Section
        title="Event Trends"
        subtitle={`Daily event distribution over the past ${period} days`}
      >
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={analytics.daily_trends} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradFalls" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradMeds" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#22c55e" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradAcoustic" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#a855f7" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="#a855f7" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDate}
                tick={{ fontSize: 12, fill: '#9ca3af' }}
                axisLine={{ stroke: '#e5e7eb' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 12, fill: '#9ca3af' }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<TrendTooltip />} />
              <Legend
                verticalAlign="bottom"
                height={36}
                iconType="circle"
                iconSize={8}
                wrapperStyle={{ fontSize: '12px', paddingTop: '12px' }}
              />
              <Area
                type="monotone"
                dataKey="total_events"
                name="Total"
                stroke="#3b82f6"
                strokeWidth={2.5}
                fill="url(#gradTotal)"
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2 }}
              />
              <Area
                type="monotone"
                dataKey="medications"
                name="Medications"
                stroke="#22c55e"
                strokeWidth={2}
                fill="url(#gradMeds)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2 }}
              />
              <Area
                type="monotone"
                dataKey="acoustic"
                name="Acoustic"
                stroke="#a855f7"
                strokeWidth={2}
                fill="url(#gradAcoustic)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2 }}
              />
              <Area
                type="monotone"
                dataKey="falls"
                name="Falls"
                stroke="#ef4444"
                strokeWidth={2}
                fill="url(#gradFalls)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Section>

      {/* ─── Section 2: Type & Severity Breakdown ─────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Events by Type */}
        <Section title="Events by Type" subtitle="Distribution across event categories">
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={eventsByTypeData}
                layout="vertical"
                margin={{ top: 0, right: 30, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#9ca3af' }} axisLine={false} tickLine={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fontSize: 11, fill: '#6b7280' }}
                  axisLine={false}
                  tickLine={false}
                  width={130}
                />
                <Tooltip
                  formatter={(value: number) => [
                    `${value} (${((value / eventsByTypeTotal) * 100).toFixed(1)}%)`,
                    'Count',
                  ]}
                  contentStyle={{
                    borderRadius: '12px',
                    border: '1px solid #e5e7eb',
                    boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.05)',
                  }}
                />
                <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={18}>
                  {eventsByTypeData.map((entry, i) => (
                    <Cell key={i} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Section>

        {/* Events by Severity — Donut */}
        <Section title="Events by Severity" subtitle="Severity level distribution">
          <div className="flex items-center justify-center h-80">
            <div className="w-full max-w-xs">
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={eventsBySeverityData}
                    cx="50%"
                    cy="50%"
                    innerRadius={65}
                    outerRadius={100}
                    paddingAngle={3}
                    dataKey="value"
                    stroke="none"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    labelLine={{ stroke: '#d1d5db', strokeWidth: 1 }}
                  >
                    {eventsBySeverityData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number) => [`${value} events`, '']}
                    contentStyle={{
                      borderRadius: '12px',
                      border: '1px solid #e5e7eb',
                      boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.05)',
                    }}
                  />
                  {/* Center label */}
                  <text x="50%" y="46%" textAnchor="middle" dominantBaseline="middle" className="fill-gray-900 text-2xl font-bold">
                    {severityTotal}
                  </text>
                  <text x="50%" y="56%" textAnchor="middle" dominantBaseline="middle" className="fill-gray-400 text-xs">
                    total events
                  </text>
                </PieChart>
              </ResponsiveContainer>

              {/* Legend */}
              <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1">
                {eventsBySeverityData.map((entry) => (
                  <div key={entry.name} className="flex items-center gap-1.5 text-xs">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.fill }} />
                    <span className="text-gray-600">{entry.name}</span>
                    <span className="font-semibold text-gray-800">{entry.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Section>
      </div>

      {/* ─── Section 3: Response Time Analysis ────────────────────── */}
      <Section
        title="Response Time Analysis"
        subtitle="Average, minimum, and maximum response times with 15-second target"
      >
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={analytics.response_times} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="gradMinMax" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.12} />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity={0.02} />
                </linearGradient>
                <linearGradient id="gradAvg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDate}
                tick={{ fontSize: 12, fill: '#9ca3af' }}
                axisLine={{ stroke: '#e5e7eb' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 12, fill: '#9ca3af' }}
                axisLine={false}
                tickLine={false}
                unit="s"
              />
              <Tooltip content={<ResponseTooltip />} />
              <ReferenceLine
                y={15}
                stroke="#ef4444"
                strokeDasharray="6 4"
                strokeWidth={1.5}
                label={{
                  value: '15s Target',
                  position: 'right',
                  fill: '#ef4444',
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />
              <Area
                type="monotone"
                dataKey="max_seconds"
                name="Max"
                stroke="#f97316"
                strokeWidth={1.5}
                fill="url(#gradMinMax)"
                dot={false}
                strokeDasharray="4 2"
              />
              <Area
                type="monotone"
                dataKey="avg_seconds"
                name="Average"
                stroke="#3b82f6"
                strokeWidth={2.5}
                fill="url(#gradAvg)"
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2 }}
              />
              <Area
                type="monotone"
                dataKey="min_seconds"
                name="Min"
                stroke="#22c55e"
                strokeWidth={1.5}
                fill="transparent"
                dot={false}
                strokeDasharray="4 2"
              />
              <Legend
                verticalAlign="bottom"
                height={36}
                iconType="circle"
                iconSize={8}
                wrapperStyle={{ fontSize: '12px', paddingTop: '12px' }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Section>

      {/* ─── Section 4: Medication Adherence Trends ───────────────── */}
      <Section
        title="Medication Adherence Trends"
        subtitle="Daily adherence rate with dose breakdown"
      >
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={analytics.medication_trends} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="gradAdherence" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#22c55e" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#22c55e" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDate}
                tick={{ fontSize: 12, fill: '#9ca3af' }}
                axisLine={{ stroke: '#e5e7eb' }}
                tickLine={false}
              />
              <YAxis
                yAxisId="left"
                tick={{ fontSize: 12, fill: '#9ca3af' }}
                axisLine={false}
                tickLine={false}
                label={{
                  value: 'Doses',
                  angle: -90,
                  position: 'insideLeft',
                  style: { fontSize: 11, fill: '#9ca3af' },
                }}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                domain={[70, 100]}
                tick={{ fontSize: 12, fill: '#9ca3af' }}
                axisLine={false}
                tickLine={false}
                unit="%"
                label={{
                  value: 'Adherence %',
                  angle: 90,
                  position: 'insideRight',
                  style: { fontSize: 11, fill: '#9ca3af' },
                }}
              />
              <Tooltip content={<MedTooltip />} />
              <ReferenceLine
                yAxisId="right"
                y={90}
                stroke="#3b82f6"
                strokeDasharray="6 4"
                strokeWidth={1.5}
                label={{
                  value: '90% Target',
                  position: 'right',
                  fill: '#3b82f6',
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />
              <Bar yAxisId="left" dataKey="taken" name="Taken" fill="#22c55e" stackId="stack" radius={[0, 0, 0, 0]} barSize={14} />
              <Bar yAxisId="left" dataKey="late" name="Late" fill="#eab308" stackId="stack" radius={[0, 0, 0, 0]} barSize={14} />
              <Bar yAxisId="left" dataKey="missed" name="Missed" fill="#ef4444" stackId="stack" radius={[2, 2, 0, 0]} barSize={14} />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="adherence_pct"
                name="Adherence"
                stroke="#059669"
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2, fill: '#fff' }}
              />
              <Legend
                verticalAlign="bottom"
                height={36}
                iconType="circle"
                iconSize={8}
                wrapperStyle={{ fontSize: '12px', paddingTop: '12px' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Section>

      {/* ─── Section 5: Sensor Network Health ─────────────────────── */}
      <Section
        title="Sensor Network Health"
        subtitle="Real-time status of all connected sensors across homes"
      >
        {/* Summary strip */}
        <div className="mb-5 flex flex-wrap gap-4">
          <div className="flex items-center gap-2 rounded-lg bg-emerald-50 px-4 py-2">
            <Wifi size={16} className="text-emerald-600" />
            <span className="text-sm font-bold text-emerald-700">{sensorsOnline}</span>
            <span className="text-sm text-emerald-600">Online</span>
          </div>
          <div className="flex items-center gap-2 rounded-lg bg-yellow-50 px-4 py-2">
            <SignalLow size={16} className="text-yellow-600" />
            <span className="text-sm font-bold text-yellow-700">{sensorsDegraded}</span>
            <span className="text-sm text-yellow-600">Degraded</span>
          </div>
          <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-2">
            <WifiOff size={16} className="text-red-600" />
            <span className="text-sm font-bold text-red-700">{sensorsOffline}</span>
            <span className="text-sm text-red-600">Offline</span>
          </div>
        </div>

        {/* Grouped by home */}
        <div className="space-y-5">
          {Object.entries(sensorsByHome).map(([homeId, homeSensors]) => {
            const resident = RESIDENTS.find((r) => r.home_id === homeId);
            return (
              <div key={homeId}>
                <div className="mb-2 flex items-center gap-2">
                  <span className="text-sm font-bold text-gray-700">{homeId}</span>
                  {resident && (
                    <span className="text-xs text-gray-400">— {resident.name}</span>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                  {homeSensors.map((sensor) => (
                    <SensorCard key={sensor.sensor_id} sensor={sensor} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* ─── Section 6: Model Quality ─────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* False-positive rates */}
        <Section
          title="False-Positive Rates"
          subtitle="Per-model false-positive % over the last 30 days"
        >
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={falsePositiveData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <defs>
                <linearGradient id="gFpFall" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#ef4444" stopOpacity={0.15} /><stop offset="95%" stopColor="#ef4444" stopOpacity={0} /></linearGradient>
                <linearGradient id="gFpAcoustic" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} /><stop offset="95%" stopColor="#6366f1" stopOpacity={0} /></linearGradient>
                <linearGradient id="gFpGait" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#f59e0b" stopOpacity={0.15} /><stop offset="95%" stopColor="#f59e0b" stopOpacity={0} /></linearGradient>
                <linearGradient id="gFpVital" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#22c55e" stopOpacity={0.15} /><stop offset="95%" stopColor="#22c55e" stopOpacity={0} /></linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="date" tickFormatter={(v) => format(parseISO(v), 'MMM d')} tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} unit="%" domain={[0, 'auto']} />
              <Tooltip content={<TrendTooltip />} />
              <Legend verticalAlign="top" align="right" iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, paddingBottom: 4 }} />
              <Area type="monotone" dataKey="fallDetection" name="Fall" stroke="#ef4444" fill="url(#gFpFall)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="acousticEvent" name="Acoustic" stroke="#6366f1" fill="url(#gFpAcoustic)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="gaitAnomaly" name="Gait" stroke="#f59e0b" fill="url(#gFpGait)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="vitalSign" name="Vitals" stroke="#22c55e" fill="url(#gFpVital)" strokeWidth={2} dot={false} />
              <ReferenceLine y={5} stroke="#dc2626" strokeDasharray="4 4" label={{ value: '5% target', fill: '#dc2626', fontSize: 10, position: 'right' }} />
            </AreaChart>
          </ResponsiveContainer>
        </Section>

        {/* Model confidence drift */}
        <Section
          title="Model Confidence Drift"
          subtitle="Average inference confidence by model — 30-day window"
        >
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={confidenceDriftData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
              <XAxis dataKey="date" tickFormatter={(v) => format(parseISO(v), 'MMM d')} tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickLine={false} axisLine={false} unit="%" domain={[80, 100]} />
              <Tooltip content={<TrendTooltip />} />
              <Legend verticalAlign="top" align="right" iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 10, paddingBottom: 4 }} />
              <Line type="monotone" dataKey="fallModel" name="Fall" stroke="#ef4444" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="acousticModel" name="Acoustic" stroke="#6366f1" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="gaitModel" name="Gait" stroke="#f59e0b" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="vitalModel" name="Vitals" stroke="#22c55e" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="avgConfidence" name="Average" stroke="#0ea5e9" strokeWidth={2.5} strokeDasharray="5 3" dot={false} />
              <ReferenceLine y={90} stroke="#dc2626" strokeDasharray="4 4" label={{ value: '90% floor', fill: '#dc2626', fontSize: 10, position: 'right' }} />
            </ComposedChart>
          </ResponsiveContainer>
        </Section>
      </div>

      {/* ─── Section 7: AI Insights ───────────────────────────────── */}
      <Section
        title="AI-Generated Insights"
        subtitle="Machine learning analysis of historical patterns and real-time data"
      >
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <InsightCard
            icon={AlertTriangle}
            iconColor="text-red-600"
            iconBg="bg-red-100"
            title="Fall Risk Elevation"
            tag="SAFETY"
            tagColor="bg-red-100 text-red-700"
            description="Suresh Kumar's fall risk has increased 15% over the past week based on gait analysis and IMU tremor patterns. Consider scheduling a physiotherapy evaluation."
          />
          <InsightCard
            icon={Pill}
            iconColor="text-emerald-600"
            iconBg="bg-emerald-100"
            title="Medication Improvement"
            tag="POSITIVE"
            tagColor="bg-emerald-100 text-emerald-700"
            description="Rajesh Patel's medication adherence improved from 82% to 91% after voice reminder adjustment. The NFC tap-to-confirm latency decreased by 40%."
          />
          <InsightCard
            icon={Mic}
            iconColor="text-violet-600"
            iconBg="bg-violet-100"
            title="Acoustic Anomaly Pattern"
            tag="ATTENTION"
            tagColor="bg-violet-100 text-violet-700"
            description="Recurring acoustic anomaly patterns detected in Home-003 between 02:00–04:00. Suggest installing window/door sensor to rule out environmental causes."
          />
          <InsightCard
            icon={Sparkles}
            iconColor="text-blue-600"
            iconBg="bg-blue-100"
            title="System Performance"
            tag="SYSTEM"
            tagColor="bg-blue-100 text-blue-700"
            description="System-wide response times improved by 23% compared to the previous period. Edge-to-cloud latency averaging 340ms — well within the 2-second SLA."
          />
        </div>
      </Section>
    </div>
  );
}
