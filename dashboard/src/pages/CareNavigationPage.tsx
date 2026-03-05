import { useMemo, useState } from 'react';
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import {
  Compass,
  Search,
  Globe,
  ExternalLink,
  Plus,
  CheckCircle,
  Clock,
  Wifi,
  WifiOff,
  ChevronDown,
  X,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { formatDistanceToNow, format } from 'date-fns';

import { CARE_NAVIGATION_QUERIES, RESIDENTS } from '../data/mockData';
import { queryCareNavigation } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import type { CareNavigationQuery, Resident } from '../types';

// ─── Constants ────────────────────────────────────────────────────────────────

const LANGUAGES = [
  'English', 'Hindi', 'Tamil', 'Telugu', 'Bengali',
  'Marathi', 'Gujarati', 'Kannada', 'Malayalam', 'Punjabi',
] as const;

const ACTION_TIER_CONFIG: Record<
  CareNavigationQuery['actionTier'],
  { label: string; bg: string; text: string; dot: string }
> = {
  self_care:    { label: 'Self Care',    bg: 'bg-emerald-100', text: 'text-emerald-700', dot: 'bg-emerald-500' },
  gp_visit:    { label: 'GP Visit',     bg: 'bg-blue-100',    text: 'text-blue-700',    dot: 'bg-blue-500' },
  urgent_care: { label: 'Urgent Care',  bg: 'bg-orange-100',  text: 'text-orange-700',  dot: 'bg-orange-500' },
  emergency:   { label: 'Emergency',    bg: 'bg-red-100',     text: 'text-red-700',     dot: 'bg-red-500' },
};

const PIE_COLORS: Record<CareNavigationQuery['actionTier'], string> = {
  self_care: '#22c55e',
  gp_visit: '#3b82f6',
  urgent_care: '#f97316',
  emergency: '#ef4444',
};

const SUGGESTION_CHIPS = [
  'What to do if blood sugar is high?',
  'Is mild fever normal after vaccination?',
  'How to manage joint pain at home?',
  'Signs of dehydration in elderly',
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function residentById(id: string): Resident | undefined {
  return RESIDENTS.find((r) => r.resident_id === id);
}

function timeAgo(ts: number): string {
  return formatDistanceToNow(new Date(ts), { addSuffix: true });
}

// ─── Action Tier Badge ────────────────────────────────────────────────────────

function TierBadge({ tier }: { tier: CareNavigationQuery['actionTier'] }) {
  const cfg = ACTION_TIER_CONFIG[tier];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-bold ${cfg.bg} ${cfg.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

// ─── Custom Pie Tooltip ───────────────────────────────────────────────────────

function PieTooltipContent({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-lg text-xs">
      <span className="font-semibold text-gray-800">{d.name}</span>:{' '}
      <span className="font-bold text-gray-900">{d.value}</span>
    </div>
  );
}

// ─── Follow-up Task Card ──────────────────────────────────────────────────────

function FollowUpCard({
  query,
  onComplete,
}: {
  query: CareNavigationQuery;
  onComplete: (id: string) => void;
}) {
  const resident = residentById(query.residentId);
  return (
    <div className="flex items-start gap-3 rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200/60 transition-all hover:shadow-md">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-amber-50">
        <Clock size={16} className="text-amber-600" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">
          {query.followUpTask}
        </p>
        <p className="mt-0.5 text-xs text-gray-400">
          {resident?.name} · {timeAgo(query.timestamp)}
        </p>
      </div>
      <button
        onClick={() => onComplete(query.id)}
        className="shrink-0 rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-emerald-50 hover:text-emerald-600"
        title="Mark complete"
      >
        <CheckCircle size={18} />
      </button>
    </div>
  );
}

// ─── Query Card ───────────────────────────────────────────────────────────────

function QueryCard({
  query,
  onCreateFollowUp,
}: {
  query: CareNavigationQuery;
  onCreateFollowUp: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const resident = residentById(query.residentId);

  return (
    <div className="rounded-xl bg-white shadow-sm ring-1 ring-gray-200/60 transition-all hover:shadow-md">
      {/* Header */}
      <button
        type="button"
        className="w-full text-left px-5 py-4 flex items-start gap-4"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-sm font-bold text-white shadow-sm">
          {resident?.name.charAt(0) ?? '?'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-gray-900 truncate">
              {resident?.name ?? 'Unknown Resident'}
            </span>
            <TierBadge tier={query.actionTier} />
            {query.isOffline ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500">
                <WifiOff size={10} /> Offline
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-600">
                <Wifi size={10} /> Online
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-gray-600 line-clamp-2">
            {query.query}
          </p>
          <p className="mt-1 text-xs text-gray-400">{timeAgo(query.timestamp)}</p>
        </div>
        <ChevronDown
          size={18}
          className={`shrink-0 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Expanded */}
      {expanded && (
        <div className="border-t border-gray-100 px-5 py-4 animate-fade-in">
          <div className="rounded-lg bg-blue-50/60 p-4">
            <p className="text-sm leading-relaxed text-gray-700 whitespace-pre-wrap">
              {query.response}
            </p>
          </div>

          {/* Sources */}
          <div className="mt-3 flex flex-wrap gap-2">
            {query.sources.map((s) => (
              <a
                key={s}
                href="#"
                className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-medium text-gray-600 transition-colors hover:bg-gray-200 hover:text-gray-800"
              >
                <ExternalLink size={10} />
                {s}
              </a>
            ))}
          </div>

          {/* Language + Follow-up */}
          <div className="mt-3 flex items-center justify-between">
            <span className="inline-flex items-center gap-1 text-xs text-gray-400">
              <Globe size={12} />
              {query.language === 'en' ? 'English' : query.language === 'hi' ? 'Hindi' : query.language}
            </span>
            {!query.followUpTask && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onCreateFollowUp(query.id);
                }}
                className="inline-flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-blue-700 active:scale-[0.98]"
              >
                <Plus size={12} />
                Create Follow-up
              </button>
            )}
            {query.followUpTask && (
              <span className="inline-flex items-center gap-1 text-xs text-emerald-600 font-medium">
                <CheckCircle size={12} />
                Follow-up created
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// Care Navigation Page
// ═════════════════════════════════════════════════════════════════════════════

export default function CareNavigationPage() {
  const { user, role } = useAuth();
  const isElder = role === 'elder';

  // State
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('English');
  const [queries, setQueries] = useState<CareNavigationQuery[]>(
    () => CARE_NAVIGATION_QUERIES,
  );
  const [completedFollowUps, setCompletedFollowUps] = useState<Set<string>>(
    () => new Set(),
  );
  const [submittedMessage, setSubmittedMessage] = useState<string | null>(null);
  const [isQuerying, setIsQuerying] = useState(false);
  const [aiSource, setAiSource] = useState<string | null>(null);

  // Filter for elder: only their own queries
  const visibleQueries = useMemo(() => {
    if (isElder && user) {
      // find resident matching elder user
      const elderResident = RESIDENTS.find((r) => r.name === user.name);
      if (elderResident) {
        return queries.filter((q) => q.residentId === elderResident.resident_id);
      }
    }
    return queries;
  }, [queries, isElder, user]);

  // Follow-up tasks
  const followUpQueries = useMemo(
    () =>
      visibleQueries.filter(
        (q) => q.followUpTask && !completedFollowUps.has(q.id),
      ),
    [visibleQueries, completedFollowUps],
  );

  // Tier distribution
  const tierDistribution = useMemo(() => {
    const counts: Record<string, number> = {
      self_care: 0,
      gp_visit: 0,
      urgent_care: 0,
      emergency: 0,
    };
    visibleQueries.forEach((q) => {
      counts[q.actionTier]++;
    });
    return Object.entries(counts).map(([tier, count]) => ({
      name: ACTION_TIER_CONFIG[tier as CareNavigationQuery['actionTier']].label,
      value: count,
      tier: tier as CareNavigationQuery['actionTier'],
    }));
  }, [visibleQueries]);

  // Pick a resident for context
  const contextResident = RESIDENTS[0];

  // Handlers — calls real Bedrock AI
  const handleSubmit = async () => {
    if (!searchQuery.trim() || isQuerying) return;
    const queryText = searchQuery.trim();
    setSearchQuery('');
    setIsQuerying(true);
    setSubmittedMessage(queryText);

    try {
      const result = await queryCareNavigation({
        query: queryText,
        resident_id: contextResident?.resident_id || 'RES-001',
        language: selectedLanguage === 'English' ? 'en' : selectedLanguage.toLowerCase().slice(0, 2),
      });

      const newQuery: CareNavigationQuery = {
        id: `CN-${Date.now()}`,
        residentId: contextResident?.resident_id || 'RES-001',
        query: queryText,
        response: result.response,
        actionTier: result.action_tier,
        sources: result.citations || [],
        isOffline: false,
        timestamp: Date.now(),
        language: selectedLanguage === 'English' ? 'en' : selectedLanguage.toLowerCase().slice(0, 2),
      };
      setQueries((prev) => [newQuery, ...prev]);
      setAiSource(result.ai_model || 'aws_bedrock');
    } catch (err) {
      console.error('Care navigation error:', err);
      // Fallback: add a query with error info
      const newQuery: CareNavigationQuery = {
        id: `CN-${Date.now()}`,
        residentId: contextResident?.resident_id || 'RES-001',
        query: queryText,
        response: `I understand you're asking about: "${queryText}". While the AI service is temporarily unavailable, I recommend consulting your healthcare provider for personalized guidance.`,
        actionTier: 'gp_visit',
        sources: ['AETHER Fallback'],
        isOffline: true,
        timestamp: Date.now(),
        language: selectedLanguage === 'English' ? 'en' : 'hi',
      };
      setQueries((prev) => [newQuery, ...prev]);
      setAiSource('fallback');
    } finally {
      setIsQuerying(false);
      setTimeout(() => setSubmittedMessage(null), 4000);
    }
  };

  const handleCreateFollowUp = (id: string) => {
    setQueries((prev) =>
      prev.map((q) =>
        q.id === id
          ? { ...q, followUpTask: q.followUpTask ?? 'Follow-up task created for this query' }
          : q,
      ),
    );
  };

  const handleCompleteFollowUp = (id: string) => {
    setCompletedFollowUps((prev) => new Set(prev).add(id));
  };

  const handleSuggestionClick = (suggestion: string) => {
    setSearchQuery(suggestion);
  };

  return (
    <div className="min-h-screen bg-gray-50/60">
      <div className="mx-auto max-w-[1440px] px-6 py-8 lg:px-10">
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="mb-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-teal-500 to-cyan-600 shadow-sm">
              <Compass className="text-white" size={20} />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">
                Care Navigation
              </h1>
              <p className="text-sm text-gray-500">
                AI-powered clinical guidance · {format(new Date(), 'EEEE, MMM d, yyyy')}
              </p>
            </div>
          </div>
        </div>

        {/* ── New Query Input ─────────────────────────────────────── */}
        <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
            {/* Search bar */}
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                Ask about symptoms, medications, care guidance...
              </label>
              <div className="relative">
                <Search
                  size={18}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
                />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                  placeholder="Describe symptoms or ask a care question..."
                  className="w-full rounded-xl border border-gray-300 bg-white py-3 pl-10 pr-4 text-sm text-gray-900 placeholder-gray-400 shadow-sm transition-all focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                />
              </div>
            </div>

            {/* Language selector */}
            <div className="sm:w-44">
              <label className="block text-sm font-medium text-gray-700 mb-1.5">
                <Globe size={14} className="inline mr-1 -mt-0.5" />
                Language
              </label>
              <select
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
                className="w-full rounded-xl border border-gray-300 bg-white py-3 px-3 text-sm text-gray-700 shadow-sm transition-all focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
              >
                {LANGUAGES.map((lang) => (
                  <option key={lang} value={lang}>{lang}</option>
                ))}
              </select>
            </div>

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={!searchQuery.trim() || isQuerying}
              className="rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {isQuerying ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <Sparkles size={16} />
                  Ask AI
                </>
              )}
            </button>
          </div>

          {/* Suggestion chips */}
          {!isElder && (
            <div className="mt-4 flex flex-wrap gap-2">
              {SUGGESTION_CHIPS.map((s) => (
                <button
                  key={s}
                  onClick={() => handleSuggestionClick(s)}
                  className="rounded-full bg-gray-50 px-3 py-1.5 text-xs text-gray-500 ring-1 ring-gray-200/80 transition-colors hover:bg-gray-100 hover:text-gray-700"
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Submitted confirmation */}
          {submittedMessage && (
            <div className="mt-4 flex items-center gap-2 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700 animate-fade-in">
              {isQuerying ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <CheckCircle size={16} />
              )}
              <span>
                {isQuerying ? (
                  <>Querying AWS Bedrock AI: <span className="font-medium">"{submittedMessage}"</span></>
                ) : (
                  <>Response from <span className="font-semibold">{aiSource || 'AWS Bedrock'}</span> for: <span className="font-medium">"{submittedMessage}"</span></>
                )}
              </span>
              <button onClick={() => setSubmittedMessage(null)} className="ml-auto">
                <X size={14} />
              </button>
            </div>
          )}
        </div>

        {/* ── Main Grid ───────────────────────────────────────────── */}
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Left: Query Log (2 cols) */}
          <div className="lg:col-span-2 space-y-6">
            {/* Tier Distribution (compact) — hidden for elder */}
            {!isElder && (
              <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
                <h2 className="text-base font-semibold text-gray-900 mb-4">
                  Action Tier Distribution
                </h2>
                <div className="flex flex-col sm:flex-row items-center gap-6">
                  <div className="w-40 h-40">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie
                          data={tierDistribution}
                          cx="50%"
                          cy="50%"
                          innerRadius={30}
                          outerRadius={60}
                          paddingAngle={3}
                          dataKey="value"
                        >
                          {tierDistribution.map((entry) => (
                            <Cell
                              key={entry.tier}
                              fill={PIE_COLORS[entry.tier]}
                            />
                          ))}
                        </Pie>
                        <Tooltip content={<PieTooltipContent />} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="grid grid-cols-2 gap-3 flex-1">
                    {tierDistribution.map((entry) => {
                      const cfg = ACTION_TIER_CONFIG[entry.tier];
                      return (
                        <div
                          key={entry.tier}
                          className={`rounded-lg ${cfg.bg} px-4 py-3`}
                        >
                          <p className={`text-2xl font-bold ${cfg.text}`}>
                            {entry.value}
                          </p>
                          <p className={`text-xs font-medium ${cfg.text} opacity-80`}>
                            {entry.name}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* Query Log */}
            <div>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    {isElder ? 'Your Queries' : 'Query Log'}
                  </h2>
                  <p className="text-xs text-gray-400">
                    {visibleQueries.length} queries recorded
                  </p>
                </div>
              </div>

              {visibleQueries.length === 0 ? (
                <div className="rounded-2xl bg-white p-12 text-center shadow-sm ring-1 ring-gray-200/60">
                  <Compass size={40} className="mx-auto text-gray-300 mb-3" />
                  <p className="text-sm font-medium text-gray-600">
                    No queries yet
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    Ask a care question above to get started.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  {visibleQueries
                    .sort((a, b) => b.timestamp - a.timestamp)
                    .map((q) => (
                      <QueryCard
                        key={q.id}
                        query={q}
                        onCreateFollowUp={handleCreateFollowUp}
                      />
                    ))}
                </div>
              )}
            </div>
          </div>

          {/* Right: Follow-up Tasks */}
          {!isElder && (
            <div className="space-y-6">
              <div className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60">
                <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
                  <div>
                    <h2 className="text-base font-semibold text-gray-900">
                      Follow-up Tasks
                    </h2>
                    <p className="text-xs text-gray-400">
                      {followUpQueries.length} pending
                    </p>
                  </div>
                  <Clock size={18} className="text-amber-500" />
                </div>
                <div className="p-4 space-y-3">
                  {followUpQueries.length === 0 ? (
                    <div className="flex flex-col items-center py-8 text-center">
                      <CheckCircle size={36} className="text-emerald-400 mb-2" />
                      <p className="text-sm font-medium text-gray-600">
                        All caught up
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        No pending follow-ups
                      </p>
                    </div>
                  ) : (
                    followUpQueries.map((q) => (
                      <FollowUpCard
                        key={q.id}
                        query={q}
                        onComplete={handleCompleteFollowUp}
                      />
                    ))
                  )}
                </div>
              </div>

              {/* Quick Stats */}
              <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200/60">
                <h3 className="text-sm font-semibold text-gray-900 mb-3">
                  Quick Stats
                </h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Total Queries</span>
                    <span className="text-sm font-bold text-gray-900">
                      {visibleQueries.length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Offline Queries</span>
                    <span className="text-sm font-bold text-gray-900">
                      {visibleQueries.filter((q) => q.isOffline).length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Emergency Tier</span>
                    <span className="text-sm font-bold text-red-600">
                      {visibleQueries.filter((q) => q.actionTier === 'emergency').length}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500">Languages Used</span>
                    <span className="text-sm font-bold text-gray-900">
                      {new Set(visibleQueries.map((q) => q.language)).size}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* ── Footer ─────────────────────────────────────────────── */}
        <div className="mt-12 border-t border-gray-200/60 pt-6 pb-8 text-center">
          <p className="text-xs text-gray-300">
            AETHER Care Navigation · AI-assisted clinical guidance with offline support
          </p>
        </div>
      </div>
    </div>
  );
}
