import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Heart,
  Shield,
  Stethoscope,
  Building2,
  LogIn,
  Loader2,
  AlertCircle,
  Activity,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

// ─── Persona cards data ───────────────────────────────────────────────────────

interface PersonaCard {
  role: string;
  name: string;
  email: string;
  icon: React.ElementType;
  color: string;         // gradient from
  colorTo: string;       // gradient to
  ring: string;          // focus ring
  bg: string;            // light bg
  description: string;
}

const PERSONAS: PersonaCard[] = [
  {
    role: 'Elder',
    name: 'Margaret Sharma',
    email: 'margaret.sharma@aether.care',
    icon: Heart,
    color: 'from-rose-500',
    colorTo: 'to-pink-600',
    ring: 'ring-rose-300',
    bg: 'bg-rose-50',
    description: 'View your health dashboard, medications, and companion',
  },
  {
    role: 'Caregiver',
    name: 'Priya Nair',
    email: 'priya.nair@aether.care',
    icon: Shield,
    color: 'from-emerald-500',
    colorTo: 'to-teal-600',
    ring: 'ring-emerald-300',
    bg: 'bg-emerald-50',
    description: 'Monitor residents, manage alerts, and coordinate care',
  },
  {
    role: 'Doctor',
    name: 'Dr. Rajesh Menon',
    email: 'rajesh.menon@aether.care',
    icon: Stethoscope,
    color: 'from-blue-500',
    colorTo: 'to-indigo-600',
    ring: 'ring-blue-300',
    bg: 'bg-blue-50',
    description: 'Review pre-consult summaries, prescriptions, and clinical notes',
  },
  {
    role: 'Ops / B2B',
    name: 'Anand Kulkarni',
    email: 'anand.kulkarni@aether.care',
    icon: Building2,
    color: 'from-amber-500',
    colorTo: 'to-orange-600',
    ring: 'ring-amber-300',
    bg: 'bg-amber-50',
    description: 'Fleet management, site health, and operational analytics',
  },
];

// ─── Login Page ───────────────────────────────────────────────────────────────

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  async function handleQuickLogin(persona: PersonaCard) {
    setError(null);
    setEmail(persona.email);
    setPassword('demo123');
    setLoading(true);
    try {
      await login(persona.email, 'demo123');
      navigate('/', { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50 flex flex-col">
      {/* ── Top accent bar ─────────────────────────────────────────────── */}
      <div className="h-1 w-full bg-gradient-to-r from-teal-400 via-aether-500 to-indigo-500" />

      <div className="flex-1 flex flex-col items-center justify-center px-4 py-10 sm:px-6 lg:px-8">
        {/* ── Branding ─────────────────────────────────────────────────── */}
        <div className="text-center mb-10 animate-fade-in">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-teal-400 to-aether-600 shadow-lg shadow-aether-200 mb-5">
            <Activity className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
            <span className="bg-gradient-to-r from-teal-600 via-aether-600 to-indigo-600 bg-clip-text text-transparent">
              AETHER
            </span>
          </h1>
          <p className="mt-2 text-sm sm:text-base text-gray-500 max-w-md mx-auto leading-relaxed">
            Autonomous Elderly ecosystem for Total Health
            <br className="hidden sm:block" />
            &amp; Emergency Response
          </p>
        </div>

        {/* ── Login card ───────────────────────────────────────────────── */}
        <div className="w-full max-w-md animate-slide-up">
          <div className="bg-white rounded-2xl shadow-xl shadow-gray-200/60 border border-gray-100 p-8">
            <h2 className="text-xl font-semibold text-gray-900 mb-6">Sign in to your account</h2>

            {/* Error banner */}
            {error && (
              <div className="mb-5 flex items-start gap-3 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700 animate-fade-in">
                <AlertCircle className="w-5 h-5 mt-0.5 shrink-0 text-red-500" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@aether.care"
                  className="input h-12 text-base"
                  disabled={loading}
                />
              </div>

              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-1.5">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input h-12 text-base"
                  disabled={loading}
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full h-12 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-teal-500 via-aether-600 to-aether-700 text-white font-semibold text-base shadow-lg shadow-aether-200 hover:shadow-xl hover:shadow-aether-300 hover:brightness-110 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-aether-500 focus:ring-offset-2"
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <LogIn className="w-5 h-5" />
                    Sign in
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* ── Divider ──────────────────────────────────────────────────── */}
        <div className="w-full max-w-3xl flex items-center gap-4 my-10">
          <div className="flex-1 h-px bg-gray-200" />
          <span className="text-xs font-medium text-gray-400 uppercase tracking-widest">
            Quick Demo Access
          </span>
          <div className="flex-1 h-px bg-gray-200" />
        </div>

        {/* ── Persona cards ────────────────────────────────────────────── */}
        <div className="w-full max-w-4xl grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-slide-up">
          {PERSONAS.map((p) => {
            const Icon = p.icon;
            return (
              <button
                key={p.email}
                onClick={() => handleQuickLogin(p)}
                disabled={loading}
                className={`group relative flex flex-col items-center text-center rounded-2xl border border-gray-100 bg-white p-6 shadow-sm hover:shadow-lg hover:-translate-y-1 transition-all duration-300 focus:outline-none focus:ring-2 ${p.ring} focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed`}
              >
                {/* Icon badge */}
                <div
                  className={`w-14 h-14 rounded-xl bg-gradient-to-br ${p.color} ${p.colorTo} flex items-center justify-center shadow-md group-hover:scale-110 transition-transform duration-300`}
                >
                  <Icon className="w-7 h-7 text-white" />
                </div>

                {/* Role label */}
                <span
                  className={`mt-4 text-[11px] font-semibold uppercase tracking-wider ${p.bg} ${p.color.replace('from-', 'text-')} px-3 py-0.5 rounded-full`}
                >
                  {p.role}
                </span>

                {/* Name */}
                <h3 className="mt-3 text-sm font-bold text-gray-900 leading-snug">{p.name}</h3>

                {/* Description */}
                <p className="mt-1.5 text-xs text-gray-500 leading-relaxed line-clamp-2">
                  {p.description}
                </p>

                {/* Quick Login CTA */}
                <span
                  className={`mt-4 inline-flex items-center gap-1 text-xs font-semibold bg-gradient-to-r ${p.color} ${p.colorTo} bg-clip-text text-transparent group-hover:underline`}
                >
                  Quick Login
                  <LogIn className="w-3.5 h-3.5 text-gray-400 group-hover:text-gray-600 transition-colors" />
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer className="py-6 text-center text-xs text-gray-400">
        <p>AETHER v0.1.0 &middot; &copy; {new Date().getFullYear()} AETHER Health Technologies</p>
        <p className="mt-1">Autonomous Elderly Care &middot; Powered by Edge AI</p>
      </footer>
    </div>
  );
}
