import { useMemo, useState, useCallback } from 'react';
import {
  Car,
  UtensilsCrossed,
  Calendar,
  ShoppingBag,
  Clock,
  CheckCircle,
  X,
  AlertTriangle,
  Send,
  Filter,
  ChevronRight,
  XCircle,
  MessageSquare,
  Package,
} from 'lucide-react';
import { format, formatDistanceToNow } from 'date-fns';

import { SERVICE_BOOKINGS, RESIDENTS } from '../data/mockData';
import { useAuth } from '../contexts/AuthContext';
import type { ServiceBooking, Resident } from '../types';

// ─── Constants ────────────────────────────────────────────────────────────────

type BookingType = ServiceBooking['type'];
type BookingStatus = ServiceBooking['status'];

const TYPE_CONFIG: Record<BookingType, { label: string; icon: React.ElementType; bg: string; text: string }> = {
  transport:   { label: 'Transport',   icon: Car,              bg: 'bg-blue-100',   text: 'text-blue-700' },
  food_order:  { label: 'Food Order',  icon: UtensilsCrossed,  bg: 'bg-orange-100', text: 'text-orange-700' },
  appointment: { label: 'Appointment', icon: Calendar,         bg: 'bg-violet-100', text: 'text-violet-700' },
  shopping:    { label: 'Shopping',    icon: ShoppingBag,      bg: 'bg-emerald-100', text: 'text-emerald-700' },
};

const STATUS_CONFIG: Record<BookingStatus, { label: string; bg: string; text: string; ring: string }> = {
  requested:   { label: 'Requested',   bg: 'bg-gray-100',    text: 'text-gray-700',    ring: 'ring-gray-600/10' },
  confirmed:   { label: 'Confirmed',   bg: 'bg-blue-100',    text: 'text-blue-700',    ring: 'ring-blue-600/10' },
  in_progress: { label: 'In Progress', bg: 'bg-yellow-100',  text: 'text-yellow-700',  ring: 'ring-yellow-600/10' },
  completed:   { label: 'Completed',   bg: 'bg-emerald-100', text: 'text-emerald-700', ring: 'ring-emerald-600/10' },
  cancelled:   { label: 'Cancelled',   bg: 'bg-red-100',     text: 'text-red-700',     ring: 'ring-red-600/10' },
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function residentById(id: string): Resident | undefined {
  return RESIDENTS.find((r) => r.resident_id === id);
}

function timeAgo(ts: number): string {
  return formatDistanceToNow(new Date(ts), { addSuffix: true });
}

function formatCurrency(amount: number): string {
  return `₹${amount.toLocaleString('en-IN')}`;
}

function StatusBadge({ status }: { status: BookingStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-bold ring-1 ring-inset ${cfg.bg} ${cfg.text} ${cfg.ring}`}>
      {cfg.label}
    </span>
  );
}

function TypeIcon({ type, size = 18 }: { type: BookingType; size?: number }) {
  const cfg = TYPE_CONFIG[type];
  return (
    <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${cfg.bg}`}>
      <cfg.icon size={size} className={cfg.text} />
    </div>
  );
}

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

// ─── Detail rendering ─────────────────────────────────────────────────────────

function BookingDetails({ booking }: { booking: ServiceBooking }) {
  const d = booking.details;

  switch (booking.type) {
    case 'transport':
      return (
        <div className="text-xs text-gray-600 space-y-1">
          <p><span className="font-medium text-gray-700">Pickup:</span> {d.pickup}</p>
          <p><span className="font-medium text-gray-700">Destination:</span> {d.destination}</p>
          {d.purpose && <p><span className="font-medium text-gray-700">Purpose:</span> {d.purpose}</p>}
          {d.escort && <p><span className="font-medium text-gray-700">Escort:</span> {d.escort}</p>}
          {d.wheelchair && <p className="text-amber-600">♿ Wheelchair required</p>}
        </div>
      );
    case 'food_order':
      return (
        <div className="text-xs text-gray-600 space-y-1">
          <p><span className="font-medium text-gray-700">From:</span> {d.restaurant}</p>
          {d.items && (
            <p><span className="font-medium text-gray-700">Items:</span> {(d.items as string[]).join(', ')}</p>
          )}
          {d.dietaryNotes && <p className="text-amber-600 italic">{d.dietaryNotes}</p>}
          {d.specialInstructions && <p><span className="font-medium text-gray-700">Note:</span> {d.specialInstructions}</p>}
        </div>
      );
    case 'appointment':
      return (
        <div className="text-xs text-gray-600 space-y-1">
          <p><span className="font-medium text-gray-700">Doctor:</span> {d.doctor}</p>
          {d.specialization && <p><span className="font-medium text-gray-700">Specialty:</span> {d.specialization}</p>}
          {d.hospital && <p><span className="font-medium text-gray-700">Hospital:</span> {d.hospital}</p>}
          {d.purpose && <p><span className="font-medium text-gray-700">Purpose:</span> {d.purpose}</p>}
          {d.telemedicine && <p className="text-blue-600">📹 Telemedicine</p>}
        </div>
      );
    case 'shopping':
      return (
        <div className="text-xs text-gray-600 space-y-1">
          <p><span className="font-medium text-gray-700">Store:</span> {d.store}</p>
          {d.items && (
            <p><span className="font-medium text-gray-700">Items:</span> {(d.items as string[]).join(', ')}</p>
          )}
          {d.deliveryNotes && <p><span className="font-medium text-gray-700">Note:</span> {d.deliveryNotes}</p>}
        </div>
      );
  }
}

// ─── New Booking Form ─────────────────────────────────────────────────────────

function NewBookingForm({ onClose, onSubmit }: { onClose: () => void; onSubmit: (b: ServiceBooking) => void }) {
  const [mode, setMode] = useState<'natural' | 'structured'>('natural');
  const [nlInput, setNlInput] = useState('');
  const [bookingType, setBookingType] = useState<BookingType>('transport');
  const [submitted, setSubmitted] = useState(false);

  // Structured fields
  const [pickup, setPickup] = useState('');
  const [destination, setDestination] = useState('');
  const [restaurant, setRestaurant] = useState('');
  const [items, setItems] = useState('');
  const [doctor, setDoctor] = useState('');
  const [specialty, setSpecialty] = useState('');
  const [storeName, setStoreName] = useState('');
  const [shoppingItems, setShoppingItems] = useState('');

  const handleSubmit = () => {
    let details: Record<string, unknown> = {};
    if (mode === 'natural') {
      details = { query: nlInput, parsedBy: 'AETHER NLP (demo)' };
    } else {
      switch (bookingType) {
        case 'transport':
          details = { pickup, destination };
          break;
        case 'food_order':
          details = { restaurant, items: items.split(',').map((s) => s.trim()) };
          break;
        case 'appointment':
          details = { doctor, specialization: specialty };
          break;
        case 'shopping':
          details = { store: storeName, items: shoppingItems.split(',').map((s) => s.trim()) };
          break;
      }
    }

    const newBooking: ServiceBooking = {
      id: `bk-${Date.now()}`,
      residentId: 'res-a1b2c3d4',
      type: mode === 'natural' ? 'transport' : bookingType,
      status: 'requested',
      details,
      requestedAt: Date.now(),
      isDemoOnly: true,
    };

    onSubmit(newBooking);
    setSubmitted(true);
    setTimeout(() => {
      setSubmitted(false);
      onClose();
    }, 2000);
  };

  if (submitted) {
    return (
      <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60 animate-fade-in">
        <div className="flex flex-col items-center py-6">
          <CheckCircle size={36} className="text-emerald-500 mb-3" />
          <p className="text-sm font-semibold text-emerald-700">Booking submitted successfully!</p>
          <p className="text-xs text-gray-400 mt-1">Demo mode — simulated booking created</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-gray-200/60 animate-slide-down">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-semibold text-gray-900">New Booking</h3>
        <button onClick={onClose} className="rounded-lg p-1 text-gray-400 hover:text-gray-600">
          <X size={16} />
        </button>
      </div>

      {/* Mode selector */}
      <div className="flex gap-2 mb-5">
        <button
          onClick={() => setMode('natural')}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
            mode === 'natural' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'
          }`}
        >
          <MessageSquare size={12} className="inline mr-1" /> Natural Language
        </button>
        <button
          onClick={() => setMode('structured')}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
            mode === 'structured' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'
          }`}
        >
          <Filter size={12} className="inline mr-1" /> Structured Form
        </button>
      </div>

      {mode === 'natural' ? (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">What do you need?</label>
          <textarea
            value={nlInput}
            onChange={(e) => setNlInput(e.target.value)}
            placeholder='e.g. "I need a ride to Apollo Hospital tomorrow at 10 AM" or "Order lunch from Swiggy — something soft and mild"'
            className="w-full rounded-xl border border-gray-300 p-3 text-sm text-gray-800 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100 resize-none h-24"
          />
        </div>
      ) : (
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Booking Type</label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {(Object.entries(TYPE_CONFIG) as [BookingType, typeof TYPE_CONFIG[BookingType]][]).map(([key, cfg]) => (
                <button
                  key={key}
                  onClick={() => setBookingType(key)}
                  className={`flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-semibold transition-all ${
                    bookingType === key
                      ? `${cfg.bg} ${cfg.text} ring-2 ring-inset ring-current`
                      : 'bg-gray-50 text-gray-600 ring-1 ring-gray-200 hover:bg-gray-100'
                  }`}
                >
                  <cfg.icon size={16} /> {cfg.label}
                </button>
              ))}
            </div>
          </div>

          {bookingType === 'transport' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Pickup</label>
                <input value={pickup} onChange={(e) => setPickup(e.target.value)} placeholder="e.g. AETHER Mumbai" className="w-full rounded-xl border border-gray-300 py-2 px-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Destination</label>
                <input value={destination} onChange={(e) => setDestination(e.target.value)} placeholder="e.g. Apollo Hospital" className="w-full rounded-xl border border-gray-300 py-2 px-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100" />
              </div>
            </div>
          )}

          {bookingType === 'food_order' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Restaurant / Service</label>
                <input value={restaurant} onChange={(e) => setRestaurant(e.target.value)} placeholder="e.g. Swiggy" className="w-full rounded-xl border border-gray-300 py-2 px-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Items (comma separated)</label>
                <input value={items} onChange={(e) => setItems(e.target.value)} placeholder="e.g. Dal Khichdi, Dahi" className="w-full rounded-xl border border-gray-300 py-2 px-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100" />
              </div>
            </div>
          )}

          {bookingType === 'appointment' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Doctor</label>
                <input value={doctor} onChange={(e) => setDoctor(e.target.value)} placeholder="e.g. Dr. Rajesh Menon" className="w-full rounded-xl border border-gray-300 py-2 px-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Specialty</label>
                <input value={specialty} onChange={(e) => setSpecialty(e.target.value)} placeholder="e.g. Endocrinology" className="w-full rounded-xl border border-gray-300 py-2 px-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100" />
              </div>
            </div>
          )}

          {bookingType === 'shopping' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Store</label>
                <input value={storeName} onChange={(e) => setStoreName(e.target.value)} placeholder="e.g. BigBasket" className="w-full rounded-xl border border-gray-300 py-2 px-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Items (comma separated)</label>
                <input value={shoppingItems} onChange={(e) => setShoppingItems(e.target.value)} placeholder="e.g. Oats, Almonds" className="w-full rounded-xl border border-gray-300 py-2 px-3 text-sm focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100" />
              </div>
            </div>
          )}
        </div>
      )}

      <div className="mt-5 flex gap-2">
        <button
          onClick={handleSubmit}
          className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700"
        >
          <Send size={14} /> Submit Booking
        </button>
        <button
          onClick={onClose}
          className="rounded-xl bg-gray-100 px-4 py-2.5 text-sm font-semibold text-gray-600 transition-all hover:bg-gray-200"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Bookings Page
// ═══════════════════════════════════════════════════════════════════════════════

export default function BookingsPage() {
  const { role } = useAuth();

  const [bookings, setBookings] = useState<ServiceBooking[]>(() => SERVICE_BOOKINGS);
  const [showNewBooking, setShowNewBooking] = useState(false);
  const [filterType, setFilterType] = useState<BookingType | 'all'>('all');
  const [filterStatus, setFilterStatus] = useState<BookingStatus | 'all'>('all');
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // Computed
  const activeBookings = useMemo(() => {
    return bookings
      .filter((b) => b.status !== 'completed' && b.status !== 'cancelled')
      .sort((a, b) => b.requestedAt - a.requestedAt);
  }, [bookings]);

  const historyBookings = useMemo(() => {
    let result = bookings.filter((b) => b.status === 'completed' || b.status === 'cancelled');
    if (filterType !== 'all') result = result.filter((b) => b.type === filterType);
    if (filterStatus !== 'all') result = result.filter((b) => b.status === filterStatus);
    return result.sort((a, b) => b.requestedAt - a.requestedAt);
  }, [bookings, filterType, filterStatus]);

  // KPIs
  const kpis = useMemo(() => {
    const total = bookings.length;
    const active = activeBookings.length;
    const completed = bookings.filter((b) => b.status === 'completed').length;
    const totalCost = bookings
      .filter((b) => b.cost)
      .reduce((s, b) => s + (b.cost ?? 0), 0);
    return { total, active, completed, totalCost };
  }, [bookings, activeBookings]);

  // Handlers
  const showToast = useCallback((msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  }, []);

  const handleCancel = useCallback(
    (id: string) => {
      setBookings((prev) =>
        prev.map((b) => (b.id === id ? { ...b, status: 'cancelled' as const } : b)),
      );
      showToast('Booking cancelled.');
    },
    [showToast],
  );

  const handleNewBooking = useCallback(
    (b: ServiceBooking) => {
      setBookings((prev) => [b, ...prev]);
      showToast('New booking created (demo).');
    },
    [showToast],
  );

  return (
    <div className="min-h-screen bg-gray-50/60">
      <div className="mx-auto max-w-[1440px] px-6 py-8 lg:px-10">
        {/* ── Demo Disclaimer ─────────────────────────────────────── */}
        <div className="mb-6 flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-700 ring-1 ring-amber-200">
          <AlertTriangle size={16} />
          All bookings are simulated for demo purposes. No real services will be dispatched.
        </div>

        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-cyan-600 shadow-sm">
              <Package className="text-white" size={20} />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-gray-900">Service Bookings</h1>
              <p className="text-sm text-gray-500">
                Transport, food, appointments & shopping · {format(new Date(), 'EEEE, MMM d, yyyy')}
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowNewBooking(!showNewBooking)}
            className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 active:scale-[0.98]"
          >
            <Send size={16} /> New Booking
          </button>
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

        {/* ── New Booking Form ─────────────────────────────────────── */}
        {showNewBooking && (
          <div className="mb-6">
            <NewBookingForm
              onClose={() => setShowNewBooking(false)}
              onSubmit={handleNewBooking}
            />
          </div>
        )}

        {/* ── KPI Row ─────────────────────────────────────────────── */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            label="Total Bookings"
            value={kpis.total}
            icon={Package}
            iconBg="bg-blue-50"
            iconColor="text-blue-600"
            subtitle="All time"
          />
          <KpiCard
            label="Active"
            value={kpis.active}
            icon={Clock}
            iconBg={kpis.active > 0 ? 'bg-yellow-50' : 'bg-emerald-50'}
            iconColor={kpis.active > 0 ? 'text-yellow-600' : 'text-emerald-600'}
            subtitle="In progress or confirmed"
          />
          <KpiCard
            label="Completed"
            value={kpis.completed}
            icon={CheckCircle}
            iconBg="bg-emerald-50"
            iconColor="text-emerald-600"
            subtitle="Successfully fulfilled"
          />
          <KpiCard
            label="Total Spend"
            value={formatCurrency(kpis.totalCost)}
            icon={ShoppingBag}
            iconBg="bg-violet-50"
            iconColor="text-violet-600"
            subtitle="Demo amounts"
          />
        </div>

        {/* ── Quick Actions (elder persona) ────────────────────────── */}
        {role === 'elder' && (
          <div className="mt-8">
            <h2 className="text-base font-semibold text-gray-900 mb-4">Quick Actions</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {([
                { type: 'transport' as const, label: 'Book a Ride', icon: Car, bg: 'bg-blue-50 hover:bg-blue-100', text: 'text-blue-700' },
                { type: 'food_order' as const, label: 'Order Food', icon: UtensilsCrossed, bg: 'bg-orange-50 hover:bg-orange-100', text: 'text-orange-700' },
                { type: 'appointment' as const, label: 'Schedule Appointment', icon: Calendar, bg: 'bg-violet-50 hover:bg-violet-100', text: 'text-violet-700' },
                { type: 'shopping' as const, label: 'Request Shopping', icon: ShoppingBag, bg: 'bg-emerald-50 hover:bg-emerald-100', text: 'text-emerald-700' },
              ]).map((action) => (
                <button
                  key={action.type}
                  onClick={() => setShowNewBooking(true)}
                  className={`rounded-2xl ${action.bg} p-6 flex flex-col items-center gap-3 transition-all ring-1 ring-inset ring-gray-200/60 shadow-sm hover:shadow-md cursor-pointer`}
                >
                  <action.icon size={28} className={action.text} />
                  <span className={`text-sm font-semibold ${action.text}`}>{action.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Active Bookings ──────────────────────────────────────── */}
        <div className="mt-8">
          <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Clock size={18} className="text-blue-500" /> Active Bookings
          </h2>

          {activeBookings.length === 0 ? (
            <div className="rounded-2xl bg-white p-12 shadow-sm ring-1 ring-gray-200/60 flex flex-col items-center text-center">
              <Package size={40} className="text-gray-300 mb-3" />
              <p className="text-sm font-medium text-gray-600">No active bookings</p>
              <p className="text-xs text-gray-400 mt-1">Create a new booking to get started.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {activeBookings.map((booking) => {
                const resident = residentById(booking.residentId);
                const typeCfg = TYPE_CONFIG[booking.type];
                return (
                  <div
                    key={booking.id}
                    className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-gray-200/60 transition-all hover:shadow-md"
                  >
                    <div className="flex items-start gap-3 mb-3">
                      <TypeIcon type={booking.type} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-semibold text-gray-800">{typeCfg.label}</span>
                          <StatusBadge status={booking.status} />
                          <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700 ring-1 ring-inset ring-amber-600/10">
                            DEMO ONLY
                          </span>
                        </div>
                        <p className="text-xs text-gray-400 mt-0.5">
                          {resident?.name ?? 'Unknown'} · {timeAgo(booking.requestedAt)}
                        </p>
                      </div>
                    </div>

                    <BookingDetails booking={booking} />

                    <div className="mt-3 flex items-center justify-between border-t border-gray-100 pt-3">
                      <div className="flex items-center gap-3 text-xs text-gray-400">
                        {booking.estimatedTime && (
                          <span className="flex items-center gap-1">
                            <Clock size={11} />
                            {new Date(booking.estimatedTime) > new Date()
                              ? `ETA: ${format(new Date(booking.estimatedTime), 'h:mm a')}`
                              : 'Arriving soon'}
                          </span>
                        )}
                        {booking.cost && (
                          <span className="font-semibold text-gray-600">{formatCurrency(booking.cost)}</span>
                        )}
                      </div>
                      <button
                        onClick={() => handleCancel(booking.id)}
                        className="inline-flex items-center gap-1 rounded-lg bg-red-50 px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-100 transition-colors"
                      >
                        <XCircle size={12} /> Cancel
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── Booking History ──────────────────────────────────────── */}
        <div className="mt-10">
          <h2 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
            <CheckCircle size={18} className="text-emerald-500" /> Booking History
          </h2>

          {/* Filters */}
          <div className="flex flex-wrap gap-3 mb-4">
            <div className="flex items-center gap-2">
              <Filter size={14} className="text-gray-400" />
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value as BookingType | 'all')}
                className="rounded-lg border border-gray-200 bg-white py-1.5 px-3 text-xs text-gray-600 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
              >
                <option value="all">All Types</option>
                {Object.entries(TYPE_CONFIG).map(([key, cfg]) => (
                  <option key={key} value={key}>{cfg.label}</option>
                ))}
              </select>
              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value as BookingStatus | 'all')}
                className="rounded-lg border border-gray-200 bg-white py-1.5 px-3 text-xs text-gray-600 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100"
              >
                <option value="all">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
          </div>

          {/* History Table */}
          <div className="rounded-2xl bg-white shadow-sm ring-1 ring-gray-200/60 overflow-hidden">
            <div className="hidden sm:grid grid-cols-12 gap-4 border-b border-gray-100 px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              <div className="col-span-2">Type</div>
              <div className="col-span-2">Resident</div>
              <div className="col-span-3">Details</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-1">Cost</div>
              <div className="col-span-2">Date</div>
            </div>

            {historyBookings.length === 0 ? (
              <div className="flex flex-col items-center py-12 text-center">
                <Package size={36} className="text-gray-300 mb-3" />
                <p className="text-sm font-medium text-gray-600">No past bookings found</p>
                <p className="text-xs text-gray-400 mt-1">Try adjusting the filters.</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-50">
                {historyBookings.map((booking) => {
                  const resident = residentById(booking.residentId);
                  const typeCfg = TYPE_CONFIG[booking.type];
                  const summary =
                    booking.type === 'transport'
                      ? booking.details.destination
                      : booking.type === 'food_order'
                        ? booking.details.restaurant
                        : booking.type === 'appointment'
                          ? booking.details.doctor
                          : booking.details.store;

                  return (
                    <div
                      key={booking.id}
                      className="grid grid-cols-1 sm:grid-cols-12 gap-2 sm:gap-4 px-6 py-4 hover:bg-gray-50 transition-colors"
                    >
                      <div className="sm:col-span-2 flex items-center gap-2">
                        <typeCfg.icon size={14} className={typeCfg.text} />
                        <span className="text-sm font-medium text-gray-700">{typeCfg.label}</span>
                      </div>
                      <div className="sm:col-span-2 flex items-center">
                        <span className="text-sm text-gray-600 truncate">{resident?.name ?? 'Unknown'}</span>
                      </div>
                      <div className="sm:col-span-3 flex items-center">
                        <span className="text-xs text-gray-500 truncate">{String(summary ?? '')}</span>
                      </div>
                      <div className="sm:col-span-2 flex items-center">
                        <StatusBadge status={booking.status} />
                      </div>
                      <div className="sm:col-span-1 flex items-center">
                        <span className="text-xs text-gray-600">
                          {booking.cost ? formatCurrency(booking.cost) : '—'}
                        </span>
                      </div>
                      <div className="sm:col-span-2 flex items-center justify-between">
                        <span className="text-xs text-gray-400">
                          {format(new Date(booking.requestedAt), 'MMM d')}
                        </span>
                        <ChevronRight size={14} className="text-gray-300 hidden sm:block" />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* ── Footer ─────────────────────────────────────────────── */}
        <div className="mt-12 border-t border-gray-200/60 pt-6 pb-8 text-center">
          <p className="text-xs text-gray-300">
            AETHER Service Bookings · All bookings are simulated for demo purposes
          </p>
        </div>
      </div>
    </div>
  );
}
