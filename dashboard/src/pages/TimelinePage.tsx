import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Calendar,
  ChevronDown,
  ChevronUp,
  Activity,
  ShieldAlert,
  Pill,
  TrendingUp,
  Gauge,
  Clock,
  ArrowUpDown,
  BarChart3,
  Wifi,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';

import { RESIDENTS, getTimeline } from '../data/mockData';
import { useLiveData } from '../contexts/LiveDataContext';
import { fetchTimeline as fetchTimelineApi } from '../services/api';
import StatusBadge from '../components/StatusBadge';
import EventIcon from '../components/EventIcon';
import type { AetherEvent, Severity, TimelineEntry } from '../types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatEventType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function formatTimeShort(ts: number): string {
  return format(new Date(ts), 'HH:mm');
}

function formatTimeFull(ts: number): string {
  return format(new Date(ts), 'HH:mm:ss');
}

function todayStr(): string {
  return format(new Date(), 'yyyy-MM-dd');
}

function severityWeight(s: Severity): number {
  const map: Record<Severity, number> = {
    CRITICAL: 5,
    HIGH: 4,
    MEDIUM: 3,
    LOW: 2,
    INFO: 1,
  };
  return map[s] ?? 0;
}

function segmentColor(severity: Severity): string {
  switch (severity) {
    case 'CRITICAL':
      return 'bg-red-500';
    case 'HIGH':
      return 'bg-orange-400';
    case 'MEDIUM':
      return 'bg-yellow-400';
    default:
      return 'bg-emerald-400';
  }
}

function dataPreview(data: Record<string, unknown>): string {
  const entries = Object.entries(data)
    .filter(([k]) => !k.startsWith('nfc_') && k !== 'privacy_note')
    .slice(0, 3)
    .map(([k, v]) => {
      const key = k.replace(/_/g, ' ');
      if (typeof v === 'number') return `${key}: ${v}`;
      if (typeof v === 'boolean') return `${key}: ${v ? 'Yes' : 'No'}`;
      return `${key}: ${String(v).replace(/_/g, ' ')}`;
    });
  return entries.join(' · ');
}

// ─── Metric Card ──────────────────────────────────────────────────────────────

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  suffix?: string;
}

function MetricCard({
  label,
  value,
  icon: Icon,
  iconBg,
  iconColor,
  suffix,
}: MetricCardProps) {
  return (
    <div className="relative overflow-hidden rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200/60 transition-all duration-200 hover:shadow-md hover:ring-gray-300/80">
      <div className="flex items-center gap-4">
        <div
          className={`flex items-center justify-center h-11 w-11 rounded-xl ${iconBg}`}
        >
          <Icon size={20} className={iconColor} />
        </div>
        <div className="min-w-0">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider truncate">
            {label}
          </p>
          <p className="mt-0.5 text-2xl font-bold tracking-tight text-gray-900">
            {value}
            {suffix && (
              <span className="text-sm font-medium text-gray-400 ml-0.5">
                {suffix}
              </span>
            )}
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Timeline Node ────────────────────────────────────────────────────────────

function TimelineNode({
  event,
  index,
}: {
  event: AetherEvent;
  index: number;
}) {
  const isLeft = index % 2 === 0;
  const critical =
    event.severity === 'CRITICAL' || event.severity === 'HIGH';

  const card = (
    <div
      className={`rounded-xl border p-4 shadow-sm transition-all duration-200 hover:shadow-md ${
        critical
          ? 'border-l-4 border-l-red-500 border-red-200 bg-red-50/50'
          : 'border-gray-200/80 bg-white'
      }`}
      style={{ animationDelay: `${index * 50}ms` }}
    >
      <div className="flex items-center gap-2 mb-2">
        <EventIcon eventType={event.event_type} size={18} />
        <span className="text-sm font-semibold text-gray-900">
          {formatEventType(event.event_type)}
        </span>
        <StatusBadge severity={event.severity} size="sm" />
      </div>
      <p className="text-xs text-gray-500 leading-relaxed">
        {dataPreview(event.data)}
      </p>
      <div className="mt-2 flex items-center gap-2 text-[11px] text-gray-400">
        <Gauge size={11} />
        <span className="text-aether-600 font-medium">
          {(event.confidence * 100).toFixed(1)}%
        </span>
        <span className="text-gray-300">·</span>
        {event.source_sensors.map((s) => (
          <span
            key={s}
            className="px-1.5 py-0.5 rounded bg-gray-100 text-[10px] font-medium uppercase tracking-wider text-gray-500"
          >
            {s}
          </span>
        ))}
      </div>
    </div>
  );

  const time = (
    <div className="flex items-center">
      <span className="text-xs font-mono text-gray-400 bg-gray-50 px-2 py-0.5 rounded whitespace-nowrap">
        {formatTimeShort(event.timestamp)}
      </span>
    </div>
  );

  return (
    <div className="relative grid grid-cols-[1fr_40px_1fr] gap-2 animate-fade-in">
      {/* Left */}
      <div className={`flex ${isLeft ? 'justify-end' : 'justify-end'}`}>
        {isLeft ? card : time}
      </div>

      {/* Center dot + line */}
      <div className="flex flex-col items-center">
        <div
          className={`h-3 w-3 rounded-full border-2 border-white shadow-sm z-10 ${segmentColor(
            event.severity,
          )}`}
        />
        <div className={`flex-1 w-0.5 ${segmentColor(event.severity)} opacity-30`} />
      </div>

      {/* Right */}
      <div className={`flex ${isLeft ? 'justify-start' : 'justify-start'}`}>
        {isLeft ? time : card}
      </div>
    </div>
  );
}

// ─── Sortable Table ───────────────────────────────────────────────────────────

type SortKey = 'time' | 'type' | 'severity' | 'confidence';

function EventTable({ events }: { events: AetherEvent[] }) {
  const [sortKey, setSortKey] = useState<SortKey>('time');
  const [sortAsc, setSortAsc] = useState(false);

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortAsc((a) => !a);
      } else {
        setSortKey(key);
        setSortAsc(key === 'time');
      }
    },
    [sortKey],
  );

  const sorted = useMemo(() => {
    const arr = [...events];
    const dir = sortAsc ? 1 : -1;
    arr.sort((a, b) => {
      switch (sortKey) {
        case 'time':
          return (a.timestamp - b.timestamp) * dir;
        case 'type':
          return a.event_type.localeCompare(b.event_type) * dir;
        case 'severity':
          return (severityWeight(a.severity) - severityWeight(b.severity)) * dir;
        case 'confidence':
          return (a.confidence - b.confidence) * dir;
        default:
          return 0;
      }
    });
    return arr;
  }, [events, sortKey, sortAsc]);

  const SortHeader = ({
    label,
    colKey,
  }: {
    label: string;
    colKey: SortKey;
  }) => (
    <th
      className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500 cursor-pointer select-none hover:text-gray-700 transition-colors"
      onClick={() => handleSort(colKey)}
    >
      <div className="flex items-center gap-1">
        {label}
        {sortKey === colKey ? (
          sortAsc ? (
            <ChevronUp size={12} />
          ) : (
            <ChevronDown size={12} />
          )
        ) : (
          <ArrowUpDown size={10} className="text-gray-300" />
        )}
      </div>
    </th>
  );

  return (
    <div className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-100">
          <thead className="bg-gray-50/80">
            <tr>
              <SortHeader label="Time" colKey="time" />
              <SortHeader label="Type" colKey="type" />
              <SortHeader label="Severity" colKey="severity" />
              <SortHeader label="Confidence" colKey="confidence" />
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                Sensors
              </th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                Details
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {sorted.map((event, idx) => (
              <tr
                key={event.event_id}
                className={`transition-colors hover:bg-aether-50/40 ${
                  idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/40'
                }`}
              >
                <td className="px-4 py-3 text-xs font-mono text-gray-500 whitespace-nowrap">
                  {formatTimeFull(event.timestamp)}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <EventIcon eventType={event.event_type} size={14} />
                    <span className="text-xs font-medium text-gray-800">
                      {formatEventType(event.event_type)}
                    </span>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge severity={event.severity} size="sm" />
                </td>
                <td className="px-4 py-3">
                  <span className="text-xs font-semibold text-aether-600">
                    {(event.confidence * 100).toFixed(1)}%
                  </span>
                </td>
                <td className="px-4 py-3">
                  <div className="flex gap-1 flex-wrap">
                    {event.source_sensors.map((s) => (
                      <span
                        key={s}
                        className="px-1.5 py-0.5 rounded bg-gray-100 text-[10px] font-medium uppercase tracking-wider text-gray-500"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                  {dataPreview(event.data)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function TimelinePage() {
  const { apiConnected } = useLiveData();
  const [selectedHome, setSelectedHome] = useState<string>(
    RESIDENTS[0].home_id,
  );
  const [selectedDate, setSelectedDate] = useState<string>(todayStr());
  const [apiTimeline, setApiTimeline] = useState<TimelineEntry | null>(null);
  const [dataSource, setDataSource] = useState<'api' | 'local'>('local');

  // Try to fetch real timeline data from API
  useEffect(() => {
    if (!apiConnected) {
      setApiTimeline(null);
      setDataSource('local');
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const entries = await fetchTimelineApi(selectedHome, 14);
        if (cancelled) return;
        // Find entry matching selectedDate
        const match = entries.find((e) => e.date === selectedDate);
        if (match) {
          // Build a TimelineEntry from API data
          const tl: TimelineEntry = {
            home_id: match.home_id,
            date: match.date,
            events: [], // API timeline doesn't include events array, use mock for events
            summary: match.daily_summary || `Real-time data: ${match.total_events} events, ${match.medication_adherence_pct}% medication adherence, ${match.sleep_hours}h sleep, ${match.steps} steps.`,
            metrics: {
              total_events: match.total_events,
              fall_count: match.fall_count,
              medication_adherence: match.medication_adherence_pct,
              activity_score: Math.min(100, (match.steps / 80)),
              acoustic_events: 0,
              avg_confidence: 0.94,
            },
          };
          setApiTimeline(tl);
          setDataSource('api');
        } else {
          setApiTimeline(null);
          setDataSource('local');
        }
      } catch {
        setApiTimeline(null);
        setDataSource('local');
      }
    })();
    return () => { cancelled = true; };
  }, [apiConnected, selectedHome, selectedDate]);

  const mockTimeline = useMemo(
    () => getTimeline(selectedHome, selectedDate),
    [selectedHome, selectedDate],
  );

  // Merge: use API metrics/summary if available, but always use mock events (API timeline doesn't contain event arrays)
  const timeline: TimelineEntry = useMemo(() => {
    if (apiTimeline) {
      return {
        ...apiTimeline,
        events: mockTimeline.events, // Use mock events for the visual timeline
        summary: apiTimeline.summary,
        metrics: apiTimeline.metrics,
      };
    }
    return mockTimeline;
  }, [apiTimeline, mockTimeline]);

  const resident = useMemo(
    () => RESIDENTS.find((r) => r.home_id === selectedHome),
    [selectedHome],
  );

  const isToday = selectedDate === todayStr();

  return (
    <div className="animate-fade-in space-y-6">
      {/* ── Controls Bar ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Timeline</h1>
          <p className="mt-0.5 text-sm text-gray-500 flex items-center gap-2">
            Chronological event history
            {dataSource === 'api' && (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                <Wifi size={10} /> AWS Live
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Home selector */}
          <select
            value={selectedHome}
            onChange={(e) => setSelectedHome(e.target.value)}
            className="input max-w-xs"
          >
            {RESIDENTS.map((r) => (
              <option key={r.home_id} value={r.home_id}>
                {r.home_id} — {r.name}
              </option>
            ))}
          </select>

          {/* Date picker */}
          <div className="relative">
            <Calendar
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
            />
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              max={todayStr()}
              className="input pl-9 pr-3 w-44"
            />
          </div>

          {/* Today button */}
          {!isToday && (
            <button
              onClick={() => setSelectedDate(todayStr())}
              className="btn-secondary text-xs"
            >
              <Clock size={14} className="mr-1.5" />
              Today
            </button>
          )}
        </div>
      </div>

      {/* ── Daily Summary ────────────────────────────────────────────── */}
      {timeline.summary && (
        <div className="rounded-2xl bg-gradient-to-r from-aether-50 to-white border border-aether-200/50 p-5">
          <div className="flex items-start gap-3">
            <div className="flex items-center justify-center h-9 w-9 rounded-xl bg-aether-100 flex-shrink-0">
              <BarChart3 size={18} className="text-aether-600" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-800">
                Daily Summary —{' '}
                {format(parseISO(selectedDate), 'MMMM d, yyyy')}
              </h3>
              <p className="mt-1 text-sm text-gray-600 leading-relaxed">
                {timeline.summary}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* ── Metric Cards ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <MetricCard
          label="Total Events"
          value={timeline.metrics.total_events}
          icon={Activity}
          iconBg="bg-aether-100"
          iconColor="text-aether-600"
        />
        <MetricCard
          label="Fall Count"
          value={timeline.metrics.fall_count}
          icon={ShieldAlert}
          iconBg={
            timeline.metrics.fall_count > 0 ? 'bg-red-100' : 'bg-emerald-100'
          }
          iconColor={
            timeline.metrics.fall_count > 0
              ? 'text-red-600'
              : 'text-emerald-600'
          }
        />
        <MetricCard
          label="Med Adherence"
          value={timeline.metrics.medication_adherence}
          icon={Pill}
          iconBg="bg-violet-100"
          iconColor="text-violet-600"
          suffix="%"
        />
        <MetricCard
          label="Activity Score"
          value={timeline.metrics.activity_score}
          icon={TrendingUp}
          iconBg="bg-amber-100"
          iconColor="text-amber-600"
        />
        <MetricCard
          label="Avg Confidence"
          value={(timeline.metrics.avg_confidence * 100).toFixed(1)}
          icon={Gauge}
          iconBg="bg-emerald-100"
          iconColor="text-emerald-600"
          suffix="%"
        />
      </div>

      {/* ── Visual Timeline ──────────────────────────────────────────── */}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-4">
          Event Timeline
        </h2>

        {timeline.events.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400">
            <Calendar size={32} className="mb-2 opacity-50" />
            <p className="text-sm">No events recorded for this day</p>
          </div>
        ) : (
          <div className="max-w-4xl mx-auto space-y-0">
            {timeline.events.map((event, idx) => (
              <TimelineNode
                key={event.event_id}
                event={event}
                index={idx}
              />
            ))}
            {/* Terminal dot */}
            <div className="flex justify-center">
              <div className="h-3 w-3 rounded-full bg-gray-300 border-2 border-white shadow-sm" />
            </div>
          </div>
        )}
      </div>

      {/* ── Events Table ─────────────────────────────────────────────── */}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-4">
          All Events — Detail View
        </h2>

        {timeline.events.length === 0 ? (
          <div className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 p-12 text-center text-gray-400 text-sm">
            No data for selected day
          </div>
        ) : (
          <EventTable events={timeline.events} />
        )}
      </div>
    </div>
  );
}
