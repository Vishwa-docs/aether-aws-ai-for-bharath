import { useMemo, useState, useCallback } from 'react';
import {
  FileText,
  Filter,
  Download,
  Edit3,
  CheckSquare,
  Clock,
  BarChart3,
  Plus,
  ChevronRight,
  X,
  Shield,
  Eye,
  Hash,
  User,
  History,
} from 'lucide-react';
import { formatDistanceToNow, format } from 'date-fns';

import { CLINICAL_DOCUMENTS, RESIDENTS } from '../data/mockData';
import { generateDocument } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import type { ClinicalDocument, Resident } from '../types';

// ─── Constants ────────────────────────────────────────────────────────────────

type DocStatus = ClinicalDocument['status'];
type DocType = ClinicalDocument['type'];

const STATUS_CONFIG: Record<DocStatus, { label: string; bg: string; text: string; ring: string }> = {
  draft:          { label: 'Draft',          bg: 'bg-gray-100',   text: 'text-gray-700',   ring: 'ring-gray-600/10' },
  pending_review: { label: 'Pending Review', bg: 'bg-yellow-100', text: 'text-yellow-700', ring: 'ring-yellow-600/10' },
  approved:       { label: 'Approved',       bg: 'bg-emerald-100', text: 'text-emerald-700', ring: 'ring-emerald-600/10' },
  exported:       { label: 'Exported',       bg: 'bg-blue-100',   text: 'text-blue-700',   ring: 'ring-blue-600/10' },
};

const TYPE_LABELS: Record<DocType, string> = {
  soap_note:      'SOAP Note',
  daily_summary:  'Daily Summary',
  weekly_summary: 'Weekly Summary',
  incident_report:'Incident Report',
  pre_consult:    'Pre-Consult Brief',
};

const FILTER_TABS: { key: DocStatus | 'all'; label: string }[] = [
  { key: 'all',            label: 'All' },
  { key: 'draft',          label: 'Drafts' },
  { key: 'pending_review', label: 'Pending Review' },
  { key: 'approved',       label: 'Approved' },
  { key: 'exported',       label: 'Exported' },
];

const SORT_OPTIONS = [
  { key: 'status',  label: 'Status (Pending first)' },
  { key: 'date',    label: 'Date (Newest first)' },
  { key: 'type',    label: 'Type' },
] as const;

type SortKey = (typeof SORT_OPTIONS)[number]['key'];

const STATUS_ORDER: Record<DocStatus, number> = {
  pending_review: 0,
  draft: 1,
  approved: 2,
  exported: 3,
};

// Mock audit trail
interface AuditEntry {
  model: string;
  promptHash: string;
  outputHash: string;
  timestamp: number;
  reviewer: string;
}

function generateAuditTrail(doc: ClinicalDocument): AuditEntry[] {
  const base = doc.generatedAt;
  const entries: AuditEntry[] = [
    {
      model: 'Amazon Nova Lite (Bedrock)',
      promptHash: `sha256:${doc.id.slice(0, 8)}a1b2c3`,
      outputHash: `sha256:${doc.id.slice(0, 8)}d4e5f6`,
      timestamp: base,
      reviewer: 'System (Auto-generated)',
    },
  ];
  if (doc.reviewedBy) {
    entries.push({
      model: 'Amazon Nova Lite (Bedrock)',
      promptHash: `sha256:${doc.id.slice(0, 8)}a1b2c3`,
      outputHash: `sha256:${doc.id.slice(0, 8)}g7h8i9`,
      timestamp: doc.approvedAt ?? base + 3600000,
      reviewer: doc.reviewedBy,
    });
  }
  return entries;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function residentById(id: string): Resident | undefined {
  return RESIDENTS.find((r) => r.resident_id === id);
}

function timeAgo(ts: number): string {
  return formatDistanceToNow(new Date(ts), { addSuffix: true });
}

function confidenceColor(c: number): string {
  if (c >= 0.93) return 'text-emerald-600';
  if (c >= 0.88) return 'text-blue-600';
  return 'text-amber-600';
}

function confidenceBarColor(c: number): string {
  if (c >= 0.93) return 'bg-emerald-500';
  if (c >= 0.88) return 'bg-blue-500';
  return 'bg-amber-500';
}

// ─── Status Badge ─────────────────────────────────────────────────────────────

function DocStatusBadge({ status }: { status: DocStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-bold ring-1 ring-inset ${cfg.bg} ${cfg.text} ${cfg.ring}`}
    >
      {cfg.label}
    </span>
  );
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
    <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200/60 transition-all hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-500 truncate">{label}</p>
          <p className="mt-1.5 text-2xl font-bold tracking-tight text-gray-900">
            {value}
          </p>
          {subtitle && (
            <p className="mt-0.5 text-xs text-gray-400">{subtitle}</p>
          )}
        </div>
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconBg}`}
        >
          <Icon className={iconColor} size={20} strokeWidth={2} />
        </div>
      </div>
    </div>
  );
}

// ─── Document Preview Panel ───────────────────────────────────────────────────

function DocumentPanel({
  doc,
  onClose,
  onApprove,
  onExport,
  onSave,
}: {
  doc: ClinicalDocument;
  onClose: () => void;
  onApprove: (id: string) => void;
  onExport: (id: string) => void;
  onSave: (id: string, content: string) => void;
}) {
  const resident = residentById(doc.residentId);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState(doc.content);
  const [showAudit, setShowAudit] = useState(false);
  const auditTrail = useMemo(() => generateAuditTrail(doc), [doc]);

  const handleSave = () => {
    onSave(doc.id, editContent);
    setEditing(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="relative w-full max-w-2xl bg-white shadow-2xl animate-slide-up overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50">
                <FileText size={18} className="text-blue-600" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-gray-900 truncate">
                  {TYPE_LABELS[doc.type]}
                </h3>
                <p className="text-xs text-gray-400">
                  {resident?.name} · v{doc.version} · {timeAgo(doc.generatedAt)}
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          {/* Meta row */}
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <DocStatusBadge status={doc.status} />
            <span className="text-xs text-gray-400 flex items-center gap-1">
              <Hash size={12} />
              v{doc.version}
            </span>
            <span className={`text-xs font-semibold ${confidenceColor(doc.aiConfidence)}`}>
              AI Confidence: {(doc.aiConfidence * 100).toFixed(0)}%
            </span>
            {doc.reviewedBy && (
              <span className="text-xs text-gray-400 flex items-center gap-1">
                <User size={12} />
                {doc.reviewedBy}
              </span>
            )}
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-6">
          {editing ? (
            <textarea
              value={editContent}
              onChange={(e) => setEditContent(e.target.value)}
              className="w-full min-h-[400px] rounded-xl border border-gray-300 p-4 text-sm text-gray-800 leading-relaxed font-mono focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100 resize-y"
            />
          ) : (
            <div className="rounded-xl bg-gray-50 p-5 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap font-mono">
              {doc.content}
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4">
          <div className="flex flex-wrap gap-3">
            {!editing && (doc.status === 'draft' || doc.status === 'pending_review') && (
              <button
                onClick={() => setEditing(true)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-700 transition-all hover:bg-gray-200"
              >
                <Edit3 size={14} />
                Edit
              </button>
            )}
            {editing && (
              <>
                <button
                  onClick={handleSave}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700"
                >
                  <CheckSquare size={14} />
                  Save Changes
                </button>
                <button
                  onClick={() => {
                    setEditContent(doc.content);
                    setEditing(false);
                  }}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-700 transition-all hover:bg-gray-200"
                >
                  Cancel
                </button>
              </>
            )}
            {!editing && (doc.status === 'draft' || doc.status === 'pending_review') && (
              <button
                onClick={() => onApprove(doc.id)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-700"
              >
                <Shield size={14} />
                Sign Off &amp; Approve
              </button>
            )}
            {!editing && (doc.status === 'approved' || doc.status === 'exported') && (
              <button
                onClick={() => onExport(doc.id)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700"
              >
                <Download size={14} />
                Export PDF
              </button>
            )}
            {!editing && (
              <button
                onClick={() => setShowAudit(!showAudit)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-700 transition-all hover:bg-gray-200"
              >
                <History size={14} />
                {showAudit ? 'Hide' : 'Show'} Audit Trail
              </button>
            )}
          </div>

          {/* Audit Trail */}
          {showAudit && (
            <div className="mt-4 rounded-xl border border-gray-200 divide-y divide-gray-100 animate-fade-in">
              {auditTrail.map((entry, i) => (
                <div key={i} className="px-4 py-3 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-gray-700">{entry.reviewer}</span>
                    <span className="text-gray-400">
                      {format(new Date(entry.timestamp), 'MMM d, h:mm a')}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-x-4 text-gray-400">
                    <span>Model: <span className="text-gray-600">{entry.model}</span></span>
                    <span>Prompt: <span className="text-gray-600 font-mono">{entry.promptHash.slice(0, 20)}…</span></span>
                    <span>Output: <span className="text-gray-600 font-mono">{entry.outputHash.slice(0, 20)}…</span></span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// Clinical Documents Page
// ═════════════════════════════════════════════════════════════════════════════

export default function ClinicalDocsPage() {
  const { role } = useAuth();

  // State
  const [docs, setDocs] = useState<ClinicalDocument[]>(() => CLINICAL_DOCUMENTS);
  const [activeFilter, setActiveFilter] = useState<DocStatus | 'all'>('all');
  const [sortBy, setSortBy] = useState<SortKey>('status');
  const [selectedDoc, setSelectedDoc] = useState<ClinicalDocument | null>(null);
  const [showGenerator, setShowGenerator] = useState(false);
  const [genResident, setGenResident] = useState(RESIDENTS[0].resident_id);
  const [genType, setGenType] = useState<DocType>('soap_note');
  const [exportedMessage, setExportedMessage] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // Computed
  const filteredDocs = useMemo(() => {
    let result = activeFilter === 'all'
      ? docs
      : docs.filter((d) => d.status === activeFilter);

    result = [...result].sort((a, b) => {
      if (sortBy === 'status') return STATUS_ORDER[a.status] - STATUS_ORDER[b.status];
      if (sortBy === 'date') return b.generatedAt - a.generatedAt;
      return a.type.localeCompare(b.type);
    });

    return result;
  }, [docs, activeFilter, sortBy]);

  // KPIs
  const kpis = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayTs = today.getTime();

    const generatedToday = docs.filter((d) => d.generatedAt >= todayTs).length;
    const pendingReviews = docs.filter((d) => d.status === 'pending_review').length;
    const approved = docs.filter((d) => d.status === 'approved' || d.status === 'exported');
    const approvalRate = docs.length > 0
      ? Math.round((approved.length / docs.length) * 100)
      : 0;

    // Avg turnaround: time from generatedAt to approvedAt for approved docs
    const withApproval = docs.filter((d) => d.approvedAt);
    const avgTurnaround = withApproval.length > 0
      ? Math.round(
          withApproval.reduce(
            (sum, d) => sum + ((d.approvedAt! - d.generatedAt) / 3600000),
            0,
          ) / withApproval.length,
        )
      : 0;

    return { generatedToday, pendingReviews, approvalRate, avgTurnaround };
  }, [docs]);

  // Handlers
  const handleApprove = useCallback(
    (id: string) => {
      setDocs((prev) =>
        prev.map((d) =>
          d.id === id
            ? {
                ...d,
                status: 'approved' as const,
                approvedAt: Date.now(),
                reviewedBy: d.reviewedBy ?? 'Current User',
                version: d.version + 1,
              }
            : d,
        ),
      );
      setSelectedDoc((prev) =>
        prev && prev.id === id
          ? {
              ...prev,
              status: 'approved' as const,
              approvedAt: Date.now(),
              reviewedBy: prev.reviewedBy ?? 'Current User',
              version: prev.version + 1,
            }
          : prev,
      );
    },
    [],
  );

  const handleExport = useCallback((id: string) => {
    setDocs((prev) =>
      prev.map((d) =>
        d.id === id
          ? { ...d, status: 'exported' as const, exportedAt: Date.now() }
          : d,
      ),
    );
    setSelectedDoc((prev) =>
      prev && prev.id === id
        ? { ...prev, status: 'exported' as const, exportedAt: Date.now() }
        : prev,
    );
    setExportedMessage('Document exported as PDF successfully.');
    setTimeout(() => setExportedMessage(null), 3000);
  }, []);

  const handleSave = useCallback((id: string, content: string) => {
    setDocs((prev) =>
      prev.map((d) =>
        d.id === id ? { ...d, content, version: d.version + 1 } : d,
      ),
    );
    setSelectedDoc((prev) =>
      prev && prev.id === id
        ? { ...prev, content, version: prev.version + 1 }
        : prev,
    );
  }, []);

  const handleGenerate = async () => {
    setIsGenerating(true);
    const resident = residentById(genResident);

    try {
      const docTypeMap: Record<DocType, 'soap_note' | 'daily_summary' | 'weekly_report' | 'pre_consult' | 'incident_report'> = {
        soap_note: 'soap_note',
        daily_summary: 'daily_summary',
        weekly_summary: 'weekly_report',
        incident_report: 'incident_report',
        pre_consult: 'pre_consult',
      };

      const result = await generateDocument({
        doc_type: docTypeMap[genType] || 'daily_summary',
        resident_id: genResident,
      });

      const newDoc: ClinicalDocument = {
        id: result.document_id || `doc-gen-${Date.now()}`,
        residentId: genResident,
        type: genType,
        status: 'draft',
        content: result.content,
        generatedAt: Date.now(),
        version: 1,
        aiConfidence: 0.92,
      };
      setDocs((prev) => [newDoc, ...prev]);
      setShowGenerator(false);
    } catch (err) {
      console.error('Doc generation error:', err);
      // Fallback to placeholder
      const newDoc: ClinicalDocument = {
        id: `doc-gen-${Date.now()}`,
        residentId: genResident,
        type: genType,
        status: 'draft',
        content: `[Auto-generated ${TYPE_LABELS[genType]}]\n\nResident: ${resident?.name ?? 'Unknown'}\nGenerated: ${format(new Date(), 'yyyy-MM-dd HH:mm')}\n\nThis document was auto-generated by AETHER AI. Content will be populated from sensor data, medication logs, and clinical knowledge base.\n\n--- AI service temporarily unavailable ---`,
        generatedAt: Date.now(),
        version: 1,
        aiConfidence: 0.5,
      };
      setDocs((prev) => [newDoc, ...prev]);
      setShowGenerator(false);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50/60">
      <div className="mx-auto max-w-[1440px] px-6 py-8 lg:px-10">
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-sm">
              <FileText className="text-white" size={20} />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">
                Clinical Documents
              </h1>
              <p className="text-sm text-gray-500">
                AI-generated clinical documentation · {format(new Date(), 'EEEE, MMM d, yyyy')}
              </p>
            </div>
          </div>
          {role !== 'elder' && (
            <button
              onClick={() => setShowGenerator(!showGenerator)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 active:scale-[0.98]"
            >
              <Plus size={16} />
              Generate Document
            </button>
          )}
        </div>

        {/* ── Export confirmation ──────────────────────────────────── */}
        {exportedMessage && (
          <div className="mb-6 flex items-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700 animate-fade-in ring-1 ring-emerald-200">
            <Download size={16} />
            {exportedMessage}
            <button onClick={() => setExportedMessage(null)} className="ml-auto text-emerald-500 hover:text-emerald-700">
              <X size={14} />
            </button>
          </div>
        )}

        {/* ── Draft Generator ─────────────────────────────────────── */}
        {showGenerator && (
          <div className="mb-6 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60 animate-slide-down">
            <h3 className="text-base font-semibold text-gray-900 mb-4">
              Generate New Document
            </h3>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Resident
                </label>
                <select
                  value={genResident}
                  onChange={(e) => setGenResident(e.target.value)}
                  className="w-full rounded-xl border border-gray-300 bg-white py-2.5 px-3 text-sm text-gray-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                >
                  {RESIDENTS.map((r) => (
                    <option key={r.resident_id} value={r.resident_id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 mb-1.5">
                  Document Type
                </label>
                <select
                  value={genType}
                  onChange={(e) => setGenType(e.target.value as DocType)}
                  className="w-full rounded-xl border border-gray-300 bg-white py-2.5 px-3 text-sm text-gray-700 shadow-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
                >
                  {Object.entries(TYPE_LABELS).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleGenerate}
                  disabled={isGenerating}
                  className="rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
                >
                  {isGenerating ? (
                    <>
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"/><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
                      Generating with AWS Bedrock...
                    </>
                  ) : (
                    'Generate with AI'
                  )}
                </button>
                <button
                  onClick={() => setShowGenerator(false)}
                  className="rounded-xl bg-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-600 transition-all hover:bg-gray-200"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── KPI Row ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Avg Turnaround"
            value={`${kpis.avgTurnaround}h`}
            icon={Clock}
            iconBg="bg-amber-50"
            iconColor="text-amber-600"
            subtitle="Draft to approval"
          />
          <KpiCard
            label="Generated Today"
            value={kpis.generatedToday}
            icon={FileText}
            iconBg="bg-blue-50"
            iconColor="text-blue-600"
            subtitle="Documents created"
          />
          <KpiCard
            label="Pending Reviews"
            value={kpis.pendingReviews}
            icon={Eye}
            iconBg={kpis.pendingReviews > 0 ? 'bg-yellow-50' : 'bg-emerald-50'}
            iconColor={kpis.pendingReviews > 0 ? 'text-yellow-600' : 'text-emerald-600'}
            subtitle={kpis.pendingReviews > 0 ? 'Awaiting sign-off' : 'All reviewed'}
          />
          <KpiCard
            label="Approval Rate"
            value={`${kpis.approvalRate}%`}
            icon={BarChart3}
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
            subtitle="Overall approval"
          />
        </div>

        {/* ── Filter & Sort Bar ───────────────────────────────────── */}
        <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          {/* Filter tabs */}
          <div className="flex flex-wrap gap-1.5">
            {FILTER_TABS.map((tab) => {
              const isActive = activeFilter === tab.key;
              const count = tab.key === 'all'
                ? docs.length
                : docs.filter((d) => d.status === tab.key).length;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveFilter(tab.key)}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'bg-white text-gray-600 ring-1 ring-gray-200 hover:bg-gray-50'
                  }`}
                >
                  {tab.label}
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                      isActive ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-500'
                    }`}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Sort */}
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-gray-400" />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortKey)}
              className="rounded-lg border border-gray-200 bg-white py-1.5 px-3 text-xs text-gray-600 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.key} value={opt.key}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* ── Document Table ──────────────────────────────────────── */}
        <div className="mt-5 rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 overflow-hidden">
          {/* Table header */}
          <div className="hidden sm:grid grid-cols-12 gap-4 border-b border-gray-100 px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
            <div className="col-span-3">Type</div>
            <div className="col-span-2">Resident</div>
            <div className="col-span-2">Status</div>
            <div className="col-span-2">Generated</div>
            <div className="col-span-1">Ver</div>
            <div className="col-span-2">AI Conf.</div>
          </div>

          {/* Rows */}
          {filteredDocs.length === 0 ? (
            <div className="flex flex-col items-center py-16 text-center">
              <FileText size={40} className="text-gray-300 mb-3" />
              <p className="text-sm font-medium text-gray-600">
                No documents found
              </p>
              <p className="text-xs text-gray-400 mt-1">
                Try changing the filter or generate a new document.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-gray-50">
              {filteredDocs.map((doc) => {
                const resident = residentById(doc.residentId);
                return (
                  <button
                    key={doc.id}
                    onClick={() => setSelectedDoc(doc)}
                    className="w-full text-left group grid grid-cols-1 sm:grid-cols-12 gap-2 sm:gap-4 px-6 py-4 transition-colors hover:bg-gray-50 cursor-pointer"
                  >
                    {/* Type */}
                    <div className="sm:col-span-3 flex items-center gap-2">
                      <FileText
                        size={16}
                        className="shrink-0 text-gray-400 group-hover:text-blue-500 transition-colors"
                      />
                      <span className="text-sm font-semibold text-gray-800 truncate">
                        {TYPE_LABELS[doc.type]}
                      </span>
                    </div>

                    {/* Resident */}
                    <div className="sm:col-span-2 flex items-center">
                      <span className="text-sm text-gray-600 truncate">
                        {resident?.name ?? 'Unknown'}
                      </span>
                    </div>

                    {/* Status */}
                    <div className="sm:col-span-2 flex items-center">
                      <DocStatusBadge status={doc.status} />
                    </div>

                    {/* Generated */}
                    <div className="sm:col-span-2 flex items-center">
                      <span className="text-xs text-gray-500">
                        {timeAgo(doc.generatedAt)}
                      </span>
                    </div>

                    {/* Version */}
                    <div className="sm:col-span-1 flex items-center">
                      <span className="text-xs text-gray-500">v{doc.version}</span>
                    </div>

                    {/* AI Confidence */}
                    <div className="sm:col-span-2 flex items-center gap-2">
                      <div className="h-1.5 w-16 rounded-full bg-gray-100 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${confidenceBarColor(doc.aiConfidence)} transition-all`}
                          style={{ width: `${doc.aiConfidence * 100}%` }}
                        />
                      </div>
                      <span
                        className={`text-xs font-semibold ${confidenceColor(doc.aiConfidence)}`}
                      >
                        {(doc.aiConfidence * 100).toFixed(0)}%
                      </span>
                      <ChevronRight
                        size={14}
                        className="ml-auto shrink-0 text-gray-300 group-hover:text-gray-500 transition-colors hidden sm:block"
                      />
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* ── Footer ─────────────────────────────────────────────── */}
        <div className="mt-12 border-t border-gray-200/60 pt-6 pb-8 text-center">
          <p className="text-xs text-gray-300">
            AETHER Clinical Documents · AI-generated with human-in-the-loop review
          </p>
        </div>
      </div>

      {/* ── Document Preview Panel ──────────────────────────────── */}
      {selectedDoc && (
        <DocumentPanel
          doc={selectedDoc}
          onClose={() => setSelectedDoc(null)}
          onApprove={handleApprove}
          onExport={handleExport}
          onSave={handleSave}
        />
      )}
    </div>
  );
}
