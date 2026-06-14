/**
 * S6 — Cargo & Logistics Dashboard
 * PRD FR-08: Wagon tracking table, route optimization panel, delay predictions
 */
import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { cargoApi } from '@/services/api'
import {
  Package, Truck, MapPin, Clock, AlertTriangle,
  ArrowRight, Search, Filter, Loader2, RefreshCw, Route
} from 'lucide-react'
import clsx from 'clsx'
import { format } from 'date-fns'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'

const STATUS_STYLE: Record<string, { bg: string; text: string; label: string }> = {
  in_transit:  { bg: 'bg-electric-500/15', text: 'text-electric-400', label: 'In Transit' },
  at_terminal: { bg: 'bg-success/15', text: 'text-success', label: 'At Terminal' },
  delayed:     { bg: 'bg-warn/15', text: 'text-warn', label: 'Delayed' },
  held:        { bg: 'bg-critical/15', text: 'text-critical', label: 'Held' },
  rerouted:    { bg: 'bg-purple-500/15', text: 'text-purple-400', label: 'Rerouted' },
  delivered:   { bg: 'bg-success/15', text: 'text-success', label: 'Delivered' },
}

export default function CargoLogisticsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(1)
  const [showRoutePanel, setShowRoutePanel] = useState(false)
  const [routeOrigin, setRouteOrigin] = useState('Delhi')
  const [routeDestination, setRouteDestination] = useState('Mumbai')

  // Fetch wagons
  const { data: wagonsData, isLoading } = useQuery({
    queryKey: ['wagons', statusFilter, searchQuery, page],
    queryFn: () => cargoApi.wagons({
      status: statusFilter || undefined,
      search: searchQuery || undefined,
      page,
      page_size: 50,
    }),
    refetchInterval: 30_000,
  })

  // Route recommendation mutation
  const routeMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => cargoApi.recommend(body),
    onSuccess: () => toast.success('Route recommendation computed by CargoFlow Agent'),
    onError: () => toast.error('Route optimization failed'),
  })

  const wagons = (wagonsData?.data as any)?.data || []
  const total = (wagonsData?.data as any)?.total || 0
  const routeResult = routeMutation.data?.data as any

  return (
    <div className="p-6 h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Package className="w-5 h-5 text-electric-400" />
            Cargo & Logistics
          </h1>
          <p className="text-sm text-white/40 mt-0.5">
            FR-08 · {total} wagons tracked · Operator+ access
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-white/30 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              className="nitcc-input pl-8 w-48"
              placeholder="Search wagon ID..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
          </div>

          {/* Status filter */}
          <select
            className="nitcc-input w-36"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            <option value="">All Status</option>
            <option value="in_transit">In Transit</option>
            <option value="at_terminal">At Terminal</option>
            <option value="delayed">Delayed</option>
            <option value="held">Held</option>
            <option value="rerouted">Rerouted</option>
            <option value="delivered">Delivered</option>
          </select>

          {/* Route optimization button */}
          <button
            className="btn-primary"
            onClick={() => setShowRoutePanel(!showRoutePanel)}
          >
            <Route className="w-4 h-4" />
            RouteOptima
          </button>
        </div>
      </div>

      {/* Route Optimization Panel */}
      <AnimatePresence>
        {showRoutePanel && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="nitcc-card p-5 flex-shrink-0"
          >
            <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <Route className="w-4 h-4 text-electric-400" />
              RouteOptima — Intelligent Route Recommendation (FR-08.2)
            </h3>
            <div className="flex items-end gap-4">
              <div className="flex-1">
                <label className="text-xs text-white/40 uppercase tracking-wider mb-1 block">Origin</label>
                <input className="nitcc-input" value={routeOrigin} onChange={e => setRouteOrigin(e.target.value)} />
              </div>
              <ArrowRight className="w-5 h-5 text-white/30 mb-2 flex-shrink-0" />
              <div className="flex-1">
                <label className="text-xs text-white/40 uppercase tracking-wider mb-1 block">Destination</label>
                <input className="nitcc-input" value={routeDestination} onChange={e => setRouteDestination(e.target.value)} />
              </div>
              <button
                className="btn-primary h-10 px-6"
                disabled={routeMutation.isPending}
                onClick={() => routeMutation.mutate({ origin: routeOrigin, destination: routeDestination, reason: 'manual_request' })}
              >
                {routeMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                Compute Route
              </button>
            </div>

            {/* Route result */}
            {routeResult?.data && (
              <div className="mt-4 grid grid-cols-2 gap-4">
                <div className="p-3 rounded-lg border border-electric-500/20 bg-electric-500/5">
                  <div className="text-xs text-electric-400 font-semibold mb-2">Primary Route</div>
                  <div className="text-sm text-white/80 font-medium">{routeResult.data.primaryRoute?.name}</div>
                  <div className="text-xs text-white/40 mt-1">
                    {routeResult.data.primaryRoute?.distance_km} km · {routeResult.data.primaryRoute?.estimatedTime}
                  </div>
                  <div className="text-[10px] text-white/30 mt-1">
                    Segments: {routeResult.data.primaryRoute?.segments?.join(' → ')}
                  </div>
                </div>
                {routeResult.data.alternativeRoutes?.map((alt: any, i: number) => (
                  <div key={i} className="p-3 rounded-lg border border-white/10 bg-white/[0.02]">
                    <div className="text-xs text-white/50 font-semibold mb-2">Alternative {i + 1}</div>
                    <div className="text-sm text-white/70">{alt.name}</div>
                    <div className="text-xs text-white/40 mt-1">
                      {alt.distance_km} km · {alt.estimatedTime}
                    </div>
                    <div className="text-[10px] text-white/30 mt-1">
                      Segments: {alt.segments?.join(' → ')}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Wagon Table */}
      <div className="flex-1 overflow-auto nitcc-card">
        <table className="nitcc-table">
          <thead>
            <tr>
              <th>Wagon ID</th>
              <th>Train</th>
              <th>Origin</th>
              <th>Destination</th>
              <th>Status</th>
              <th>ETA</th>
              <th>Exceptions</th>
              <th>Last Updated</th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <tr>
                <td colSpan={8} className="text-center py-12 text-white/40">
                  <Loader2 className="w-5 h-5 animate-spin inline-block mr-2" />
                  Loading wagon data...
                </td>
              </tr>
            )}
            {wagons.map((wagon: any) => {
              const ss = STATUS_STYLE[wagon.status] || STATUS_STYLE.in_transit
              const hasExceptions = wagon.exceptions?.some((e: any) => !e.resolved)
              return (
                <tr key={wagon.wagonId} className={clsx(hasExceptions && 'border-l-2 border-l-warn')}>
                  <td className="font-mono font-medium text-electric-400 text-xs">{wagon.wagonId}</td>
                  <td className="text-white/60 text-xs">{wagon.trainId || '—'}</td>
                  <td>
                    <div className="flex items-center gap-1.5">
                      <MapPin className="w-3 h-3 text-success" />
                      <span className="text-xs text-white/70">{wagon.origin}</span>
                    </div>
                  </td>
                  <td>
                    <div className="flex items-center gap-1.5">
                      <MapPin className="w-3 h-3 text-critical" />
                      <span className="text-xs text-white/70">{wagon.destination}</span>
                    </div>
                  </td>
                  <td>
                    <span className={clsx('text-[11px] px-2 py-0.5 rounded-full font-medium', ss.bg, ss.text)}>
                      {ss.label}
                    </span>
                  </td>
                  <td className="text-xs text-white/50">
                    {wagon.eta ? format(new Date(wagon.eta), 'dd MMM HH:mm') : '—'}
                  </td>
                  <td>
                    {hasExceptions ? (
                      <span className="flex items-center gap-1 text-warn text-xs">
                        <AlertTriangle className="w-3 h-3" />
                        {wagon.exceptions.filter((e: any) => !e.resolved).length}
                      </span>
                    ) : (
                      <span className="text-xs text-success/50">None</span>
                    )}
                  </td>
                  <td className="text-[11px] text-white/30">
                    {wagon.updatedAt ? format(new Date(wagon.updatedAt), 'HH:mm:ss') : '—'}
                  </td>
                </tr>
              )
            })}
            {!isLoading && wagons.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center py-16 text-white/30">
                  <Package className="w-10 h-10 mx-auto mb-3 opacity-20" />
                  No wagons matching filters
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="flex items-center justify-between pt-2 flex-shrink-0">
          <span className="text-xs text-white/40">
            Showing {(page - 1) * 50 + 1}–{Math.min(page * 50, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button className="btn-ghost text-xs px-3 py-1.5" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
              ← Previous
            </button>
            <button className="btn-ghost text-xs px-3 py-1.5" disabled={page * 50 >= total} onClick={() => setPage(p => p + 1)}>
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}