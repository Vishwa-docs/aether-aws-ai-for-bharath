import { useState, useCallback } from 'react';
import {
  Settings,
  Server,
  Shield,
  Bell,
  Users,
  Activity,
  Wifi,
  Cloud,
  Lock,
  Eye,
  EyeOff,
  Mic,
  Move,
  Database,
  Clock,
  Save,
  Check,
  ChevronRight,
  Plus,
  Radio,
  Mail,
  Phone,
  MessageSquare,
  Volume2,
  AlertTriangle,
  HardDrive,
  Timer,
  Layers,
} from 'lucide-react';

import { RESIDENTS, DASHBOARD_STATS, SENSOR_HEALTH } from '../data/mockData';

// ─── Types ────────────────────────────────────────────────────────────────────

type TabKey = 'system' | 'privacy' | 'notifications' | 'residents' | 'health';

interface TabItem {
  key: TabKey;
  label: string;
  icon: React.ElementType;
  description: string;
}

const TABS: TabItem[] = [
  { key: 'system', label: 'System', icon: Server, description: 'Edge & cloud configuration' },
  { key: 'privacy', label: 'Privacy', icon: Shield, description: 'Data protection settings' },
  { key: 'notifications', label: 'Notifications', icon: Bell, description: 'Alert preferences' },
  { key: 'residents', label: 'Residents', icon: Users, description: 'Resident management' },
  { key: 'health', label: 'Health', icon: Activity, description: 'System diagnostics' },
];

// ─── Reusable Components ──────────────────────────────────────────────────────

function InputField({
  label,
  value,
  readOnly = false,
  type = 'text',
  helpText,
}: {
  label: string;
  value: string;
  readOnly?: boolean;
  type?: string;
  helpText?: string;
}) {
  const [val, setVal] = useState(value);
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      <input
        type={type}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        readOnly={readOnly}
        className={`w-full rounded-xl border px-4 py-2.5 text-sm transition-all ${
          readOnly
            ? 'border-gray-200 bg-gray-50 text-gray-500 cursor-not-allowed'
            : 'border-gray-300 bg-white text-gray-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 hover:border-gray-400'
        }`}
      />
      {helpText && <p className="mt-1 text-xs text-gray-400">{helpText}</p>}
    </div>
  );
}

function Toggle({
  label,
  description,
  defaultChecked = false,
  disabled = false,
  forcedOn = false,
  warning,
}: {
  label: string;
  description?: string;
  defaultChecked?: boolean;
  disabled?: boolean;
  forcedOn?: boolean;
  warning?: string;
}) {
  const [checked, setChecked] = useState(forcedOn || defaultChecked);

  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-900">{label}</span>
          {forcedOn && (
            <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-700">
              REQUIRED
            </span>
          )}
        </div>
        {description && <p className="mt-0.5 text-xs text-gray-500">{description}</p>}
        {warning && (
          <div className="mt-1.5 flex items-center gap-1.5 text-xs text-amber-600">
            <AlertTriangle size={12} />
            <span>{warning}</span>
          </div>
        )}
      </div>
      <button
        onClick={() => !forcedOn && !disabled && setChecked(!checked)}
        disabled={forcedOn || disabled}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-200 ${
          checked ? 'bg-blue-600' : 'bg-gray-200'
        } ${forcedOn || disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200 ${
            checked ? 'translate-x-6' : 'translate-x-1'
          }`}
        />
      </button>
    </div>
  );
}

function SectionCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60">
      <div className="mb-5 flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100">
          <Icon size={18} className="text-gray-600" />
        </div>
        <h3 className="text-base font-bold text-gray-900">{title}</h3>
      </div>
      {children}
    </div>
  );
}

// ─── Tab Contents ─────────────────────────────────────────────────────────────

function SystemTab() {
  return (
    <div className="space-y-6 animate-fade-in">
      <SectionCard title="Edge Gateway Configuration" icon={Wifi}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <InputField
            label="Gateway Host"
            value="192.168.1.100"
            readOnly
            helpText="Edge gateway IP (auto-discovered)"
          />
          <InputField
            label="Gateway Port"
            value="8883"
            readOnly
            helpText="TLS-secured MQTT port"
          />
          <InputField
            label="Gateway ID"
            value="aether-edge-gw-001"
            readOnly
          />
          <InputField
            label="Firmware Version"
            value="2.4.1-stable"
            readOnly
          />
        </div>
      </SectionCard>

      <SectionCard title="MQTT Broker Settings" icon={Radio}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <InputField
            label="Broker Host"
            value="mqtt.aether-iot.local"
            helpText="Internal MQTT broker address"
          />
          <InputField
            label="Broker Port"
            value="8883"
          />
          <InputField
            label="Client ID"
            value="aether-dashboard-v2"
          />
          <InputField
            label="Topic Prefix"
            value="aether/homes/"
          />
        </div>
      </SectionCard>

      <SectionCard title="AWS Cloud Configuration" icon={Cloud}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">AWS Region</label>
            <select className="w-full rounded-xl border border-gray-300 bg-white px-4 py-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 hover:border-gray-400 transition-all">
              <option value="ap-south-1">Asia Pacific (Mumbai) — ap-south-1</option>
              <option value="us-east-1">US East (N. Virginia) — us-east-1</option>
              <option value="eu-west-1">Europe (Ireland) — eu-west-1</option>
              <option value="ap-southeast-1">Asia Pacific (Singapore) — ap-southeast-1</option>
            </select>
          </div>
          <InputField
            label="IoT Core Endpoint"
            value="a1b2c3d4e5f6g7-ats.iot.ap-south-1.amazonaws.com"
          />
          <InputField
            label="API Gateway URL"
            value="https://api.aether-care.in/v1"
            readOnly
            helpText="REST API endpoint (CDK-deployed)"
          />
          <InputField
            label="S3 Evidence Bucket"
            value="aether-evidence-packets-prod"
            readOnly
          />
        </div>
      </SectionCard>
    </div>
  );
}

function PrivacyTab() {
  const [privacyLevel, setPrivacyLevel] = useState<'minimal' | 'standard' | 'enhanced'>('standard');
  const [retention, setRetention] = useState(90);

  const levels = [
    {
      key: 'minimal' as const,
      label: 'Minimal',
      description: 'Only essential safety alerts. No behavioral analysis. Lowest data collection.',
      color: 'border-emerald-500 bg-emerald-50',
      iconColor: 'text-emerald-600',
    },
    {
      key: 'standard' as const,
      label: 'Standard',
      description: 'Safety monitoring with behavioral patterns. Audio classification without recording. Recommended for most homes.',
      color: 'border-blue-500 bg-blue-50',
      iconColor: 'text-blue-600',
    },
    {
      key: 'enhanced' as const,
      label: 'Enhanced',
      description: 'Full sensor fusion with detailed activity tracking. Maximum safety coverage for high-risk residents.',
      color: 'border-violet-500 bg-violet-50',
      iconColor: 'text-violet-600',
    },
  ];

  const retentionOptions = [
    { value: 30, label: '30 days', description: 'Minimum retention' },
    { value: 90, label: '90 days', description: 'Recommended' },
    { value: 365, label: '1 year', description: 'Extended' },
    { value: 2555, label: '7 years', description: 'Regulatory compliance' },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionCard title="Privacy Level" icon={Lock}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {levels.map((level) => (
            <button
              key={level.key}
              onClick={() => setPrivacyLevel(level.key)}
              className={`relative rounded-xl border-2 p-4 text-left transition-all ${
                privacyLevel === level.key
                  ? level.color
                  : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              {privacyLevel === level.key && (
                <div className="absolute top-3 right-3">
                  <Check size={16} className={level.iconColor} />
                </div>
              )}
              <div className="flex items-center gap-2 mb-2">
                <Shield size={16} className={privacyLevel === level.key ? level.iconColor : 'text-gray-400'} />
                <span className={`text-sm font-bold ${privacyLevel === level.key ? 'text-gray-900' : 'text-gray-700'}`}>
                  {level.label}
                </span>
              </div>
              <p className="text-xs text-gray-500 leading-relaxed">{level.description}</p>
            </button>
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Data Processing Controls" icon={Eye}>
        <div className="divide-y divide-gray-100">
          <Toggle
            label="Enable audio feature extraction"
            description="Extract acoustic features (MFCCs, spectral data) for event classification"
            defaultChecked={true}
          />
          <Toggle
            label="Enable pose keypoint extraction"
            description="Process camera feed to extract skeletal keypoints for fall detection"
            defaultChecked={true}
          />
          <Toggle
            label="Enable raw audio recording"
            description="Store raw audio clips when events are detected"
            defaultChecked={false}
            warning="Raw audio recording may have privacy implications. Consent required from all household members."
          />
          <Toggle
            label="Federated learning participation"
            description="Contribute anonymized model updates to improve system-wide accuracy"
            defaultChecked={true}
          />
        </div>
      </SectionCard>

      <SectionCard title="Data Retention Policy" icon={Database}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {retentionOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setRetention(opt.value)}
              className={`rounded-xl border-2 px-4 py-3 text-center transition-all ${
                retention === opt.value
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className={`text-lg font-bold ${retention === opt.value ? 'text-blue-700' : 'text-gray-900'}`}>
                {opt.label}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">{opt.description}</div>
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs text-gray-400">
          Event data, evidence packets, and analytics will be retained for the selected period before automatic deletion.
        </p>
      </SectionCard>
    </div>
  );
}

function NotificationsTab() {
  const alertTypes = [
    { label: 'Fall Detection Alerts', description: 'Immediate notification on fall events', defaultOn: true },
    { label: 'Medication Reminders', description: 'Missed or late medication alerts', defaultOn: true },
    { label: 'Acoustic Anomalies', description: 'Screams, glass breaks, impacts', defaultOn: true },
    { label: 'Vital Sign Alerts', description: 'Abnormal heart rate, SpO2, blood pressure', defaultOn: true },
    { label: 'Routine Anomalies', description: 'Unusual activity patterns', defaultOn: false },
    { label: 'Check-in Confirmations', description: 'Scheduled check-in completions', defaultOn: false },
    { label: 'System Health Alerts', description: 'Sensor offline, low battery warnings', defaultOn: true },
  ];

  const channels = [
    { label: 'Push Notifications', icon: Bell, defaultOn: true },
    { label: 'SMS', icon: MessageSquare, defaultOn: true },
    { label: 'Email', icon: Mail, defaultOn: true },
    { label: 'Voice Call', icon: Phone, defaultOn: false },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionCard title="Alert Types" icon={Bell}>
        <div className="divide-y divide-gray-100">
          {alertTypes.map((alert) => (
            <Toggle
              key={alert.label}
              label={alert.label}
              description={alert.description}
              defaultChecked={alert.defaultOn}
            />
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Quiet Hours" icon={Clock}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <InputField label="Start Time" value="22:00" type="time" />
          <InputField label="End Time" value="07:00" type="time" />
        </div>
        <div className="mt-4 divide-y divide-gray-100">
          <Toggle
            label="Safety events override quiet hours"
            description="CRITICAL and HIGH severity events will always send notifications"
            forcedOn={true}
          />
        </div>
      </SectionCard>

      <SectionCard title="Notification Channels" icon={Volume2}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {channels.map((ch) => {
            const [on, setOn] = useState(ch.defaultOn);
            const ChIcon = ch.icon;
            return (
              <button
                key={ch.label}
                onClick={() => setOn(!on)}
                className={`flex flex-col items-center gap-2 rounded-xl border-2 px-4 py-4 transition-all ${
                  on
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 bg-white hover:border-gray-300'
                }`}
              >
                <ChIcon size={20} className={on ? 'text-blue-600' : 'text-gray-400'} />
                <span className={`text-xs font-semibold ${on ? 'text-blue-700' : 'text-gray-600'}`}>
                  {ch.label}
                </span>
                <div className={`h-1.5 w-1.5 rounded-full ${on ? 'bg-blue-500' : 'bg-gray-300'}`} />
              </button>
            );
          })}
        </div>
      </SectionCard>
    </div>
  );
}

function ResidentsTab() {
  const riskColor = (score: number) =>
    score < 0.3 ? 'text-emerald-600' : score <= 0.6 ? 'text-amber-600' : 'text-red-600';
  const riskBg = (score: number) =>
    score < 0.3 ? 'bg-emerald-50' : score <= 0.6 ? 'bg-amber-50' : 'bg-red-50';

  return (
    <div className="space-y-6 animate-fade-in">
      <SectionCard title="Registered Residents" icon={Users}>
        <div className="space-y-3">
          {RESIDENTS.map((resident) => (
            <div
              key={resident.resident_id}
              className="flex items-center gap-4 rounded-xl border border-gray-100 bg-gray-50/50 px-5 py-4 transition-all hover:bg-white hover:shadow-sm"
            >
              {/* Avatar */}
              <div className="flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-blue-600 text-white font-bold text-sm shrink-0">
                {resident.name.split(' ').map((n) => n[0]).join('')}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-gray-900">{resident.name}</span>
                  <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold ${
                    resident.status === 'active' ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'
                  }`}>
                    {resident.status.toUpperCase()}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-3 text-xs text-gray-500">
                  <span>Age {resident.age}</span>
                  <span>·</span>
                  <span>{resident.home_id}</span>
                  <span>·</span>
                  <span>{resident.medications.length} medications</span>
                </div>
              </div>

              {/* Risk score */}
              <div className="hidden sm:flex flex-col items-end shrink-0 gap-1">
                <span className={`text-xs font-bold ${riskColor(resident.risk_score ?? 0)}`}>
                  Risk: {((resident.risk_score ?? 0) * 100).toFixed(0)}%
                </span>
                <div className="h-1.5 w-16 rounded-full bg-gray-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      (resident.risk_score ?? 0) < 0.3
                        ? 'bg-emerald-500'
                        : (resident.risk_score ?? 0) <= 0.6
                        ? 'bg-amber-400'
                        : 'bg-red-500'
                    }`}
                    style={{ width: `${(resident.risk_score ?? 0) * 100}%` }}
                  />
                </div>
              </div>

              {/* Edit button */}
              <button className="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors shrink-0">
                <ChevronRight size={16} />
              </button>
            </div>
          ))}
        </div>

        {/* Add button */}
        <button
          disabled
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-gray-200 px-4 py-3 text-sm font-medium text-gray-400 transition-all hover:border-gray-300 cursor-not-allowed"
        >
          <Plus size={16} />
          Add New Resident
        </button>
        <p className="mt-2 text-xs text-gray-400 text-center">
          Resident onboarding requires admin access and privacy consent documentation.
        </p>
      </SectionCard>
    </div>
  );
}

function HealthTab() {
  const now = new Date();
  const uptimeStart = new Date(now.getTime() - 47 * 24 * 60 * 60 * 1000);
  const lastBackup = new Date(now.getTime() - 2 * 60 * 60 * 1000);

  const sensorsOnline = SENSOR_HEALTH.filter((s) => s.status === 'online').length;
  const sensorsTotal = SENSOR_HEALTH.length;

  const stats = [
    {
      label: 'System Uptime',
      value: `${DASHBOARD_STATS.system_uptime}%`,
      detail: `Since ${uptimeStart.toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' })}`,
      icon: Timer,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
    },
    {
      label: 'Last Backup',
      value: lastBackup.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
      detail: lastBackup.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
      icon: Database,
      color: 'text-blue-600',
      bg: 'bg-blue-50',
    },
    {
      label: 'CDK Stack Version',
      value: 'v2.4.1',
      detail: 'AetherIoTStack + AetherStorageStack',
      icon: Layers,
      color: 'text-violet-600',
      bg: 'bg-violet-50',
    },
    {
      label: 'Connected Devices',
      value: `${sensorsOnline} / ${sensorsTotal}`,
      detail: `${sensorsTotal - sensorsOnline} device(s) need attention`,
      icon: Wifi,
      color: 'text-cyan-600',
      bg: 'bg-cyan-50',
    },
  ];

  const healthMetrics = [
    { label: 'Edge CPU Usage', value: 23, max: 100, unit: '%', color: 'bg-blue-500' },
    { label: 'Edge Memory', value: 512, max: 2048, unit: ' MB', color: 'bg-violet-500' },
    { label: 'MQTT Throughput', value: 142, max: 500, unit: ' msg/s', color: 'bg-emerald-500' },
    { label: 'Event Processing Latency', value: 340, max: 2000, unit: ' ms', color: 'bg-cyan-500' },
    { label: 'Evidence Upload Queue', value: 2, max: 50, unit: ' packets', color: 'bg-amber-500' },
    { label: 'DynamoDB WCU Usage', value: 35, max: 100, unit: '%', color: 'bg-orange-500' },
  ];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const StatIcon = stat.icon;
          return (
            <div
              key={stat.label}
              className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200/60"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${stat.bg}`}>
                  <StatIcon size={18} className={stat.color} />
                </div>
                <span className="text-sm font-medium text-gray-500">{stat.label}</span>
              </div>
              <div className="text-2xl font-bold text-gray-900">{stat.value}</div>
              <div className="mt-1 text-xs text-gray-400">{stat.detail}</div>
            </div>
          );
        })}
      </div>

      <SectionCard title="Performance Metrics" icon={Activity}>
        <div className="space-y-4">
          {healthMetrics.map((metric) => {
            const pct = (metric.value / metric.max) * 100;
            return (
              <div key={metric.label}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm font-medium text-gray-700">{metric.label}</span>
                  <span className="text-sm font-bold text-gray-900">
                    {metric.value}{metric.unit}
                  </span>
                </div>
                <div className="h-2 w-full rounded-full bg-gray-100 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${metric.color} transition-all duration-700`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </SectionCard>

      <SectionCard title="Infrastructure Details" icon={HardDrive}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <InputField label="Lambda Runtime" value="Python 3.12" readOnly />
          <InputField label="Step Functions" value="2 state machines active" readOnly />
          <InputField label="DynamoDB Tables" value="Events, Residents, Timeline, Evidence" readOnly />
          <InputField label="IoT Rules" value="4 rules (fall, medication, acoustic, vital)" readOnly />
          <InputField label="CloudWatch Alarms" value="12 active, 0 in alarm" readOnly />
          <InputField label="OpenAPI Spec" value="v1.2.0 — 8 endpoints" readOnly />
        </div>
      </SectionCard>
    </div>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═════════════════════════════════════════════════════════════════════════════

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('system');
  const [showToast, setShowToast] = useState(false);

  const handleSave = useCallback(() => {
    setShowToast(true);
    setTimeout(() => setShowToast(false), 2500);
  }, []);

  const renderTab = () => {
    switch (activeTab) {
      case 'system':
        return <SystemTab />;
      case 'privacy':
        return <PrivacyTab />;
      case 'notifications':
        return <NotificationsTab />;
      case 'residents':
        return <ResidentsTab />;
      case 'health':
        return <HealthTab />;
    }
  };

  return (
    <div className="animate-fade-in">
      {/* ─── Header ───────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
          <p className="mt-1 text-sm text-gray-500">
            System configuration and preferences
          </p>
        </div>
        <button
          onClick={handleSave}
          className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 active:scale-[0.98]"
        >
          <Save size={16} />
          Save Changes
        </button>
      </div>

      {/* ─── Tab Bar ──────────────────────────────────────────────── */}
      <div className="mb-6 flex gap-1 overflow-x-auto rounded-xl bg-gray-100 p-1">
        {TABS.map((tab) => {
          const TabIcon = tab.icon;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-all ${
                activeTab === tab.key
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <TabIcon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ─── Tab Content ──────────────────────────────────────────── */}
      {renderTab()}

      {/* ─── Toast ────────────────────────────────────────────────── */}
      {showToast && (
        <div className="fixed bottom-6 right-6 z-50 animate-slide-up">
          <div className="flex items-center gap-3 rounded-xl bg-gray-900 px-5 py-3.5 text-sm font-medium text-white shadow-2xl">
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500">
              <Check size={14} className="text-white" />
            </div>
            Settings saved successfully
          </div>
        </div>
      )}
    </div>
  );
}
