import { useMemo, useState, useCallback } from 'react';
import {
  ClipboardList,
  Upload,
  AlertTriangle,
  CheckCircle,
  Pill,
  FileText,
  Search,
  X,
  ChevronRight,
  ChevronDown,
  Clock,
  Shield,
  Flag,
  Send,
  Image,
  Sparkles,
  Loader2,
  Zap,
  Brain,
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

import { PRESCRIPTIONS, RESIDENTS } from '../data/mockData';
import { useAuth } from '../contexts/AuthContext';
import { checkPolypharmacy, type PolypharmacyResponse } from '../services/api';
import type { Prescription, DrugInteraction, Resident } from '../types';

// ─── Constants ────────────────────────────────────────────────────────────────

type RxStatus = Prescription['status'];
type InteractionSeverity = DrugInteraction['severity'];

const STATUS_CONFIG: Record<RxStatus, { label: string; bg: string; text: string; ring: string }> = {
  pending_review: { label: 'Pending Review', bg: 'bg-yellow-100', text: 'text-yellow-700', ring: 'ring-yellow-600/10' },
  approved:       { label: 'Approved',       bg: 'bg-emerald-100', text: 'text-emerald-700', ring: 'ring-emerald-600/10' },
  flagged:        { label: 'Flagged',        bg: 'bg-red-100',    text: 'text-red-700',    ring: 'ring-red-600/10' },
};

const SEVERITY_CONFIG: Record<InteractionSeverity, { label: string; bg: string; text: string; ring: string; dot: string }> = {
  minor:           { label: 'Minor',           bg: 'bg-gray-100',   text: 'text-gray-700',   ring: 'ring-gray-600/10',   dot: 'bg-gray-400' },
  moderate:        { label: 'Moderate',        bg: 'bg-yellow-100', text: 'text-yellow-700', ring: 'ring-yellow-600/10', dot: 'bg-yellow-400' },
  severe:          { label: 'Severe',          bg: 'bg-orange-100', text: 'text-orange-700', ring: 'ring-orange-600/10', dot: 'bg-orange-500' },
  contraindicated: { label: 'Contraindicated', bg: 'bg-red-100',    text: 'text-red-700',    ring: 'ring-red-600/10',    dot: 'bg-red-500' },
};

const FILTER_TABS: { key: RxStatus | 'all'; label: string }[] = [
  { key: 'all',            label: 'All' },
  { key: 'pending_review', label: 'Pending' },
  { key: 'approved',       label: 'Approved' },
  { key: 'flagged',        label: 'Flagged' },
];

const ADHERENCE_COLORS = ['#10b981', '#f59e0b', '#ef4444'];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function residentById(id: string): Resident | undefined {
  return RESIDENTS.find((r) => r.resident_id === id);
}

function timeAgo(ts: number): string {
  return formatDistanceToNow(new Date(ts), { addSuffix: true });
}

function confidenceColor(c: number): string {
  if (c >= 0.95) return 'text-emerald-600';
  if (c >= 0.90) return 'text-blue-600';
  return 'text-amber-600';
}

function confidenceBarColor(c: number): string {
  if (c >= 0.95) return 'bg-emerald-500';
  if (c >= 0.90) return 'bg-blue-500';
  return 'bg-amber-500';
}

// ─── Status Badge ─────────────────────────────────────────────────────────────

function RxStatusBadge({ status }: { status: RxStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-bold ring-1 ring-inset ${cfg.bg} ${cfg.text} ${cfg.ring}`}>
      {cfg.label}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: InteractionSeverity }) {
  const cfg = SEVERITY_CONFIG[severity];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-bold ring-1 ring-inset ${cfg.bg} ${cfg.text} ${cfg.ring}`}>
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
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

// ─── Prescription Detail Panel ────────────────────────────────────────────────

function PrescriptionPanel({
  rx,
  onClose,
  onApprove,
  onFlag,
  onRequestReview,
}: {
  rx: Prescription;
  onClose: () => void;
  onApprove: (id: string) => void;
  onFlag: (id: string) => void;
  onRequestReview: (id: string) => void;
}) {
  const resident = residentById(rx.residentId);
  const [aiChecking, setAiChecking] = useState(false);
  const [aiResult, setAiResult] = useState<PolypharmacyResponse | null>(null);

  const runAiCheck = async () => {
    setAiChecking(true);
    try {
      const meds = rx.medications.map((m) => ({
        name: m.name,
        dosage: m.dosage,
        frequency: m.frequency ?? 'daily',
      }));
      const conditions = resident?.conditions ?? [];
      const age = resident?.age ?? 75;
      const result = await checkPolypharmacy({ medications: meds, conditions, age });
      setAiResult(result);
    } catch {
      // silent fail
    } finally {
      setAiChecking(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white shadow-2xl overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-50">
                <ClipboardList size={18} className="text-violet-600" />
              </div>
              <div className="min-w-0">
                <h3 className="text-base font-semibold text-gray-900 truncate">
                  Prescription — {resident?.name ?? 'Unknown'}
                </h3>
                <p className="text-xs text-gray-400">
                  {rx.doctorName} · {format(new Date(rx.date), 'MMM d, yyyy')}
                </p>
              </div>
            </div>
            <button onClick={onClose} className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors">
              <X size={20} />
            </button>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <RxStatusBadge status={rx.status} />
            <span className={`text-xs font-semibold ${confidenceColor(rx.ocrConfidence)}`}>
              OCR Confidence: {(rx.ocrConfidence * 100).toFixed(0)}%
            </span>
            <span className="text-xs text-gray-400">{rx.medications.length} medication{rx.medications.length !== 1 ? 's' : ''}</span>
          </div>
        </div>

        {/* Medications */}
        <div className="px-6 py-5">
          <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Pill size={15} className="text-blue-500" /> Medications Extracted
          </h4>
          <div className="space-y-3">
            {rx.medications.map((med, i) => (
              <div key={i} className="rounded-xl bg-gray-50 p-4 ring-1 ring-gray-100">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-800">{med.name}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{med.dosage} · {med.frequency}</p>
                    <p className="text-xs text-gray-400 mt-0.5">Duration: {med.duration}</p>
                    {med.notes && (
                      <p className="text-xs text-blue-500 mt-1 italic">Note: {med.notes}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="h-1.5 w-10 rounded-full bg-gray-200 overflow-hidden">
                      <div className={`h-full rounded-full ${confidenceBarColor(rx.ocrConfidence - i * 0.02)}`} style={{ width: `${(rx.ocrConfidence - i * 0.02) * 100}%` }} />
                    </div>
                    <span className={`text-[10px] font-semibold ${confidenceColor(rx.ocrConfidence - i * 0.02)}`}>
                      {((rx.ocrConfidence - i * 0.02) * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Drug Interactions */}
        {rx.interactions.length > 0 && (
          <div className="px-6 pb-5">
            <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <AlertTriangle size={15} className="text-orange-500" /> Drug Interactions
            </h4>
            <div className="space-y-3">
              {rx.interactions.map((ix, i) => {
                const cfg = SEVERITY_CONFIG[ix.severity];
                return (
                  <div key={i} className={`rounded-xl p-4 ring-1 ring-inset ${cfg.ring} ${cfg.bg}`}>
                    <div className="flex items-start justify-between mb-2">
                      <p className={`text-sm font-semibold ${cfg.text}`}>
                        {ix.drugA} ↔ {ix.drugB}
                      </p>
                      <SeverityBadge severity={ix.severity} />
                    </div>
                    <p className="text-xs text-gray-700 leading-relaxed mb-2">{ix.description}</p>
                    <div className="flex items-start gap-2 rounded-lg bg-white/70 p-3">
                      <Shield size={14} className="text-blue-500 shrink-0 mt-0.5" />
                      <p className="text-xs text-gray-700 leading-relaxed">
                        <span className="font-semibold text-blue-700">Recommendation:</span> {ix.recommendation}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* AI Polypharmacy Check */}
        <div className="px-6 pb-5">
          <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Brain size={15} className="text-violet-500" /> AI Polypharmacy Analysis
          </h4>
          {!aiResult && !aiChecking && (
            <button
              onClick={runAiCheck}
              className="w-full rounded-xl border-2 border-dashed border-violet-300 bg-violet-50/50 p-6 flex flex-col items-center cursor-pointer hover:bg-violet-50 transition-colors group"
            >
              <Sparkles size={24} className="text-violet-400 mb-2 group-hover:text-violet-600 transition-colors" />
              <p className="text-sm font-semibold text-violet-600">Run AI Drug Interaction Check</p>
              <p className="text-xs text-violet-400 mt-1">Powered by Amazon Bedrock · Beers Criteria + Interaction Analysis</p>
            </button>
          )}
          {aiChecking && (
            <div className="rounded-xl bg-violet-50 p-6 flex flex-col items-center">
              <Loader2 size={24} className="text-violet-600 animate-spin mb-2" />
              <p className="text-sm font-semibold text-violet-700">Analyzing with Amazon Bedrock...</p>
              <p className="text-xs text-violet-400 mt-1">Checking {rx.medications.length} medications for interactions</p>
            </div>
          )}
          {aiResult && (
            <div className="space-y-3">
              <div className="flex items-center gap-3 rounded-xl bg-violet-50 p-3 ring-1 ring-violet-100">
                <Zap size={16} className="text-violet-600" />
                <div className="flex-1">
                  <p className="text-xs font-semibold text-violet-700">Risk Score: {aiResult.risk_score}/10</p>
                  <p className="text-[10px] text-violet-400">{aiResult.ai_model || 'Amazon Bedrock'}</p>
                </div>
                <div className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold text-white ${
                  aiResult.risk_score >= 7 ? 'bg-red-500' : aiResult.risk_score >= 4 ? 'bg-amber-500' : 'bg-emerald-500'
                }`}>
                  {aiResult.risk_score}
                </div>
              </div>

              {aiResult.summary && (
                <div className="rounded-lg bg-blue-50 p-3 ring-1 ring-blue-100">
                  <p className="text-xs text-blue-800 leading-relaxed">{aiResult.summary}</p>
                </div>
              )}

              {aiResult.interactions.length > 0 && (
                <div className="space-y-2">
                  {aiResult.interactions.map((ix, i) => {
                    const sevColor = ix.severity === 'contraindicated' ? 'bg-red-50 text-red-700 ring-red-200'
                      : ix.severity === 'major' ? 'bg-orange-50 text-orange-700 ring-orange-200'
                      : ix.severity === 'moderate' ? 'bg-yellow-50 text-yellow-700 ring-yellow-200'
                      : 'bg-gray-50 text-gray-700 ring-gray-200';
                    return (
                      <div key={i} className={`rounded-lg p-3 ring-1 ring-inset ${sevColor}`}>
                        <p className="text-xs font-semibold">{ix.drug1} ↔ {ix.drug2}
                          <span className="ml-2 text-[10px] font-bold uppercase opacity-60">{ix.severity}</span>
                        </p>
                        <p className="text-xs opacity-80 mt-0.5">{ix.description}</p>
                      </div>
                    );
                  })}
                </div>
              )}

              {aiResult.beers_criteria_flags.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">Beers Criteria</p>
                  {aiResult.beers_criteria_flags.map((f, i) => (
                    <p key={i} className="text-xs text-orange-700 flex items-start gap-1 mb-1">
                      <AlertTriangle size={10} className="shrink-0 mt-0.5" /> {f}
                    </p>
                  ))}
                </div>
              )}

              {aiResult.recommendations.length > 0 && (
                <div>
                  <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-1">Recommendations</p>
                  {aiResult.recommendations.map((r, i) => (
                    <p key={i} className="text-xs text-gray-700 flex items-start gap-1 mb-1">
                      <Shield size={10} className="text-blue-500 shrink-0 mt-0.5" /> {r}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Source Document Placeholder */}
        <div className="px-6 pb-5">
          <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Image size={15} className="text-gray-500" /> Source Document
          </h4>
          <div className="rounded-xl border-2 border-dashed border-gray-200 bg-gray-50 p-8 flex flex-col items-center text-center">
            <FileText size={32} className="text-gray-300 mb-2" />
            <p className="text-sm text-gray-500">
              {rx.sourceDocUrl ? rx.sourceDocUrl : 'Original prescription document preview'}
            </p>
            <p className="text-xs text-gray-400 mt-1">Image/PDF preview would appear here</p>
          </div>
        </div>

        {/* Actions */}
        <div className="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4">
          <div className="flex flex-wrap gap-3">
            {rx.status !== 'approved' && (
              <button
                onClick={() => onApprove(rx.id)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-700"
              >
                <CheckCircle size={14} /> Approve
              </button>
            )}
            {rx.status !== 'flagged' && (
              <button
                onClick={() => onFlag(rx.id)}
                className="inline-flex items-center gap-1.5 rounded-xl bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-red-700"
              >
                <Flag size={14} /> Flag for Review
              </button>
            )}
            <button
              onClick={() => onRequestReview(rx.id)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-700 transition-all hover:bg-gray-200"
            >
              <Send size={14} /> Request Doctor Review
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Upload + AI Polypharmacy ─────────────────────────────────────────────────

function UploadPanel({ onClose }: { onClose: () => void }) {
  const [stage, setStage] = useState<'idle' | 'uploading' | 'processing' | 'done' | 'error'>('idle');
  const [aiResult, setAiResult] = useState<PolypharmacyResponse | null>(null);

  const handleUpload = async () => {
    setStage('uploading');
    // Simulate OCR scanning delay
    await new Promise((r) => setTimeout(r, 1200));
    setStage('processing');

    // Pick a resident's real medications for AI analysis
    const resident = RESIDENTS.find((r) => r.medications && r.medications.length > 2) ?? RESIDENTS[0];
    const meds = resident.medications.map((m) => ({
      name: m.name,
      dosage: m.dosage,
      frequency: m.schedule?.[0] ?? 'daily',
    }));
    const conditions = resident.conditions ?? [];
    const age = resident.age ?? 75;

    try {
      const result = await checkPolypharmacy({ medications: meds, conditions, age });
      setAiResult(result);
      setStage('done');
    } catch {
      setStage('error');
    }
  };

  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60 animate-slide-down">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2">
          <Upload size={16} className="text-blue-500" /> Upload New Prescription
        </h3>
        <button onClick={onClose} className="rounded-lg p-1 text-gray-400 hover:text-gray-600">
          <X size={16} />
        </button>
      </div>

      {stage === 'idle' && (
        <div
          onClick={handleUpload}
          className="rounded-xl border-2 border-dashed border-blue-300 bg-blue-50/50 p-10 flex flex-col items-center cursor-pointer hover:bg-blue-50 transition-colors"
        >
          <Upload size={36} className="text-blue-400 mb-3" />
          <p className="text-sm font-semibold text-blue-600">Drag & drop or click to upload</p>
          <p className="text-xs text-blue-400 mt-1">Accepts PDF, JPG, PNG · AI polypharmacy check included</p>
        </div>
      )}

      {stage === 'uploading' && (
        <div className="rounded-xl bg-blue-50 p-8 flex flex-col items-center">
          <Loader2 size={32} className="text-blue-600 mb-3 animate-spin" />
          <p className="text-sm font-semibold text-blue-700">Scanning prescription with OCR...</p>
          <p className="text-xs text-blue-400 mt-1">Extracting text via AWS Textract</p>
        </div>
      )}

      {stage === 'processing' && (
        <div className="rounded-xl bg-amber-50 p-8 flex flex-col items-center">
          <div className="flex items-center gap-2 mb-3">
            <Brain size={20} className="text-amber-600 animate-pulse" />
            <span className="text-sm font-semibold text-amber-700">Running AI Polypharmacy Analysis...</span>
          </div>
          <p className="text-xs text-amber-500 mb-3">Amazon Bedrock analyzing drug interactions & Beers Criteria</p>
          <div className="w-full max-w-xs bg-amber-200 rounded-full h-2 overflow-hidden">
            <div className="bg-amber-500 h-full rounded-full animate-pulse" style={{ width: '85%' }} />
          </div>
        </div>
      )}

      {stage === 'done' && aiResult && (
        <div className="space-y-4">
          <div className="rounded-xl bg-emerald-50 p-4 flex items-center gap-3">
            <CheckCircle size={20} className="text-emerald-500 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-emerald-700">AI Analysis Complete</p>
              <p className="text-xs text-emerald-500">
                Powered by {aiResult.ai_model || 'Amazon Bedrock'} · Risk Score: {aiResult.risk_score}/10
              </p>
            </div>
          </div>

          {/* AI Summary */}
          {aiResult.summary && (
            <div className="rounded-xl bg-blue-50 p-4 ring-1 ring-blue-100">
              <p className="text-xs font-semibold text-blue-700 mb-1 flex items-center gap-1">
                <Sparkles size={12} /> AI Summary
              </p>
              <p className="text-sm text-blue-800 leading-relaxed">{aiResult.summary}</p>
            </div>
          )}

          {/* Interactions found */}
          {aiResult.interactions && aiResult.interactions.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Drug Interactions Detected</p>
              <div className="space-y-2">
                {aiResult.interactions.map((ix, i) => {
                  const sevColor = ix.severity === 'contraindicated' ? 'bg-red-100 text-red-700 ring-red-200'
                    : ix.severity === 'major' ? 'bg-orange-100 text-orange-700 ring-orange-200'
                    : ix.severity === 'moderate' ? 'bg-yellow-100 text-yellow-700 ring-yellow-200'
                    : 'bg-gray-100 text-gray-700 ring-gray-200';
                  return (
                    <div key={i} className={`rounded-lg p-3 ring-1 ring-inset ${sevColor}`}>
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-xs font-semibold">{ix.drug1} ↔ {ix.drug2}</p>
                        <span className="text-[10px] font-bold uppercase">{ix.severity}</span>
                      </div>
                      <p className="text-xs opacity-80">{ix.description}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Beers Criteria */}
          {aiResult.beers_criteria_flags && aiResult.beers_criteria_flags.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Beers Criteria Flags (Elderly)</p>
              <div className="space-y-1">
                {aiResult.beers_criteria_flags.map((flag, i) => (
                  <div key={i} className="flex items-start gap-2 rounded-lg bg-orange-50 p-2 ring-1 ring-orange-100">
                    <AlertTriangle size={12} className="text-orange-500 shrink-0 mt-0.5" />
                    <p className="text-xs text-orange-700">{flag}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommendations */}
          {aiResult.recommendations && aiResult.recommendations.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">AI Recommendations</p>
              <div className="rounded-xl bg-white p-4 ring-1 ring-gray-100 space-y-2">
                {aiResult.recommendations.map((rec, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <Shield size={12} className="text-blue-500 shrink-0 mt-0.5" />
                    <p className="text-xs text-gray-700">{rec}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {stage === 'error' && (
        <div className="rounded-xl bg-red-50 p-8 flex flex-col items-center">
          <AlertTriangle size={28} className="text-red-400 mb-2" />
          <p className="text-sm font-semibold text-red-700">AI analysis unavailable</p>
          <p className="text-xs text-red-500 mt-1">Check API server connection and try again</p>
          <button
            onClick={() => setStage('idle')}
            className="mt-3 text-xs font-semibold text-red-600 underline hover:text-red-800"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Prescriptions Page
// ═══════════════════════════════════════════════════════════════════════════════

export default function PrescriptionsPage() {
  const { role } = useAuth();

  // State
  const [prescriptions, setPrescriptions] = useState<Prescription[]>(() => PRESCRIPTIONS);
  const [activeFilter, setActiveFilter] = useState<RxStatus | 'all'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRx, setSelectedRx] = useState<Prescription | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // Computed
  const filtered = useMemo(() => {
    let result = activeFilter === 'all'
      ? prescriptions
      : prescriptions.filter((p) => p.status === activeFilter);

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (p) =>
          residentById(p.residentId)?.name.toLowerCase().includes(q) ||
          p.doctorName.toLowerCase().includes(q) ||
          p.medications.some((m) => m.name.toLowerCase().includes(q)),
      );
    }

    return result.sort((a, b) => b.date - a.date);
  }, [prescriptions, activeFilter, searchQuery]);

  // KPIs
  const kpis = useMemo(() => {
    const total = prescriptions.length;
    const pending = prescriptions.filter((p) => p.status === 'pending_review').length;
    const interactions = prescriptions.reduce((sum, p) => sum + p.interactions.length, 0);
    const avgConf =
      prescriptions.length > 0
        ? prescriptions.reduce((sum, p) => sum + p.ocrConfidence, 0) / prescriptions.length
        : 0;
    return { total, pending, interactions, avgConf };
  }, [prescriptions]);

  // Medication schedule mock data
  const scheduleData = useMemo(() => {
    const hours = ['06:00', '08:00', '10:00', '12:00', '14:00', '16:00', '18:00', '20:00', '22:00'];
    return hours.map((h) => ({
      time: h,
      onTime: Math.floor(Math.random() * 5) + 1,
      late: Math.floor(Math.random() * 2),
      missed: Math.floor(Math.random() * 2),
    }));
  }, []);

  // Handlers
  const showToast = useCallback((msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  }, []);

  const handleApprove = useCallback(
    (id: string) => {
      setPrescriptions((prev) =>
        prev.map((p) => (p.id === id ? { ...p, status: 'approved' as const } : p)),
      );
      setSelectedRx((prev) =>
        prev && prev.id === id ? { ...prev, status: 'approved' as const } : prev,
      );
      showToast('Prescription approved.');
    },
    [showToast],
  );

  const handleFlag = useCallback(
    (id: string) => {
      setPrescriptions((prev) =>
        prev.map((p) => (p.id === id ? { ...p, status: 'flagged' as const } : p)),
      );
      setSelectedRx((prev) =>
        prev && prev.id === id ? { ...prev, status: 'flagged' as const } : prev,
      );
      showToast('Prescription flagged for review.');
    },
    [showToast],
  );

  const handleRequestReview = useCallback(
    (id: string) => {
      void id;
      showToast('Review request sent to prescribing doctor.');
    },
    [showToast],
  );

  return (
    <div className="min-h-screen bg-gray-50/60">
      <div className="mx-auto max-w-[1440px] px-6 py-8 lg:px-10">
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 shadow-sm">
              <ClipboardList className="text-white" size={20} />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">Prescriptions</h1>
              <p className="text-sm text-gray-500">
                OCR-powered prescription management · {format(new Date(), 'EEEE, MMM d, yyyy')}
              </p>
            </div>
          </div>
          {role !== 'elder' && (
            <button
              onClick={() => setShowUpload(!showUpload)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 active:scale-[0.98]"
            >
              <Upload size={16} /> Upload Prescription
            </button>
          )}
        </div>

        {/* ── Toast ────────────────────────────────────────────────── */}
        {toastMsg && (
          <div className="mb-6 flex items-center gap-2 rounded-xl bg-emerald-50 px-4 py-3 text-sm text-emerald-700 animate-fade-in ring-1 ring-emerald-200">
            <CheckCircle size={16} />
            {toastMsg}
            <button onClick={() => setToastMsg(null)} className="ml-auto text-emerald-500 hover:text-emerald-700">
              <X size={14} />
            </button>
          </div>
        )}

        {/* ── Upload Panel ────────────────────────────────────────── */}
        {showUpload && (
          <div className="mb-6">
            <UploadPanel onClose={() => setShowUpload(false)} />
          </div>
        )}

        {/* ── KPI Row ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Total Prescriptions"
            value={kpis.total}
            icon={ClipboardList}
            iconBg="bg-blue-50"
            iconColor="text-blue-600"
            subtitle="All records"
          />
          <KpiCard
            label="Pending Review"
            value={kpis.pending}
            icon={Clock}
            iconBg={kpis.pending > 0 ? 'bg-yellow-50' : 'bg-emerald-50'}
            iconColor={kpis.pending > 0 ? 'text-yellow-600' : 'text-emerald-600'}
            subtitle={kpis.pending > 0 ? 'Awaiting approval' : 'All reviewed'}
          />
          <KpiCard
            label="Drug Interactions"
            value={kpis.interactions}
            icon={AlertTriangle}
            iconBg={kpis.interactions > 0 ? 'bg-orange-50' : 'bg-emerald-50'}
            iconColor={kpis.interactions > 0 ? 'text-orange-600' : 'text-emerald-600'}
            subtitle="Detected across all Rx"
          />
          <KpiCard
            label="Avg OCR Confidence"
            value={`${(kpis.avgConf * 100).toFixed(0)}%`}
            icon={Search}
            iconBg="bg-violet-50"
            iconColor="text-violet-600"
            subtitle="Text extraction accuracy"
          />
        </div>

        {/* ── Filter & Search ─────────────────────────────────────── */}
        <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-1.5">
            {FILTER_TABS.map((tab) => {
              const isActive = activeFilter === tab.key;
              const count =
                tab.key === 'all'
                  ? prescriptions.length
                  : prescriptions.filter((p) => p.status === tab.key).length;
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
                  <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${isActive ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-500'}`}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search by patient, doctor, or medication..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="rounded-xl border border-gray-200 bg-white py-2 pl-9 pr-4 text-sm text-gray-700 w-full sm:w-72 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
          </div>
        </div>

        {/* ── Prescription Cards ──────────────────────────────────── */}
        <div className="mt-5 space-y-4">
          {filtered.length === 0 ? (
            <div className="rounded-2xl bg-white p-16 shadow-sm ring-1 ring-gray-200/60 flex flex-col items-center text-center">
              <ClipboardList size={40} className="text-gray-300 mb-3" />
              <p className="text-sm font-medium text-gray-600">No prescriptions found</p>
              <p className="text-xs text-gray-400 mt-1">Try changing the filter or search query.</p>
            </div>
          ) : (
            filtered.map((rx) => {
              const resident = residentById(rx.residentId);
              const isExpanded = expandedId === rx.id;
              return (
                <div
                  key={rx.id}
                  className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 overflow-hidden transition-all hover:shadow-md"
                >
                  {/* Card Header */}
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : rx.id)}
                    className="w-full text-left px-6 py-4 flex items-center gap-4 group cursor-pointer"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-50 group-hover:bg-violet-100 transition-colors">
                      <FileText size={18} className="text-violet-600" />
                    </div>

                    <div className="flex-1 min-w-0 grid grid-cols-1 sm:grid-cols-5 gap-2 sm:gap-4 items-center">
                      <div className="sm:col-span-1">
                        <p className="text-sm font-semibold text-gray-800 truncate">{resident?.name ?? 'Unknown'}</p>
                        <p className="text-xs text-gray-400">{rx.doctorName}</p>
                      </div>
                      <div className="sm:col-span-1">
                        <span className="text-xs text-gray-500">{format(new Date(rx.date), 'MMM d, yyyy')}</span>
                      </div>
                      <div className="sm:col-span-1">
                        <RxStatusBadge status={rx.status} />
                      </div>
                      <div className="sm:col-span-1 flex items-center gap-2">
                        <div className="h-1.5 w-16 rounded-full bg-gray-100 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${confidenceBarColor(rx.ocrConfidence)} transition-all`}
                            style={{ width: `${rx.ocrConfidence * 100}%` }}
                          />
                        </div>
                        <span className={`text-xs font-semibold ${confidenceColor(rx.ocrConfidence)}`}>
                          {(rx.ocrConfidence * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="sm:col-span-1 flex items-center justify-between">
                        <span className="text-xs text-gray-500 flex items-center gap-1">
                          <Pill size={12} /> {rx.medications.length} med{rx.medications.length !== 1 ? 's' : ''}
                          {rx.interactions.length > 0 && (
                            <span className="ml-2 text-orange-500 flex items-center gap-0.5">
                              <AlertTriangle size={12} /> {rx.interactions.length}
                            </span>
                          )}
                        </span>
                        {isExpanded ? (
                          <ChevronDown size={16} className="text-gray-400" />
                        ) : (
                          <ChevronRight size={16} className="text-gray-400" />
                        )}
                      </div>
                    </div>
                  </button>

                  {/* Expanded Content */}
                  {isExpanded && (
                    <div className="border-t border-gray-100 px-6 py-4 bg-gray-50/50 animate-fade-in">
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {/* Medications */}
                        <div>
                          <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Medications</h5>
                          <div className="space-y-2">
                            {rx.medications.map((med, i) => (
                              <div key={i} className="rounded-lg bg-white p-3 ring-1 ring-gray-100">
                                <p className="text-sm font-semibold text-gray-800">{med.name}</p>
                                <p className="text-xs text-gray-500">{med.dosage} · {med.frequency} · {med.duration}</p>
                                {med.notes && <p className="text-xs text-blue-500 mt-1 italic">{med.notes}</p>}
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Interactions */}
                        <div>
                          <h5 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Interactions</h5>
                          {rx.interactions.length === 0 ? (
                            <div className="rounded-lg bg-white p-4 ring-1 ring-gray-100 flex items-center gap-2 text-emerald-600">
                              <CheckCircle size={14} />
                              <span className="text-sm">No drug interactions detected</span>
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {rx.interactions.map((ix, i) => (
                                <div key={i} className={`rounded-lg p-3 ring-1 ring-inset ${SEVERITY_CONFIG[ix.severity].ring} ${SEVERITY_CONFIG[ix.severity].bg}`}>
                                  <div className="flex items-center justify-between mb-1">
                                    <p className={`text-xs font-semibold ${SEVERITY_CONFIG[ix.severity].text}`}>{ix.drugA} ↔ {ix.drugB}</p>
                                    <SeverityBadge severity={ix.severity} />
                                  </div>
                                  <p className="text-xs text-gray-600">{ix.description}</p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="mt-4 flex gap-2">
                        <button
                          onClick={() => setSelectedRx(rx)}
                          className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700"
                        >
                          View Full Details
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* ── Medication Schedule ─────────────────────────────────── */}
        <div className="mt-10">
          <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Clock size={18} className="text-blue-500" /> Medication Schedule Overview
          </h2>
          <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
            <p className="text-xs text-gray-400 mb-4">Daily medication adherence timeline across all residents</p>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={scheduleData} barCategoryGap="20%">
                <XAxis dataKey="time" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ borderRadius: 12, fontSize: 12, border: '1px solid #e5e7eb' }}
                />
                <Bar dataKey="onTime" name="On Time" stackId="a" radius={[0, 0, 0, 0]}>
                  {scheduleData.map((_, i) => (
                    <Cell key={i} fill={ADHERENCE_COLORS[0]} />
                  ))}
                </Bar>
                <Bar dataKey="late" name="Late" stackId="a" radius={[0, 0, 0, 0]}>
                  {scheduleData.map((_, i) => (
                    <Cell key={i} fill={ADHERENCE_COLORS[1]} />
                  ))}
                </Bar>
                <Bar dataKey="missed" name="Missed" stackId="a" radius={[4, 4, 0, 0]}>
                  {scheduleData.map((_, i) => (
                    <Cell key={i} fill={ADHERENCE_COLORS[2]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="flex items-center gap-4 mt-3 justify-center">
              <span className="flex items-center gap-1.5 text-xs text-gray-500">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> On Time
              </span>
              <span className="flex items-center gap-1.5 text-xs text-gray-500">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> Late
              </span>
              <span className="flex items-center gap-1.5 text-xs text-gray-500">
                <span className="h-2.5 w-2.5 rounded-full bg-red-500" /> Missed
              </span>
            </div>
          </div>
        </div>

        {/* ── Footer ─────────────────────────────────────────────── */}
        <div className="mt-12 border-t border-gray-200/60 pt-6 pb-8 text-center">
          <p className="text-xs text-gray-300">
            AETHER Prescriptions · OCR-powered with AI polypharmacy checking (Amazon Bedrock)
          </p>
        </div>
      </div>

      {/* ── Detail Panel ──────────────────────────────────────────── */}
      {selectedRx && (
        <PrescriptionPanel
          rx={selectedRx}
          onClose={() => setSelectedRx(null)}
          onApprove={handleApprove}
          onFlag={handleFlag}
          onRequestReview={handleRequestReview}
        />
      )}
    </div>
  );
}
