/**
 * S7 — Infrastructure Health Dashboard
 * PRD FR-07: Track segment list with health score + components, work orders, history trends
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { tracksApi } from '@/services/api'
import {
  Activity, Search, Filter, Loader2, Wrench, AlertTriangle,
  TrendingDown, TrendingUp, Clock, ChevronRight, ChevronDown
} from 'lucide-react'
import clsx from 'clsx'
import { format } from 'date-fns'
import { motion, AnimatePresence } from 'framer-motion'

function getHealthColor(score: number): string {
  if (score >= 80) return '#10B981'
  if (score >= 60) return '#EAB308'
  if (score >= 30) return '#F97316'
  return '#EF4444'
}

function getHealthLabel(score: number): string {
  if (score >= 80) return 'Healthy'
  if (score >= 60) return 'Watch'
  if (score >= 30) return 'Degraded'
  return 'Critical'
}

function getPriority(score: number): { label: string; class: string } {
  if (score < 30) return { label: 'CRITICAL', class: 'text-critical bg-critical/15' }
  if (score < 60) return { label: 'HIGH', class: 'text-orange-400 bg-orange-400/15' }
  if (score < 80) return { label: 'MEDIUM', class: 'text-warn bg-warn/15' }
  return { label: 'LOW', class: 'text-success bg-success/15' }
}

export default function InfrastructureHealthPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [sortField, setSortField] = useState<'healthScore' | 'failureProbability' | 'ageYears'>('healthScore')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [expandedSegment, setExpandedSegment] = useState<string | null>(null)

  // Fetch all track segments
  const { data: tracksData, isLoading } = useQuery({
    queryKey: ['tracks', sortField, sortDir],
    queryFn: () => tracksApi.list({ sort: `${sortDir === 'desc' ? '-' : ''}${sortField}`, page_size: 200 }),
    refetchInterval: 360_000,  // 6 hours (FR-07)
  })

  // Fetch work orders for expanded segment
  const { data: workOrdersData } = useQuery({
    queryKey: ['work-orders', expandedSegment],
    queryFn: () => tracksApi.workOrders(expandedSegment!),
    enabled: !!expandedSegment,
  })

  // Fetch history for expanded segment
  const { data: historyData } = useQuery({
    queryKey: ['track-history', expandedSegment],
    queryFn: () => tracksApi.history(expandedSegment!, 30),
    enabled: !!expandedSegment,
  })

  const segments: any[] = (tracksData?.data as any)?.data || []
  const workOrders: any[] = (workOrdersData?.data as any)?.data || []
  const history: any[] = (historyData?.data as any)?.data || []

  const filteredSegments = segments.filter(s =>
    !searchQuery ||
    s.segmentId?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.fromStation?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    s.toStation?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // Aggregations
  const criticalCount = segments.filter(s => s.healthScore < 30).length
  const degradedCount = segments.filter(s => s.healthScore >= 30 && s.healthScore < 60).length
  const avgHealth = segments.length > 0
    ? segments.reduce((sum, s) => sum + s.healthScore, 0) / segments.length : 0

  const toggleSort = (field: typeof sortField) => {
    if (sortField === field) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortField(field); setSortDir('asc') }
  }

  return (
    <div className="p-6 h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Activity className="w-5 h-5 text-electric-400" />
            Infrastructure Health
          </h1>
          <p className="text-sm text-white/40 mt-0.5">
            FR-07 · {segments.length} segments · 6-hour refresh cycle · Supervisor+ access
          </p>
        </div>
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-white/30 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            className="nitcc-input pl-8 w-60"
            placeholder="Search segment or station..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-4 gap-3 flex-shrink-0">
        <div className="nitcc-card p-3 flex items-center gap-3">
          <Activity className="w-4 h-4 text-electric-400" />
          <div>
            <div className="text-lg font-bold text-electric-400">{segments.length}</div>
            <div className="text-[10px] text-white/40">Total Segments</div>
          </div>
        </div>
        <div className="nitcc-card p-3 flex items-center gap-3">
          <TrendingUp className="w-4 h-4 text-success" />
          <div>
            <div className="text-lg font-bold text-success">{avgHealth.toFixed(0)}</div>
            <div className="text-[10px] text-white/40">Avg Health Score</div>
          </div>
        </div>
        <div className="nitcc-card p-3 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-critical" />
          <div>
            <div className="text-lg font-bold text-critical">{criticalCount}</div>
            <div className="text-[10px] text-white/40">Critical Segments</div>
          </div>
        </div>
        <div className="nitcc-card p-3 flex items-center gap-3">
          <TrendingDown className="w-4 h-4 text-warn" />
          <div>
            <div className="text-lg font-bold text-warn">{degradedCount}</div>
            <div className="text-[10px] text-white/40">Degraded Segments</div>
          </div>
        </div>
      </div>

      {/* Segments Table */}
      <div className="flex-1 overflow-auto nitcc-card">
        <table className="nitcc-table">
          <thead>
            <tr>
              <th className="w-8"></th>
              <th>Segment</th>
              <th>Route</th>
              <th className="cursor-pointer" onClick={() => toggleSort('healthScore')}>
                <span className="flex items-center gap-1">
                  Health Score
                  {sortField === 'healthScore' && (sortDir === 'asc' ? '↑' : '↓')}
                </span>
              </th>
              <th>Status</th>
              <th>Components</th>
              <th className="cursor-pointer" onClick={() => toggleSort('failureProbability')}>
                <span className="flex items-center gap-1">
                  Failure Prob.
                  {sortField === 'failureProbability' && (sortDir === 'asc' ? '↑' : '↓')}
                </span>
              </th>
              <th className="cursor-pointer" onClick={() => toggleSort('ageYears')}>
                <span className="flex items-center gap-1">
                  Age
                  {sortField === 'ageYears' && (sortDir === 'asc' ? '↑' : '↓')}
                </span>
              </th>
              <th>Last Maintenance</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr><td colSpan={9} className="text-center py-12 text-white/40">
                <Loader2 className="w-5 h-5 animate-spin inline-block mr-2" />Loading track data...
              </td></tr>
            )}
            {filteredSegments.map((seg: any) => {
              const isExpanded = expandedSegment === seg.segmentId
              const priority = getPriority(seg.healthScore)
              return (
                <motion.tr
                  key={seg.segmentId}
                  layout
                  className="cursor-pointer"
                  onClick={() => setExpandedSegment(isExpanded ? null : seg.segmentId)}
                >
                  <td>
                    <ChevronRight className={clsx('w-3.5 h-3.5 text-white/30 transition-transform', isExpanded && 'rotate-90')} />
                  </td>
                  <td className="font-mono text-xs text-electric-400">{seg.segmentId}</td>
                  <td className="text-xs text-white/70">{seg.fromStation} → {seg.toStation}</td>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="w-12 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{
                          width: `${seg.healthScore}%`,
                          backgroundColor: getHealthColor(seg.healthScore)
                        }} />
                      </div>
                      <span className="text-sm font-bold tabular-nums" style={{ color: getHealthColor(seg.healthScore) }}>
                        {seg.healthScore?.toFixed(0)}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className={clsx('text-[10px] px-2 py-0.5 rounded-full font-semibold', priority.class)}>
                      {getHealthLabel(seg.healthScore)}
                    </span>
                  </td>
                  <td>
                    <div className="flex gap-1">
                      {['structural_integrity', 'environmental_stress', 'operational_load', 'maintenance_recency'].map(k => {
                        const val = seg.healthComponents?.[k] || 0
                        return (
                          <div key={k} className="w-2 h-6 rounded-sm bg-white/10 overflow-hidden flex flex-col-reverse" title={`${k}: ${val.toFixed(0)}`}>
                            <div className="rounded-sm" style={{
                              height: `${val}%`,
                              backgroundColor: getHealthColor(val)
                            }} />
                          </div>
                        )
                      })}
                    </div>
                  </td>
                  <td className={clsx('text-xs tabular-nums', seg.failureProbability > 0.3 ? 'text-critical' : 'text-white/50')}>
                    {(seg.failureProbability * 100).toFixed(1)}%
                  </td>
                  <td className="text-xs text-white/50">{seg.ageYears?.toFixed(0)} yrs</td>
                  <td className="text-[11px] text-white/30">
                    {seg.lastMaintenanceDate ? format(new Date(seg.lastMaintenanceDate), 'dd MMM yyyy') : '—'}
                  </td>
                </motion.tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Expanded detail panel */}
      <AnimatePresence>
        {expandedSegment && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="flex-shrink-0 grid grid-cols-2 gap-4"
          >
            {/* Work Orders */}
            <div className="nitcc-card p-4">
              <h3 className="section-heading flex items-center gap-2">
                <Wrench className="w-3.5 h-3.5" /> Work Orders for {expandedSegment}
              </h3>
              {workOrders.length > 0 ? (
                <div className="space-y-2 max-h-40 overflow-y-auto scrollbar-thin">
                  {workOrders.map((wo: any) => (
                    <div key={wo.workOrderId} className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.05]">
                      <div>
                        <div className="text-xs font-medium text-white/80">{wo.recommendedAction}</div>
                        <div className="text-[10px] text-white/30">{wo.workOrderId} · Est: {wo.estimatedDuration}</div>
                      </div>
                      <span className={clsx('text-[10px] px-2 py-0.5 rounded-full', getPriority(
                        wo.priority === 'CRITICAL' ? 10 : wo.priority === 'HIGH' ? 40 : 70
                      ).class)}>
                        {wo.priority}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-white/30 py-4 text-center">No work orders for this segment</p>
              )}
            </div>

            {/* Health History */}
            <div className="nitcc-card p-4">
              <h3 className="section-heading flex items-center gap-2">
                <Clock className="w-3.5 h-3.5" /> Health History (30 days)
              </h3>
              {history.length > 0 ? (
                <div className="flex items-end gap-1 h-28 px-2">
                  {history.slice(-30).map((point: any, i: number) => (
                    <div
                      key={i}
                      className="flex-1 rounded-t-sm transition-all hover:opacity-80"
                      style={{
                        height: `${point.healthScore || 0}%`,
                        backgroundColor: getHealthColor(point.healthScore || 0),
                        minWidth: '4px',
                      }}
                      title={`${point.date}: ${point.healthScore?.toFixed(0)}`}
                    />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-white/30 py-4 text-center">No history data available</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}