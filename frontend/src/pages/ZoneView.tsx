/**
 * S3 — Zone / Corridor Drill-Down
 * PRD FR-03.1: Corridor-level view with train list, track health segments,
 * weather conditions, and risk aggregation for a selected zone.
 */
import { useState, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { trainsApi, tracksApi, weatherApi } from '@/services/api'
import { useDashboardStore } from '@/store/dashboardStore'
import {
  Map, Train, Activity, AlertTriangle, Cloud, Thermometer,
  Wind, Eye, Droplets, ArrowLeft, ChevronRight, Search
} from 'lucide-react'
import clsx from 'clsx'
import { motion } from 'framer-motion'

const CORRIDORS = [
  { id: 'DELHI-MUMBAI', name: 'Delhi–Mumbai Corridor', color: '#1E6FD9' },
  { id: 'DELHI-KOLKATA', name: 'Delhi–Kolkata Corridor', color: '#10B981' },
  { id: 'DELHI-CHENNAI', name: 'Delhi–Chennai Corridor', color: '#F59E0B' },
  { id: 'MUMBAI-CHENNAI', name: 'Mumbai–Chennai Corridor', color: '#8B5CF6' },
  { id: 'KOLKATA-CHENNAI', name: 'Kolkata–Chennai Corridor', color: '#EF4444' },
]

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

export default function ZoneViewPage() {
  const { zoneId } = useParams<{ zoneId?: string }>()
  const navigate = useNavigate()
  const [selectedCorridor, setSelectedCorridor] = useState(zoneId || '')
  const [searchQuery, setSearchQuery] = useState('')
  const { trains, alerts } = useDashboardStore()

  const activeCorridor = selectedCorridor || zoneId || ''

  // Fetch track segments for this corridor
  const { data: tracksData } = useQuery({
    queryKey: ['tracks', activeCorridor],
    queryFn: () => tracksApi.list({ corridorId: activeCorridor, page_size: 100 }),
    enabled: !!activeCorridor,
    refetchInterval: 60_000,
  })

  // Fetch weather for this corridor
  const { data: weatherData } = useQuery({
    queryKey: ['weather', activeCorridor],
    queryFn: () => weatherApi.corridors({ corridorId: activeCorridor }),
    enabled: !!activeCorridor,
    refetchInterval: 60_000,
  })

  // Filter trains for this corridor
  const corridorTrains = useMemo(() =>
    trains.filter(t => t.corridorId === activeCorridor)
      .filter(t =>
        !searchQuery || t.trainId.toLowerCase().includes(searchQuery.toLowerCase())
      )
      .sort((a, b) => b.riskScore - a.riskScore),
    [trains, activeCorridor, searchQuery]
  )

  const corridorAlerts = useMemo(() =>
    alerts.filter(a => !a.dismissedAt && (a as any).corridorId === activeCorridor),
    [alerts, activeCorridor]
  )

  const segments = (tracksData?.data as any)?.data || []
  const weather = (weatherData?.data as any)?.data || []

  // Corridor aggregate stats
  const avgHealth = segments.length > 0
    ? segments.reduce((sum: number, s: any) => sum + (s.healthScore || 0), 0) / segments.length
    : 0
  const avgRisk = corridorTrains.length > 0
    ? corridorTrains.reduce((sum, t) => sum + t.riskScore, 0) / corridorTrains.length
    : 0

  // If no corridor selected, show corridor selector
  if (!activeCorridor) {
    return (
      <div className="p-6 h-full">
        <h1 className="text-xl font-bold text-white mb-1 flex items-center gap-2">
          <Map className="w-5 h-5 text-electric-400" />
          Zone / Corridor View
        </h1>
        <p className="text-sm text-white/40 mb-6">Select a corridor to drill down into detailed view</p>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {CORRIDORS.map(corridor => {
            const ct = trains.filter(t => t.corridorId === corridor.id)
            const ca = alerts.filter(a => !a.dismissedAt && a.severity === 'CRITICAL')
            return (
              <motion.button
                key={corridor.id}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => {
                  setSelectedCorridor(corridor.id)
                  navigate(`/zones/${corridor.id}`)
                }}
                className="nitcc-card p-5 text-left"
              >
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: corridor.color }} />
                  <h3 className="text-sm font-semibold text-white">{corridor.name}</h3>
                </div>
                <div className="grid grid-cols-3 gap-3 text-center">
                  <div>
                    <div className="text-lg font-bold text-electric-400">{ct.length}</div>
                    <div className="text-[10px] text-white/40">Trains</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-white/80">
                      {ct.length > 0 ? (ct.reduce((s, t) => s + t.riskScore, 0) / ct.length).toFixed(0) : '—'}
                    </div>
                    <div className="text-[10px] text-white/40">Avg Risk</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-warn">{ca.length}</div>
                    <div className="text-[10px] text-white/40">Alerts</div>
                  </div>
                </div>
              </motion.button>
            )
          })}
        </div>
      </div>
    )
  }

  const corridorMeta = CORRIDORS.find(c => c.id === activeCorridor)

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/[0.06] flex items-center gap-4">
        <button onClick={() => { setSelectedCorridor(''); navigate('/zones') }}
          className="btn-icon">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: corridorMeta?.color }} />
          <div>
            <h1 className="text-base font-bold text-white">{corridorMeta?.name || activeCorridor}</h1>
            <p className="text-xs text-white/40">{corridorTrains.length} trains · {segments.length} track segments</p>
          </div>
        </div>

        {/* Search */}
        <div className="ml-auto relative">
          <Search className="w-3.5 h-3.5 text-white/30 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            className="nitcc-input pl-8 w-52"
            placeholder="Search train ID..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {/* KPI Row */}
        <div className="grid grid-cols-5 gap-3 mb-6">
          <StatCard label="Active Trains" value={corridorTrains.length} icon={Train} color="text-electric-400" />
          <StatCard label="Avg Risk" value={avgRisk.toFixed(0)} suffix="/100" icon={AlertTriangle}
            color={avgRisk > 70 ? 'text-critical' : avgRisk > 40 ? 'text-warn' : 'text-success'} />
          <StatCard label="Avg Track Health" value={avgHealth.toFixed(0)} suffix="/100" icon={Activity}
            color={avgHealth >= 80 ? 'text-success' : avgHealth >= 60 ? 'text-warn' : 'text-critical'} />
          <StatCard label="Critical Alerts" value={corridorAlerts.filter(a => a.severity === 'CRITICAL').length}
            icon={AlertTriangle} color="text-critical" />
          <StatCard label="Track Segments" value={segments.length} icon={Map} color="text-white/60" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Train List */}
          <div className="nitcc-card p-4">
            <h3 className="section-heading flex items-center gap-2">
              <Train className="w-3.5 h-3.5" /> Active Trains
            </h3>
            <div className="space-y-1.5 max-h-[400px] overflow-y-auto scrollbar-thin">
              {corridorTrains.map(train => (
                <div key={train.trainId}
                  className="flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-white/[0.03] transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getHealthColor(100 - train.riskScore) }} />
                    <div>
                      <div className="text-sm font-medium text-white/80">{train.trainId}</div>
                      <div className="text-[11px] text-white/30">{train.status} · {train.speedKmh.toFixed(0)} km/h</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold tabular-nums" style={{ color: getHealthColor(100 - train.riskScore) }}>
                      {train.riskScore.toFixed(0)}
                    </div>
                    <div className="text-[10px] text-white/30">Risk</div>
                  </div>
                </div>
              ))}
              {corridorTrains.length === 0 && (
                <p className="text-center text-white/30 text-xs py-8">No trains in this corridor</p>
              )}
            </div>
          </div>

          {/* Track Health */}
          <div className="nitcc-card p-4">
            <h3 className="section-heading flex items-center gap-2">
              <Activity className="w-3.5 h-3.5" /> Track Health Segments
            </h3>
            <div className="space-y-1.5 max-h-[400px] overflow-y-auto scrollbar-thin">
              {segments.map((seg: any) => (
                <div key={seg.segmentId}
                  className="flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-white/[0.03] transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: getHealthColor(seg.healthScore) }} />
                    <div>
                      <div className="text-sm text-white/80">{seg.fromStation} → {seg.toStation}</div>
                      <div className="text-[11px] text-white/30">{seg.segmentId}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold tabular-nums" style={{ color: getHealthColor(seg.healthScore) }}>
                      {seg.healthScore.toFixed(0)}
                    </div>
                    <div className="text-[10px] text-white/30">{getHealthLabel(seg.healthScore)}</div>
                  </div>
                </div>
              ))}
              {segments.length === 0 && (
                <p className="text-center text-white/30 text-xs py-8">No track data available</p>
              )}
            </div>
          </div>

          {/* Weather Conditions */}
          <div className="nitcc-card p-4 lg:col-span-2">
            <h3 className="section-heading flex items-center gap-2">
              <Cloud className="w-3.5 h-3.5" /> Corridor Weather Conditions
            </h3>
            {weather.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {weather.slice(0, 8).map((w: any, i: number) => (
                  <div key={i} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.05]">
                    <div className="text-xs text-white/40 mb-2 truncate">{w.corridorId || `Waypoint ${i + 1}`}</div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="flex items-center gap-1">
                        <Thermometer className="w-3 h-3 text-orange-400" />
                        <span className="text-white/70">{w.temperature?.toFixed(0) || '—'}°C</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Wind className="w-3 h-3 text-blue-400" />
                        <span className="text-white/70">{w.windSpeed?.toFixed(0) || '—'} km/h</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Droplets className="w-3 h-3 text-cyan-400" />
                        <span className="text-white/70">{w.precipitation?.toFixed(0) || '—'} mm</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <Eye className="w-3 h-3 text-gray-400" />
                        <span className="text-white/70">{w.visibility?.toFixed(1) || '—'} km</span>
                      </div>
                    </div>
                    {w.floodRisk > 0.5 && (
                      <div className="mt-2 text-[10px] text-critical font-semibold flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        Flood Risk: {(w.floodRisk * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center text-white/30 text-xs py-8">No weather data for this corridor</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function StatCard({ label, value, suffix, icon: Icon, color }: {
  label: string; value: number | string; suffix?: string; icon: React.ElementType; color: string
}) {
  return (
    <div className="nitcc-card p-3 flex items-center gap-3">
      <Icon className={clsx('w-4 h-4 flex-shrink-0', color)} />
      <div>
        <div className={clsx('text-lg font-bold tabular-nums', color)}>{value}{suffix}</div>
        <div className="text-[10px] text-white/40">{label}</div>
      </div>
    </div>
  )
}