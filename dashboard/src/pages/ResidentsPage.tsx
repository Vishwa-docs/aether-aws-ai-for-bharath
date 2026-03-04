import { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Search,
  UserPlus,
  Phone,
  Shield,
  ChevronDown,
  ChevronUp,
  X,
  Activity,
  Clock,
  Pill,
  AlertTriangle,
  Users,
  Heart,
  Eye,
  ExternalLink,
  Moon,
  Wind,
  Wifi,
  Sparkles,
  Loader2,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

import { RESIDENTS, getRecentEvents, MOCK_EVENTS, getSleepMetrics, getRespiratoryMetrics } from '../data/mockData';
import { useLiveData } from '../contexts/LiveDataContext';
import { fetchHealthInsights, type HealthInsightsResponse } from '../services/api';
import EventIcon from '../components/EventIcon';
import type { Resident, AetherEvent } from '../types';

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
    'bg-indigo-500',
    'bg-pink-500',
  ];
  return colors[Math.abs(hash) % colors.length];
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

function riskLabel(score: number): string {
  if (score < 0.3) return 'Low Risk';
  if (score <= 0.6) return 'Moderate Risk';
  return 'High Risk';
}

function riskBarColor(score: number): string {
  if (score < 0.3) return 'bg-emerald-500';
  if (score <= 0.6) return 'bg-amber-400';
  return 'bg-red-500';
}

function riskTextColor(score: number): string {
  if (score < 0.3) return 'text-emerald-600';
  if (score <= 0.6) return 'text-amber-600';
  return 'text-red-600';
}

function riskBgColor(score: number): string {
  if (score < 0.3) return 'bg-emerald-50';
  if (score <= 0.6) return 'bg-amber-50';
  return 'bg-red-50';
}

function privacyBadge(level: string): { bg: string; text: string } {
  switch (level) {
    case 'elevated':
      return { bg: 'bg-purple-100 text-purple-700', text: 'Elevated Privacy' };
    case 'maximum':
      return { bg: 'bg-red-100 text-red-700', text: 'Maximum Privacy' };
    default:
      return { bg: 'bg-gray-100 text-gray-600', text: 'Standard Privacy' };
  }
}

// ─── Resident Card ────────────────────────────────────────────────────────────

interface ResidentCardProps {
  resident: Resident;
  recentEvents: AetherEvent[];
  onSelect: (r: Resident) => void;
}

function ResidentCard({ resident, recentEvents, onSelect }: ResidentCardProps) {
  const [medsExpanded, setMedsExpanded] = useState(false);

  const risk = resident.risk_score ?? 0;
  const primaryContact = resident.emergency_contacts.find((c) => c.is_primary);
  const otherContactCount = resident.emergency_contacts.length - 1;
  const privacy = privacyBadge(resident.privacy_level);

  return (
    <div
      className="group relative overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 transition-all duration-200 hover:shadow-lg hover:ring-gray-300/80 cursor-pointer"
      onClick={() => onSelect(resident)}
    >
      {/* Top accent bar */}
      <div
        className={`h-1 ${
          resident.status === 'active' ? 'bg-gradient-to-r from-aether-400 to-aether-600' : 'bg-gray-300'
        }`}
      />

      <div className="p-6">
        {/* ── Header: Avatar + Name + Status ── */}
        <div className="flex items-start gap-4">
          <div
            className={`flex h-14 w-14 flex-shrink-0 items-center justify-center rounded-full text-lg font-bold text-white shadow-inner ${nameToColor(
              resident.name,
            )}`}
          >
            {getInitials(resident.name)}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-semibold text-gray-900 truncate">
                {resident.name}
              </h3>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  resident.status === 'active'
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-red-50 text-red-700'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    resident.status === 'active' ? 'bg-emerald-500' : 'bg-red-500'
                  }`}
                />
                {resident.status === 'active' ? 'Active' : 'Inactive'}
              </span>
            </div>
            <p className="mt-0.5 text-sm text-gray-500">
              Age {resident.age} &middot; {resident.home_id}
            </p>
          </div>

          {/* Privacy badge */}
          <span
            className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${privacy.bg}`}
          >
            <Shield className="mr-1 inline h-3 w-3" />
            {privacy.text}
          </span>
        </div>

        {/* ── Risk Score ── */}
        <div className="mt-5">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs font-medium text-gray-500">Risk Score</span>
            <span className={`text-xs font-bold ${riskTextColor(risk)}`}>
              {(risk * 100).toFixed(0)}% &middot; {riskLabel(risk)}
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-gray-100">
            <div
              className={`h-full rounded-full transition-all duration-700 ${riskBarColor(risk)}`}
              style={{ width: `${risk * 100}%` }}
            />
          </div>
        </div>

        {/* ── Conditions ── */}
        <div className="mt-4">
          <p className="mb-1.5 text-xs font-medium text-gray-400 uppercase tracking-wider">
            Conditions
          </p>
          <div className="flex flex-wrap gap-1.5">
            {resident.conditions.map((c) => (
              <span
                key={c}
                className="inline-flex items-center rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-medium text-blue-700 ring-1 ring-inset ring-blue-200/60"
              >
                {c}
              </span>
            ))}
          </div>
        </div>

        {/* ── Medications (Expandable) ── */}
        <div className="mt-4">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setMedsExpanded(!medsExpanded);
            }}
            className="flex w-full items-center justify-between text-xs font-medium text-gray-400 uppercase tracking-wider hover:text-gray-600 transition-colors"
          >
            <span className="flex items-center gap-1">
              <Pill className="h-3 w-3" />
              Medications ({resident.medications.length})
            </span>
            {medsExpanded ? (
              <ChevronUp className="h-3.5 w-3.5" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" />
            )}
          </button>

          {medsExpanded && (
            <div className="mt-2 space-y-1.5">
              {resident.medications.map((med) => (
                <div
                  key={med.name}
                  className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2"
                >
                  <div>
                    <p className="text-sm font-medium text-gray-800">{med.name}</p>
                    <p className="text-[11px] text-gray-500">{med.dosage}</p>
                  </div>
                  <div className="flex gap-1">
                    {med.schedule.map((s) => (
                      <span
                        key={s}
                        className="rounded bg-aether-50 px-1.5 py-0.5 text-[10px] font-medium text-aether-700"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Emergency Contact ── */}
        {primaryContact && (
          <div className="mt-4">
            <p className="mb-1 text-xs font-medium text-gray-400 uppercase tracking-wider">
              Emergency Contact
            </p>
            <div className="flex items-center gap-2 text-sm">
              <Phone className="h-3.5 w-3.5 text-gray-400" />
              <span className="font-medium text-gray-700">{primaryContact.name}</span>
              <span className="text-gray-400">({primaryContact.relationship})</span>
              <span className="text-aether-600">{primaryContact.phone}</span>
              {otherContactCount > 0 && (
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                  +{otherContactCount} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* ── Recent Activity ── */}
        <div className="mt-4">
          <p className="mb-1.5 text-xs font-medium text-gray-400 uppercase tracking-wider">
            Recent Activity
          </p>
          {recentEvents.length > 0 ? (
            <div className="divide-y divide-gray-100">
              {recentEvents.map((ev) => (
                <div
                  key={ev.event_id}
                  className="flex items-center gap-2.5 py-1.5"
                >
                  <EventIcon eventType={ev.event_type} size={14} />
                  <span className="flex-1 text-xs text-gray-700 truncate">
                    {formatEventType(ev.event_type)}
                  </span>
                  <span className="text-[11px] text-gray-400 whitespace-nowrap">
                    {timeAgo(ev.timestamp)}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-gray-400 italic">No recent events</p>
          )}
        </div>

        {/* ── Bottom Actions ── */}
        <div className="mt-5 flex items-center gap-2 pt-4 border-t border-gray-100">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onSelect(resident);
            }}
            className="btn-primary flex-1 text-xs py-2"
          >
            <Eye className="mr-1.5 h-3.5 w-3.5" />
            View Details
          </button>
          <button
            onClick={(e) => e.stopPropagation()}
            className="btn-secondary flex-1 text-xs py-2"
          >
            <Clock className="mr-1.5 h-3.5 w-3.5" />
            View Timeline
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Detail Modal ─────────────────────────────────────────────────────────────

interface ResidentModalProps {
  resident: Resident;
  onClose: () => void;
}

function ResidentModal({ resident, onClose }: ResidentModalProps) {
  const allEvents = useMemo(
    () => getRecentEvents(resident.home_id, 30),
    [resident.home_id],
  );

  const risk = resident.risk_score ?? 0;
  const privacy = privacyBadge(resident.privacy_level);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white shadow-2xl animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-gray-200 bg-white px-8 py-5 rounded-t-2xl">
          <div className="flex items-center gap-4">
            <div
              className={`flex h-16 w-16 items-center justify-center rounded-full text-xl font-bold text-white shadow-lg ${nameToColor(
                resident.name,
              )}`}
            >
              {getInitials(resident.name)}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-gray-900">
                  {resident.name}
                </h2>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    resident.status === 'active'
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  <span
                    className={`h-2 w-2 rounded-full ${
                      resident.status === 'active' ? 'bg-emerald-500' : 'bg-red-500'
                    }`}
                  />
                  {resident.status === 'active' ? 'Active' : 'Inactive'}
                </span>
              </div>
              <p className="text-sm text-gray-500">
                Age {resident.age} &middot; {resident.home_id} &middot; ID:{' '}
                {resident.resident_id}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-8 space-y-8">
          {/* ── Risk + Privacy Row ── */}
          <div className="grid grid-cols-2 gap-6">
            <div className={`rounded-xl p-4 ${riskBgColor(risk)}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-gray-700">Risk Assessment</span>
                <span className={`text-2xl font-bold ${riskTextColor(risk)}`}>
                  {(risk * 100).toFixed(0)}%
                </span>
              </div>
              <div className="h-3 w-full overflow-hidden rounded-full bg-white/60">
                <div
                  className={`h-full rounded-full ${riskBarColor(risk)}`}
                  style={{ width: `${risk * 100}%` }}
                />
              </div>
              <p className={`mt-2 text-sm font-medium ${riskTextColor(risk)}`}>
                {riskLabel(risk)}
              </p>
            </div>

            <div className="rounded-xl bg-gray-50 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="h-4 w-4 text-gray-500" />
                <span className="text-sm font-semibold text-gray-700">Privacy Level</span>
              </div>
              <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${privacy.bg}`}>
                {privacy.text}
              </span>
              {resident.last_activity && (
                <p className="mt-2 text-xs text-gray-500">
                  Last seen {timeAgo(resident.last_activity)}
                </p>
              )}
            </div>
          </div>

          {/* ── Conditions ── */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
              <Heart className="inline h-4 w-4 mr-1.5 text-rose-400" />
              Medical Conditions
            </h3>
            <div className="flex flex-wrap gap-2">
              {resident.conditions.map((c) => (
                <span
                  key={c}
                  className="inline-flex items-center rounded-lg bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 ring-1 ring-inset ring-blue-200/60"
                >
                  {c}
                </span>
              ))}
            </div>
          </div>

          {/* ── Full Medication Schedule ── */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
              <Pill className="inline h-4 w-4 mr-1.5 text-aether-500" />
              Medication Schedule
            </h3>
            <div className="overflow-hidden rounded-xl border border-gray-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-xs uppercase tracking-wider text-gray-500">
                    <th className="px-4 py-3 font-semibold">Medication</th>
                    <th className="px-4 py-3 font-semibold">Dosage</th>
                    <th className="px-4 py-3 font-semibold">Schedule</th>
                    <th className="px-4 py-3 font-semibold">NFC Tag</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {resident.medications.map((med) => (
                    <tr key={med.name} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-4 py-3 font-medium text-gray-900">{med.name}</td>
                      <td className="px-4 py-3 text-gray-600">{med.dosage}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-1">
                          {med.schedule.map((s) => (
                            <span
                              key={s}
                              className="rounded bg-aether-50 px-2 py-0.5 text-xs font-medium text-aether-700"
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-400 font-mono">
                        {med.nfc_tag_id ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── All Emergency Contacts ── */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
              <Phone className="inline h-4 w-4 mr-1.5 text-emerald-500" />
              Emergency Contacts
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {resident.emergency_contacts.map((contact) => (
                <div
                  key={contact.phone}
                  className={`rounded-xl p-4 ${
                    contact.is_primary
                      ? 'bg-emerald-50 ring-1 ring-emerald-200'
                      : 'bg-gray-50 ring-1 ring-gray-200'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-900">{contact.name}</span>
                    {contact.is_primary && (
                      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700 uppercase">
                        Primary
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 mt-0.5">{contact.relationship}</p>
                  <p className="text-sm text-aether-600 font-medium mt-1">
                    <Phone className="inline h-3 w-3 mr-1" />
                    {contact.phone}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* ── Sleep & Respiratory Health ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Sleep */}
            <div>
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
                <Moon className="inline h-4 w-4 mr-1.5 text-indigo-400" />
                Sleep Health (Latest)
              </h3>
              {(() => {
                const sleepData = getSleepMetrics();
                const latest = sleepData[sleepData.length - 1];
                if (!latest) return <p className="text-sm text-gray-400">No data</p>;
                return (
                  <div className="rounded-xl bg-indigo-50 p-4 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Quality Score</span>
                      <span className={`text-lg font-bold ${latest.qualityScore >= 70 ? 'text-emerald-600' : latest.qualityScore >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                        {latest.qualityScore}/100
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-white/60 overflow-hidden">
                      <div className={`h-full rounded-full ${latest.qualityScore >= 70 ? 'bg-emerald-500' : latest.qualityScore >= 50 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${latest.qualityScore}%` }} />
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div><span className="text-gray-500">Efficiency:</span> <span className="font-semibold text-gray-800">{latest.sleepEfficiency}%</span></div>
                      <div><span className="text-gray-500">Bed Exits:</span> <span className="font-semibold text-gray-800">{latest.bedExits}</span></div>
                      <div><span className="text-gray-500">Apnea Events:</span> <span className="font-semibold text-gray-800">{latest.apneaEvents}</span></div>
                      <div><span className="text-gray-500">Fragmentation:</span> <span className="font-semibold text-gray-800">{latest.fragmentationIndex.toFixed(1)}</span></div>
                    </div>
                    <div className="flex gap-1 text-[10px]">
                      <span className="rounded bg-indigo-200/60 px-1.5 py-0.5 text-indigo-700">Deep {latest.deepSleepPct}%</span>
                      <span className="rounded bg-blue-200/60 px-1.5 py-0.5 text-blue-700">REM {latest.remSleepPct}%</span>
                      <span className="rounded bg-sky-200/60 px-1.5 py-0.5 text-sky-700">Light {latest.lightSleepPct}%</span>
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Respiratory */}
            <div>
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
                <Wind className="inline h-4 w-4 mr-1.5 text-teal-400" />
                Respiratory Health (Latest)
              </h3>
              {(() => {
                const respData = getRespiratoryMetrics();
                const latest = respData[respData.length - 1];
                if (!latest) return <p className="text-sm text-gray-400">No data</p>;
                return (
                  <div className="rounded-xl bg-teal-50 p-4 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-600">Respiratory Score</span>
                      <span className={`text-lg font-bold ${latest.respiratoryScore >= 70 ? 'text-emerald-600' : latest.respiratoryScore >= 50 ? 'text-amber-600' : 'text-red-600'}`}>
                        {latest.respiratoryScore}/100
                      </span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-white/60 overflow-hidden">
                      <div className={`h-full rounded-full ${latest.respiratoryScore >= 70 ? 'bg-emerald-500' : latest.respiratoryScore >= 50 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${latest.respiratoryScore}%` }} />
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div><span className="text-gray-500">Cough/hr:</span> <span className="font-semibold text-gray-800">{latest.coughPerHour.toFixed(1)}</span></div>
                      <div><span className="text-gray-500">Wheezing:</span> <span className="font-semibold text-gray-800">{latest.wheezingEpisodes} episodes</span></div>
                      <div><span className="text-gray-500">Breath Rate:</span> <span className="font-semibold text-gray-800">{latest.avgBreathingRate} bpm</span></div>
                      <div><span className="text-gray-500">SpO₂:</span> <span className="font-semibold text-gray-800">{latest.avgSpO2}%</span></div>
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>

          {/* ── Full Event History ── */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3">
              <Activity className="inline h-4 w-4 mr-1.5 text-aether-500" />
              Event History ({allEvents.length} events)
            </h3>
            <div className="max-h-72 overflow-y-auto rounded-xl border border-gray-200">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-gray-50">
                  <tr className="text-left text-xs uppercase tracking-wider text-gray-500">
                    <th className="px-4 py-2 font-semibold">Event</th>
                    <th className="px-4 py-2 font-semibold">Severity</th>
                    <th className="px-4 py-2 font-semibold">Confidence</th>
                    <th className="px-4 py-2 font-semibold">Sensors</th>
                    <th className="px-4 py-2 font-semibold">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {allEvents.map((ev) => (
                    <tr key={ev.event_id} className="hover:bg-gray-50/50 transition-colors">
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <EventIcon eventType={ev.event_type} size={14} />
                          <span className="text-gray-800">{formatEventType(ev.event_type)}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                            ev.severity === 'CRITICAL'
                              ? 'bg-red-100 text-red-800'
                              : ev.severity === 'HIGH'
                              ? 'bg-orange-100 text-orange-800'
                              : ev.severity === 'MEDIUM'
                              ? 'bg-yellow-100 text-yellow-800'
                              : ev.severity === 'LOW'
                              ? 'bg-green-100 text-green-800'
                              : 'bg-gray-100 text-gray-700'
                          }`}
                        >
                          {ev.severity}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-gray-600">
                        {(ev.confidence * 100).toFixed(1)}%
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex gap-1">
                          {ev.source_sensors.map((s) => (
                            <span
                              key={s}
                              className="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 uppercase"
                            >
                              {s}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-xs text-gray-400 whitespace-nowrap">
                        {timeAgo(ev.timestamp)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Page Component ───────────────────────────────────────────────────────────

export default function ResidentsPage() {
  const { residents: apiResidents, apiConnected } = useLiveData();
  const [search, setSearch] = useState('');
  const [selectedResident, setSelectedResident] = useState<Resident | null>(null);
  const [aiInsights, setAiInsights] = useState<Record<string, HealthInsightsResponse>>({});
  const [loadingInsightId, setLoadingInsightId] = useState<string | null>(null);

  // Merge API residents with mock data — API data enhances mock residents when API is connected
  const allResidents = useMemo(() => {
    if (!apiConnected || apiResidents.length === 0) return RESIDENTS;
    // Update mock residents with any API data (same resident IDs)
    return RESIDENTS.map((r) => {
      const apiR = apiResidents.find((ar) => ar.resident_id === r.resident_id);
      if (apiR) {
        return {
          ...r,
          name: apiR.name || r.name,
          age: apiR.age || r.age,
          status: (apiR.status as 'active' | 'inactive') ?? r.status,
        };
      }
      return r;
    });
  }, [apiConnected, apiResidents]);

  const filteredResidents = useMemo(() => {
    if (!search.trim()) return allResidents;
    const q = search.toLowerCase();
    return allResidents.filter(
      (r) =>
        r.name.toLowerCase().includes(q) ||
        r.home_id.toLowerCase().includes(q) ||
        r.conditions.some((c) => c.toLowerCase().includes(q)),
    );
  }, [search, allResidents]);

  const residentEvents = useMemo(() => {
    const map = new Map<string, AetherEvent[]>();
    allResidents.forEach((r) => {
      map.set(r.resident_id, getRecentEvents(r.home_id, 3));
    });
    return map;
  }, [allResidents]);

  const handleSelect = useCallback((r: Resident) => {
    setSelectedResident(r);
  }, []);

  const runHealthInsight = useCallback(async (residentId: string) => {
    if (aiInsights[residentId] || loadingInsightId) return;
    setLoadingInsightId(residentId);
    try {
      const result = await fetchHealthInsights({ resident_id: residentId });
      setAiInsights((prev) => ({ ...prev, [residentId]: result }));
    } catch {
      // silent
    } finally {
      setLoadingInsightId(null);
    }
  }, [aiInsights, loadingInsightId]);

  return (
    <div className="animate-fade-in space-y-6">
      {/* ── Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">Residents</h1>
          <span className="flex h-7 min-w-[28px] items-center justify-center rounded-full bg-aether-100 px-2.5 text-sm font-bold text-aether-700">
            {allResidents.length}
          </span>
          {apiConnected && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
              <Wifi size={10} /> AWS Live
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search residents, conditions…"
              className="input pl-9 w-64"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button className="btn-secondary opacity-60 cursor-not-allowed" disabled>
            <UserPlus className="mr-1.5 h-4 w-4" />
            Add Resident
          </button>
        </div>
      </div>

      {/* ── Summary Stats ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-aether-50 p-2">
              <Users className="h-4 w-4 text-aether-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{allResidents.length}</p>
              <p className="text-xs text-gray-500">Total Residents</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-emerald-50 p-2">
              <Activity className="h-4 w-4 text-emerald-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {allResidents.filter((r) => r.status === 'active').length}
              </p>
              <p className="text-xs text-gray-500">Active</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-amber-50 p-2">
              <AlertTriangle className="h-4 w-4 text-amber-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {allResidents.filter((r) => (r.risk_score ?? 0) > 0.6).length}
              </p>
              <p className="text-xs text-gray-500">High Risk</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-violet-50 p-2">
              <Shield className="h-4 w-4 text-violet-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {allResidents.filter((r) => r.privacy_level === 'elevated').length}
              </p>
              <p className="text-xs text-gray-500">Elevated Privacy</p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Residents Grid ── */}
      {filteredResidents.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl bg-white p-16 shadow-sm ring-1 ring-gray-200/60">
          <Users className="h-12 w-12 text-gray-300" />
          <p className="mt-3 text-lg font-medium text-gray-500">No residents found</p>
          <p className="text-sm text-gray-400">Try adjusting your search query</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {filteredResidents.map((resident) => (
            <ResidentCard
              key={resident.resident_id}
              resident={resident}
              recentEvents={residentEvents.get(resident.resident_id) ?? []}
              onSelect={handleSelect}
            />
          ))}
        </div>
      )}

      {/* ── Detail Modal ── */}
      {selectedResident && (
        <ResidentModal
          resident={selectedResident}
          onClose={() => setSelectedResident(null)}
        />
      )}
    </div>
  );
}
