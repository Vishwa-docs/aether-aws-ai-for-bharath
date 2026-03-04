import { useState, useMemo, useCallback } from 'react';
import {
  Bell,
  BellOff,
  Shield,
  ShieldAlert,
  Clock,
  ChevronUp,
  ChevronDown,
  AlertTriangle,
  CheckCircle,
  XOctagon,
  ArrowUpRight,
  Timer,
  TrendingUp,
  Filter,
  Activity,
  Zap,
  Phone,
  Wifi,
} from 'lucide-react';
import { formatDistanceToNow, format } from 'date-fns';

import {
  getActiveAlerts,
  MOCK_EVENTS,
  RESIDENTS,
} from '../data/mockData';
import { useLiveData } from '../contexts/LiveDataContext';
import { acknowledgeAlert } from '../services/api';
import StatusBadge from '../components/StatusBadge';
import EventIcon from '../components/EventIcon';
import type {
  AlertNotification,
  AetherEvent,
  Severity,
  EscalationTier,
  Resident,
} from '../types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(ts: number): string {
  return formatDistanceToNow(new Date(ts), { addSuffix: true });
}

function formatEventType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function residentById(id: string): Resident | undefined {
  return RESIDENTS.find((r) => r.resident_id === id);
}

function elapsedStr(ms: number): string {
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ${secs % 60}s`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m`;
}

function tierLabel(tier: EscalationTier): string {
  return tier.replace('_', ' ');
}

const TIER_ORDER: EscalationTier[] = ['TIER_1', 'TIER_2', 'TIER_3', 'TIER_4'];

function tierIndex(tier: EscalationTier): number {
  return TIER_ORDER.indexOf(tier);
}

function tierDescription(tier: EscalationTier): string {
  switch (tier) {
    case 'TIER_1':
      return 'In-Home Alert';
    case 'TIER_2':
      return 'Caregiver Notified';
    case 'TIER_3':
      return 'Emergency Contact';
    case 'TIER_4':
      return 'Emergency Services';
  }
}

function severitySort(s: Severity): number {
  const order: Record<Severity, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, INFO: 4 };
  return order[s];
}

function nameToInitials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

function nameToColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const colors = [
    'bg-aether-500',
    'bg-emerald-500',
    'bg-violet-500',
    'bg-rose-500',
    'bg-amber-500',
    'bg-cyan-500',
  ];
  return colors[Math.abs(hash) % colors.length];
}

type AlertStatus = 'acknowledged' | 'false_alarm' | 'auto_escalated' | 'active';

function deriveAlertStatus(ev: AetherEvent): AlertStatus {
  if (ev.acknowledged && ev.acknowledged_by === 'system_auto') return 'auto_escalated';
  if (ev.acknowledged) return 'acknowledged';
  return 'active';
}

// ─── Escalation Timeline Visual ───────────────────────────────────────────────

function EscalationTimeline({ currentTier }: { currentTier: EscalationTier }) {
  const currentIdx = tierIndex(currentTier);

  return (
    <div className="flex items-center gap-1">
      {TIER_ORDER.map((tier, idx) => {
        const isReached = idx <= currentIdx;
        const isCurrent = idx === currentIdx;
        return (
          <div key={tier} className="flex items-center">
            <div className="flex flex-col items-center">
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-bold transition-all ${
                  isCurrent
                    ? 'bg-red-500 text-white ring-2 ring-red-300 ring-offset-1'
                    : isReached
                    ? 'bg-orange-400 text-white'
                    : 'bg-gray-200 text-gray-400'
                }`}
              >
                {idx + 1}
              </div>
              <span
                className={`mt-1 text-[9px] font-medium whitespace-nowrap ${
                  isReached ? 'text-gray-700' : 'text-gray-400'
                }`}
              >
                {tierDescription(tier)}
              </span>
            </div>
            {idx < TIER_ORDER.length - 1 && (
              <div
                className={`mx-1 h-0.5 w-6 rounded transition-all ${
                  idx < currentIdx ? 'bg-orange-400' : 'bg-gray-200'
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Active Alert Card ────────────────────────────────────────────────────────

interface ActiveAlertCardProps {
  alert: AlertNotification;
  onAcknowledge: (id: string) => void;
  onEscalate: (id: string) => void;
  onFalseAlarm: (id: string) => void;
}

function ActiveAlertCard({
  alert,
  onAcknowledge,
  onEscalate,
  onFalseAlarm,
}: ActiveAlertCardProps) {
  const isCritical = alert.event.severity === 'CRITICAL';
  const elapsed = Date.now() - alert.created_at;
  const primaryContact = alert.resident.emergency_contacts.find((c) => c.is_primary);

  return (
    <div
      className={`relative overflow-hidden rounded-2xl bg-white shadow-md ring-1 transition-all duration-300 ${
        isCritical
          ? 'ring-red-300 alert-pulse'
          : alert.event.severity === 'HIGH'
          ? 'ring-orange-300'
          : 'ring-gray-200'
      }`}
    >
      {/* Severity stripe */}
      <div
        className={`h-1.5 ${
          isCritical
            ? 'bg-gradient-to-r from-red-500 via-red-600 to-red-500'
            : alert.event.severity === 'HIGH'
            ? 'bg-gradient-to-r from-orange-400 to-orange-500'
            : 'bg-gradient-to-r from-yellow-400 to-yellow-500'
        }`}
      />

      <div className="p-6">
        {/* Top row: severity + tier + time */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <StatusBadge severity={alert.event.severity} />
            <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-semibold text-gray-600 uppercase tracking-wide">
              {tierLabel(alert.escalation_tier)}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-sm">
            <Clock className="h-3.5 w-3.5 text-gray-400" />
            <span
              className={`font-semibold ${
                elapsed > 5 * 60 * 1000 ? 'text-red-600' : 'text-gray-600'
              }`}
            >
              {elapsedStr(elapsed)}
            </span>
          </div>
        </div>

        {/* Resident info */}
        <div className="mt-4 flex items-center gap-3">
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold text-white ${nameToColor(
              alert.resident.name,
            )}`}
          >
            {nameToInitials(alert.resident.name)}
          </div>
          <div>
            <p className="font-semibold text-gray-900">{alert.resident.name}</p>
            <p className="text-xs text-gray-500">
              Age {alert.resident.age} &middot; {alert.resident.home_id}
            </p>
          </div>
          {primaryContact && (
            <div className="ml-auto flex items-center gap-1.5 text-xs text-gray-500">
              <Phone className="h-3 w-3" />
              {primaryContact.name}
            </div>
          )}
        </div>

        {/* Event details */}
        <div className="mt-4 rounded-xl bg-gray-50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <EventIcon eventType={alert.event.event_type} size={16} />
            <span className="font-semibold text-gray-800">
              {formatEventType(alert.event.event_type)}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <span className="text-gray-400 text-xs">Confidence</span>
              <p className="font-semibold text-gray-700">
                {(alert.event.confidence * 100).toFixed(1)}%
              </p>
            </div>
            <div>
              <span className="text-gray-400 text-xs">Sensors</span>
              <div className="flex gap-1 mt-0.5">
                {alert.event.source_sensors.map((s) => (
                  <span
                    key={s}
                    className="rounded bg-aether-50 px-1.5 py-0.5 text-[10px] font-semibold text-aether-700 uppercase"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
            {/* Show data highlights */}
            {'room' in alert.event.data && alert.event.data.room != null && (
              <div>
                <span className="text-gray-400 text-xs">Location</span>
                <p className="font-medium text-gray-700 capitalize">
                  {String(alert.event.data.room).replace(/_/g, ' ')}
                </p>
              </div>
            )}
            {'fall_type' in alert.event.data && alert.event.data.fall_type != null && (
              <div>
                <span className="text-gray-400 text-xs">Fall Type</span>
                <p className="font-medium text-gray-700 capitalize">
                  {String(alert.event.data.fall_type)}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Escalation timeline */}
        <div className="mt-4">
          <p className="text-xs font-medium text-gray-400 uppercase tracking-wider mb-2">
            Escalation Progress
          </p>
          <EscalationTimeline currentTier={alert.escalation_tier} />
        </div>

        {/* Actions */}
        <div className="mt-5 flex items-center gap-2 pt-4 border-t border-gray-100">
          <button
            onClick={() => onAcknowledge(alert.id)}
            className="btn-primary flex-1 text-xs py-2.5"
          >
            <CheckCircle className="mr-1.5 h-4 w-4" />
            Acknowledge
          </button>
          <button
            onClick={() => onEscalate(alert.id)}
            className="btn-secondary text-xs py-2.5"
          >
            <ArrowUpRight className="mr-1 h-4 w-4" />
            Escalate
          </button>
          <button
            onClick={() => onFalseAlarm(alert.id)}
            className="btn text-xs py-2.5 text-gray-500 hover:bg-gray-100 border border-gray-200"
          >
            <BellOff className="mr-1 h-4 w-4" />
            False Alarm
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Sort state ───────────────────────────────────────────────────────────────

type SortKey = 'time' | 'severity' | 'confidence' | 'response';
type SortDir = 'asc' | 'desc';

function SortableHeader({
  label,
  sortKey,
  currentSort,
  currentDir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  currentSort: SortKey;
  currentDir: SortDir;
  onSort: (k: SortKey) => void;
}) {
  const active = currentSort === sortKey;
  return (
    <th
      className="px-4 py-3 font-semibold cursor-pointer select-none hover:text-gray-700 transition-colors group"
      onClick={() => onSort(sortKey)}
    >
      <div className="flex items-center gap-1">
        {label}
        <span className={`transition-opacity ${active ? 'opacity-100' : 'opacity-0 group-hover:opacity-40'}`}>
          {active && currentDir === 'asc' ? (
            <ChevronUp className="h-3 w-3" />
          ) : (
            <ChevronDown className="h-3 w-3" />
          )}
        </span>
      </div>
    </th>
  );
}

// ─── Page Component ───────────────────────────────────────────────────────────

export default function AlertsPage() {
  const { apiConnected, events: liveEvents } = useLiveData();
  // ── State ──
  const [alerts, setAlerts] = useState<AlertNotification[]>(() => getActiveAlerts());
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [acknowledgedAlerts, setAcknowledgedAlerts] = useState<
    Array<{ alert: AlertNotification; action: 'acknowledged' | 'false_alarm'; time: number }>
  >([]);

  const [severityFilter, setSeverityFilter] = useState<'ALL' | 'CRITICAL' | 'HIGH' | 'MEDIUM'>('ALL');
  const [statusFilter, setStatusFilter] = useState<'ACTIVE' | 'ACKNOWLEDGED' | 'ALL'>('ACTIVE');

  const [sortKey, setSortKey] = useState<SortKey>('time');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // ── Derived ──
  const activeAlerts = useMemo(
    () => alerts.filter((a) => a.is_active && !dismissedIds.has(a.id)),
    [alerts, dismissedIds],
  );

  const filteredActive = useMemo(() => {
    let result = activeAlerts;
    if (severityFilter !== 'ALL') {
      result = result.filter((a) => a.event.severity === severityFilter);
    }
    // Sort critical first
    return result.sort(
      (a, b) => severitySort(a.event.severity) - severitySort(b.event.severity),
    );
  }, [activeAlerts, severityFilter]);

  // History events: CRITICAL/HIGH from MOCK_EVENTS
  const historyEvents = useMemo(() => {
    let events = MOCK_EVENTS.filter(
      (e) => e.severity === 'CRITICAL' || e.severity === 'HIGH',
    )
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, 20);

    // Sort
    events = [...events].sort((a, b) => {
      switch (sortKey) {
        case 'time':
          return sortDir === 'desc' ? b.timestamp - a.timestamp : a.timestamp - b.timestamp;
        case 'severity':
          return sortDir === 'desc'
            ? severitySort(a.severity) - severitySort(b.severity)
            : severitySort(b.severity) - severitySort(a.severity);
        case 'confidence':
          return sortDir === 'desc' ? b.confidence - a.confidence : a.confidence - b.confidence;
        case 'response': {
          const aTime = a.acknowledged_at ? a.acknowledged_at - a.timestamp : Infinity;
          const bTime = b.acknowledged_at ? b.acknowledged_at - b.timestamp : Infinity;
          return sortDir === 'desc' ? bTime - aTime : aTime - bTime;
        }
        default:
          return 0;
      }
    });

    return events;
  }, [sortKey, sortDir]);

  // Statistics
  const stats = useMemo(() => {
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    const todayEvents = MOCK_EVENTS.filter(
      (e) =>
        e.timestamp >= todayStart.getTime() &&
        (e.severity === 'CRITICAL' || e.severity === 'HIGH'),
    );
    const totalToday = todayEvents.length || 3; // ensure demo has value

    const ackedEvents = MOCK_EVENTS.filter((e) => e.acknowledged);
    const responseTimes = ackedEvents
      .filter((e) => e.acknowledged_at)
      .map((e) => (e.acknowledged_at! - e.timestamp) / 1000);
    const avgResponse =
      responseTimes.length > 0
        ? responseTimes.reduce((s, t) => s + t, 0) / responseTimes.length
        : 11.4;

    const highSevTotal = MOCK_EVENTS.filter(
      (e) => e.severity === 'CRITICAL' || e.severity === 'HIGH',
    ).length;
    const ackRate = highSevTotal > 0 ? (ackedEvents.filter((e) => e.severity === 'CRITICAL' || e.severity === 'HIGH').length / highSevTotal) * 100 : 87;

    // False alarm rate: a demo value
    const falseAlarmRate = 4.2 + acknowledgedAlerts.filter((a) => a.action === 'false_alarm').length * 0.5;

    return {
      totalToday,
      avgResponse: avgResponse.toFixed(1),
      ackRate: Math.min(ackRate, 100).toFixed(1),
      falseAlarmRate: falseAlarmRate.toFixed(1),
    };
  }, [acknowledgedAlerts]);

  // ── Actions ──
  const handleAcknowledge = useCallback(
    (id: string) => {
      const alert = alerts.find((a) => a.id === id);
      if (!alert) return;
      setDismissedIds((prev) => new Set(prev).add(id));
      setAcknowledgedAlerts((prev) => [
        ...prev,
        {
          alert: { ...alert, is_active: false, response_time: (Date.now() - alert.created_at) / 1000 },
          action: 'acknowledged',
          time: Date.now(),
        },
      ]);
    },
    [alerts],
  );

  const handleEscalate = useCallback(
    (id: string) => {
      setAlerts((prev) =>
        prev.map((a) => {
          if (a.id !== id) return a;
          const nextIdx = Math.min(tierIndex(a.escalation_tier) + 1, 3);
          return { ...a, escalation_tier: TIER_ORDER[nextIdx] };
        }),
      );
    },
    [],
  );

  const handleFalseAlarm = useCallback(
    (id: string) => {
      const alert = alerts.find((a) => a.id === id);
      if (!alert) return;
      setDismissedIds((prev) => new Set(prev).add(id));
      setAcknowledgedAlerts((prev) => [
        ...prev,
        {
          alert: { ...alert, is_active: false },
          action: 'false_alarm',
          time: Date.now(),
        },
      ]);
    },
    [alerts],
  );

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
      } else {
        setSortKey(key);
        setSortDir('desc');
      }
    },
    [sortKey],
  );

  return (
    <div className="animate-fade-in space-y-6">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">Alert Management</h1>
          {apiConnected && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
              <Wifi size={10} /> AWS Live
            </span>
          )}
          {filteredActive.length > 0 && (
            <span className="flex h-7 min-w-[28px] items-center justify-center rounded-full bg-red-100 px-2.5 text-sm font-bold text-red-700 animate-pulse">
              {filteredActive.length} active
            </span>
          )}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white p-0.5">
            {(['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'] as const).map((sev) => (
              <button
                key={sev}
                onClick={() => setSeverityFilter(sev)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                  severityFilter === sev
                    ? sev === 'CRITICAL'
                      ? 'bg-red-500 text-white'
                      : sev === 'HIGH'
                      ? 'bg-orange-500 text-white'
                      : sev === 'MEDIUM'
                      ? 'bg-yellow-500 text-white'
                      : 'bg-gray-900 text-white'
                    : 'text-gray-500 hover:bg-gray-100'
                }`}
              >
                {sev === 'ALL' ? 'All' : sev}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-white p-0.5">
            {(['ACTIVE', 'ACKNOWLEDGED', 'ALL'] as const).map((st) => (
              <button
                key={st}
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-md transition-all ${
                  statusFilter === st
                    ? 'bg-aether-600 text-white'
                    : 'text-gray-500 hover:bg-gray-100'
                }`}
              >
                {st === 'ACTIVE' ? 'Active' : st === 'ACKNOWLEDGED' ? 'Acknowledged' : 'All'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Statistics ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-red-50 p-2">
              <Bell className="h-4 w-4 text-red-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{stats.totalToday}</p>
              <p className="text-xs text-gray-500">Alerts Today</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-aether-50 p-2">
              <Timer className="h-4 w-4 text-aether-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{stats.avgResponse}s</p>
              <p className="text-xs text-gray-500">Avg Response</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-emerald-50 p-2">
              <CheckCircle className="h-4 w-4 text-emerald-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{stats.ackRate}%</p>
              <p className="text-xs text-gray-500">Ack Rate</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-amber-50 p-2">
              <BellOff className="h-4 w-4 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{stats.falseAlarmRate}%</p>
              <p className="text-xs text-gray-500">False Alarm Rate</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Active Alerts ── */}
      {(statusFilter === 'ACTIVE' || statusFilter === 'ALL') && filteredActive.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <ShieldAlert className="h-5 w-5 text-red-500" />
            <h2 className="text-lg font-bold text-gray-900">Active Alerts</h2>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {filteredActive.map((alert) => (
              <ActiveAlertCard
                key={alert.id}
                alert={alert}
                onAcknowledge={handleAcknowledge}
                onEscalate={handleEscalate}
                onFalseAlarm={handleFalseAlarm}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Acknowledged section ── */}
      {(statusFilter === 'ACKNOWLEDGED' || statusFilter === 'ALL') && acknowledgedAlerts.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="h-5 w-5 text-emerald-500" />
            <h2 className="text-lg font-bold text-gray-900">Recently Handled</h2>
          </div>
          <div className="space-y-3">
            {acknowledgedAlerts.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center gap-4 rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60"
              >
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold text-white ${nameToColor(
                    item.alert.resident.name,
                  )}`}
                >
                  {nameToInitials(item.alert.resident.name)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">{item.alert.resident.name}</span>
                    <StatusBadge severity={item.alert.event.severity} size="sm" />
                    <EventIcon eventType={item.alert.event.event_type} size={14} />
                    <span className="text-sm text-gray-600">
                      {formatEventType(item.alert.event.event_type)}
                    </span>
                  </div>
                </div>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${
                    item.action === 'acknowledged'
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-amber-100 text-amber-700'
                  }`}
                >
                  {item.action === 'acknowledged' ? 'Acknowledged' : 'False Alarm'}
                </span>
                {item.alert.response_time != null && (
                  <span className="text-xs text-gray-400">{item.alert.response_time.toFixed(0)}s response</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── No Active Alerts ── */}
      {filteredActive.length === 0 && (statusFilter === 'ACTIVE' || statusFilter === 'ALL') && (
        <div className="flex flex-col items-center justify-center rounded-2xl bg-white p-12 shadow-sm ring-1 ring-gray-200/60">
          <div className="rounded-full bg-emerald-50 p-4">
            <CheckCircle className="h-10 w-10 text-emerald-500" />
          </div>
          <p className="mt-4 text-lg font-semibold text-gray-700">All Clear</p>
          <p className="text-sm text-gray-400">No active alerts matching your filters</p>
        </div>
      )}

      {/* ── Alert History ── */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Activity className="h-5 w-5 text-gray-500" />
          <h2 className="text-lg font-bold text-gray-900">Alert History</h2>
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500">
            Last {historyEvents.length} high-severity events
          </span>
        </div>
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left text-xs uppercase tracking-wider text-gray-500">
                  <SortableHeader
                    label="Time"
                    sortKey="time"
                    currentSort={sortKey}
                    currentDir={sortDir}
                    onSort={handleSort}
                  />
                  <th className="px-4 py-3 font-semibold">Resident</th>
                  <th className="px-4 py-3 font-semibold">Type</th>
                  <SortableHeader
                    label="Severity"
                    sortKey="severity"
                    currentSort={sortKey}
                    currentDir={sortDir}
                    onSort={handleSort}
                  />
                  <SortableHeader
                    label="Confidence"
                    sortKey="confidence"
                    currentSort={sortKey}
                    currentDir={sortDir}
                    onSort={handleSort}
                  />
                  <SortableHeader
                    label="Response"
                    sortKey="response"
                    currentSort={sortKey}
                    currentDir={sortDir}
                    onSort={handleSort}
                  />
                  <th className="px-4 py-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {historyEvents.map((ev) => {
                  const resident = residentById(ev.resident_id);
                  const rowStatus = deriveAlertStatus(ev);
                  const responseTime =
                    ev.acknowledged_at && ev.timestamp
                      ? ((ev.acknowledged_at - ev.timestamp) / 1000).toFixed(0)
                      : null;

                  return (
                    <tr
                      key={ev.event_id}
                      className={`transition-colors hover:bg-gray-50/70 ${
                        ev.severity === 'CRITICAL'
                          ? 'bg-red-50/30'
                          : ev.severity === 'HIGH'
                          ? 'bg-orange-50/20'
                          : ''
                      }`}
                    >
                      <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500">
                        <div>
                          <p className="font-medium text-gray-700">
                            {format(new Date(ev.timestamp), 'MMM d, HH:mm')}
                          </p>
                          <p className="text-gray-400">{timeAgo(ev.timestamp)}</p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {resident ? (
                          <div className="flex items-center gap-2">
                            <div
                              className={`flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-bold text-white ${nameToColor(
                                resident.name,
                              )}`}
                            >
                              {nameToInitials(resident.name)}
                            </div>
                            <div>
                              <p className="font-medium text-gray-800 text-xs">{resident.name}</p>
                              <p className="text-[10px] text-gray-400">{resident.home_id}</p>
                            </div>
                          </div>
                        ) : (
                          <span className="text-gray-400 text-xs">{ev.resident_id}</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <EventIcon eventType={ev.event_type} size={14} />
                          <span className="text-xs text-gray-700">
                            {formatEventType(ev.event_type)}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge severity={ev.severity} size="sm" />
                      </td>
                      <td className="px-4 py-3 text-xs font-medium text-gray-700">
                        {(ev.confidence * 100).toFixed(1)}%
                      </td>
                      <td className="px-4 py-3 text-xs whitespace-nowrap">
                        {responseTime ? (
                          <span className="font-medium text-gray-700">{responseTime}s</span>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                            rowStatus === 'acknowledged'
                              ? 'bg-emerald-100 text-emerald-700'
                              : rowStatus === 'auto_escalated'
                              ? 'bg-purple-100 text-purple-700'
                              : 'bg-red-100 text-red-700'
                          }`}
                        >
                          {rowStatus === 'acknowledged' && (
                            <>
                              <CheckCircle className="h-3 w-3" />
                              Acknowledged
                            </>
                          )}
                          {rowStatus === 'auto_escalated' && (
                            <>
                              <ArrowUpRight className="h-3 w-3" />
                              Auto-Escalated
                            </>
                          )}
                          {rowStatus === 'active' && (
                            <>
                              <AlertTriangle className="h-3 w-3" />
                              Pending
                            </>
                          )}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
