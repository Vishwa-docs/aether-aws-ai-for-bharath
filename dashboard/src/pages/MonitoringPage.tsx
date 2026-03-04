import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  Cpu,
  Radio,
  Wifi,
  WifiOff,
  Battery,
  BatteryLow,
  BatteryWarning,
  Gauge,
  ChevronDown,
  ChevronRight,
  Mic,
  Watch,
  Pill,
  Heart,
  Eye,
  Thermometer,
  Droplets,
  Wind,
  Flame,
  AlertTriangle,
  Sun,
  Volume2,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

import {
  RESIDENTS,
  SENSOR_HEALTH,
  generateLiveEvent,
} from '../data/mockData';
import { useLiveData } from '../contexts/LiveDataContext';
import StatusBadge from '../components/StatusBadge';
import EventIcon from '../components/EventIcon';
import type { AetherEvent, SensorHealth, SensorType } from '../types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatEventType(type: string): string {
  return type
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function residentName(residentId: string): string {
  return RESIDENTS.find((r) => r.resident_id === residentId)?.name ?? 'Unknown';
}

function timeAgo(ts: number): string {
  return formatDistanceToNow(new Date(ts), { addSuffix: true });
}

const SENSOR_ICONS: Record<SensorType, React.ElementType> = {
  imu: Watch,
  acoustic: Mic,
  pose: Eye,
  medication: Pill,
  vital: Heart,
  environmental: Thermometer,
  toilet: Droplets,
  temperature: Thermometer,
  humidity: Droplets,
  air_quality: Wind,
  smoke: Flame,
  co: AlertTriangle,
  light: Sun,
  noise: Volume2,
};

function sensorStatusDot(status: SensorHealth['status']): string {
  switch (status) {
    case 'online':
      return 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.6)]';
    case 'degraded':
      return 'bg-amber-400 shadow-[0_0_6px_rgba(251,191,36,0.5)]';
    case 'offline':
      return 'bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]';
  }
}

function batteryIcon(pct: number) {
  if (pct <= 15) return BatteryLow;
  if (pct <= 40) return BatteryWarning;
  return Battery;
}

function batteryColor(pct: number): string {
  if (pct <= 15) return 'text-red-500';
  if (pct <= 40) return 'text-amber-500';
  return 'text-emerald-500';
}

function signalColor(q: number): string {
  if (q >= 0.8) return 'bg-emerald-400';
  if (q >= 0.5) return 'bg-amber-400';
  return 'bg-red-400';
}

function isCriticalEvent(event: AetherEvent): boolean {
  return event.severity === 'CRITICAL' || event.severity === 'HIGH';
}

// ─── Sensor Card ──────────────────────────────────────────────────────────────

function SensorCard({ sensor }: { sensor: SensorHealth }) {
  const Icon = SENSOR_ICONS[sensor.type] ?? Cpu;
  const BattIcon = sensor.battery_pct != null ? batteryIcon(sensor.battery_pct) : null;

  return (
    <div
      className={`rounded-xl border p-3 transition-all duration-200 ${
        sensor.status === 'online'
          ? 'border-gray-200/80 bg-white hover:shadow-sm'
          : sensor.status === 'degraded'
          ? 'border-amber-200 bg-amber-50/40'
          : 'border-red-200 bg-red-50/40'
      }`}
    >
      <div className="flex items-center gap-2">
        <div
          className={`flex items-center justify-center h-8 w-8 rounded-lg ${
            sensor.status === 'online'
              ? 'bg-aether-50 text-aether-600'
              : sensor.status === 'degraded'
              ? 'bg-amber-100 text-amber-600'
              : 'bg-red-100 text-red-500'
          }`}
        >
          <Icon size={16} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-gray-800 capitalize truncate">
            {sensor.room.replace(/_/g, ' ')}
          </p>
          <p className="text-[10px] text-gray-400 uppercase tracking-wider">
            {sensor.type}
          </p>
        </div>
        <span
          className={`h-2 w-2 rounded-full flex-shrink-0 ${sensorStatusDot(sensor.status)}`}
        />
      </div>

      {/* Battery */}
      {sensor.battery_pct != null && BattIcon && (
        <div className="mt-2 flex items-center gap-1.5">
          <BattIcon size={12} className={batteryColor(sensor.battery_pct)} />
          <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                sensor.battery_pct <= 15
                  ? 'bg-red-400'
                  : sensor.battery_pct <= 40
                  ? 'bg-amber-400'
                  : 'bg-emerald-400'
              }`}
              style={{ width: `${sensor.battery_pct}%` }}
            />
          </div>
          <span className="text-[10px] text-gray-500 w-7 text-right">
            {sensor.battery_pct}%
          </span>
        </div>
      )}

      {/* Signal quality */}
      <div className="mt-1.5 flex items-center gap-1.5">
        <Gauge size={11} className="text-gray-400" />
        <div className="flex-1 h-1.5 rounded-full bg-gray-100 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${signalColor(sensor.signal_quality)}`}
            style={{ width: `${Math.round(sensor.signal_quality * 100)}%` }}
          />
        </div>
        <span className="text-[10px] text-gray-500 w-7 text-right">
          {Math.round(sensor.signal_quality * 100)}%
        </span>
      </div>

      {/* Last seen */}
      <p className="mt-1.5 text-[10px] text-gray-400 truncate">
        {sensor.status === 'offline' ? (
          <span className="text-red-400 font-medium">
            Offline · {timeAgo(sensor.last_seen)}
          </span>
        ) : (
          <>Seen {timeAgo(sensor.last_seen)}</>
        )}
      </p>
    </div>
  );
}

// ─── Live Event Card ──────────────────────────────────────────────────────────

function LiveEventCard({
  event,
  isNew,
}: {
  event: AetherEvent;
  isNew: boolean;
}) {
  const critical = isCriticalEvent(event);

  return (
    <div
      className={`rounded-xl border p-4 transition-all duration-500 ${
        isNew ? 'animate-slide-down' : ''
      } ${
        critical
          ? 'border-l-4 border-l-red-500 border-red-200 bg-red-50/50'
          : 'border-gray-200/80 bg-white'
      } hover:shadow-sm`}
    >
      <div className="flex items-start gap-3">
        {/* Timestamp */}
        <div className="flex-shrink-0 pt-0.5">
          <span className="text-xs font-mono text-gray-400 bg-gray-50 px-2 py-0.5 rounded">
            {formatTime(event.timestamp)}
          </span>
        </div>

        {/* Icon */}
        <div className="flex-shrink-0 pt-0.5">
          <EventIcon eventType={event.event_type} size={20} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-gray-900">
              {formatEventType(event.event_type)}
            </span>
            <StatusBadge severity={event.severity} size="sm" />
          </div>
          <div className="mt-1 flex items-center gap-3 text-xs text-gray-500 flex-wrap">
            <span className="font-medium text-gray-700">
              {residentName(event.resident_id)}
            </span>
            <span className="text-gray-300">·</span>
            <span>{event.home_id}</span>
            <span className="text-gray-300">·</span>
            <span className="text-aether-600 font-medium">
              {(event.confidence * 100).toFixed(1)}%
            </span>
          </div>
          {/* Sensor chips */}
          <div className="mt-2 flex gap-1 flex-wrap">
            {event.source_sensors.map((s) => (
              <span
                key={s}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-gray-100 text-[10px] font-medium text-gray-600 uppercase tracking-wider"
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Quick Stats ──────────────────────────────────────────────────────────────

function QuickStats({ events }: { events: AetherEvent[] }) {
  const oneHourAgo = Date.now() - 60 * 60 * 1000;
  const recentEvents = events.filter((e) => e.timestamp > oneHourAgo);
  const eventsLastHour = recentEvents.length;
  const avgConfidence =
    events.length > 0
      ? (events.reduce((s, e) => s + e.confidence, 0) / events.length) * 100
      : 0;
  const activeSensors = SENSOR_HEALTH.filter(
    (s) => s.status === 'online',
  ).length;

  return (
    <div className="grid grid-cols-3 gap-3">
      <div className="rounded-xl bg-white border border-gray-200/80 p-3 text-center">
        <Activity size={16} className="mx-auto text-aether-500 mb-1" />
        <p className="text-lg font-bold text-gray-900">{eventsLastHour}</p>
        <p className="text-[10px] text-gray-400 uppercase tracking-wider">
          Last Hour
        </p>
      </div>
      <div className="rounded-xl bg-white border border-gray-200/80 p-3 text-center">
        <Gauge size={16} className="mx-auto text-emerald-500 mb-1" />
        <p className="text-lg font-bold text-gray-900">
          {avgConfidence.toFixed(1)}%
        </p>
        <p className="text-[10px] text-gray-400 uppercase tracking-wider">
          Avg Conf.
        </p>
      </div>
      <div className="rounded-xl bg-white border border-gray-200/80 p-3 text-center">
        <Radio size={16} className="mx-auto text-violet-500 mb-1" />
        <p className="text-lg font-bold text-gray-900">
          {activeSensors}/{SENSOR_HEALTH.length}
        </p>
        <p className="text-[10px] text-gray-400 uppercase tracking-wider">
          Sensors
        </p>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

const MAX_FEED_EVENTS = 50;

export default function MonitoringPage() {
  const [events, setEvents] = useState<AetherEvent[]>([]);
  const [newEventIds, setNewEventIds] = useState<Set<string>>(new Set());
  const [homeFilter, setHomeFilter] = useState<string>('all');
  const [expandedHomes, setExpandedHomes] = useState<Set<string>>(
    () => new Set(RESIDENTS.map((r) => r.home_id)),
  );
  const feedRef = useRef<HTMLDivElement>(null);
  const { apiConnected, events: apiEvents, residents } = useLiveData();

  // Seed initial events – mix real API events with generated ones
  useEffect(() => {
    const seed: AetherEvent[] = [];

    // Try to use real API events first
    if (apiConnected) {
      const allApiEvents = Object.values(apiEvents).flat();
      const mapped = allApiEvents.slice(0, 8).map((e) => ({
        event_id: e.event_id,
        home_id: e.home_id,
        resident_id: e.resident_id,
        event_type: e.event_type as AetherEvent['event_type'],
        severity: e.severity as AetherEvent['severity'],
        timestamp: typeof e.timestamp === 'number' ? e.timestamp * 1000 : Date.now(),
        confidence: typeof e.confidence === 'string' ? parseFloat(e.confidence) : (e.confidence as number),
        source_sensors: e.source_sensors as AetherEvent['source_sensors'],
        privacy_level: e.privacy_level,
        data: e.data as Record<string, unknown>,
      }));
      seed.push(...mapped);
    }

    // Fill remaining with generated
    while (seed.length < 8) {
      const e = generateLiveEvent();
      e.timestamp = Date.now() - (8 - seed.length) * 4000;
      seed.push(e);
    }
    setEvents(seed);
  }, [apiConnected, apiEvents]);

  // Live event ticker
  useEffect(() => {
    const interval = setInterval(() => {
      const newEvent = generateLiveEvent();
      setEvents((prev) => [newEvent, ...prev].slice(0, MAX_FEED_EVENTS));
      setNewEventIds((prev) => {
        const next = new Set(prev);
        next.add(newEvent.event_id);
        return next;
      });

      // Clear "new" flag after animation
      setTimeout(() => {
        setNewEventIds((prev) => {
          const next = new Set(prev);
          next.delete(newEvent.event_id);
          return next;
        });
      }, 800);
    }, 3000 + Math.random() * 2000);

    return () => clearInterval(interval);
  }, []);

  // Filter events
  const filteredEvents = useMemo(
    () =>
      homeFilter === 'all'
        ? events
        : events.filter((e) => e.home_id === homeFilter),
    [events, homeFilter],
  );

  // Group sensors by home
  const sensorsByHome = useMemo(() => {
    const groups: Record<string, SensorHealth[]> = {};
    SENSOR_HEALTH.forEach((s) => {
      const homeId = s.sensor_id.split('-').slice(0, 2).join('-');
      if (!groups[homeId]) groups[homeId] = [];
      groups[homeId].push(s);
    });
    return groups;
  }, []);

  const toggleHome = useCallback((homeId: string) => {
    setExpandedHomes((prev) => {
      const next = new Set(prev);
      if (next.has(homeId)) next.delete(homeId);
      else next.add(homeId);
      return next;
    });
  }, []);

  const homes = RESIDENTS.map((r) => ({
    home_id: r.home_id,
    name: r.name,
  }));

  return (
    <div className="animate-fade-in space-y-6">
      {/* ── Top Bar ──────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">Live Monitoring</h1>
          <div className="flex items-center gap-2 bg-emerald-50 text-emerald-700 px-3 py-1 rounded-full text-xs font-semibold">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            LIVE
          </div>
        </div>

        <select
          value={homeFilter}
          onChange={(e) => setHomeFilter(e.target.value)}
          className="input max-w-xs"
        >
          <option value="all">All Homes</option>
          {homes.map((h) => (
            <option key={h.home_id} value={h.home_id}>
              {h.home_id} — {h.name}
            </option>
          ))}
        </select>
      </div>

      {/* ── Content Grid ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Live Event Feed */}
        <div className="lg:col-span-2 space-y-3" ref={feedRef}>
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider">
              Event Feed
            </h2>
            <span className="text-xs text-gray-400">
              {filteredEvents.length} events
            </span>
          </div>

          {filteredEvents.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <Activity size={32} className="mb-2 opacity-50" />
              <p className="text-sm">Waiting for events…</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[calc(100vh-200px)] overflow-y-auto pr-1">
              {filteredEvents.map((event) => (
                <LiveEventCard
                  key={event.event_id}
                  event={event}
                  isNew={newEventIds.has(event.event_id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right: Sensor Grid + Quick Stats */}
        <div className="space-y-6">
          {/* Sensor Grid */}
          <div>
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
              Sensor Health
            </h2>
            <div className="space-y-4">
              {Object.entries(sensorsByHome).map(([homeId, sensors]) => {
                const resident = RESIDENTS.find((r) => r.home_id === homeId);
                const expanded = expandedHomes.has(homeId);
                const onlineCount = sensors.filter(
                  (s) => s.status === 'online',
                ).length;
                const hasIssue = sensors.some(
                  (s) => s.status !== 'online',
                );

                return (
                  <div key={homeId}>
                    <button
                      onClick={() => toggleHome(homeId)}
                      className={`w-full flex items-center justify-between rounded-lg px-3 py-2 text-left transition-colors ${
                        hasIssue
                          ? 'bg-amber-50 hover:bg-amber-100/70'
                          : 'bg-gray-50 hover:bg-gray-100'
                      }`}
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        {expanded ? (
                          <ChevronDown size={14} className="text-gray-400 flex-shrink-0" />
                        ) : (
                          <ChevronRight size={14} className="text-gray-400 flex-shrink-0" />
                        )}
                        <span className="text-xs font-semibold text-gray-700 truncate">
                          {homeId}
                        </span>
                        {resident && (
                          <span className="text-[10px] text-gray-400 truncate">
                            — {resident.name}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        {hasIssue ? (
                          <WifiOff size={12} className="text-amber-500" />
                        ) : (
                          <Wifi size={12} className="text-emerald-500" />
                        )}
                        <span className="text-[10px] text-gray-500">
                          {onlineCount}/{sensors.length}
                        </span>
                      </div>
                    </button>

                    {expanded && (
                      <div className="mt-2 grid grid-cols-2 gap-2 animate-fade-in">
                        {sensors.map((sensor) => (
                          <SensorCard key={sensor.sensor_id} sensor={sensor} />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Quick Stats */}
          <div>
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
              Quick Stats
            </h2>
            <QuickStats events={events} />
          </div>
        </div>
      </div>
    </div>
  );
}
