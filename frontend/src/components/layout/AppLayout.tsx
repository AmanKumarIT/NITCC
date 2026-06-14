/**
 * AppLayout — Main application shell with sidebar navigation
 * Contains: Left sidebar nav, top header (KPI bar), main content area
 * PRD S2–S12 share this layout
 */

import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useWebSocket } from '@/hooks/useWebSocket'
import { useDashboardStore } from '@/store/dashboardStore'
import { useAuthStore } from '@/store/authStore'
import {
  Map, Bell, AlertTriangle, Package, Activity,
  Satellite, Cloud, BarChart2, Settings, User,
  Train, Wifi, WifiOff, Shield, LogOut, Menu, X, ChevronRight
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { trainsApi, alertsApi, incidentsApi } from '@/services/api'
import clsx from 'clsx'
import { motion, AnimatePresence } from 'framer-motion'

interface NavItem {
  path: string
  label: string
  icon: React.ElementType
  badge?: number
  minRole?: number   // 0=ReadOnly, 1=Op, 2=Super, 3=Emergency, 4=Admin
}

export default function AppLayout() {
  useWebSocket()  // Initialize WebSocket connection
  const { wsConnected, kpis } = useDashboardStore()
  const { user, logout } = useAuthStore()
  const { setTrains, setAlerts, setIncidents } = useDashboardStore()
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const userLevel = user?.maxRoleLevel ?? 0

  // Initial data fetch on mount
  const { data: trainsData } = useQuery({
    queryKey: ['trains'],
    queryFn: () => trainsApi.list({ page_size: 200 }),
    refetchInterval: 60_000,
  })
  const { data: alertsData } = useQuery({
    queryKey: ['alerts', { dismissed: false }],
    queryFn: () => alertsApi.list({ page_size: 200 }),
    refetchInterval: 30_000,
  })
  const { data: incidentsData } = useQuery({
    queryKey: ['incidents', { status: 'active' }],
    queryFn: () => incidentsApi.list({ page_size: 100 }),
    refetchInterval: 30_000,
  })

  useEffect(() => {
    if (trainsData?.data?.data) setTrains(trainsData.data.data)
  }, [trainsData])
  useEffect(() => {
    if (alertsData?.data?.data) setAlerts(alertsData.data.data)
  }, [alertsData])
  useEffect(() => {
    if (incidentsData?.data?.data) setIncidents(incidentsData.data.data)
  }, [incidentsData])

  const navItems: NavItem[] = [
    { path: '/overview', label: 'National Overview', icon: Map, minRole: 0 },
    { path: '/alerts', label: 'Alert Center', icon: Bell, badge: kpis.criticalAlerts, minRole: 1 },
    { path: '/emergency', label: 'Emergency Console', icon: Shield, badge: kpis.activeIncidents, minRole: 3 },
    { path: '/cargo', label: 'Cargo & Logistics', icon: Package, minRole: 1 },
    { path: '/infrastructure', label: 'Infrastructure Health', icon: Activity, minRole: 2 },
    { path: '/satellite', label: 'Satellite Risk', icon: Satellite, minRole: 2 },
    { path: '/weather', label: 'Weather Intelligence', icon: Cloud, minRole: 1 },
    { path: '/analytics', label: 'Analytics & Reports', icon: BarChart2, minRole: 2 },
    { path: '/admin', label: 'Admin Console', icon: Settings, minRole: 4 },
  ]

  const visibleNavItems = navItems.filter(item => userLevel >= (item.minRole ?? 0))

  return (
    <div className="flex h-screen bg-navy-900 overflow-hidden">
      {/* Sidebar */}
      <AnimatePresence>
        <motion.aside
          initial={false}
          animate={{ width: sidebarOpen ? 240 : 64 }}
          transition={{ duration: 0.2, ease: 'easeInOut' }}
          className="flex-shrink-0 flex flex-col border-r border-white/[0.06] bg-navy-900/80 backdrop-blur-sm relative z-20"
        >
          {/* Logo */}
          <div className="flex items-center gap-3 px-4 py-4 border-b border-white/[0.06]">
            <div className="flex-shrink-0 flex items-center justify-center w-9 h-9 rounded-lg bg-electric-500/10 border border-electric-500/20">
              <Train className="w-5 h-5 text-electric-400" />
            </div>
            <AnimatePresence>
              {sidebarOpen && (
                <motion.div
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: 'auto' }}
                  exit={{ opacity: 0, width: 0 }}
                  className="overflow-hidden"
                >
                  <div className="text-sm font-bold text-white whitespace-nowrap">NITCC</div>
                  <div className="text-[10px] text-white/40 whitespace-nowrap">Command Center</div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Navigation */}
          <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto scrollbar-thin">
            {visibleNavItems.map((item) => (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  clsx(isActive ? 'nav-item-active' : 'nav-item', 'relative')
                }
                title={!sidebarOpen ? item.label : undefined}
              >
                <item.icon className="w-4 h-4 flex-shrink-0" />
                {sidebarOpen && (
                  <span className="flex-1 text-sm truncate">{item.label}</span>
                )}
                {item.badge && item.badge > 0 && (
                  <span className={clsx(
                    'flex-shrink-0 flex items-center justify-center rounded-full text-[10px] font-bold bg-critical text-white',
                    sidebarOpen ? 'w-5 h-5' : 'absolute -top-1 -right-1 w-4 h-4'
                  )}>
                    {item.badge > 99 ? '99+' : item.badge}
                  </span>
                )}
              </NavLink>
            ))}
          </nav>

          {/* Bottom: User + WS status */}
          <div className="border-t border-white/[0.06] p-3 space-y-2">
            {/* WS Connection status */}
            <div className={clsx(
              'flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs',
              wsConnected ? 'text-success' : 'text-white/40'
            )}>
              {wsConnected
                ? <><Wifi className="w-3.5 h-3.5 flex-shrink-0" />{sidebarOpen && 'Live Connected'}</>
                : <><WifiOff className="w-3.5 h-3.5 flex-shrink-0" />{sidebarOpen && 'Reconnecting...'}</>
              }
            </div>

            {/* User profile */}
            <NavLink to="/profile" className="nav-item">
              <User className="w-4 h-4 flex-shrink-0" />
              {sidebarOpen && (
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-white/80 truncate">{user?.email?.split('@')[0]}</div>
                  <div className="text-[10px] text-white/40 truncate">{user?.roles?.[0]}</div>
                </div>
              )}
            </NavLink>

            {/* Logout */}
            <button onClick={logout} className="nav-item w-full text-critical/70 hover:text-critical">
              <LogOut className="w-4 h-4 flex-shrink-0" />
              {sidebarOpen && <span>Sign Out</span>}
            </button>
          </div>

          {/* Collapse toggle */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="absolute -right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-navy-800 border border-white/10 flex items-center justify-center text-white/40 hover:text-white hover:border-white/20 transition-all"
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            <ChevronRight className={clsx('w-3 h-3 transition-transform', sidebarOpen && 'rotate-180')} />
          </button>
        </motion.aside>
      </AnimatePresence>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top KPI Bar (FR-03.3 — no scroll required) */}
        <header className="flex-shrink-0 flex items-center gap-4 px-6 py-3 border-b border-white/[0.06] bg-navy-900/60 backdrop-blur-sm">
          {/* KPI Widgets */}
          <div className="flex items-center gap-3 flex-1">
            <KPIWidget
              id="kpi-active-trains"
              label="Active Trains"
              value={kpis.activeTrains}
              icon={Train}
              color="text-electric-400"
            />
            <KPIWidget
              id="kpi-active-incidents"
              label="Active Incidents"
              value={kpis.activeIncidents}
              icon={AlertTriangle}
              color={kpis.activeIncidents > 0 ? 'text-critical' : 'text-white/50'}
              urgent={kpis.activeIncidents > 0}
            />
            <KPIWidget
              id="kpi-critical-alerts"
              label="Critical Alerts"
              value={kpis.criticalAlerts}
              icon={Bell}
              color={kpis.criticalAlerts > 0 ? 'text-critical' : 'text-white/50'}
              urgent={kpis.criticalAlerts > 0}
            />
            <KPIWidget
              id="kpi-nri"
              label="NRI"
              value={`${kpis.nri.toFixed(0)}`}
              icon={Activity}
              color={kpis.nri > 70 ? 'text-critical' : kpis.nri > 40 ? 'text-warn' : 'text-success'}
              suffix="/100"
            />
            <KPIWidget
              id="kpi-uptime"
              label="System Uptime"
              value={`${kpis.systemUptime.toFixed(1)}`}
              icon={Wifi}
              color="text-success"
              suffix="%"
            />
          </div>

          {/* Right side: system time */}
          <div className="text-right">
            <LiveClock />
            <div className="text-[10px] text-white/30">IST (UTC+5:30)</div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Sub-components
// ─────────────────────────────────────────────────────────────────────────────

function KPIWidget({
  id, label, value, icon: Icon, color, urgent, suffix
}: {
  id: string
  label: string
  value: number | string
  icon: React.ElementType
  color: string
  urgent?: boolean
  suffix?: string
}) {
  return (
    <div id={id} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.03] border border-white/[0.05] hover:bg-white/[0.05] cursor-pointer transition-colors">
      <Icon className={clsx('w-3.5 h-3.5', color, urgent && 'animate-pulse')} />
      <div>
        <div className={clsx('text-sm font-bold tabular-nums', color)}>
          {value}{suffix}
        </div>
        <div className="text-[10px] text-white/40 whitespace-nowrap">{label}</div>
      </div>
    </div>
  )
}

function LiveClock() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="text-sm font-mono font-medium text-white/70">
      {time.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false })}
    </div>
  )
}

export { }
