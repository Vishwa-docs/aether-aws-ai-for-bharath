import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  X,
  ChevronRight,
  ChevronLeft,
  Activity,
  Shield,
  Stethoscope,
  Brain,
  BarChart3,
  Pill,
  AlertTriangle,
  Users,
  Clock,
  Map,
  Sparkles,
  Heart,
  FileText,
  MessageCircle,
  Car,
  Zap,
  BookOpen,
  Building2,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import type { UserRole } from '../types';

// ─── Tour step definitions per role ──────────────────────────────────────────

interface TourStep {
  title: string;
  description: string;
  path: string;
  icon: React.ElementType;
  iconBg: string;
  highlight?: string; // What to look for on the page
}

const SHARED_INTRO: TourStep = {
  title: 'Welcome to AETHER',
  description:
    'AETHER is an AI-powered elderly care operating system. It monitors residents through ambient sensors, uses Amazon Bedrock for clinical reasoning, and coordinates care across families, nurses, and doctors. This guided tour will walk you through the key features.',
  path: '/',
  icon: Activity,
  iconBg: 'bg-aether-500',
};

const ROLE_TOURS: Record<UserRole, TourStep[]> = {
  elder: [
    SHARED_INTRO,
    {
      title: 'Your Health Dashboard',
      description:
        'The home page shows your daily status at a glance — medication adherence, activity level, sleep quality, and recent events. The Command Center strip at the top shows real-time alerts and system status.',
      path: '/',
      icon: Heart,
      iconBg: 'bg-rose-500',
      highlight: 'Look at the status cards and weekly trend charts.',
    },
    {
      title: 'Medications & Prescriptions',
      description:
        'View your complete medication schedule with visual pill identification, adherence tracking, and AI-powered drug interaction checking. The polypharmacy checker uses Amazon Bedrock to flag dangerous combinations and suggest generic alternatives.',
      path: '/prescriptions',
      icon: Pill,
      iconBg: 'bg-violet-500',
      highlight: 'Click "Check Interactions" to see the AI analyze drug safety.',
    },
    {
      title: 'Activity Timeline',
      description:
        'A chronological view of all events — medication taken, check-ins, movement patterns, alerts. Filter by type and date. Each entry shows sensor evidence and severity classification.',
      path: '/timeline',
      icon: Clock,
      iconBg: 'bg-blue-500',
    },
    {
      title: 'Live Monitoring',
      description:
        'See real-time sensor data flowing from edge devices — motion, acoustics, vitals, environmental readings. Events appear live as they happen, showing the multi-sensor fusion in action.',
      path: '/monitoring',
      icon: Activity,
      iconBg: 'bg-emerald-500',
      highlight: 'Watch the live event feed on the right panel.',
    },
    {
      title: 'Health Education',
      description:
        'Micro-lessons on medication safety, diabetes management, fall prevention, and more. Each lesson is personalized to the resident\'s conditions.',
      path: '/education',
      icon: BookOpen,
      iconBg: 'bg-cyan-500',
    },
  ],
  caregiver: [
    SHARED_INTRO,
    {
      title: 'Operations Dashboard',
      description:
        'The home page gives you a fleet-level view of all residents with color-coded status indicators (green/yellow/red), active alerts, medication adherence rates, and the escalation funnel showing how events are triaged.',
      path: '/',
      icon: Shield,
      iconBg: 'bg-emerald-500',
      highlight: 'Check the Risk Trends chart and Escalation Funnel.',
    },
    {
      title: 'Resident Management',
      description:
        'Click any resident card to expand detailed health profiles, recent events, sensor data, and AI-generated health insights. The "AI Health Insights" button uses Amazon Bedrock to analyze patterns.',
      path: '/residents',
      icon: Users,
      iconBg: 'bg-blue-500',
      highlight: 'Expand a resident card and click "AI Health Insights" to see Bedrock in action.',
    },
    {
      title: 'Alert Triage',
      description:
        'View and manage alerts with 4-tier escalation (In-Home → Caregiver → Emergency Contact → Emergency Services). Acknowledge alerts, mark false positives, and see how the AI suppresses noise to reduce alert fatigue.',
      path: '/alerts',
      icon: AlertTriangle,
      iconBg: 'bg-amber-500',
      highlight: 'Click "Acknowledge" on an alert to see the workflow.',
    },
    {
      title: 'Live Monitoring',
      description:
        'Real-time event feed from edge sensors. See fall detection, acoustic events, medication events, and environmental readings as they flow through the system.',
      path: '/monitoring',
      icon: Activity,
      iconBg: 'bg-emerald-500',
    },
    {
      title: 'Care Navigation AI',
      description:
        'Ask health questions in natural language. Amazon Bedrock responds with patient-aware, culturally appropriate guidance. Try asking about medication side effects, diet recommendations, or symptom assessment.',
      path: '/care-navigation',
      icon: MessageCircle,
      iconBg: 'bg-purple-500',
      highlight: 'Type a question like "What should Kamala eat for diabetes management?" and hit Send.',
    },
    {
      title: 'Analytics & Trends',
      description:
        'Deep analytics on event distribution, response times, sensor performance, and AI model confidence. Track false positive rates over time and identify patterns.',
      path: '/analytics',
      icon: BarChart3,
      iconBg: 'bg-indigo-500',
    },
  ],
  doctor: [
    SHARED_INTRO,
    {
      title: 'Clinical Dashboard',
      description:
        'Overview of patient population with risk scores, medication adherence, and health trends. The dashboard pulls live data from DynamoDB and presents it with clinical context.',
      path: '/',
      icon: Stethoscope,
      iconBg: 'bg-blue-500',
      highlight: 'Review the Patient Risk Overview section.',
    },
    {
      title: 'Resident Clinical Profiles',
      description:
        'Detailed patient profiles with conditions, medications, sensor data, and Bedrock-generated health insights. Click "AI Health Insights" to get a clinical summary powered by Amazon Bedrock Nova Lite.',
      path: '/residents',
      icon: Users,
      iconBg: 'bg-emerald-500',
      highlight: 'Expand Kamala Devi\'s card and click the sparkle icon for AI analysis.',
    },
    {
      title: 'Clinical Document Generation',
      description:
        'Generate SOAP notes, discharge summaries, care plans, and incident reports using Amazon Bedrock. Select a resident, choose a document type, and the AI creates a comprehensive clinical document in seconds.',
      path: '/clinical-docs',
      icon: FileText,
      iconBg: 'bg-violet-500',
      highlight: 'Select a resident, choose "SOAP Note", and click Generate.',
    },
    {
      title: 'Prescription & Polypharmacy AI',
      description:
        'Review medication lists with AI-powered drug interaction analysis. The Polypharmacy Checker uses Bedrock to detect dangerous combinations, food-drug interactions, and generic alternatives.',
      path: '/prescriptions',
      icon: Pill,
      iconBg: 'bg-rose-500',
      highlight: 'Click "Check Interactions" to see Bedrock analyze drug safety.',
    },
    {
      title: 'Care Navigation AI',
      description:
        'Natural language health Q&A powered by Amazon Bedrock. The AI has access to patient context and provides clinically-grounded responses with appropriate disclaimers.',
      path: '/care-navigation',
      icon: Brain,
      iconBg: 'bg-purple-500',
      highlight: 'Ask a clinical question to see the RAG-grounded AI in action.',
    },
    {
      title: 'Event Timeline & Alerts',
      description:
        'Patient event history with drift detection, severity classification, and escalation tracking. View the complete audit trail of every detected event.',
      path: '/timeline',
      icon: Clock,
      iconBg: 'bg-amber-500',
    },
  ],
  ops: [
    SHARED_INTRO,
    {
      title: 'Fleet Operations Dashboard',
      description:
        'Bird\'s-eye view of all monitored homes with aggregate metrics — active alerts, medication adherence, response times, and caregiver workload distribution.',
      path: '/',
      icon: Building2,
      iconBg: 'bg-amber-500',
      highlight: 'Check the fleet-wide status cards and risk trends.',
    },
    {
      title: 'Fleet & Site Management',
      description:
        'Manage edge gateways, monitor site health, track caregiver workload distribution, and view sensor status across all sites. Identify connectivity issues and hardware alerts.',
      path: '/fleet-ops',
      icon: Map,
      iconBg: 'bg-blue-500',
      highlight: 'Expand a gateway card to see sensor details and health metrics.',
    },
    {
      title: 'Analytics & Compliance',
      description:
        'Operational analytics with event distribution, response time trends, sensor performance, and AI model confidence tracking. Generate compliance reports for audits.',
      path: '/analytics',
      icon: BarChart3,
      iconBg: 'bg-indigo-500',
      highlight: 'Toggle between time periods to see trend analysis.',
    },
    {
      title: 'Resident Overview',
      description:
        'View all residents with color-coded risk indicators. Drill into individual profiles for detailed health data, AI insights, and care history.',
      path: '/residents',
      icon: Users,
      iconBg: 'bg-emerald-500',
    },
    {
      title: 'Alert Management',
      description:
        'Central alert console with triage tiers, severity filtering, and bulk acknowledgment. Track response times and false positive rates across the operation.',
      path: '/alerts',
      icon: AlertTriangle,
      iconBg: 'bg-red-500',
    },
    {
      title: 'Family Portal',
      description:
        'View the family-facing portal that remote caregivers use to monitor their loved ones — status updates, medication adherence, and event notifications.',
      path: '/family',
      icon: Heart,
      iconBg: 'bg-rose-500',
    },
  ],
};

// ─── Tour features summary ──────────────────────────────────────────────────

const AI_FEATURES = [
  { label: 'Care Navigation AI', icon: Brain, color: 'text-purple-600' },
  { label: 'Polypharmacy Checker', icon: Pill, color: 'text-rose-600' },
  { label: 'Clinical Doc Generator', icon: FileText, color: 'text-blue-600' },
  { label: 'Health Insights Engine', icon: Sparkles, color: 'text-amber-600' },
  { label: 'Fall Detection Pipeline', icon: AlertTriangle, color: 'text-red-600' },
  { label: 'Drift Detection Engine', icon: Activity, color: 'text-emerald-600' },
];

// ─── Demo Scenarios (accessible from tour or DemoPanel) ─────────────────────

const DEMO_SCENARIOS = [
  {
    label: 'Simulate a Fall Event',
    description: 'Open the Demo Panel (⚡ button in sidebar) → select "Fall Detected" → watch it appear on the dashboard.',
    icon: Zap,
  },
  {
    label: 'Try Care Navigation AI',
    description: 'Go to Care Navigation → type "What diet should Kamala follow for diabetes?" → see Bedrock respond with context.',
    icon: MessageCircle,
  },
  {
    label: 'Generate a Clinical Document',
    description: 'Go to Clinical Docs → pick a resident → choose "SOAP Note" → click Generate → see Bedrock create a clinical note.',
    icon: FileText,
  },
  {
    label: 'Check Drug Interactions',
    description: 'Go to Prescriptions → click "Check Interactions" on any resident → see Bedrock analyze polypharmacy risks.',
    icon: Pill,
  },
];

// ─── Component ──────────────────────────────────────────────────────────────

const TOUR_DISMISSED_KEY = 'aether_tour_dismissed';

export default function GuidedTour() {
  const { user, role } = useAuth();
  const navigate = useNavigate();
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!user) return;
    const dismissed = localStorage.getItem(TOUR_DISMISSED_KEY);
    if (!dismissed) {
      // Show tour on first login
      const timer = setTimeout(() => setVisible(true), 600);
      return () => clearTimeout(timer);
    }
  }, [user]);

  if (!visible || !role) return null;

  const steps = ROLE_TOURS[role];
  const currentStep = steps[step];
  const isFirst = step === 0;
  const isLast = step === steps.length - 1;
  const Icon = currentStep.icon;

  function dismiss() {
    localStorage.setItem(TOUR_DISMISSED_KEY, 'true');
    setVisible(false);
  }

  function goToStep(idx: number) {
    setStep(idx);
    if (idx > 0) {
      navigate(steps[idx].path);
    }
  }

  function handleNext() {
    if (isLast) {
      dismiss();
    } else {
      goToStep(step + 1);
    }
  }

  function handlePrev() {
    if (!isFirst) {
      goToStep(step - 1);
    }
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-xl mx-4 bg-white rounded-2xl shadow-2xl overflow-hidden">
        {/* Progress bar */}
        <div className="h-1 bg-gray-100">
          <div
            className="h-full bg-gradient-to-r from-teal-400 via-aether-500 to-indigo-500 transition-all duration-500"
            style={{ width: `${((step + 1) / steps.length) * 100}%` }}
          />
        </div>

        {/* Close button */}
        <button
          onClick={dismiss}
          className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-600 transition-colors z-10"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Content */}
        <div className="p-8">
          {/* Step counter */}
          <div className="flex items-center gap-2 mb-5">
            <span className="text-xs font-semibold text-aether-600 bg-aether-50 px-2.5 py-1 rounded-full">
              {step + 1} / {steps.length}
            </span>
            <span className="text-xs text-gray-400">
              {role === 'elder' ? 'Elder' : role === 'caregiver' ? 'Caregiver' : role === 'doctor' ? 'Doctor' : 'Operations'} Tour
            </span>
          </div>

          {/* Icon + Title */}
          <div className="flex items-start gap-4 mb-4">
            <div className={`w-12 h-12 rounded-xl ${Icon ? currentStep.iconBg : 'bg-aether-500'} flex items-center justify-center shrink-0`}>
              <Icon className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900">{currentStep.title}</h2>
            </div>
          </div>

          {/* Description */}
          <p className="text-sm text-gray-600 leading-relaxed mb-4">
            {currentStep.description}
          </p>

          {/* Highlight tip */}
          {currentStep.highlight && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 px-4 py-3 mb-4">
              <p className="text-sm text-amber-800">
                <span className="font-semibold">💡 Try this: </span>
                {currentStep.highlight}
              </p>
            </div>
          )}

          {/* On intro step, show AI features + demo scenarios */}
          {isFirst && (
            <div className="space-y-4">
              <div>
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
                  AI Features (Amazon Bedrock)
                </h3>
                <div className="flex flex-wrap gap-2">
                  {AI_FEATURES.map((f) => (
                    <span
                      key={f.label}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-gray-50 border border-gray-200 text-xs font-medium text-gray-700"
                    >
                      <f.icon className={`w-3.5 h-3.5 ${f.color}`} />
                      {f.label}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
                  Things to Try
                </h3>
                <div className="space-y-2">
                  {DEMO_SCENARIOS.map((s) => (
                    <div
                      key={s.label}
                      className="flex items-start gap-2 text-xs text-gray-600 bg-gray-50 rounded-lg px-3 py-2"
                    >
                      <s.icon className="w-4 h-4 text-aether-500 mt-0.5 shrink-0" />
                      <div>
                        <span className="font-semibold text-gray-800">{s.label}: </span>
                        {s.description}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between px-8 py-5 bg-gray-50 border-t border-gray-100">
          <button
            onClick={handlePrev}
            disabled={isFirst}
            className="flex items-center gap-1.5 text-sm font-medium text-gray-600 hover:text-gray-900 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Back
          </button>

          {/* Step dots */}
          <div className="flex gap-1.5">
            {steps.map((_, i) => (
              <button
                key={i}
                onClick={() => goToStep(i)}
                className={`w-2 h-2 rounded-full transition-all ${
                  i === step
                    ? 'bg-aether-500 w-5'
                    : i < step
                    ? 'bg-aether-300'
                    : 'bg-gray-300'
                }`}
              />
            ))}
          </div>

          <button
            onClick={handleNext}
            className="flex items-center gap-1.5 text-sm font-semibold text-white bg-gradient-to-r from-teal-500 to-aether-600 px-5 py-2 rounded-xl shadow-sm hover:shadow-md hover:brightness-110 transition-all"
          >
            {isLast ? 'Start Exploring' : 'Next'}
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
