import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from 'react';
import type { User, UserRole } from '../types';
import { DEMO_USERS } from '../data/mockData';

// ─── Types ────────────────────────────────────────────────────────────────────

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  role: UserRole | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const STORAGE_KEY = 'aether_auth_user';
const DEMO_PASSWORD = 'demo123';

// ─── Context ──────────────────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ─── Provider ─────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? (JSON.parse(stored) as User) : null;
    } catch {
      return null;
    }
  });

  // Persist to localStorage whenever user changes
  useEffect(() => {
    if (user) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [user]);

  const login = useCallback(async (email: string, password: string) => {
    // Simulate network delay for realism
    await new Promise((r) => setTimeout(r, 800));

    if (password !== DEMO_PASSWORD) {
      throw new Error('Invalid credentials. Use password "demo123" for demo accounts.');
    }

    const match = DEMO_USERS.find(
      (u) => u.email.toLowerCase() === email.trim().toLowerCase(),
    );

    if (!match) {
      throw new Error('No account found with that email. Try a demo account below.');
    }

    setUser(match);
  }, []);

  const logout = useCallback(() => {
    setUser(null);
  }, []);

  const value: AuthContextValue = {
    user,
    isAuthenticated: !!user,
    role: user?.role ?? null,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ─── Hook ─────────────────────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}

// ─── Role helpers ─────────────────────────────────────────────────────────────

/** Routes each role is allowed to access (path prefixes). */
const ROLE_ROUTES: Record<UserRole, string[]> = {
  elder: ['/', '/monitoring', '/timeline', '/settings', '/prescriptions', '/education', '/bookings'],
  caregiver: ['/', '/monitoring', '/timeline', '/residents', '/alerts', '/analytics', '/settings', '/care-navigation'],
  doctor: ['/', '/monitoring', '/timeline', '/residents', '/alerts', '/analytics', '/settings', '/clinical-docs', '/prescriptions', '/care-navigation'],
  ops: ['/', '/monitoring', '/timeline', '/residents', '/alerts', '/analytics', '/settings', '/fleet-ops', '/family'],
};

export function canAccess(role: UserRole | null, path: string): boolean {
  if (!role) return false;
  const allowed = ROLE_ROUTES[role];
  return allowed.some((r) => path === r || path.startsWith(r + '/'));
}

export function getDefaultRoute(_role: UserRole): string {
  return '/';
}
