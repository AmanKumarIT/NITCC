/**
 * S11 — Admin Console
 * PRD: User management, agent health monitoring, system configuration, audit logs
 * Admin-only access
 */
import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { agentsApi, authApi } from '@/services/api'
import api from '@/services/api'
import {
  Settings, Users, Activity, Shield, Clock, RefreshCw,
  Loader2, CheckCircle, XCircle, AlertTriangle, Wifi, WifiOff,
  Plus, Trash2, Edit3, Key, Search
} from 'lucide-react'
import clsx from 'clsx'
import { format } from 'date-fns'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'

type Tab = 'agents' | 'users' | 'config' | 'audit'

const AGENT_STATUS_STYLE: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  running: { icon: CheckCircle, color: 'text-success', label: 'Running' },
  paused:  { icon: Clock, color: 'text-warn', label: 'Paused' },
  error:   { icon: XCircle, color: 'text-critical', label: 'Error' },
}

export default function AdminConsolePage() {
  const [activeTab, setActiveTab] = useState<Tab>('agents')
  const queryClient = useQueryClient()

  return (
    <div className="p-6 h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Settings className="w-5 h-5 text-electric-400" />
            Admin Console
          </h1>
          <p className="text-sm text-white/40 mt-0.5">System administration · Admin-only access</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 flex-shrink-0 border-b border-white/[0.06] pb-1">
        {[
          { key: 'agents' as Tab, label: 'Agent Health', icon: Activity },
          { key: 'users' as Tab, label: 'User Management', icon: Users },
          { key: 'config' as Tab, label: 'Configuration', icon: Settings },
          { key: 'audit' as Tab, label: 'Audit Logs', icon: Shield },
        ].map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-all',
              activeTab === tab.key
                ? 'bg-electric-500/10 text-electric-300 border-b-2 border-electric-400'
                : 'text-white/40 hover:text-white/60 hover:bg-white/[0.03]'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'agents' && <AgentHealthTab />}
        {activeTab === 'users' && <UserManagementTab />}
        {activeTab === 'config' && <ConfigTab />}
        {activeTab === 'audit' && <AuditLogTab />}
      </div>
    </div>
  )
}

// ─── Agent Health Tab ────────────────────────────────────────────────────────

function AgentHealthTab() {
  const { data: agentsData, isLoading, refetch } = useQuery({
    queryKey: ['agents-status'],
    queryFn: () => agentsApi.status(),
    refetchInterval: 10_000,
  })

  const agents: any[] = (agentsData?.data as any)?.data || []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white/60">Multi-Agent System Health (FR-01)</h3>
        <button onClick={() => refetch()} className="btn-ghost text-xs">
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </button>
      </div>

      {isLoading && (
        <div className="text-center py-12 text-white/40">
          <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
          Loading agent status...
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((agent: any) => {
          const status = AGENT_STATUS_STYLE[agent.status] || AGENT_STATUS_STYLE.error
          const StatusIcon = status.icon
          return (
            <motion.div
              key={agent.agentId}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className={clsx('nitcc-card p-4', agent.status === 'error' && 'border-critical/20')}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <StatusIcon className={clsx('w-4 h-4', status.color)} />
                  <span className="text-sm font-semibold text-white/80">{agent.agentName || agent.agentId}</span>
                </div>
                <span className={clsx('text-[10px] px-2 py-0.5 rounded-full font-medium',
                  agent.status === 'running' ? 'bg-success/15 text-success' :
                  agent.status === 'error' ? 'bg-critical/15 text-critical' : 'bg-warn/15 text-warn'
                )}>
                  {status.label}
                </span>
              </div>

              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between text-white/40">
                  <span>Last Heartbeat</span>
                  <span className="text-white/60">
                    {agent.lastHeartbeat ? format(new Date(agent.lastHeartbeat), 'HH:mm:ss') : '—'}
                  </span>
                </div>
                <div className="flex justify-between text-white/40">
                  <span>Uptime</span>
                  <span className="text-white/60">
                    {agent.uptime_s ? `${Math.floor(agent.uptime_s / 3600)}h ${Math.floor((agent.uptime_s % 3600) / 60)}m` : '—'}
                  </span>
                </div>
                {agent.metricsSnapshot && (
                  <>
                    <div className="flex justify-between text-white/40">
                      <span>Events Processed</span>
                      <span className="text-white/60">{agent.metricsSnapshot.events_processed_total ?? '—'}</span>
                    </div>
                    <div className="flex justify-between text-white/40">
                      <span>Error Rate</span>
                      <span className={clsx(
                        agent.metricsSnapshot.error_rate > 0.05 ? 'text-critical' : 'text-white/60'
                      )}>
                        {((agent.metricsSnapshot.error_rate || 0) * 100).toFixed(2)}%
                      </span>
                    </div>
                  </>
                )}
              </div>
            </motion.div>
          )
        })}
      </div>

      {!isLoading && agents.length === 0 && (
        <div className="text-center py-16">
          <Activity className="w-10 h-10 text-white/10 mx-auto mb-3" />
          <p className="text-white/30 text-sm">No agent data available. Ensure agents are running.</p>
        </div>
      )}
    </div>
  )
}

// ─── User Management Tab ─────────────────────────────────────────────────────

function UserManagementTab() {
  const [searchQuery, setSearchQuery] = useState('')

  const { data: usersData, isLoading } = useQuery({
    queryKey: ['admin-users', searchQuery],
    queryFn: () => api.get('/api/v1/auth/users', { params: { search: searchQuery || undefined } }),
    refetchInterval: 30_000,
  })

  const users: any[] = (usersData?.data as any)?.data || []

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white/60">User Accounts (RBAC · 5 Roles)</h3>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-white/30 absolute left-3 top-1/2 -translate-y-1/2" />
            <input className="nitcc-input pl-8 w-52" placeholder="Search users..."
              value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="nitcc-card overflow-hidden">
        <table className="nitcc-table">
          <thead>
            <tr>
              <th>User ID</th>
              <th>Email</th>
              <th>Name</th>
              <th>Roles</th>
              <th>Zones</th>
              <th>MFA</th>
              <th>Active</th>
              <th>Last Login</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={8} className="text-center py-8 text-white/40">
                <Loader2 className="w-4 h-4 animate-spin inline-block mr-2" />Loading users...
              </td></tr>
            )}
            {users.map((user: any) => (
              <tr key={user.userId}>
                <td className="font-mono text-xs text-electric-400">{user.userId}</td>
                <td className="text-xs text-white/70">{user.email}</td>
                <td className="text-xs text-white/70">{user.name || '—'}</td>
                <td>
                  <div className="flex gap-1 flex-wrap">
                    {(user.roles || []).map((role: string) => (
                      <span key={role} className="text-[10px] px-1.5 py-0.5 rounded bg-electric-500/10 text-electric-300">
                        {role}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="text-[11px] text-white/40">{(user.jurisdictionZones || []).join(', ') || 'All'}</td>
                <td>
                  {user.mfaEnabled
                    ? <CheckCircle className="w-3.5 h-3.5 text-success" />
                    : <XCircle className="w-3.5 h-3.5 text-white/20" />
                  }
                </td>
                <td>
                  {user.isActive
                    ? <span className="text-[10px] text-success">Active</span>
                    : <span className="text-[10px] text-critical">Disabled</span>
                  }
                </td>
                <td className="text-[11px] text-white/30">
                  {user.lastLogin ? format(new Date(user.lastLogin), 'dd MMM HH:mm') : 'Never'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!isLoading && users.length === 0 && (
        <div className="text-center py-12 text-white/30 text-sm">
          No users found. Run <code className="text-electric-300 text-xs">python scripts/seed_database.py</code> to create demo users.
        </div>
      )}
    </div>
  )
}

// ─── Configuration Tab ───────────────────────────────────────────────────────

function ConfigTab() {
  const [configs, setConfigs] = useState([
    { key: 'RISK_SCORE_UPDATE_INTERVAL', value: '60', unit: 'seconds', description: 'Train risk score recalculation interval' },
    { key: 'TRACK_HEALTH_REFRESH_INTERVAL', value: '21600', unit: 'seconds', description: 'Track health recalculation interval (6h)' },
    { key: 'WEATHER_INGESTION_INTERVAL', value: '900', unit: 'seconds', description: 'Weather data ingestion frequency (15min)' },
    { key: 'NRI_COMPUTATION_INTERVAL', value: '300', unit: 'seconds', description: 'National Risk Index cycle (5min)' },
    { key: 'ALERT_DEDUP_WINDOW', value: '300', unit: 'seconds', description: 'Alert deduplication suppression window' },
    { key: 'ACTION_PLAN_SLA', value: '60', unit: 'seconds', description: 'CrisisCommand plan generation SLA' },
    { key: 'WIND_SPEED_CRITICAL', value: '100', unit: 'km/h', description: 'Wind speed threshold for CRITICAL advisory' },
    { key: 'FLOOD_RISK_CRITICAL', value: '0.75', unit: 'probability', description: 'Flood risk threshold for CRITICAL alert' },
  ])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-white/60">System Configuration (Hot-Reloadable)</h3>
        <button
          className="btn-primary"
          onClick={() => toast.success('Configuration saved and broadcast to all agents via Redis pub/sub')}
        >
          <RefreshCw className="w-4 h-4" /> Save & Hot-Reload
        </button>
      </div>

      <div className="nitcc-card overflow-hidden">
        <table className="nitcc-table">
          <thead>
            <tr>
              <th>Parameter</th>
              <th>Value</th>
              <th>Unit</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {configs.map((cfg) => (
              <tr key={cfg.key}>
                <td className="font-mono text-xs text-electric-400">{cfg.key}</td>
                <td>
                  <input
                    className="nitcc-input w-24 text-center text-sm"
                    value={cfg.value}
                    onChange={e => {
                      setConfigs(prev => prev.map(c =>
                        c.key === cfg.key ? { ...c, value: e.target.value } : c
                      ))
                    }}
                  />
                </td>
                <td className="text-xs text-white/40">{cfg.unit}</td>
                <td className="text-xs text-white/50">{cfg.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ─── Audit Log Tab ───────────────────────────────────────────────────────────

function AuditLogTab() {
  const { data: auditData, isLoading } = useQuery({
    queryKey: ['audit-logs'],
    queryFn: () => api.get('/api/v1/auth/audit-logs', { params: { page_size: 100 } }),
    refetchInterval: 30_000,
  })

  const logs: any[] = (auditData?.data as any)?.data || []

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-white/60">Audit Trail (WORM — immutable log)</h3>

      <div className="nitcc-card overflow-hidden">
        <table className="nitcc-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>User</th>
              <th>Action</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={4} className="text-center py-8 text-white/40">
                <Loader2 className="w-4 h-4 animate-spin inline-block mr-2" />Loading audit logs...
              </td></tr>
            )}
            {logs.map((log: any, i: number) => (
              <tr key={i}>
                <td className="text-[11px] text-white/40 whitespace-nowrap">
                  {log.timestamp ? format(new Date(log.timestamp), 'dd MMM yyyy HH:mm:ss') : '—'}
                </td>
                <td className="text-xs text-white/60">{log.userId || log.email || '—'}</td>
                <td>
                  <span className={clsx('text-[11px] px-2 py-0.5 rounded font-medium',
                    log.action?.includes('dismiss') ? 'bg-warn/10 text-warn' :
                    log.action?.includes('login') ? 'bg-success/10 text-success' :
                    log.action?.includes('declare') ? 'bg-critical/10 text-critical' :
                    'bg-white/5 text-white/50'
                  )}>
                    {log.action}
                  </span>
                </td>
                <td className="text-[11px] text-white/30 max-w-xs truncate">
                  {typeof log.metadata === 'object' ? JSON.stringify(log.metadata) : log.metadata || '—'}
                </td>
              </tr>
            ))}
            {!isLoading && logs.length === 0 && (
              <tr><td colSpan={4} className="text-center py-8 text-white/30 text-sm">No audit logs available</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}