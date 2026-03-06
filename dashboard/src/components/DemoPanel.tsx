/**
 * AETHER Demo Panel — Floating simulation control for judges
 * Triggers real events through the API and shows live AI responses.
 */

import { useState, useCallback } from 'react';
import {
  Zap,
  X,
  AlertTriangle,
  Pill,
  Activity,
  Wind,
  Heart,
  Loader2,
  CheckCircle,
  Sparkles,
} from 'lucide-react';
import { useLiveData } from '../contexts/LiveDataContext';
import { voiceSession, type VoiceSessionResponse } from '../services/api';

interface ScenarioResult {
  scenario: string;
  success: boolean;
  message: string;
  timestamp: number;
}

const SCENARIOS = [
  {
    key: 'fall_detection',
    label: 'Fall Detection',
    icon: AlertTriangle,
    color: 'bg-red-500',
    description: 'Simulates IMU + acoustic fall in bathroom',
  },
  {
    key: 'medication_missed',
    label: 'Missed Medication',
    icon: Pill,
    color: 'bg-orange-500',
    description: 'Metformin 500mg overdue by 3.5 hours',
  },
  {
    key: 'choking_detected',
    label: 'Choking Event',
    icon: Wind,
    color: 'bg-red-600',
    description: 'Acoustic choking detection in dining room',
  },
  {
    key: 'wandering',
    label: 'Night Wandering',
    icon: Activity,
    color: 'bg-purple-500',
    description: 'Front door contact sensor at night',
  },
  {
    key: 'vital_anomaly',
    label: 'Vital Anomaly',
    icon: Heart,
    color: 'bg-pink-500',
    description: 'Elevated HR, BP, low SpO2',
  },
] as const;

export default function DemoPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [isTriggering, setIsTriggering] = useState<string | null>(null);
  const [results, setResults] = useState<ScenarioResult[]>([]);
  const [voiceResponse, setVoiceResponse] = useState<VoiceSessionResponse | null>(null);
  const [isVoicing, setIsVoicing] = useState(false);
  const { triggerScenario, apiConnected, residents } = useLiveData();

  const handleTrigger = useCallback(async (key: string) => {
    setIsTriggering(key);
    const residentId = residents.length > 0 ? residents[0].resident_id : 'RES-001';
    const result = await triggerScenario(key, residentId);

    setResults((prev) => [
      {
        scenario: key,
        success: !!result,
        message: result ? `Event ${result.event_id} created (${result.severity})` : 'Failed to trigger scenario',
        timestamp: Date.now(),
      },
      ...prev.slice(0, 4),
    ]);
    setIsTriggering(null);
  }, [triggerScenario, residents]);

  const handleVoiceCheckin = useCallback(async () => {
    setIsVoicing(true);
    try {
      const residentId = residents.length > 0 ? residents[0].resident_id : 'RES-001';
      const response = await voiceSession({
        resident_id: residentId,
        session_type: 'daily_checkin',
        message: 'I am feeling a bit tired today but otherwise okay. I took my morning meditation.',
      });
      setVoiceResponse(response);
    } catch (err) {
      console.error('Voice session error:', err);
    } finally {
      setIsVoicing(false);
    }
  }, [residents]);

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-indigo-600 px-5 py-3 text-sm font-bold text-white shadow-lg shadow-violet-500/30 transition-all hover:shadow-xl hover:scale-105 active:scale-95"
      >
        <Zap size={18} />
        Live Demo
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-96 rounded-2xl bg-white shadow-2xl ring-1 ring-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between bg-gradient-to-r from-violet-600 to-indigo-600 px-5 py-3">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-white" />
          <span className="text-sm font-bold text-white">AETHER Live Demo</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`flex items-center gap-1 text-[10px] font-medium ${apiConnected ? 'text-emerald-200' : 'text-yellow-200'}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${apiConnected ? 'bg-emerald-400' : 'bg-yellow-400'}`} />
            {apiConnected ? 'AWS Connected' : 'Offline'}
          </span>
          <button onClick={() => setIsOpen(false)} className="text-white/70 hover:text-white">
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Scenarios */}
      <div className="p-4 space-y-2 max-h-[500px] overflow-y-auto">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
          Trigger Scenarios
        </p>
        {SCENARIOS.map((s) => {
          const SIcon = s.icon;
          const isBusy = isTriggering === s.key;
          return (
            <button
              key={s.key}
              onClick={() => handleTrigger(s.key)}
              disabled={isBusy || !apiConnected}
              className="w-full flex items-center gap-3 rounded-xl px-4 py-3 text-left transition-all hover:bg-gray-50 active:scale-[0.98] disabled:opacity-50"
            >
              <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${s.color} text-white`}>
                {isBusy ? <Loader2 size={16} className="animate-spin" /> : <SIcon size={16} />}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-800">{s.label}</p>
                <p className="text-[11px] text-gray-400">{s.description}</p>
              </div>
            </button>
          );
        })}

        {/* Voice Companion */}
        <div className="border-t border-gray-100 pt-3 mt-3">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
            AI Voice Check-in
          </p>
          <button
            onClick={handleVoiceCheckin}
            disabled={isVoicing || !apiConnected}
            className="w-full flex items-center gap-3 rounded-xl px-4 py-3 text-left transition-all hover:bg-blue-50 active:scale-[0.98] disabled:opacity-50 bg-blue-50/50 ring-1 ring-blue-100"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-500 text-white">
              {isVoicing ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-blue-800">Daily Check-in (Bedrock)</p>
              <p className="text-[11px] text-blue-500">Triggers real AI conversation</p>
            </div>
          </button>

          {voiceResponse && (
            <div className="mt-3 rounded-xl bg-blue-50 p-4 text-xs space-y-2">
              <div className="flex items-center gap-2 text-blue-700 font-semibold">
                <Sparkles size={12} />
                AI Response ({voiceResponse.ai_model})
              </div>
              <p className="text-blue-800 leading-relaxed">{voiceResponse.response_text}</p>
              <div className="flex items-center gap-3 text-[10px] text-blue-500">
                <span>Sentiment: {voiceResponse.sentiment}</span>
                <span>Mood: {voiceResponse.mood_score}/10</span>
                {voiceResponse.follow_up_needed && (
                  <span className="text-red-500 font-bold">Follow-up needed</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Results Log */}
        {results.length > 0 && (
          <div className="border-t border-gray-100 pt-3 mt-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
              Recent Events
            </p>
            <div className="space-y-2">
              {results.map((r, i) => (
                <div key={i} className="flex items-center gap-2 rounded-lg bg-gray-50 px-3 py-2">
                  {r.success ? (
                    <CheckCircle size={14} className="text-emerald-500 shrink-0" />
                  ) : (
                    <AlertTriangle size={14} className="text-red-500 shrink-0" />
                  )}
                  <span className="text-[11px] text-gray-600 truncate">{r.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
