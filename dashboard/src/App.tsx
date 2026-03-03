import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import MonitoringPage from './pages/MonitoringPage';
import TimelinePage from './pages/TimelinePage';
import ResidentsPage from './pages/ResidentsPage';
import AlertsPage from './pages/AlertsPage';
import AnalyticsPage from './pages/AnalyticsPage';
import SettingsPage from './pages/SettingsPage';
import LoginPage from './pages/LoginPage';
import CareNavigationPage from './pages/CareNavigationPage';
import ClinicalDocsPage from './pages/ClinicalDocsPage';
import FleetOpsPage from './pages/FleetOpsPage';
import FamilyPortalPage from './pages/FamilyPortalPage';
import PrescriptionsPage from './pages/PrescriptionsPage';
import EducationPage from './pages/EducationPage';
import BookingsPage from './pages/BookingsPage';
import { AuthProvider, useAuth, canAccess } from './contexts/AuthContext';
import { LiveDataProvider } from './contexts/LiveDataContext';

// ─── Route guards ─────────────────────────────────────────────────────────────

function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

function RequireRole({ children }: { children: ReactNode }) {
  const { role } = useAuth();
  const location = useLocation();

  if (!canAccess(role, location.pathname)) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

function PublicOnly({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <AuthProvider>
      <LiveDataProvider>
      <Routes>
        {/* Public */}
        <Route
          path="/login"
          element={
            <PublicOnly>
              <LoginPage />
            </PublicOnly>
          }
        />

        {/* Protected */}
        <Route
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route path="/" element={<DashboardPage />} />
          <Route path="/monitoring" element={<MonitoringPage />} />
          <Route path="/timeline" element={<TimelinePage />} />
          <Route
            path="/residents"
            element={<RequireRole><ResidentsPage /></RequireRole>}
          />
          <Route
            path="/analytics"
            element={<RequireRole><AnalyticsPage /></RequireRole>}
          />
          <Route
            path="/alerts"
            element={<RequireRole><AlertsPage /></RequireRole>}
          />
          <Route path="/settings" element={<SettingsPage />} />

          {/* New role-specific routes */}
          <Route
            path="/care-navigation"
            element={<RequireRole><CareNavigationPage /></RequireRole>}
          />
          <Route
            path="/clinical-docs"
            element={<RequireRole><ClinicalDocsPage /></RequireRole>}
          />
          <Route
            path="/fleet-ops"
            element={<RequireRole><FleetOpsPage /></RequireRole>}
          />
          <Route
            path="/family"
            element={<RequireRole><FamilyPortalPage /></RequireRole>}
          />
          <Route
            path="/prescriptions"
            element={<RequireRole><PrescriptionsPage /></RequireRole>}
          />
          <Route
            path="/education"
            element={<RequireRole><EducationPage /></RequireRole>}
          />
          <Route
            path="/bookings"
            element={<RequireRole><BookingsPage /></RequireRole>}
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      </LiveDataProvider>
    </AuthProvider>
  );
}
