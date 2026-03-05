import { useMemo, useState } from 'react';
import {
  BookOpen,
  CheckCircle,
  Clock,
  Award,
  BarChart3,
  ChevronRight,
  X,
  Shield,
  Stethoscope,
  Brain,
  Heart,
  Flame,
  Smartphone,
  AlertTriangle,
} from 'lucide-react';
import { format } from 'date-fns';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
} from 'recharts';

import { MICRO_LESSONS, RESIDENTS } from '../data/mockData';
import { useAuth } from '../contexts/AuthContext';
import type { MicroLesson } from '../types';

// ─── Constants ────────────────────────────────────────────────────────────────

const CATEGORY_CONFIG: Record<string, { icon: React.ElementType; bg: string; text: string; color: string }> = {
  'Medication Safety':   { icon: Shield,        bg: 'bg-blue-100',    text: 'text-blue-700',    color: '#3b82f6' },
  'Diabetes Management': { icon: Stethoscope,   bg: 'bg-violet-100',  text: 'text-violet-700',  color: '#8b5cf6' },
  'Respiratory Care':    { icon: Heart,          bg: 'bg-red-100',     text: 'text-red-700',     color: '#ef4444' },
  'Physical Safety':     { icon: AlertTriangle,  bg: 'bg-amber-100',   text: 'text-amber-700',   color: '#f59e0b' },
  'Safety & Security':   { icon: Shield,         bg: 'bg-emerald-100', text: 'text-emerald-700', color: '#10b981' },
  'Emergency Response':  { icon: Flame,          bg: 'bg-orange-100',  text: 'text-orange-700',  color: '#f97316' },
  'Mental Health':       { icon: Brain,          bg: 'bg-pink-100',    text: 'text-pink-700',    color: '#ec4899' },
  'Technology Usage':    { icon: Smartphone,     bg: 'bg-cyan-100',    text: 'text-cyan-700',    color: '#06b6d4' },
  'Fall Prevention':     { icon: AlertTriangle,  bg: 'bg-yellow-100',  text: 'text-yellow-700',  color: '#eab308' },
  'Nutrition':           { icon: Heart,          bg: 'bg-green-100',   text: 'text-green-700',   color: '#22c55e' },
};

function getCategoryConfig(cat: string) {
  return CATEGORY_CONFIG[cat] ?? { icon: BookOpen, bg: 'bg-gray-100', text: 'text-gray-700', color: '#6b7280' };
}

const CAREGIVER_TRAINING = [
  {
    id: 'ct-1',
    title: 'Shift Handoff Best Practices',
    category: 'Shift Management',
    description: 'Structured handoff protocol to ensure no critical information is missed between shift changes.',
    duration: 15,
    completed: true,
  },
  {
    id: 'ct-2',
    title: 'Emergency Response Drill Walkthrough',
    category: 'Emergency Response',
    description: 'Step-by-step guide for choking, fall, and cardiac emergency scenarios with AETHER integration.',
    duration: 20,
    completed: false,
  },
  {
    id: 'ct-3',
    title: 'Documentation Standards for AETHER',
    category: 'Documentation',
    description: 'How to document incidents, observations, and medication administrations in the AETHER system accurately.',
    duration: 10,
    completed: false,
  },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

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
    <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200/60 transition-all hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-500 truncate">{label}</p>
          <p className="mt-1.5 text-2xl font-bold tracking-tight text-gray-900">{value}</p>
          {subtitle && <p className="mt-0.5 text-xs text-gray-400">{subtitle}</p>}
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconBg}`}>
          <Icon className={iconColor} size={20} strokeWidth={2} />
        </div>
      </div>
    </div>
  );
}

function CategoryBadge({ category }: { category: string }) {
  const cfg = getCategoryConfig(category);
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold ${cfg.bg} ${cfg.text}`}>
      <cfg.icon size={11} />
      {category}
    </span>
  );
}

// ─── Lesson Detail Panel ──────────────────────────────────────────────────────

function LessonPanel({
  lesson,
  onClose,
  onMarkRead,
}: {
  lesson: MicroLesson;
  onClose: () => void;
  onMarkRead: (id: string) => void;
}) {
  const isCompleted = lesson.completedBy.length > 0;
  const cfg = getCategoryConfig(lesson.category);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-xl bg-white shadow-2xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${cfg.bg}`}>
                <cfg.icon size={18} className={cfg.text} />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-gray-900 truncate">{lesson.title}</h3>
                <p className="text-xs text-gray-400">{lesson.duration} min read</p>
              </div>
            </div>
            <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors">
              <X size={20} />
            </button>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <CategoryBadge category={lesson.category} />
            {isCompleted && (
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600">
                <CheckCircle size={12} /> Completed
              </span>
            )}
            {lesson.teachBackRequired && (
              <span className={`inline-flex items-center gap-1 text-xs font-semibold ${lesson.teachBackCompleted ? 'text-emerald-600' : 'text-amber-600'}`}>
                <Award size={12} /> Teach-back {lesson.teachBackCompleted ? 'passed' : 'required'}
              </span>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-6">
          <div className="rounded-xl bg-gray-50 p-5 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
            {lesson.content}
          </div>

          {lesson.teachBackRequired && !lesson.teachBackCompleted && (
            <div className="mt-4 rounded-xl bg-amber-50 p-4 ring-1 ring-amber-200">
              <p className="text-sm font-semibold text-amber-700 flex items-center gap-2">
                <Award size={14} /> Teach-Back Required
              </p>
              <p className="text-xs text-amber-600 mt-1">
                After reading, demonstrate understanding to a supervisor. This lesson requires verbal confirmation.
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4">
          <div className="flex gap-3">
            {!isCompleted && (
              <button
                onClick={() => onMarkRead(lesson.id)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-700"
              >
                <CheckCircle size={14} /> Mark as Read
              </button>
            )}
            <button
              onClick={onClose}
              className="inline-flex items-center gap-1.5 rounded-xl bg-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-700 transition-all hover:bg-gray-200"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Education Page
// ═══════════════════════════════════════════════════════════════════════════════

export default function EducationPage() {
  const { role } = useAuth();

  const [lessons, setLessons] = useState<MicroLesson[]>(() => MICRO_LESSONS);
  const [selectedLesson, setSelectedLesson] = useState<MicroLesson | null>(null);
  const [filterCategory, setFilterCategory] = useState<string>('all');

  // Computed
  const categories = useMemo(() => {
    const cats = new Set(lessons.map((l) => l.category));
    return ['all', ...Array.from(cats).sort()];
  }, [lessons]);

  const filtered = useMemo(() => {
    if (filterCategory === 'all') return lessons;
    return lessons.filter((l) => l.category === filterCategory);
  }, [lessons, filterCategory]);

  // KPIs
  const kpis = useMemo(() => {
    const total = lessons.length;
    const completed = lessons.filter((l) => l.completedBy.length > 0).length;
    const completionPct = total > 0 ? Math.round((completed / total) * 100) : 0;
    const teachBackRequired = lessons.filter((l) => l.teachBackRequired).length;
    const teachBackDone = lessons.filter((l) => l.teachBackRequired && l.teachBackCompleted).length;
    const avgDuration = total > 0 ? Math.round(lessons.reduce((s, l) => s + l.duration, 0) / total) : 0;
    return { total, completed, completionPct, teachBackRequired, teachBackDone, avgDuration };
  }, [lessons]);

  // Chart data: lessons by category (donut)
  const categoryChartData = useMemo(() => {
    const counts: Record<string, number> = {};
    lessons.forEach((l) => {
      counts[l.category] = (counts[l.category] || 0) + 1;
    });
    return Object.entries(counts).map(([name, value]) => ({
      name,
      value,
      color: getCategoryConfig(name).color,
    }));
  }, [lessons]);

  // Chart data: completion per module
  const moduleCompletionData = useMemo(() => {
    const catMap: Record<string, { total: number; done: number }> = {};
    lessons.forEach((l) => {
      if (!catMap[l.category]) catMap[l.category] = { total: 0, done: 0 };
      catMap[l.category].total++;
      if (l.completedBy.length > 0) catMap[l.category].done++;
    });
    return Object.entries(catMap).map(([cat, v]) => ({
      category: cat.length > 15 ? cat.slice(0, 14) + '…' : cat,
      completion: v.total > 0 ? Math.round((v.done / v.total) * 100) : 0,
    }));
  }, [lessons]);

  // Recent completions
  const recentCompletions = useMemo(() => {
    return lessons
      .filter((l) => l.completedBy.length > 0)
      .slice(0, 5);
  }, [lessons]);

  // Per-resident completion
  const residentCompletion = useMemo(() => {
    return RESIDENTS.slice(0, 4).map((r) => ({
      name: r.name,
      total: lessons.length,
      read: Math.floor(lessons.length * (0.3 + Math.random() * 0.5)),
    }));
  }, [lessons]);

  // Mark read handler
  const handleMarkRead = (id: string) => {
    setLessons((prev) =>
      prev.map((l) =>
        l.id === id ? { ...l, completedBy: [...l.completedBy, 'current-user'] } : l,
      ),
    );
    setSelectedLesson((prev) =>
      prev && prev.id === id
        ? { ...prev, completedBy: [...prev.completedBy, 'current-user'] }
        : prev,
    );
  };

  return (
    <div className="min-h-screen bg-gray-50/60">
      <div className="mx-auto max-w-[1440px] px-6 py-8 lg:px-10">
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-sm">
              <BookOpen className="text-white" size={20} />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">Health Education</h1>
              <p className="text-sm text-gray-500">
                Micro-lessons & caregiver training · {format(new Date(), 'EEEE, MMM d, yyyy')}
              </p>
            </div>
          </div>
        </div>

        {/* ── KPI Row ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Total Lessons"
            value={kpis.total}
            icon={BookOpen}
            iconBg="bg-blue-50"
            iconColor="text-blue-600"
            subtitle={`${kpis.avgDuration} min avg`}
          />
          <KpiCard
            label="Completion Rate"
            value={`${kpis.completionPct}%`}
            icon={BarChart3}
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
            subtitle={`${kpis.completed} of ${kpis.total} completed`}
          />
          <KpiCard
            label="Teach-Back"
            value={`${kpis.teachBackDone}/${kpis.teachBackRequired}`}
            icon={Award}
            iconBg="bg-amber-50"
            iconColor="text-amber-600"
            subtitle="Verbal confirmations"
          />
          <KpiCard
            label="Categories"
            value={categoryChartData.length}
            icon={BookOpen}
            iconBg="bg-violet-50"
            iconColor="text-violet-600"
            subtitle="Learning domains"
          />
        </div>

        {/* ── Progress Overview ────────────────────────────────────── */}
        <div className="mt-8 mb-2">
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-base font-semibold text-gray-900">Overall Progress</h2>
            <span className="text-xs text-gray-400">{kpis.completionPct}% complete</span>
          </div>
          <div className="h-3 w-full rounded-full bg-gray-200 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-emerald-600 transition-all duration-500"
              style={{ width: `${kpis.completionPct}%` }}
            />
          </div>
        </div>

        {/* ── Charts Row ──────────────────────────────────────────── */}
        <div className="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Category Donut */}
          <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Lessons by Category</h3>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={categoryChartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {categoryChartData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ borderRadius: 12, fontSize: 12, border: '1px solid #e5e7eb' }}
                  formatter={(value: number, name: string) => [`${value} lessons`, name]}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex flex-wrap gap-2 mt-3 justify-center">
              {categoryChartData.map((d) => (
                <span key={d.name} className="flex items-center gap-1.5 text-xs text-gray-500">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: d.color }} />
                  {d.name}
                </span>
              ))}
            </div>
          </div>

          {/* Module Completion Bar */}
          <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Module Completion</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={moduleCompletionData} layout="vertical" barCategoryGap="25%">
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="category" tick={{ fontSize: 10 }} width={100} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ borderRadius: 12, fontSize: 12, border: '1px solid #e5e7eb' }}
                  formatter={(value: number) => [`${value}%`, 'Completion']}
                />
                <Bar dataKey="completion" radius={[0, 6, 6, 0]} fill="#10b981" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ── Category Filter ─────────────────────────────────────── */}
        <div className="mt-8 flex flex-wrap gap-1.5">
          {categories.map((cat) => {
            const isActive = filterCategory === cat;
            return (
              <button
                key={cat}
                onClick={() => setFilterCategory(cat)}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'bg-white text-gray-600 ring-1 ring-gray-200 hover:bg-gray-50'
                }`}
              >
                {cat === 'all' ? 'All' : cat}
              </button>
            );
          })}
        </div>

        {/* ── Lesson Grid ─────────────────────────────────────────── */}
        <div className="mt-5 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
          {filtered.length === 0 ? (
            <div className="col-span-full rounded-2xl bg-white p-16 shadow-sm ring-1 ring-gray-200/60 flex flex-col items-center text-center">
              <BookOpen size={40} className="text-gray-300 mb-3" />
              <p className="text-sm font-medium text-gray-600">No lessons found</p>
              <p className="text-xs text-gray-400 mt-1">Try selecting a different category.</p>
            </div>
          ) : (
            filtered.map((lesson) => {
              const isCompleted = lesson.completedBy.length > 0;
              const cfg = getCategoryConfig(lesson.category);
              return (
                <button
                  key={lesson.id}
                  onClick={() => setSelectedLesson(lesson)}
                  className="text-left rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200/60 transition-all hover:shadow-md cursor-pointer group"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${cfg.bg}`}>
                      <cfg.icon size={16} className={cfg.text} />
                    </div>
                    <div className="flex items-center gap-2">
                      {isCompleted && (
                        <CheckCircle size={16} className="text-emerald-500" />
                      )}
                      <ChevronRight size={16} className="text-gray-300 group-hover:text-gray-500 transition-colors" />
                    </div>
                  </div>
                  <h3 className="text-sm font-semibold text-gray-800 mb-1 line-clamp-2">
                    {lesson.title}
                  </h3>
                  <div className="flex flex-wrap items-center gap-2 mt-2">
                    <CategoryBadge category={lesson.category} />
                    <span className="text-xs text-gray-400 flex items-center gap-1">
                      <Clock size={11} /> {lesson.duration} min
                    </span>
                  </div>
                  {lesson.teachBackRequired && (
                    <div className="mt-3 flex items-center gap-1.5">
                      <Award size={12} className={lesson.teachBackCompleted ? 'text-emerald-500' : 'text-amber-500'} />
                      <span className={`text-[11px] font-semibold ${lesson.teachBackCompleted ? 'text-emerald-600' : 'text-amber-600'}`}>
                        Teach-back {lesson.teachBackCompleted ? 'passed' : 'required'}
                      </span>
                    </div>
                  )}
                  {/* Progress */}
                  <div className="mt-3">
                    <div className="h-1.5 w-full rounded-full bg-gray-100 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${isCompleted ? 'bg-emerald-500' : 'bg-gray-200'}`}
                        style={{ width: isCompleted ? '100%' : '0%' }}
                      />
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* ── Progress Tracking ────────────────────────────────────── */}
        <div className="mt-10 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Per-resident */}
          <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Per-Resident Completion</h3>
            <div className="space-y-4">
              {residentCompletion.map((r) => {
                const pct = Math.round((r.read / r.total) * 100);
                return (
                  <div key={r.name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-gray-700">{r.name}</span>
                      <span className="text-xs font-semibold text-gray-500">{pct}%</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-blue-400 to-blue-600 transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recent Completions */}
          <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Recent Completions</h3>
            {recentCompletions.length === 0 ? (
              <p className="text-sm text-gray-400">No completions yet.</p>
            ) : (
              <div className="space-y-3">
                {recentCompletions.map((l) => (
                  <div key={l.id} className="flex items-center gap-3 p-3 rounded-xl bg-gray-50 ring-1 ring-gray-100">
                    <CheckCircle size={16} className="text-emerald-500 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-gray-800 truncate">{l.title}</p>
                      <p className="text-xs text-gray-400">{l.category} · {l.duration} min</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Caregiver Training (caregiver role only) ────────────── */}
        {role === 'caregiver' && (
          <div className="mt-10">
            <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Shield size={18} className="text-violet-500" /> Caregiver Training Modules
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
              {CAREGIVER_TRAINING.map((mod) => (
                <div
                  key={mod.id}
                  className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200/60 transition-all hover:shadow-md"
                >
                  <div className="flex items-start justify-between mb-2">
                    <span className="inline-flex items-center rounded-full bg-violet-100 px-2.5 py-0.5 text-[11px] font-bold text-violet-700">
                      {mod.category}
                    </span>
                    {mod.completed && <CheckCircle size={16} className="text-emerald-500" />}
                  </div>
                  <h3 className="text-sm font-semibold text-gray-800 mb-1">{mod.title}</h3>
                  <p className="text-xs text-gray-500 leading-relaxed">{mod.description}</p>
                  <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
                    <Clock size={11} /> {mod.duration} min
                    {mod.completed && <span className="text-emerald-600 font-semibold ml-auto">Completed</span>}
                    {!mod.completed && <span className="text-amber-600 font-semibold ml-auto">Not started</span>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Footer ─────────────────────────────────────────────── */}
        <div className="mt-12 border-t border-gray-200/60 pt-6 pb-8 text-center">
          <p className="text-xs text-gray-300">
            AETHER Health Education · Micro-lessons with teach-back verification
          </p>
        </div>
      </div>

      {/* ── Lesson Detail Panel ───────────────────────────────────── */}
      {selectedLesson && (
        <LessonPanel
          lesson={selectedLesson}
          onClose={() => setSelectedLesson(null)}
          onMarkRead={handleMarkRead}
        />
      )}
    </div>
  );
}
