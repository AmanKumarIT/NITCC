import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

// Layouts
import AppLayout from '@/components/layout/AppLayout'
import AuthLayout from '@/components/layout/AuthLayout'

// Pages (S1–S12)
import LoginPage from '@/pages/Login'
import NationalOverviewPage from '@/pages/NationalOverview'
import ZoneViewPage from '@/pages/ZoneView'
import AlertCenterPage from '@/pages/AlertCenter'
import EmergencyConsolePage from '@/pages/EmergencyConsole'
import CargoLogisticsPage from '@/pages/CargoLogistics'
import InfrastructureHealthPage from '@/pages/InfrastructureHealth'
import SatelliteDashboardPage from '@/pages/SatelliteDashboard'
import WeatherPanelPage from '@/pages/WeatherPanel'
import AnalyticsPage from '@/pages/Analytics'
import AdminConsolePage from '@/pages/AdminConsole'
import UserProfilePage from '@/pages/UserProfile'

// Route guard component
function RequireAuth({ children, minRole }: { children: React.ReactNode; minRole?: string }) {
  const { isAuthenticated, user } = useAuthStore()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (minRole && user?.maxRoleLevel !== undefined) {
    const roleLevels: Record<string, number> = {
      ReadOnly: 0, Operator: 1, Supervisor: 2, Emergency: 3, Admin: 4
    }
    const required = roleLevels[minRole] ?? 0
    if ((user.maxRoleLevel ?? 0) < required) {
      return <Navigate to="/" replace />
    }
  }
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      {/* Auth routes (S1) */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
      </Route>

      {/* Protected application routes */}
      <Route element={
        <RequireAuth>
          <AppLayout />
        </RequireAuth>
      }>
        {/* S2 — National Overview (default) */}
        <Route index element={<NationalOverviewPage />} />
        <Route path="overview" element={<NationalOverviewPage />} />

        {/* S3 — Zone/Corridor Drill-Down (Operator+) */}
        <Route path="zones/:zoneId?" element={
          <RequireAuth minRole="Operator"><ZoneViewPage /></RequireAuth>
        } />

        {/* S4 — Alert Center (Operator+) */}
        <Route path="alerts" element={
          <RequireAuth minRole="Operator"><AlertCenterPage /></RequireAuth>
        } />

        {/* S5 — Emergency Response Console (Emergency+) */}
        <Route path="emergency" element={
          <RequireAuth minRole="Emergency"><EmergencyConsolePage /></RequireAuth>
        } />
        <Route path="emergency/:incidentId" element={
          <RequireAuth minRole="Emergency"><EmergencyConsolePage /></RequireAuth>
        } />

        {/* S6 — Cargo & Logistics (Operator+) */}
        <Route path="cargo" element={
          <RequireAuth minRole="Operator"><CargoLogisticsPage /></RequireAuth>
        } />

        {/* S7 — Infrastructure Health (Supervisor+) */}
        <Route path="infrastructure" element={
          <RequireAuth minRole="Supervisor"><InfrastructureHealthPage /></RequireAuth>
        } />

        {/* S8 — Satellite Risk Dashboard (Supervisor+) */}
        <Route path="satellite" element={
          <RequireAuth minRole="Supervisor"><SatelliteDashboardPage /></RequireAuth>
        } />

        {/* S9 — Weather Intelligence (Operator+) */}
        <Route path="weather" element={
          <RequireAuth minRole="Operator"><WeatherPanelPage /></RequireAuth>
        } />

        {/* S10 — Analytics & Reports (Supervisor+) */}
        <Route path="analytics" element={
          <RequireAuth minRole="Supervisor"><AnalyticsPage /></RequireAuth>
        } />

        {/* S11 — Admin Console (Admin only) */}
        <Route path="admin" element={
          <RequireAuth minRole="Admin"><AdminConsolePage /></RequireAuth>
        } />

        {/* S12 — User Profile (All authenticated) */}
        <Route path="profile" element={<UserProfilePage />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
