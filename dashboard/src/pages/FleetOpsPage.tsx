import { useMemo, useState } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  Server,
  Wifi,
  WifiOff,
  MapPin,
  Cpu,
  HardDrive,
  Clock,
  AlertTriangle,
  Users,
  Activity,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Timer,
  Gauge,
  Coffee,
} from 'lucide-react';
import { formatDistanceToNow, format } from 'date-fns';

import {
  EDGE_GATEWAYS,
  SITE_HEALTH_DATA,
  CAREGIVER_WORKLOAD,
  SENSOR_HEALTH,
} from '../data/mockData';
import { useAuth } from '../contexts/AuthContext';
import type {
  EdgeGateway,
  SiteHealth,
  CaregiverWorkload,
  SensorHealth,
} from '../types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(ts: number): string {
  return formatDistanceToNow(new Date(ts), { addSuffix: true });
}

function statusDot(status: 'online' | 'offline' | 'degraded' | 'healthy' | 'critical'): string {
  switch (status) {
    case 'online':
    case 'healthy':
      return 'bg-emerald-500';
    case 'degraded':
      return 'bg-amber-400';
    case 'offline':
    case 'critical':
      return 'bg-red-500';
    default:
      return 'bg-gray-400';
  }
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'online':
    case 'healthy':
      return 'bg-emerald-50 text-emerald-700 ring-emerald-600/20';
    case 'degraded':
      return 'bg-amber-50 text-amber-700 ring-amber-600/20';
    case 'offline':
    case 'critical':
      return 'bg-red-50 text-red-700 ring-red-600/20';
    default:
      return 'bg-gray-50 text-gray-700 ring-gray-600/20';
  }
}

function burnoutColor(score: number): string {
  if (score < 30) return 'bg-emerald-500';
  if (score < 50) return 'bg-lime-500';
  if (score < 65) return 'bg-amber-400';
  if (score < 80) return 'bg-orange-500';
  return 'bg-red-500';
}

function burnoutTextColor(score: number): string {
  if (score < 30) return 'text-emerald-600';
  if (score < 50) return 'text-lime-600';
  if (score < 65) return 'text-amber-600';
  if (score < 80) return 'text-orange-600';
  return 'text-red-600';
}

// Derive sensor matrix from SENSOR_HEALTH + sites
type SensorCategory = 'pose' | 'acoustic' | 'imu' | 'medication' | 'environmental';
const SENSOR_CATEGORIES: SensorCategory[] = ['pose', 'acoustic', 'imu', 'medication', 'environmental'];
const SENSOR_CATEGORY_LABELS: Record<SensorCategory, string> = {
  pose: 'Camera/Pose',
  acoustic: 'Acoustic',
  imu: 'Watch/IMU',
  medication: 'Med Disp.',
  environmental: 'Environ.',
};

function getSensorStatus(
  sensorType: SensorCategory,
  siteId: string,
  allSensors: SensorHealth[],
): 'online' | 'degraded' | 'offline' {
  const matching = allSensors.filter(
    (s) =>
      s.type === sensorType &&
      s.sensor_id.includes(
        siteId === 'site-mumbai' ? 'home-001' :
        siteId === 'site-delhi' ? 'home-002' :
        siteId === 'site-bangalore' ? 'home-003' : 'home-004',
      ),
  );
  if (matching.length === 0) {
    // Check via "environmental" umbrella types
    const envTypes = ['environmental', 'temperature', 'humidity', 'air_quality'];
    if (sensorType === 'environmental') {
      const envMatching = allSensors.filter(
        (s) =>
          envTypes.includes(s.type) &&
          s.sensor_id.includes(
            siteId === 'site-mumbai' ? 'home-001' :
            siteId === 'site-delhi' ? 'home-002' :
            siteId === 'site-bangalore' ? 'home-003' : 'home-004',
          ),
      );
      if (envMatching.length === 0) return 'offline';
      if (envMatching.some((s) => s.status === 'offline')) return 'offline';
      if (envMatching.some((s) => s.status === 'degraded')) return 'degraded';
      return 'online';
    }
    return 'offline';
  }
  if (matching.some((s) => s.status === 'offline')) return 'offline';
  if (matching.some((s) => s.status === 'degraded')) return 'degraded';
  return 'online';
}

// ─── KPI Card ─────────────────────────────────────────────────────────────────

function KpiCard({
  label,
  value,
  icon: Icon,
  iconBg,
  iconColor,
  subtitle,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  subtitle?: string;
}) {
  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60 transition-all hover:shadow-md hover:ring-gray-300/80">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-500 truncate">{label}</p>
          <p className="mt-2 text-3xl font-bold tracking-tight text-gray-900">{value}</p>
          {subtitle && <p className="mt-1 text-xs text-gray-400">{subtitle}</p>}
        </div>
        <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${iconBg}`}>
          <Icon className={iconColor} size={22} strokeWidth={2} />
        </div>
      </div>
    </div>
  );
}

// ─── Usage Bar ────────────────────────────────────────────────────────────────

function UsageBar({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-10 text-[10px] font-medium text-gray-400 text-right">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all duration-500`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
      <span className="w-8 text-[10px] font-semibold text-gray-500 text-right">{value}%</span>
    </div>
  );
}

// ─── Gateway Card ─────────────────────────────────────────────────────────────

function GatewayCard({ gw }: { gw: EdgeGateway }) {
  const borderColor =
    gw.status === 'online'
      ? 'ring-gray-200/60 hover:ring-emerald-300/60'
      : gw.status === 'degraded'
        ? 'ring-amber-200/60 hover:ring-amber-400/60'
        : 'ring-red-200/60 hover:ring-red-400/60';
  const bgGradient =
    gw.status === 'degraded'
      ? 'bg-gradient-to-br from-amber-50/40 to-white'
      : gw.status === 'offline'
        ? 'bg-gradient-to-br from-red-50/40 to-white'
        : 'bg-white';

  return (
    <div className={`rounded-2xl ${bgGradient} p-5 shadow-sm ring-1 ${borderColor} transition-all hover:shadow-md`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2.5">
          <div className="relative">
            <Server size={18} className="text-gray-500" />
            <span className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white ${statusDot(gw.status)}`} />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900">{gw.siteName}</p>
            <p className="text-[11px] text-gray-400">{gw.id} · FW {gw.firmwareVersion}</p>
          </div>
        </div>
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ring-1 ring-inset ${statusBadgeClass(gw.status)}`}
        >
          {gw.status.toUpperCase()}
        </span>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3 py-3 border-t border-b border-gray-100">
        <div className="text-center">
          <p className="text-lg font-bold text-gray-900">{gw.uptime}%</p>
          <p className="text-[10px] text-gray-400">Uptime</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-bold text-gray-900">
            {gw.connectedSensors}<span className="text-xs text-gray-400">/{gw.totalSensors}</span>
          </p>
          <p className="text-[10px] text-gray-400">Sensors</p>
        </div>
        <div className="text-center">
          <p className="text-lg font-bold text-gray-900">{gw.networkLatency}<span className="text-xs text-gray-400">ms</span></p>
          <p className="text-[10px] text-gray-400">Latency</p>
        </div>
      </div>

      {/* Usage Bars */}
      <div className="mt-3 space-y-1.5">
        <UsageBar
          label="CPU"
          value={gw.cpuUsage}
          color={gw.cpuUsage > 80 ? 'bg-red-500' : gw.cpuUsage > 60 ? 'bg-amber-400' : 'bg-blue-500'}
        />
        <UsageBar
          label="MEM"
          value={gw.memoryUsage}
          color={gw.memoryUsage > 80 ? 'bg-red-500' : gw.memoryUsage > 60 ? 'bg-amber-400' : 'bg-blue-500'}
        />
      </div>

      {/* Footer */}
      <div className="mt-3 flex items-center gap-1.5 text-[11px] text-gray-400">
        <Clock size={11} />
        Last heartbeat {timeAgo(gw.lastHeartbeat)}
      </div>
    </div>
  );
}

// ─── Site Health Row ──────────────────────────────────────────────────────────

function SiteHealthRow({ site }: { site: SiteHealth }) {
  const slaOk = site.slaResponseTime <= site.slaTarget;
  return (
    <tr className="border-t border-gray-100 hover:bg-gray-50/60 transition-colors">
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <MapPin size={14} className="text-gray-400 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-gray-800">{site.siteName}</p>
            <p className="text-[11px] text-gray-400">{site.city}</p>
          </div>
        </div>
      </td>
      <td className="py-3 px-4 text-center">
        <span className="text-sm font-medium text-gray-700">{site.totalResidents}</span>
      </td>
      <td className="py-3 px-4 text-center">
        <span
          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ring-1 ring-inset ${statusBadgeClass(site.gatewayStatus)}`}
        >
          {site.gatewayStatus.toUpperCase()}
        </span>
      </td>
      <td className="py-3 px-4 text-center">
        {site.activeAlerts > 0 ? (
          <span className="inline-flex items-center gap-1 text-sm font-semibold text-red-600">
            <AlertTriangle size={13} />
            {site.activeAlerts}
          </span>
        ) : (
          <span className="text-sm text-gray-400">0</span>
        )}
      </td>
      <td className="py-3 px-4 text-center">
        <div className="flex items-center justify-center gap-1.5">
          <span className={`text-sm font-semibold ${slaOk ? 'text-emerald-600' : 'text-red-600'}`}>
            {site.slaResponseTime}s
          </span>
          <span className="text-[10px] text-gray-400">/ {site.slaTarget}s</span>
          {!slaOk && <AlertTriangle size={12} className="text-red-500" />}
        </div>
      </td>
      <td className="py-3 px-4">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                site.sensorCoverage >= 95
                  ? 'bg-emerald-500'
                  : site.sensorCoverage >= 85
                    ? 'bg-amber-400'
                    : 'bg-red-500'
              }`}
              style={{ width: `${site.sensorCoverage}%` }}
            />
          </div>
          <span className="text-xs font-medium text-gray-500 w-10 text-right">
            {site.sensorCoverage}%
          </span>
        </div>
      </td>
      <td className="py-3 px-4 text-center text-xs text-gray-400">
        {site.lastIncident ? timeAgo(site.lastIncident) : '—'}
      </td>
    </tr>
  );
}

// ─── Sensor Heatmap Cell ──────────────────────────────────────────────────────

function HeatmapCell({
  status,
  onClick,
}: {
  status: 'online' | 'degraded' | 'offline';
  onClick?: () => void;
}) {
  const bg =
    status === 'online'
      ? 'bg-emerald-400 hover:bg-emerald-500'
      : status === 'degraded'
        ? 'bg-amber-400 hover:bg-amber-500'
        : 'bg-red-400 hover:bg-red-500';
  return (
    <button
      onClick={onClick}
      className={`h-8 w-full rounded-md ${bg} transition-colors cursor-pointer`}
      title={status}
    />
  );
}

// ─── Caregiver Burnout Card ───────────────────────────────────────────────────

function CaregiverCard({ cg }: { cg: CaregiverWorkload }) {
  return (
    <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60 transition-all hover:shadow-md">
      <div className="flex items-center gap-3 mb-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-sm font-bold text-white shadow-sm">
          {cg.name.charAt(0)}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-800 truncate">{cg.name}</p>
          <p className="text-[11px] text-gray-400">{cg.shift}</p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center py-2 border-t border-gray-100">
        <div>
          <p className="text-sm font-bold text-gray-800">{cg.alertsHandled}</p>
          <p className="text-[10px] text-gray-400">Alerts</p>
        </div>
        <div>
          <p className="text-sm font-bold text-gray-800">{cg.avgResponseTime}s</p>
          <p className="text-[10px] text-gray-400">Avg Resp.</p>
        </div>
        <div>
          <p className="text-sm font-bold text-gray-800">{cg.hoursWorked}h</p>
          <p className="text-[10px] text-gray-400">Worked</p>
        </div>
      </div>

      {/* Burnout Score */}
      <div className="mt-3">
        <div className="flex items-center justify-between mb-1">
          <span className="text-[11px] font-medium text-gray-400">Burnout Score</span>
          <span className={`text-xs font-bold ${burnoutTextColor(cg.burnoutScore)}`}>
            {cg.burnoutScore}/100
          </span>
        </div>
        <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
          <div
            className={`h-full rounded-full ${burnoutColor(cg.burnoutScore)} transition-all duration-500`}
            style={{ width: `${cg.burnoutScore}%` }}
          />
        </div>
      </div>

      {/* Last Break */}
      <div className="mt-2 flex items-center gap-1 text-[11px] text-gray-400">
        <Coffee size={11} />
        Last break: {cg.lastBreak ? timeAgo(cg.lastBreak) : 'Unknown'}
      </div>
    </div>
  );
}

// ─── SLA Bar Chart Data ───────────────────────────────────────────────────────

function buildSlaData(sites: SiteHealth[]) {
  return sites.map((s) => ({
    name: s.city,
    response: s.slaResponseTime,
    target: s.slaTarget,
    breached: s.slaResponseTime > s.slaTarget,
  }));
}

// ─── Custom Tooltip ───────────────────────────────────────────────────────────

function SlaTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-gray-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur-sm">
      <p className="mb-1 text-xs font-semibold text-gray-500">{label}</p>
      {payload.map((entry: any) => (
        <div key={entry.name} className="flex items-center gap-2 text-sm">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-gray-600">{entry.name}:</span>
          <span className="font-semibold text-gray-900">{entry.value}s</span>
        </div>
      ))}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// Fleet & Ops Page
// ═════════════════════════════════════════════════════════════════════════════

export default function FleetOpsPage() {
  const { role } = useAuth();
  const [selectedCell, setSelectedCell] = useState<{ site: string; sensor: SensorCategory } | null>(null);

  const gateways = EDGE_GATEWAYS;
  const sites = SITE_HEALTH_DATA;
  const caregivers = CAREGIVER_WORKLOAD;

  // KPI calculations
  const totalSites = sites.length;
  const gwOnline = gateways.filter((g) => g.status === 'online').length;
  const avgSla = (sites.reduce((sum, s) => sum + s.slaResponseTime, 0) / sites.length).toFixed(1);
  const avgCoverage = (sites.reduce((sum, s) => sum + s.sensorCoverage, 0) / sites.length).toFixed(1);
  const slaData = useMemo(() => buildSlaData(sites), [sites]);

  // If not ops role, show limited view
  const isOps = role === 'ops';

  return (
    <div className="min-h-screen bg-gray-50/60">
      <div className="mx-auto max-w-[1440px] px-6 py-8 lg:px-10">
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="mb-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-purple-600 shadow-sm">
              <Server className="text-white" size={20} />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">
                Fleet & Operations
              </h1>
              <p className="text-sm text-gray-500">
                Edge infrastructure monitoring · {format(new Date(), 'EEEE, MMM d, yyyy · h:mm a')}
              </p>
            </div>
          </div>
        </div>

        {/* ── KPI Row ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Total Sites"
            value={totalSites}
            icon={MapPin}
            iconBg="bg-blue-50"
            iconColor="text-blue-600"
            subtitle="Active deployments"
          />
          <KpiCard
            label="Gateways Online"
            value={`${gwOnline}/${gateways.length}`}
            icon={Wifi}
            iconBg={gwOnline === gateways.length ? 'bg-emerald-50' : 'bg-amber-50'}
            iconColor={gwOnline === gateways.length ? 'text-emerald-600' : 'text-amber-600'}
            subtitle={gwOnline === gateways.length ? 'All healthy' : `${gateways.length - gwOnline} need attention`}
          />
          <KpiCard
            label="Avg SLA Response"
            value={`${avgSla}s`}
            icon={Timer}
            iconBg="bg-violet-50"
            iconColor="text-violet-600"
            subtitle="Across all sites"
          />
          <KpiCard
            label="Sensor Coverage"
            value={`${avgCoverage}%`}
            icon={Activity}
            iconBg="bg-sky-50"
            iconColor="text-sky-600"
            subtitle="Average across sites"
          />
        </div>

        {/* ── Edge Gateway Grid ───────────────────────────────────── */}
        <div className="mt-8">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Edge Gateways</h2>
            <p className="text-xs text-gray-400">Real-time gateway health and resource usage</p>
          </div>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
            {gateways.map((gw) => (
              <GatewayCard key={gw.id} gw={gw} />
            ))}
          </div>
        </div>

        {/* ── Site Health Table ────────────────────────────────────── */}
        <div className="mt-8 rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-900">Site Health Overview</h2>
            <p className="text-xs text-gray-400">SLA compliance and sensor coverage per site</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-gray-50/80 text-[11px] font-semibold text-gray-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Site</th>
                  <th className="py-3 px-4 text-center">Residents</th>
                  <th className="py-3 px-4 text-center">Gateway</th>
                  <th className="py-3 px-4 text-center">Alerts</th>
                  <th className="py-3 px-4 text-center">SLA (Actual / Target)</th>
                  <th className="py-3 px-4">Sensor Coverage</th>
                  <th className="py-3 px-4 text-center">Last Incident</th>
                </tr>
              </thead>
              <tbody>
                {sites.map((site) => (
                  <SiteHealthRow key={site.siteId} site={site} />
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ── Row: Sensor Heatmap + SLA Chart ─────────────────────── */}
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Sensor Drift Heatmap */}
          <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Sensor Status Heatmap</h2>
              <p className="text-xs text-gray-400">Sensor health across sites by type</p>
            </div>

            {/* Legend */}
            <div className="flex items-center gap-4 mb-4 text-[11px] text-gray-500">
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-sm bg-emerald-400" />
                Online
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-sm bg-amber-400" />
                Degraded
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-3 rounded-sm bg-red-400" />
                Offline
              </div>
            </div>

            {/* Heatmap Grid */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="py-2 px-2 text-left text-[10px] font-semibold text-gray-400 uppercase w-28">Site</th>
                    {SENSOR_CATEGORIES.map((cat) => (
                      <th key={cat} className="py-2 px-1 text-center text-[10px] font-semibold text-gray-400 uppercase">
                        {SENSOR_CATEGORY_LABELS[cat]}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sites.map((site) => (
                    <tr key={site.siteId}>
                      <td className="py-1.5 px-2 text-xs font-medium text-gray-600">{site.city}</td>
                      {SENSOR_CATEGORIES.map((cat) => {
                        const status = getSensorStatus(cat, site.siteId, SENSOR_HEALTH);
                        return (
                          <td key={cat} className="py-1.5 px-1">
                            <HeatmapCell
                              status={status}
                              onClick={() => setSelectedCell({ site: site.city, sensor: cat })}
                            />
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Selected cell detail */}
            {selectedCell && (
              <div className="mt-3 rounded-lg bg-gray-50 p-3 text-xs text-gray-600">
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    {selectedCell.site} · {SENSOR_CATEGORY_LABELS[selectedCell.sensor]}
                  </span>
                  <button
                    onClick={() => setSelectedCell(null)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    ✕
                  </button>
                </div>
                <p className="mt-1 text-gray-400">
                  Status: {getSensorStatus(
                    selectedCell.sensor,
                    sites.find((s) => s.city === selectedCell.site)?.siteId ?? '',
                    SENSOR_HEALTH,
                  ).toUpperCase()}
                  — Click to view detailed sensor logs (demo placeholder)
                </p>
              </div>
            )}
          </div>

          {/* SLA Response Chart */}
          <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
            <div className="mb-5">
              <h2 className="text-lg font-semibold text-gray-900">SLA Response Times</h2>
              <p className="text-xs text-gray-400">Average response vs. target per site</p>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={slaData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  tickLine={false}
                  axisLine={false}
                  unit="s"
                />
                <Tooltip content={<SlaTooltip />} />
                <Bar dataKey="response" name="Response Time" fill="#6366f1" radius={[6, 6, 0, 0]} maxBarSize={48} />
                <Bar dataKey="target" name="SLA Target" fill="#d1d5db" radius={[6, 6, 0, 0]} maxBarSize={48} />
              </BarChart>
            </ResponsiveContainer>

            {/* Breach indicator */}
            {slaData.some((d) => d.breached) && (
              <div className="mt-3 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700">
                <AlertTriangle size={14} />
                <span className="font-medium">SLA Breached:</span>
                {slaData
                  .filter((d) => d.breached)
                  .map((d) => d.name)
                  .join(', ')}
              </div>
            )}
          </div>
        </div>

        {/* ── Caregiver Burnout ────────────────────────────────────── */}
        {isOps && (
          <div className="mt-8">
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Caregiver Burnout Metrics</h2>
              <p className="text-xs text-gray-400">Workload and burnout indicators per caregiver</p>
            </div>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
              {caregivers.map((cg) => (
                <CaregiverCard key={cg.caregiverId} cg={cg} />
              ))}
            </div>
          </div>
        )}

        {/* ── Empty State (non-ops) ───────────────────────────────── */}
        {!isOps && (
          <div className="mt-8 rounded-2xl bg-white p-12 shadow-sm ring-1 ring-gray-200/60 text-center">
            <ShieldCheck size={40} className="mx-auto text-gray-300 mb-3" />
            <p className="text-sm font-medium text-gray-500">
              Additional operational controls are available for Ops administrators.
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Contact your site administrator for full fleet access.
            </p>
          </div>
        )}

        {/* ── Footer ─────────────────────────────────────────────── */}
        <div className="mt-12 border-t border-gray-200/60 pt-6 pb-8 text-center">
          <p className="text-xs text-gray-300">
            AETHER · Adaptive Elderly Tracking & Home Emergency Response ·
            Fleet Operations Console
          </p>
        </div>
      </div>
    </div>
  );
}
