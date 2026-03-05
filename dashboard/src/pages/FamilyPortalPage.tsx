import { useState, useMemo, useCallback } from 'react';
import {
  Pill,
  Stethoscope,
  Car,
  Users,
  Activity,
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Phone,
  PhoneCall,
  Download,
  FileText,
  CheckCircle2,
  Circle,
  Shield,
  Eye,
  EyeOff,
  Trash2,
  Plus,
  Clock,
  AlertTriangle,
  RefreshCcw,
  ChevronDown,
  ChevronUp,
  X,
  UserCheck,
  ArrowRight,
  Wifi,
} from 'lucide-react';
import {
  format,
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  addDays,
  addMonths,
  subMonths,
  isSameMonth,
  isSameDay,
  isToday,
} from 'date-fns';
import { formatDistanceToNow } from 'date-fns';

import {
  CALENDAR_EVENTS,
  CARE_HANDOFFS,
  CONSENT_SETTINGS,
  RESIDENTS,
} from '../data/mockData';
import { useAuth } from '../contexts/AuthContext';
import { useLiveData } from '../contexts/LiveDataContext';
import type {
  CalendarEvent,
  CareHandoff,
  ConsentSettings,
  Resident,
  HandoffItem,
} from '../types';

// ─── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(ts: number): string {
  return formatDistanceToNow(new Date(ts), { addSuffix: true });
}

const EVENT_TYPE_CONFIG: Record<
  CalendarEvent['type'],
  { icon: React.ElementType; bg: string; text: string; ring: string }
> = {
  medication: { icon: Pill, bg: 'bg-violet-50', text: 'text-violet-600', ring: 'ring-violet-200' },
  appointment: { icon: Stethoscope, bg: 'bg-blue-50', text: 'text-blue-600', ring: 'ring-blue-200' },
  transport: { icon: Car, bg: 'bg-amber-50', text: 'text-amber-600', ring: 'ring-amber-200' },
  visit: { icon: Users, bg: 'bg-emerald-50', text: 'text-emerald-600', ring: 'ring-emerald-200' },
  activity: { icon: Activity, bg: 'bg-sky-50', text: 'text-sky-600', ring: 'ring-sky-200' },
};

function priorityBadge(p: 'high' | 'medium' | 'low'): string {
  switch (p) {
    case 'high':
      return 'bg-red-50 text-red-700 ring-red-600/20';
    case 'medium':
      return 'bg-amber-50 text-amber-700 ring-amber-600/20';
    case 'low':
      return 'bg-gray-50 text-gray-600 ring-gray-500/20';
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// Calendar Section
// ═════════════════════════════════════════════════════════════════════════════

function SharedCalendar({ events }: { events: CalendarEvent[] }) {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(new Date());
  const [showAddForm, setShowAddForm] = useState(false);

  const monthStart = startOfMonth(currentMonth);
  const monthEnd = endOfMonth(monthStart);
  const calStart = startOfWeek(monthStart);
  const calEnd = endOfWeek(monthEnd);

  // Build weeks
  const weeks: Date[][] = [];
  let day = calStart;
  while (day <= calEnd) {
    const week: Date[] = [];
    for (let i = 0; i < 7; i++) {
      week.push(day);
      day = addDays(day, 1);
    }
    weeks.push(week);
  }

  function eventsForDay(d: Date): CalendarEvent[] {
    return events.filter((ev) => isSameDay(new Date(ev.datetime), d));
  }

  const selectedEvents = selectedDate ? eventsForDay(selectedDate) : [];

  return (
    <div className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Shared Calendar</h2>
          <p className="text-xs text-gray-400">Medications, appointments, visits & activities</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
          >
            <Plus size={14} />
            Add Event
          </button>
        </div>
      </div>

      {/* Add Event Form */}
      {showAddForm && (
        <div className="border-b border-gray-100 bg-gray-50/80 px-6 py-4">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-semibold text-gray-700">New Event</span>
            <button onClick={() => setShowAddForm(false)} className="text-gray-400 hover:text-gray-600">
              <X size={16} />
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <input
              type="text"
              placeholder="Event title"
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            />
            <select className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/40">
              <option value="medication">Medication</option>
              <option value="appointment">Appointment</option>
              <option value="transport">Transport</option>
              <option value="visit">Family Visit</option>
              <option value="activity">Activity</option>
            </select>
            <input
              type="datetime-local"
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            />
            <select className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/40">
              <option value="">Recurrence</option>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div className="mt-3 flex gap-2">
            <input
              type="text"
              placeholder="Participants (comma-separated)"
              className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            />
            <input
              type="text"
              placeholder="Notes"
              className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/40"
            />
          </div>
          <button className="mt-3 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700 transition-colors">
            Save Event (Demo)
          </button>
        </div>
      )}

      <div className="flex flex-col lg:flex-row">
        {/* Calendar Grid */}
        <div className="flex-1 p-4">
          {/* Month Navigation */}
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
              className="rounded-lg p-1.5 hover:bg-gray-100 transition-colors"
            >
              <ChevronLeft size={18} className="text-gray-500" />
            </button>
            <h3 className="text-sm font-semibold text-gray-800">
              {format(currentMonth, 'MMMM yyyy')}
            </h3>
            <button
              onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
              className="rounded-lg p-1.5 hover:bg-gray-100 transition-colors"
            >
              <ChevronRight size={18} className="text-gray-500" />
            </button>
          </div>

          {/* Day Headers */}
          <div className="grid grid-cols-7 gap-1 mb-1">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
              <div key={d} className="text-center text-[10px] font-semibold text-gray-400 uppercase py-1">
                {d}
              </div>
            ))}
          </div>

          {/* Calendar Days */}
          {weeks.map((week, wi) => (
            <div key={wi} className="grid grid-cols-7 gap-1">
              {week.map((d) => {
                const dayEvents = eventsForDay(d);
                const inMonth = isSameMonth(d, currentMonth);
                const selected = selectedDate && isSameDay(d, selectedDate);
                const today = isToday(d);
                return (
                  <button
                    key={d.toISOString()}
                    onClick={() => setSelectedDate(d)}
                    className={`relative flex flex-col items-center rounded-lg py-1.5 px-1 min-h-[52px] transition-all text-xs ${
                      selected
                        ? 'bg-blue-600 text-white shadow-sm'
                        : today
                          ? 'bg-blue-50 text-blue-700 ring-1 ring-blue-200'
                          : inMonth
                            ? 'hover:bg-gray-50 text-gray-700'
                            : 'text-gray-300'
                    }`}
                  >
                    <span className={`font-medium ${selected ? 'text-white' : ''}`}>
                      {format(d, 'd')}
                    </span>
                    {/* Event dots */}
                    {dayEvents.length > 0 && (
                      <div className="flex gap-0.5 mt-0.5 flex-wrap justify-center">
                        {dayEvents.slice(0, 3).map((ev, i) => {
                          const cfg = EVENT_TYPE_CONFIG[ev.type];
                          return (
                            <span
                              key={i}
                              className={`h-1.5 w-1.5 rounded-full ${selected ? 'bg-white/70' : cfg.text.replace('text-', 'bg-')}`}
                            />
                          );
                        })}
                        {dayEvents.length > 3 && (
                          <span className={`text-[8px] font-bold ${selected ? 'text-white/70' : 'text-gray-400'}`}>
                            +{dayEvents.length - 3}
                          </span>
                        )}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {/* Day Detail Sidebar */}
        <div className="lg:w-72 border-t lg:border-t-0 lg:border-l border-gray-100 p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">
            {selectedDate ? format(selectedDate, 'EEE, MMM d') : 'Select a day'}
          </h3>
          {selectedEvents.length === 0 ? (
            <p className="text-xs text-gray-400 py-4 text-center">No events this day</p>
          ) : (
            <div className="space-y-2">
              {selectedEvents
                .sort((a, b) => a.datetime - b.datetime)
                .map((ev) => {
                  const cfg = EVENT_TYPE_CONFIG[ev.type];
                  const Icon = cfg.icon;
                  return (
                    <div
                      key={ev.id}
                      className={`rounded-lg ${cfg.bg} p-3 ring-1 ring-inset ${cfg.ring}`}
                    >
                      <div className="flex items-start gap-2">
                        <Icon size={14} className={`${cfg.text} mt-0.5 shrink-0`} />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-semibold text-gray-800 truncate">{ev.title}</p>
                          <p className="text-[10px] text-gray-500 mt-0.5">
                            {format(new Date(ev.datetime), 'h:mm a')}
                            {ev.duration && ` · ${ev.duration} min`}
                          </p>
                          {ev.recurrence && (
                            <span className="inline-flex items-center gap-0.5 mt-1 text-[9px] font-medium text-gray-400">
                              <RefreshCcw size={8} />
                              {ev.recurrence}
                            </span>
                          )}
                          {ev.notes && (
                            <p className="text-[10px] text-gray-400 mt-1">{ev.notes}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// Emergency Card
// ═════════════════════════════════════════════════════════════════════════════

function EmergencyCard({ residents }: { residents: Resident[] }) {
  const [expandedResident, setExpandedResident] = useState<string | null>(
    residents[0]?.resident_id ?? null,
  );

  return (
    <div className="rounded-2xl bg-gradient-to-br from-red-50 to-white shadow-sm ring-1 ring-red-200/60 overflow-hidden">
      <div className="flex items-center justify-between border-b border-red-100 px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-100">
            <PhoneCall size={16} className="text-red-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Emergency Contacts</h2>
            <p className="text-xs text-gray-400">One-tap contact tree per resident</p>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-3">
        {residents.map((r) => {
          const isExpanded = expandedResident === r.resident_id;
          const contacts = r.emergency_contacts;
          return (
            <div key={r.resident_id} className="rounded-xl bg-white ring-1 ring-gray-200/60 overflow-hidden">
              <button
                onClick={() => setExpandedResident(isExpanded ? null : r.resident_id)}
                className="flex w-full items-center justify-between px-4 py-3 hover:bg-gray-50/60 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-[10px] font-bold text-white">
                    {r.name.charAt(0)}
                  </div>
                  <span className="text-sm font-semibold text-gray-800">{r.name}</span>
                </div>
                {isExpanded ? (
                  <ChevronUp size={16} className="text-gray-400" />
                ) : (
                  <ChevronDown size={16} className="text-gray-400" />
                )}
              </button>

              {isExpanded && (
                <div className="px-4 pb-4">
                  {/* Contact Tree */}
                  <div className="space-y-1">
                    {contacts.map((c, idx) => (
                      <div key={idx} className="flex items-center gap-3">
                        {/* Tree connector */}
                        <div className="flex flex-col items-center w-6">
                          {idx > 0 && <div className="w-px h-3 bg-gray-200" />}
                          <div
                            className={`flex h-5 w-5 items-center justify-center rounded-full text-[9px] font-bold ${
                              c.is_primary
                                ? 'bg-red-100 text-red-600'
                                : 'bg-gray-100 text-gray-500'
                            }`}
                          >
                            {idx + 1}
                          </div>
                          {idx < contacts.length - 1 && <div className="w-px h-3 bg-gray-200" />}
                        </div>
                        {/* Contact Info */}
                        <div className="flex-1 flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2">
                          <div>
                            <p className="text-xs font-semibold text-gray-700">{c.name}</p>
                            <p className="text-[10px] text-gray-400">{c.relationship}</p>
                          </div>
                          <a
                            href={`tel:${c.phone}`}
                            className="flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-1 text-[10px] font-semibold text-emerald-700 hover:bg-emerald-200 transition-colors"
                          >
                            <Phone size={10} />
                            {c.phone}
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Fallback numbers */}
                  <div className="mt-3 rounded-lg bg-red-50 px-3 py-2">
                    <p className="text-[10px] font-semibold text-red-600 uppercase mb-1">Emergency Fallback</p>
                    <div className="flex gap-3">
                      <a href="tel:112" className="flex items-center gap-1 text-xs font-medium text-red-700 hover:underline">
                        <PhoneCall size={11} /> 112 (Emergency)
                      </a>
                      <a href="tel:108" className="flex items-center gap-1 text-xs font-medium text-red-700 hover:underline">
                        <PhoneCall size={11} /> 108 (Ambulance)
                      </a>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// Offline Care Binder
// ═════════════════════════════════════════════════════════════════════════════

function OfflineCareBinder({ residents }: { residents: Resident[] }) {
  const [activeTab, setActiveTab] = useState<'medications' | 'allergies' | 'doctors' | 'incidents'>('medications');
  const lastSynced = useMemo(() => Date.now() - 3 * 60 * 1000, []);

  const tabs = [
    { key: 'medications' as const, label: 'Medications' },
    { key: 'allergies' as const, label: 'Allergies' },
    { key: 'doctors' as const, label: 'Doctors' },
    { key: 'incidents' as const, label: 'Recent Incidents' },
  ];

  // Mock allergies
  const allergies: Record<string, string[]> = {
    'res-a1b2c3d4': ['Sulfa drugs', 'Iodine contrast'],
    'res-e5f6g7h8': ['Penicillin', 'Shellfish'],
    'res-i9j0k1l2': ['Aspirin sensitivity (cross-reaction with Warfarin protocol)'],
    'res-m3n4o5p6': ['No known drug allergies'],
  };

  // Mock doctors
  const doctors = [
    { name: 'Dr. Rajesh Menon', specialty: 'Geriatric Medicine', phone: '+91-99000-22222', clinic: 'AETHER Clinic Mumbai' },
    { name: 'Dr. Anita Desai', specialty: 'Neurology', phone: '+91-98000-44444', clinic: 'Manipal Hospital, Bangalore' },
    { name: 'Dr. Suresh Nair', specialty: 'Pulmonology', phone: '+91-99100-55555', clinic: 'Apollo Chennai' },
    { name: 'Dr. Kavitha Rao', specialty: 'Cardiology', phone: '+91-98300-66666', clinic: 'Fortis Delhi' },
  ];

  // Mock recent incidents
  const incidents = [
    { date: 'Mar 3, 2026', resident: 'Suresh Kumar', type: 'Fall — Bathroom', severity: 'HIGH' },
    { date: 'Mar 2, 2026', resident: 'Rajesh Patel', type: 'SpO2 Drop — 89%', severity: 'CRITICAL' },
    { date: 'Mar 1, 2026', resident: 'Margaret Sharma', type: 'Medication Missed — Evening', severity: 'MEDIUM' },
    { date: 'Feb 28, 2026', resident: 'Suresh Kumar', type: 'Gait Degradation', severity: 'MEDIUM' },
    { date: 'Feb 27, 2026', resident: 'Lakshmi Iyer', type: 'Irregular Heartbeat', severity: 'HIGH' },
  ];

  return (
    <div className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 overflow-hidden">
      <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Offline Care Binder</h2>
          <div className="flex items-center gap-1.5 mt-0.5">
            <RefreshCcw size={10} className="text-gray-400" />
            <p className="text-[11px] text-gray-400">Last synced: {timeAgo(lastSynced)}</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-100 px-4 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="p-4">
        {/* Medications Tab */}
        {activeTab === 'medications' && (
          <div className="space-y-3">
            {residents.map((r) => (
              <div key={r.resident_id} className="rounded-lg bg-gray-50 p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-gray-700">{r.name}</span>
                  <button className="flex items-center gap-1 text-[10px] font-medium text-blue-600 hover:text-blue-700">
                    <Download size={10} /> PDF
                  </button>
                </div>
                <div className="space-y-1">
                  {r.medications.map((med, i) => (
                    <div key={i} className="flex items-center justify-between bg-white rounded-md px-3 py-1.5 text-xs">
                      <div>
                        <span className="font-medium text-gray-700">{med.name}</span>
                        <span className="text-gray-400 ml-1.5">{med.dosage}</span>
                      </div>
                      <span className="text-gray-400">{med.schedule.join(', ')}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Allergies Tab */}
        {activeTab === 'allergies' && (
          <div className="space-y-3">
            {residents.map((r) => (
              <div key={r.resident_id} className="rounded-lg bg-gray-50 p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-gray-700">{r.name}</span>
                  <button className="flex items-center gap-1 text-[10px] font-medium text-blue-600 hover:text-blue-700">
                    <Download size={10} /> PDF
                  </button>
                </div>
                <div className="space-y-1">
                  {(allergies[r.resident_id] ?? ['No known allergies']).map((a, i) => (
                    <div key={i} className="flex items-center gap-2 bg-white rounded-md px-3 py-1.5 text-xs">
                      <AlertTriangle size={11} className="text-amber-500 shrink-0" />
                      <span className="text-gray-700">{a}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Doctors Tab */}
        {activeTab === 'doctors' && (
          <div className="space-y-2">
            {doctors.map((doc, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3">
                <div>
                  <p className="text-xs font-semibold text-gray-700">{doc.name}</p>
                  <p className="text-[10px] text-gray-400">{doc.specialty} · {doc.clinic}</p>
                </div>
                <a
                  href={`tel:${doc.phone}`}
                  className="flex items-center gap-1 rounded-full bg-blue-50 px-2 py-1 text-[10px] font-medium text-blue-600 hover:bg-blue-100 transition-colors"
                >
                  <Phone size={10} />
                  {doc.phone}
                </a>
              </div>
            ))}
            <button className="w-full flex items-center justify-center gap-1 text-[10px] font-medium text-blue-600 hover:text-blue-700 py-2">
              <Download size={10} /> Download as PDF
            </button>
          </div>
        )}

        {/* Incidents Tab */}
        {activeTab === 'incidents' && (
          <div className="space-y-1.5">
            {incidents.map((inc, i) => {
              const sevColor =
                inc.severity === 'CRITICAL'
                  ? 'bg-red-50 text-red-700 ring-red-600/20'
                  : inc.severity === 'HIGH'
                    ? 'bg-orange-50 text-orange-700 ring-orange-600/20'
                    : 'bg-amber-50 text-amber-700 ring-amber-600/20';
              return (
                <div key={i} className="flex items-center justify-between bg-gray-50 rounded-lg px-4 py-2.5">
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] text-gray-400 w-20 shrink-0">{inc.date}</span>
                    <div>
                      <p className="text-xs font-medium text-gray-700">{inc.type}</p>
                      <p className="text-[10px] text-gray-400">{inc.resident}</p>
                    </div>
                  </div>
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[9px] font-bold ring-1 ring-inset ${sevColor}`}>
                    {inc.severity}
                  </span>
                </div>
              );
            })}
            <button className="w-full flex items-center justify-center gap-1 text-[10px] font-medium text-blue-600 hover:text-blue-700 py-2">
              <Download size={10} /> Download as PDF
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// Caregiver Handoff Checklist
// ═════════════════════════════════════════════════════════════════════════════

function HandoffChecklist({ handoffs }: { handoffs: CareHandoff[] }) {
  const [activeHandoff, setActiveHandoff] = useState(0);
  const [checklist, setChecklist] = useState<HandoffItem[][]>(() =>
    handoffs.map((h) => [...h.checklist]),
  );

  const current = handoffs[activeHandoff];
  const currentChecklist = checklist[activeHandoff] ?? [];

  const toggleItem = useCallback(
    (idx: number) => {
      setChecklist((prev) => {
        const next = [...prev];
        next[activeHandoff] = next[activeHandoff].map((item, i) =>
          i === idx ? { ...item, completed: !item.completed } : item,
        );
        return next;
      });
    },
    [activeHandoff],
  );

  if (!current) return null;

  const completedCount = currentChecklist.filter((i) => i.completed).length;
  const totalCount = currentChecklist.length;

  return (
    <div className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 overflow-hidden">
      <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Caregiver Handoff</h2>
          <p className="text-xs text-gray-400">
            {completedCount}/{totalCount} items completed
          </p>
        </div>
        <button className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-violet-700 transition-colors">
          <UserCheck size={14} />
          Start New Handoff
        </button>
      </div>

      {/* Handoff selector */}
      {handoffs.length > 1 && (
        <div className="flex gap-2 px-6 py-3 border-b border-gray-100 overflow-x-auto">
          {handoffs.map((h, i) => (
            <button
              key={h.id}
              onClick={() => setActiveHandoff(i)}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium whitespace-nowrap transition-colors ${
                i === activeHandoff
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {h.fromCaregiver} → {h.toCaregiver}
            </button>
          ))}
        </div>
      )}

      <div className="p-4">
        {/* Handoff info */}
        <div className="flex items-center gap-3 mb-4 rounded-lg bg-gray-50 px-4 py-3">
          <div className="flex items-center gap-1.5 text-xs font-medium text-gray-600">
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 text-[10px] font-bold text-blue-600">
              {current.fromCaregiver.charAt(0)}
            </span>
            {current.fromCaregiver}
          </div>
          <ArrowRight size={14} className="text-gray-400" />
          <div className="flex items-center gap-1.5 text-xs font-medium text-gray-600">
            <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-[10px] font-bold text-emerald-600">
              {current.toCaregiver.charAt(0)}
            </span>
            {current.toCaregiver}
          </div>
          <span className="ml-auto text-[10px] text-gray-400 flex items-center gap-1">
            <Clock size={10} />
            {timeAgo(current.timestamp)}
          </span>
        </div>

        {/* Progress bar */}
        <div className="mb-4">
          <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
            <div
              className="h-full rounded-full bg-blue-500 transition-all duration-500"
              style={{ width: `${(completedCount / totalCount) * 100}%` }}
            />
          </div>
        </div>

        {/* Checklist */}
        <div className="space-y-1.5">
          {currentChecklist.map((item, idx) => (
            <button
              key={idx}
              onClick={() => toggleItem(idx)}
              className={`w-full flex items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${
                item.completed ? 'bg-emerald-50/60' : 'bg-gray-50 hover:bg-gray-100/80'
              }`}
            >
              {item.completed ? (
                <CheckCircle2 size={16} className="text-emerald-500 mt-0.5 shrink-0" />
              ) : (
                <Circle size={16} className="text-gray-300 mt-0.5 shrink-0" />
              )}
              <span
                className={`text-xs flex-1 ${
                  item.completed ? 'text-gray-400 line-through' : 'text-gray-700'
                }`}
              >
                {item.task}
              </span>
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-[9px] font-bold ring-1 ring-inset shrink-0 ${priorityBadge(item.priority)}`}
              >
                {item.priority.toUpperCase()}
              </span>
            </button>
          ))}
        </div>

        {/* Notes */}
        <div className="mt-4 rounded-lg bg-amber-50 px-4 py-3">
          <p className="text-[10px] font-semibold text-amber-700 uppercase mb-1">Shift Notes</p>
          <p className="text-xs text-amber-800 leading-relaxed">{current.notes}</p>
        </div>

        {/* Pending Tasks */}
        {current.pendingTasks.length > 0 && (
          <div className="mt-3 rounded-lg bg-red-50 px-4 py-3">
            <p className="text-[10px] font-semibold text-red-700 uppercase mb-1">
              Pending Tasks ({current.pendingTasks.length})
            </p>
            <ul className="space-y-1">
              {current.pendingTasks.map((t, i) => (
                <li key={i} className="flex items-center gap-1.5 text-xs text-red-700">
                  <span className="h-1 w-1 rounded-full bg-red-400 shrink-0" />
                  {t}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// Consent / Privacy Center
// ═════════════════════════════════════════════════════════════════════════════

function ConsentCenter({
  settings,
  residents,
}: {
  settings: ConsentSettings[];
  residents: Resident[];
}) {
  const [activeResident, setActiveResident] = useState(0);
  const [localSettings, setLocalSettings] = useState<ConsentSettings[]>(() =>
    settings.map((s) => ({ ...s, dataTypes: s.dataTypes.map((d) => ({ ...d })) })),
  );
  const [retentionDays, setRetentionDays] = useState<number[]>(() =>
    settings.map((s) => s.retentionDays),
  );

  const current = localSettings[activeResident];
  const currentResident = residents.find((r) => r.resident_id === current?.residentId);

  const toggleDataType = useCallback(
    (idx: number) => {
      setLocalSettings((prev) => {
        const next = [...prev];
        const dt = { ...next[activeResident] };
        dt.dataTypes = dt.dataTypes.map((d, i) =>
          i === idx ? { ...d, enabled: !d.enabled } : d,
        );
        next[activeResident] = dt;
        return next;
      });
    },
    [activeResident],
  );

  if (!current) return null;

  return (
    <div className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 overflow-hidden">
      <div className="flex items-center justify-between border-b border-gray-100 px-6 py-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50">
            <Shield size={16} className="text-blue-600" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Consent & Privacy</h2>
            <p className="text-xs text-gray-400">Data sharing preferences by resident</p>
          </div>
        </div>
      </div>

      {/* Resident Tabs */}
      <div className="flex gap-2 px-6 py-3 border-b border-gray-100 overflow-x-auto">
        {localSettings.map((s, i) => {
          const r = residents.find((res) => res.resident_id === s.residentId);
          return (
            <button
              key={s.residentId}
              onClick={() => setActiveResident(i)}
              className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium whitespace-nowrap transition-colors ${
                i === activeResident
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {r?.name ?? s.residentId}
            </button>
          );
        })}
      </div>

      <div className="p-4 space-y-4">
        {/* Data Type Toggles */}
        <div>
          <p className="text-xs font-semibold text-gray-600 mb-2">Data Sharing Settings</p>
          <div className="space-y-1.5">
            {current.dataTypes.map((dt, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-2.5"
              >
                <div className="flex items-center gap-2">
                  {dt.enabled ? (
                    <Eye size={14} className="text-emerald-500" />
                  ) : (
                    <EyeOff size={14} className="text-gray-300" />
                  )}
                  <div>
                    <p className="text-xs font-medium text-gray-700">{dt.type}</p>
                    <p className="text-[10px] text-gray-400">
                      Viewers: {dt.allowedViewers.join(', ')}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => toggleDataType(idx)}
                  className={`relative inline-flex h-[22px] w-[40px] items-center rounded-full transition-colors ${
                    dt.enabled ? 'bg-emerald-500' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`inline-block h-[18px] w-[18px] rounded-full bg-white shadow-sm transition-transform ${
                      dt.enabled ? 'translate-x-[20px]' : 'translate-x-[2px]'
                    }`}
                  />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Data Retention Slider */}
        <div className="rounded-lg bg-gray-50 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-600">Data Retention Period</span>
            <span className="text-xs font-bold text-blue-600">
              {retentionDays[activeResident]} days
            </span>
          </div>
          <input
            type="range"
            min={30}
            max={365}
            step={30}
            value={retentionDays[activeResident]}
            onChange={(e) => {
              const val = parseInt(e.target.value);
              setRetentionDays((prev) => {
                const next = [...prev];
                next[activeResident] = val;
                return next;
              });
            }}
            className="w-full accent-blue-600 h-1.5"
          />
          <div className="flex justify-between text-[10px] text-gray-400 mt-1">
            <span>30 days</span>
            <span>365 days</span>
          </div>
        </div>

        {/* Export/Delete Requests */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-gray-600">Export / Delete Requests</span>
            <button className="flex items-center gap-1 rounded-lg bg-gray-100 px-2 py-1 text-[10px] font-medium text-gray-600 hover:bg-gray-200 transition-colors">
              <Plus size={10} />
              New Request
            </button>
          </div>
          {current.exportRequests.length === 0 ? (
            <p className="text-xs text-gray-400 py-3 text-center bg-gray-50 rounded-lg">
              No export requests
            </p>
          ) : (
            <div className="space-y-1.5">
              {current.exportRequests.map((req) => {
                const statusColor =
                  req.status === 'completed'
                    ? 'bg-emerald-50 text-emerald-700 ring-emerald-600/20'
                    : req.status === 'processing'
                      ? 'bg-blue-50 text-blue-700 ring-blue-600/20'
                      : 'bg-amber-50 text-amber-700 ring-amber-600/20';
                return (
                  <div key={req.id} className="flex items-center justify-between bg-gray-50 rounded-lg px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <FileText size={13} className="text-gray-400" />
                      <div>
                        <p className="text-xs font-medium text-gray-700">
                          Export as {req.format.toUpperCase()}
                        </p>
                        <p className="text-[10px] text-gray-400">
                          Requested {timeAgo(req.requestedAt)}
                        </p>
                      </div>
                    </div>
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[9px] font-bold ring-1 ring-inset ${statusColor}`}>
                      {req.status.toUpperCase()}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// Family Portal Page
// ═════════════════════════════════════════════════════════════════════════════

export default function FamilyPortalPage() {
  const { role } = useAuth();
  const { apiConnected } = useLiveData();
  const isElder = role === 'elder';

  return (
    <div className="min-h-screen bg-gray-50/60">
      <div className="mx-auto max-w-[1440px] px-6 py-8 lg:px-10">
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="mb-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-sm">
              <Users className="text-white" size={20} />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">
                {isElder ? 'My Family Portal' : 'Family Portal'}
              </h1>
              <p className="text-sm text-gray-500 flex items-center gap-2">
                {isElder
                  ? 'Your schedule, contacts & care information'
                  : 'Shared calendar, handoffs & privacy management'}
                {apiConnected && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                    <Wifi size={10} /> AWS Live
                  </span>
                )}
              </p>
            </div>
          </div>
        </div>

        {/* ── Shared Calendar ─────────────────────────────────────── */}
        <SharedCalendar events={CALENDAR_EVENTS} />

        {/* ── Row: Emergency Card + Offline Binder ────────────────── */}
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <EmergencyCard residents={RESIDENTS} />
          <OfflineCareBinder residents={RESIDENTS} />
        </div>

        {/* ── Caregiver Handoff (hidden for elder) ─────────────────── */}
        {!isElder && (
          <div className="mt-8">
            <HandoffChecklist handoffs={CARE_HANDOFFS} />
          </div>
        )}

        {/* ── Consent Center (hidden for elder simplified view) ──── */}
        {!isElder && (
          <div className="mt-8">
            <ConsentCenter settings={CONSENT_SETTINGS} residents={RESIDENTS} />
          </div>
        )}

        {/* ── Elder Simplified Consent View ────────────────────────── */}
        {isElder && (
          <div className="mt-8 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
            <div className="flex items-center gap-2 mb-4">
              <Shield size={18} className="text-blue-600" />
              <h2 className="text-lg font-semibold text-gray-900">Your Privacy</h2>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              Your data is protected by AETHER's privacy-first architecture. Only authorized caregivers and doctors
              can access your health information.
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-lg bg-emerald-50 px-4 py-3">
                <p className="text-xs font-semibold text-emerald-700">Data Encrypted</p>
                <p className="text-[10px] text-emerald-600 mt-0.5">All data encrypted at rest and in transit</p>
              </div>
              <div className="rounded-lg bg-blue-50 px-4 py-3">
                <p className="text-xs font-semibold text-blue-700">Edge Processing</p>
                <p className="text-[10px] text-blue-600 mt-0.5">Sensor data processed locally on-device</p>
              </div>
              <div className="rounded-lg bg-violet-50 px-4 py-3">
                <p className="text-xs font-semibold text-violet-700">Access Controlled</p>
                <p className="text-[10px] text-violet-600 mt-0.5">Role-based access to your information</p>
              </div>
              <div className="rounded-lg bg-amber-50 px-4 py-3">
                <p className="text-xs font-semibold text-amber-700">Your Rights</p>
                <p className="text-[10px] text-amber-600 mt-0.5">Request export or deletion anytime</p>
              </div>
            </div>
          </div>
        )}

        {/* ── Footer ─────────────────────────────────────────────── */}
        <div className="mt-12 border-t border-gray-200/60 pt-6 pb-8 text-center">
          <p className="text-xs text-gray-300">
            AETHER · Adaptive Elderly Tracking & Home Emergency Response ·
            Family Portal
          </p>
        </div>
      </div>
    </div>
  );
}
