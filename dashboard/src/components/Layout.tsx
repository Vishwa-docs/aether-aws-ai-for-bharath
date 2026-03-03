import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Activity,
  Clock,
  Users,
  BarChart3,
  Bell,
  Settings,
  ChevronRight,
  Shield,
  Heart,
  Pill,
  MessageCircle,
  ShoppingBag,
  Compass,
  FileText,
  ClipboardList,
  Home,
  GraduationCap,
  Server,
  MapPin,
  Menu,
  X,
  Search,
  LogOut,
  ChevronDown,
  AlertTriangle,
  Wifi,
  CheckCircle2,
} from 'lucide-react';
import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useLiveData } from '../contexts/LiveDataContext';
import { getActiveAlerts, getCommandCenterData } from '../data/mockData';
import DemoPanel from './DemoPanel';
import type { UserRole } from '../types';
import type { CommandCenterData } from '../types';

// ─── Navigation Definitions ──────────────────────────────────────────────────

interface NavItem {
  label: string;
  path: string;
  icon: React.ElementType;
  badge?: 'alerts';
}

const ELDER_NAV: NavItem[] = [
  { label: 'Home', path: '/', icon: LayoutDashboard },
  { label: 'My Health', path: '/timeline', icon: Heart },
  { label: 'Medications', path: '/residents', icon: Pill },
  { label: 'Companion', path: '/care-navigation', icon: MessageCircle },
  { label: 'Services', path: '/bookings', icon: ShoppingBag },
  { label: 'Settings', path: '/settings', icon: Settings },
];

const CAREGIVER_NAV: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard },
  { label: 'Monitoring', path: '/monitoring', icon: Activity },
  { label: 'Timeline', path: '/timeline', icon: Clock },
  { label: 'Residents', path: '/residents', icon: Users },
  { label: 'Alerts', path: '/alerts', icon: Bell, badge: 'alerts' },
  { label: 'Analytics', path: '/analytics', icon: BarChart3 },
  { label: 'Care Navigation', path: '/care-navigation', icon: Compass },
  { label: 'Clinical Docs', path: '/clinical-docs', icon: FileText },
  { label: 'Prescriptions', path: '/prescriptions', icon: ClipboardList },
  { label: 'Family Portal', path: '/family', icon: Home },
  { label: 'Education', path: '/education', icon: GraduationCap },
  { label: 'Settings', path: '/settings', icon: Settings },
];

const DOCTOR_NAV: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard },
  { label: 'Patients', path: '/residents', icon: Users },
  { label: 'Clinical Docs', path: '/clinical-docs', icon: FileText },
  { label: 'Prescriptions', path: '/prescriptions', icon: ClipboardList },
  { label: 'Analytics', path: '/analytics', icon: BarChart3 },
  { label: 'Settings', path: '/settings', icon: Settings },
];

const OPS_NAV: NavItem[] = [
  { label: 'Dashboard', path: '/', icon: LayoutDashboard },
  { label: 'Fleet & Ops', path: '/fleet-ops', icon: Server },
  { label: 'Analytics', path: '/analytics', icon: BarChart3 },
  { label: 'Alerts', path: '/alerts', icon: Bell, badge: 'alerts' },
  { label: 'Monitoring', path: '/monitoring', icon: Activity },
  { label: 'Sites', path: '/fleet-ops', icon: MapPin },
  { label: 'Settings', path: '/settings', icon: Settings },
];

const ROLE_NAV: Record<UserRole, NavItem[]> = {
  elder: ELDER_NAV,
  caregiver: CAREGIVER_NAV,
  doctor: DOCTOR_NAV,
  ops: OPS_NAV,
};

const ROLE_LABELS: Record<UserRole, string> = {
  elder: 'Elder',
  caregiver: 'Caregiver',
  doctor: 'Physician',
  ops: 'Operations',
};

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/monitoring': 'Live Monitoring',
  '/timeline': 'Timeline',
  '/residents': 'Residents',
  '/analytics': 'Analytics',
  '/alerts': 'Alerts',
  '/settings': 'Settings',
  '/care-navigation': 'Care Navigation',
  '/clinical-docs': 'Clinical Documents',
  '/prescriptions': 'Prescriptions',
  '/fleet-ops': 'Fleet Operations',
  '/family': 'Family Portal',
  '/education': 'Health Education',
  '/bookings': 'Service Bookings',
};

// ─── Command Center Strip ────────────────────────────────────────────────────

function CommandCenterStrip() {
  const navigate = useNavigate();
  const [data, setData] = useState<CommandCenterData>(() => getCommandCenterData());
  const { apiConnected, lastUpdated, residents } = useLiveData();

  useEffect(() => {
    const interval = setInterval(() => {
      setData(getCommandCenterData());
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  const lastUpdatedStr = useMemo(() => {
    const d = new Date(data.lastUpdated);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }, [data.lastUpdated]);

  const criticalCount = data.criticalAlerts.length;

  return (
    <div className="flex h-9 items-center justify-between bg-gray-900 px-4 text-xs">
      <div className="flex items-center gap-5">
        {/* Critical Alerts */}
        <button
          onClick={() => navigate('/alerts')}
          className="group flex items-center gap-1.5 transition-colors hover:text-white"
        >
          <AlertTriangle className="h-3.5 w-3.5 text-red-400" />
          <span className="text-gray-400 group-hover:text-gray-200">Critical</span>
          <span
            className={[
              'flex h-5 min-w-[20px] items-center justify-center rounded-full px-1.5 text-[11px] font-bold text-white',
              criticalCount > 0 ? 'alert-pulse bg-red-500' : 'bg-gray-600',
            ].join(' ')}
          >
            {criticalCount}
          </span>
        </button>

        {/* Unresolved Meds */}
        <button
          onClick={() => navigate('/prescriptions')}
          className="group flex items-center gap-1.5 transition-colors hover:text-white"
        >
          <Pill className="h-3.5 w-3.5 text-orange-400" />
          <span className="text-gray-400 group-hover:text-gray-200">Med Issues</span>
          <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-orange-500 px-1.5 text-[11px] font-bold text-white">
            {data.unresolvedMeds}
          </span>
        </button>

        {/* Pending Approvals */}
        <button
          onClick={() => navigate('/clinical-docs')}
          className="group flex items-center gap-1.5 transition-colors hover:text-white"
        >
          <CheckCircle2 className="h-3.5 w-3.5 text-yellow-400" />
          <span className="text-gray-400 group-hover:text-gray-200">Approvals</span>
          <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-yellow-500 px-1.5 text-[11px] font-bold text-gray-900">
            {data.pendingApprovals}
          </span>
        </button>

        {/* Connectivity */}
        <button
          onClick={() => navigate('/monitoring')}
          className="group flex items-center gap-1.5 transition-colors hover:text-white"
        >
          <Wifi className="h-3.5 w-3.5 text-gray-400" />
          <span className="text-gray-400 group-hover:text-gray-200">Connectivity</span>
          <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-gray-600 px-1.5 text-[11px] font-bold text-white">
            {data.connectivityIncidents}
          </span>
        </button>
      </div>

      {/* API Status + Last Updated */}
      <div className="flex items-center gap-3 text-gray-500">
        {apiConnected ? (
          <span className="flex items-center gap-1.5 text-emerald-400 text-[10px] font-medium">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
            </span>
            AWS Live · {residents.length} residents
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-yellow-400 text-[10px] font-medium">
            <span className="h-1.5 w-1.5 rounded-full bg-yellow-500" />
            Demo Mode
          </span>
        )}
        <span className="text-gray-600">|</span>
        <div className="flex items-center gap-1.5">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-green-500" />
          </span>
          <span>Updated {lastUpdatedStr}</span>
        </div>
      </div>
    </div>
  );
}

// ─── User Dropdown ───────────────────────────────────────────────────────────

function UserDropdown() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  if (!user) return null;

  const initials = user.name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-lg p-1.5 transition-colors hover:bg-gray-100"
      >
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-aether-100 text-sm font-semibold text-aether-700">
          {initials}
        </div>
        <div className="hidden flex-col items-start md:flex">
          <span className="text-sm font-medium text-gray-900">{user.name}</span>
          <span className="text-[11px] text-gray-400">{ROLE_LABELS[user.role]}</span>
        </div>
        <ChevronDown className="hidden h-4 w-4 text-gray-400 md:block" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-56 rounded-lg border border-gray-200 bg-white py-1 shadow-lg animate-fade-in">
          <div className="border-b border-gray-100 px-4 py-3">
            <p className="text-sm font-medium text-gray-900">{user.name}</p>
            <p className="text-xs text-gray-500">{user.email}</p>
          </div>
          <button
            onClick={() => {
              setOpen(false);
              logout();
            }}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-red-600 transition-colors hover:bg-red-50"
          >
            <LogOut className="h-4 w-4" />
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Layout ──────────────────────────────────────────────────────────────────

export default function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, role, logout } = useAuth();

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Close mobile sidebar on route change
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  // Responsive: collapse sidebar on small screens
  useEffect(() => {
    const mql = window.matchMedia('(max-width: 1024px)');
    const handler = (e: MediaQueryListEvent | MediaQueryList) => {
      if (e.matches) {
        setSidebarOpen(false);
      } else {
        setSidebarOpen(true);
      }
    };
    handler(mql);
    mql.addEventListener('change', handler);
    return () => mql.removeEventListener('change', handler);
  }, []);

  const navItems = useMemo(() => ROLE_NAV[role ?? 'caregiver'], [role]);
  const activeAlerts = useMemo(() => getActiveAlerts(), []);
  const alertCount = activeAlerts.filter((a) => a.is_active).length;
  const currentPage = PAGE_TITLES[location.pathname] ?? 'Page';
  const showCommandCenter = role === 'caregiver' || role === 'doctor' || role === 'ops';

  const initials = useMemo(() => {
    if (!user) return '??';
    return user.name
      .split(' ')
      .map((w) => w[0])
      .join('')
      .slice(0, 2)
      .toUpperCase();
  }, [user]);

  const sidebarWidth = sidebarOpen ? 'w-64' : 'w-16';
  const contentPadding = sidebarOpen ? 'pl-64' : 'pl-16';

  const toggleSidebar = useCallback(() => setSidebarOpen((v) => !v), []);

  // ── Render ──

  return (
    <div className="flex h-screen flex-col bg-gray-50">
      {/* ── Command Center Strip ─────────────────────────────── */}
      {showCommandCenter && <CommandCenterStrip />}

      <div className="flex flex-1 overflow-hidden">
        {/* ── Mobile overlay ─────────────────────────────────── */}
        {mobileOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/40 lg:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}

        {/* ── Sidebar ──────────────────────────────────────────── */}
        <aside
          className={[
            'fixed inset-y-0 left-0 z-50 flex flex-col bg-gray-900 transition-all duration-300 ease-in-out',
            showCommandCenter ? 'top-9' : 'top-0',
            // Desktop: controlled width
            sidebarWidth,
            // Mobile: slide in/out
            mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
          ].join(' ')}
        >
          {/* Brand */}
          <div className="flex h-14 items-center gap-3 px-4">
            <Shield className="h-7 w-7 flex-shrink-0 text-aether-400" />
            {sidebarOpen && (
              <div className="flex flex-col overflow-hidden transition-opacity duration-200">
                <span className="text-base font-bold tracking-wide text-white">AETHER</span>
                <span className="text-[9px] font-medium uppercase tracking-widest text-gray-500">
                  Care Platform
                </span>
              </div>
            )}
          </div>

          {/* User info */}
          {sidebarOpen && user && (
            <div className="mx-3 mb-3 rounded-lg bg-gray-800/60 px-3 py-2.5">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-aether-600/30 text-xs font-bold text-aether-300">
                  {initials}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-200">{user.name}</p>
                  <span className="inline-flex items-center rounded-full bg-aether-600/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-aether-400">
                    {ROLE_LABELS[user.role]}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Divider */}
          <div className="mx-3 border-t border-gray-700/40" />

          {/* Navigation */}
          <nav className="mt-2 flex flex-1 flex-col gap-0.5 overflow-y-auto px-2">
            {navItems.map(({ label, path, icon: Icon, badge }) => {
              const showBadge = badge === 'alerts' && alertCount > 0;
              return (
                <NavLink
                  key={label + path}
                  to={path}
                  end={path === '/'}
                  title={sidebarOpen ? undefined : label}
                  className={({ isActive }) =>
                    [
                      'group relative flex items-center gap-3 rounded-lg text-sm font-medium transition-all duration-150',
                      sidebarOpen ? 'px-3 py-2.5' : 'justify-center px-0 py-2.5',
                      isActive
                        ? 'bg-aether-600/20 text-aether-400'
                        : 'text-gray-400 hover:bg-gray-800 hover:text-white',
                    ].join(' ')
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span className="absolute left-0 top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full bg-aether-400" />
                      )}
                      <Icon
                        className={[
                          'h-5 w-5 flex-shrink-0 transition-colors',
                          isActive ? 'text-aether-400' : 'text-gray-500 group-hover:text-gray-300',
                        ].join(' ')}
                      />
                      {sidebarOpen && <span className="flex-1 truncate">{label}</span>}
                      {sidebarOpen && showBadge && (
                        <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1.5 text-[11px] font-semibold text-white">
                          {alertCount}
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>

          {/* Logout */}
          <div className="mx-2 mb-3 mt-1">
            <button
              onClick={logout}
              title={sidebarOpen ? undefined : 'Sign Out'}
              className={[
                'flex w-full items-center gap-3 rounded-lg py-2.5 text-sm font-medium text-gray-400 transition-colors hover:bg-gray-800 hover:text-red-400',
                sidebarOpen ? 'px-3' : 'justify-center px-0',
              ].join(' ')}
            >
              <LogOut className="h-5 w-5 flex-shrink-0" />
              {sidebarOpen && <span>Sign Out</span>}
            </button>
          </div>
        </aside>

        {/* ── Main Area ────────────────────────────────────────── */}
        <div className={['flex flex-1 flex-col transition-all duration-300', contentPadding].join(' ')}>
          {/* Header Bar */}
          <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6">
            <div className="flex items-center gap-4">
              {/* Sidebar toggle / hamburger */}
              <button
                onClick={() => {
                  // Desktop: toggle collapse; Mobile: toggle overlay
                  const isMobile = window.innerWidth < 1024;
                  if (isMobile) {
                    setMobileOpen(!mobileOpen);
                  } else {
                    toggleSidebar();
                  }
                }}
                className="rounded-lg p-1.5 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
                aria-label="Toggle sidebar"
              >
                {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </button>

              {/* Breadcrumb */}
              <div className="hidden items-center gap-2 text-sm sm:flex">
                <span className="font-medium text-gray-400">AETHER</span>
                <ChevronRight className="h-3.5 w-3.5 text-gray-300" />
                <span className="font-semibold text-gray-900">{currentPage}</span>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Search */}
              <div className="relative hidden md:block">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search residents, events..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-9 w-64 rounded-lg border border-gray-200 bg-gray-50 pl-9 pr-3 text-sm placeholder-gray-400 transition-colors focus:border-aether-400 focus:bg-white focus:outline-none focus:ring-1 focus:ring-aether-400"
                />
              </div>

              {/* Notification bell */}
              <button
                onClick={() => navigate('/alerts')}
                className="relative rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
                aria-label="Notifications"
              >
                <Bell className="h-5 w-5" />
                {alertCount > 0 && (
                  <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                    {alertCount}
                  </span>
                )}
              </button>

              {/* Divider */}
              <div className="h-8 w-px bg-gray-200" />

              {/* User dropdown */}
              <UserDropdown />
            </div>
          </header>

          {/* Page Content */}
          <main className="flex-1 overflow-y-auto p-4 pb-20 sm:p-6 lg:p-8 lg:pb-8">
            <Outlet />
          </main>
        </div>
      </div>

      {/* ── Mobile Bottom Tab Bar ─────────────────────────────── */}
      <MobileTabBar navItems={navItems} alertCount={alertCount} />

      {/* Live Demo Panel */}
      <DemoPanel />
    </div>
  );
}

// ─── Mobile Bottom Tab Bar ────────────────────────────────────────────────────

function MobileTabBar({ navItems, alertCount }: { navItems: NavItem[]; alertCount: number }) {
  // Show max 5 items on mobile tab bar (first 4 + last item as "More")
  const visibleItems = navItems.slice(0, 5);

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-gray-200 bg-white/95 backdrop-blur-lg lg:hidden safe-area-bottom">
      <div className="flex items-center justify-around px-1 py-1">
        {visibleItems.map(({ label, path, icon: Icon, badge }) => {
          const showBadge = badge === 'alerts' && alertCount > 0;
          return (
            <NavLink
              key={label + path}
              to={path}
              end={path === '/'}
              className={({ isActive }) =>
                [
                  'flex flex-col items-center justify-center gap-0.5 px-2 py-1.5 rounded-lg min-w-[56px] text-center transition-colors',
                  isActive
                    ? 'text-aether-600'
                    : 'text-gray-400',
                ].join(' ')
              }
            >
              {({ isActive }) => (
                <>
                  <div className="relative">
                    <Icon
                      className={[
                        'h-5 w-5',
                        isActive ? 'text-aether-600' : 'text-gray-400',
                      ].join(' ')}
                    />
                    {showBadge && (
                      <span className="absolute -right-1.5 -top-1 flex h-3.5 min-w-[14px] items-center justify-center rounded-full bg-red-500 px-0.5 text-[8px] font-bold text-white">
                        {alertCount}
                      </span>
                    )}
                  </div>
                  <span className={[
                    'text-[10px] font-medium leading-tight truncate max-w-[56px]',
                    isActive ? 'text-aether-600 font-semibold' : 'text-gray-400',
                  ].join(' ')}>
                    {label}
                  </span>
                  {isActive && (
                    <span className="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 w-6 rounded-b-full bg-aether-500" />
                  )}
                </>
              )}
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}
