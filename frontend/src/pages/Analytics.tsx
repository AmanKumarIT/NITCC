/**
 * S10 — Analytics & Reports
 * PRD FR-09, FR-10: NRI trend chart, risk distribution, alert analytics,
 * report generation, downloadable exports
 */
import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { reportsApi } from '@/services/api'
import { useDashboardStore } from '@/store/dashboardStore'
import {
  BarChart2, TrendingUp, TrendingDown, PieChart, FileText,
  Download, Loader2, Calendar, RefreshCw, AlertTriangle,
  Activity, Train, Shield
} from 'lucide-react'
import clsx from 'clsx'
import { format, subDays } from 'date-fns'
import { motion } from 'framer-motion'
import toast from 'react-hot-toast'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart as RePieChart, Pie, Cell,
  LineChart, Line, Legend
} from 'recharts'

const CHART_COLORS = ['#1E6FD9', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#F97316']
const PIE_COLORS = ['#EF4444', '#F97316', '#F59E0B', '#10B981']

export default function AnalyticsPage() {
  const { kpis, alerts, incidents, trains } = useDashboardStore()
  const [reportType, setReportType] = useState('daily_summary')
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d'>('30d')

  // Report generation
  const generateReport = useMutation({
    mutationFn: (body: Record<string, unknown>) => reportsApi.generate(body),
    onSuccess: (data) => {
      const reportId = (data.data as any)?.data?.reportId
      toast.success(`Report generated: ${reportId}`)
    },
    onError: () => toast.error('Report generation failed'),
  })

  // Mock NRI trend data (in production, fetched from API)
  const nriTrendData = Array.from({ length: 30 }, (_, i) => ({
    date: format(subDays(new Date(), 29 - i), 'dd MMM'),
    nri: Math.round(30 + Math.random() * 40 + (i > 20 ? 15 : 0)),
    p1: Math.floor(Math.random() * 3),
    p2: Math.floor(Math.random() * 5),
  }))

  // Alert distribution by severity
  const alertDistribution = [
    { name: 'CRITICAL', value: alerts.filter(a => a.severity === 'CRITICAL' && !a.dismissedAt).length, color: '#EF4444' },
    { name: 'WARN', value: alerts.filter(a => a.severity === 'WARN' && !a.dismissedAt).length, color: '#F59E0B' },
    { name: 'INFO', value: alerts.filter(a => a.severity === 'INFO' && !a.dismissedAt).length, color: '#3B82F6' },
  ].filter(d => d.value > 0)

  // Alert by domain
  const domainDistribution = [
    { name: 'Operational', value: alerts.filter(a => a.domain === 'operational').length },
    { name: 'Environmental', value: alerts.filter(a => a.domain === 'environmental').length },
    { name: 'Logistics', value: alerts.filter(a => a.domain === 'logistics').length },
    { name: 'Emergency', value: alerts.filter(a => a.domain === 'emergency').length },
  ].filter(d => d.value > 0)

  // Train risk distribution
  const riskBuckets = [
    { range: '0–25', count: trains.filter(t => t.riskScore <= 25).length },
    { range: '26–50', count: trains.filter(t => t.riskScore > 25 && t.riskScore <= 50).length },
    { range: '51–75', count: trains.filter(t => t.riskScore > 50 && t.riskScore <= 75).length },
    { range: '76–100', count: trains.filter(t => t.riskScore > 75).length },
  ]

  // Incident counts by severity
  const incidentBySeverity = [
    { severity: 'P1', active: incidents.filter(i => i.severity === 'P1' && i.status !== 'resolved').length },
    { severity: 'P2', active: incidents.filter(i => i.severity === 'P2' && i.status !== 'resolved').length },
    { severity: 'P3', active: incidents.filter(i => i.severity === 'P3' && i.status !== 'resolved').length },
    { severity: 'P4', active: incidents.filter(i => i.severity === 'P4' && i.status !== 'resolved').length },
  ]

  return (
    <div className="p-6 h-full overflow-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-electric-400" />
            Analytics & Reports
          </h1>
          <p className="text-sm text-white/40 mt-0.5">
            FR-09/FR-10 · NRI trends, risk analytics, report export · Supervisor+ access
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Date range selector */}
          <div className="flex gap-1">
            {(['7d', '30d', '90d'] as const).map(range => (
              <button key={range}
                onClick={() => setDateRange(range)}
                className={clsx('text-xs px-3 py-1.5 rounded-md transition-all',
                  dateRange === range
                    ? 'bg-electric-500/20 text-electric-300 border border-electric-500/30'
                    : 'text-white/40 hover:text-white/60'
                )}>
                {range}
              </button>
            ))}
          </div>

          {/* Generate report */}
          <div className="flex items-center gap-2">
            <select className="nitcc-input w-40" value={reportType} onChange={e => setReportType(e.target.value)}>
              <option value="daily_summary">Daily Summary</option>
              <option value="risk_analysis">Risk Analysis</option>
              <option value="incident_report">Incident Report</option>
              <option value="infrastructure_audit">Infrastructure Audit</option>
            </select>
            <button
              className="btn-primary"
              disabled={generateReport.isPending}
              onClick={() => generateReport.mutate({
                type: reportType,
                date_range: dateRange,
                format: 'pdf',
              })}
            >
              {generateReport.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              Generate
            </button>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-6">
        {/* NRI Trend Chart */}
        <div className="nitcc-card p-5 lg:col-span-2">
          <h3 className="section-heading flex items-center gap-2 mb-4">
            <Activity className="w-3.5 h-3.5" /> National Risk Index (NRI) Trend — {dateRange}
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={nriTrendData} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="nriGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#1E6FD9" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#1E6FD9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" stroke="rgba(255,255,255,0.2)" fontSize={10} />
                <YAxis stroke="rgba(255,255,255,0.2)" fontSize={10} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: '#162338', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                  labelStyle={{ color: 'rgba(255,255,255,0.6)' }}
                  itemStyle={{ color: 'rgba(255,255,255,0.8)' }}
                />
                <Area type="monotone" dataKey="nri" stroke="#1E6FD9" fill="url(#nriGrad)" strokeWidth={2} name="NRI Score" />
                <Line type="monotone" dataKey="p1" stroke="#EF4444" strokeWidth={1} dot={false} name="P1 Incidents" />
                <Line type="monotone" dataKey="p2" stroke="#F97316" strokeWidth={1} dot={false} name="P2 Incidents" />
                <Legend wrapperStyle={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Alert Severity Distribution */}
        <div className="nitcc-card p-5">
          <h3 className="section-heading flex items-center gap-2 mb-4">
            <AlertTriangle className="w-3.5 h-3.5" /> Alert Severity Distribution
          </h3>
          <div className="h-48">
            {alertDistribution.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <RePieChart>
                  <Pie data={alertDistribution} dataKey="value" nameKey="name"
                    cx="50%" cy="50%" innerRadius={40} outerRadius={70}
                    strokeWidth={0}>
                    {alertDistribution.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: '#162338', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }} />
                </RePieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-white/20 text-sm">No active alerts</div>
            )}
          </div>
        </div>

        {/* Train Risk Histogram */}
        <div className="nitcc-card p-5">
          <h3 className="section-heading flex items-center gap-2 mb-4">
            <Train className="w-3.5 h-3.5" /> Train Risk Score Distribution
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={riskBuckets} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="range" stroke="rgba(255,255,255,0.2)" fontSize={10} />
                <YAxis stroke="rgba(255,255,255,0.2)" fontSize={10} />
                <Tooltip
                  contentStyle={{ background: '#162338', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                />
                <Bar dataKey="count" name="Trains" radius={[4, 4, 0, 0]}>
                  {riskBuckets.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Alert by Domain */}
        <div className="nitcc-card p-5">
          <h3 className="section-heading flex items-center gap-2 mb-4">
            <PieChart className="w-3.5 h-3.5" /> Alerts by Domain
          </h3>
          <div className="h-48">
            {domainDistribution.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={domainDistribution} layout="vertical" margin={{ top: 5, right: 10, left: 50, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis type="number" stroke="rgba(255,255,255,0.2)" fontSize={10} />
                  <YAxis type="category" dataKey="name" stroke="rgba(255,255,255,0.3)" fontSize={11} />
                  <Tooltip
                    contentStyle={{ background: '#162338', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                  />
                  <Bar dataKey="value" name="Alerts" fill="#1E6FD9" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-white/20 text-sm">No alert data</div>
            )}
          </div>
        </div>

        {/* Active Incidents by Severity */}
        <div className="nitcc-card p-5">
          <h3 className="section-heading flex items-center gap-2 mb-4">
            <Shield className="w-3.5 h-3.5" /> Active Incidents by Severity
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={incidentBySeverity} margin={{ top: 5, right: 10, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="severity" stroke="rgba(255,255,255,0.3)" fontSize={11} />
                <YAxis stroke="rgba(255,255,255,0.2)" fontSize={10} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: '#162338', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }}
                />
                <Bar dataKey="active" name="Active" radius={[4, 4, 0, 0]}>
                  {incidentBySeverity.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}