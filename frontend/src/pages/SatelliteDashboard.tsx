/**
 * S8 — Satellite Risk Dashboard
 * PRD FR-04: GeoJSON risk zone list with tier classification,
 * change detection status, analysis date, and risk type filtering
 */
import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { satelliteApi } from '@/services/api'
import {
  Satellite, AlertTriangle, Loader2, Filter,
  MapPin, Calendar, Eye, Layers, Mountain, Droplets, Building, TrendingDown
} from 'lucide-react'
import clsx from 'clsx'
import { format } from 'date-fns'
import { motion } from 'framer-motion'

const RISK_TIER_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  CRITICAL: { bg: 'bg-critical/15', text: 'text-critical', border: 'border-critical/30' },
  HIGH:     { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/30' },
  MEDIUM:   { bg: 'bg-warn/15', text: 'text-warn', border: 'border-warn/30' },
  LOW:      { bg: 'bg-electric-500/15', text: 'text-electric-400', border: 'border-electric-500/30' },
}

const RISK_TYPE_ICON: Record<string, React.ElementType> = {
  landslide: Mountain,
  flood: Droplets,
  encroachment: Building,
  erosion: TrendingDown,
}

export default function SatelliteDashboardPage() {
  const [tierFilter, setTierFilter] = useState<string>('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [changeOnly, setChangeOnly] = useState(false)

  // Fetch risk zones
  const { data: zonesData, isLoading } = useQuery({
    queryKey: ['satellite-risk-zones', tierFilter, typeFilter],
    queryFn: () => satelliteApi.riskZones({
      riskTier: tierFilter || undefined,
      riskType: typeFilter || undefined,
      page_size: 200,
    }),
    refetchInterval: 3_600_000,  // hourly
  })

  const allZones: any[] = (zonesData?.data as any)?.data || []
  const zones = useMemo(() => {
    let filtered = allZones
    if (changeOnly) filtered = filtered.filter(z => z.changeDetected)
    return filtered
  }, [allZones, changeOnly])

  // Aggregation
  const criticalZones = allZones.filter(z => z.riskTier === 'CRITICAL').length
  const highZones = allZones.filter(z => z.riskTier === 'HIGH').length
  const changesDetected = allZones.filter(z => z.changeDetected).length

  return (
    <div className="p-6 h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Satellite className="w-5 h-5 text-electric-400" />
            Satellite Risk Dashboard
          </h1>
          <p className="text-sm text-white/40 mt-0.5">
            FR-04 · {allZones.length} risk zones · Daily analysis · Supervisor+ access
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Tier filter */}
          <select className="nitcc-input w-32" value={tierFilter} onChange={e => setTierFilter(e.target.value)}>
            <option value="">All Tiers</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          {/* Type filter */}
          <select className="nitcc-input w-36" value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
            <option value="">All Types</option>
            <option value="landslide">Landslide</option>
            <option value="flood">Flood</option>
            <option value="encroachment">Encroachment</option>
            <option value="erosion">Erosion</option>
          </select>

          {/* Change detection toggle */}
          <button
            onClick={() => setChangeOnly(!changeOnly)}
            className={clsx('text-xs px-3 py-2 rounded-lg border transition-all',
              changeOnly
                ? 'bg-warn/10 text-warn border-warn/20'
                : 'text-white/40 border-white/10 hover:border-white/20'
            )}
          >
            <Eye className="w-3.5 h-3.5 inline-block mr-1" />
            Changes Only
          </button>
        </div>
      </div>

      {/* KPI Summary */}
      <div className="grid grid-cols-4 gap-3 flex-shrink-0">
        <div className="nitcc-card p-3 flex items-center gap-3">
          <Layers className="w-4 h-4 text-electric-400" />
          <div>
            <div className="text-lg font-bold text-electric-400">{allZones.length}</div>
            <div className="text-[10px] text-white/40">Total Risk Zones</div>
          </div>
        </div>
        <div className="nitcc-card p-3 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-critical" />
          <div>
            <div className="text-lg font-bold text-critical">{criticalZones}</div>
            <div className="text-[10px] text-white/40">Critical Zones</div>
          </div>
        </div>
        <div className="nitcc-card p-3 flex items-center gap-3">
          <AlertTriangle className="w-4 h-4 text-orange-400" />
          <div>
            <div className="text-lg font-bold text-orange-400">{highZones}</div>
            <div className="text-[10px] text-white/40">High Risk Zones</div>
          </div>
        </div>
        <div className="nitcc-card p-3 flex items-center gap-3">
          <Eye className="w-4 h-4 text-warn" />
          <div>
            <div className="text-lg font-bold text-warn">{changesDetected}</div>
            <div className="text-[10px] text-white/40">Changes Detected</div>
          </div>
        </div>
      </div>

      {/* Risk Zone Cards */}
      <div className="flex-1 overflow-auto">
        {isLoading && (
          <div className="text-center py-16 text-white/40">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-3" />
            Fetching satellite risk zones from SatEye Agent...
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {zones.map((zone: any) => {
            const style = RISK_TIER_STYLE[zone.riskTier] || RISK_TIER_STYLE.LOW
            const TypeIcon = RISK_TYPE_ICON[zone.riskType] || Satellite
            return (
              <motion.div
                key={zone.zoneId}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={clsx('nitcc-card p-4 border', style.border)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <TypeIcon className={clsx('w-4 h-4', style.text)} />
                    <div>
                      <div className="text-sm font-semibold text-white/80">{zone.zoneId}</div>
                      <div className="text-[11px] text-white/40 capitalize">{zone.riskType}</div>
                    </div>
                  </div>
                  <span className={clsx('text-[10px] px-2 py-0.5 rounded-full font-bold', style.bg, style.text)}>
                    {zone.riskTier}
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  {/* Change detection */}
                  {zone.changeDetected && (
                    <div className="flex items-center gap-2 p-2 rounded-lg bg-warn/5 border border-warn/10">
                      <Eye className="w-3.5 h-3.5 text-warn" />
                      <span className="text-warn font-medium">Change Detected</span>
                      {zone.ndviChange && (
                        <span className="text-white/40 ml-auto">NDVI: {zone.ndviChange.toFixed(3)}</span>
                      )}
                    </div>
                  )}

                  {/* Metadata */}
                  <div className="flex items-center justify-between text-white/40">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {zone.analysisDate ? format(new Date(zone.analysisDate), 'dd MMM yyyy') : '—'}
                    </span>
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      {zone.source || zone.dataSource || 'satellite'}
                    </span>
                  </div>

                  {/* Confidence */}
                  {zone.confidenceScore && (
                    <div className="flex items-center gap-2">
                      <span className="text-white/40">Confidence:</span>
                      <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-electric-400" style={{ width: `${zone.confidenceScore * 100}%` }} />
                      </div>
                      <span className="text-white/60 tabular-nums">{(zone.confidenceScore * 100).toFixed(0)}%</span>
                    </div>
                  )}

                  {/* Image ID */}
                  {zone.imageId && (
                    <div className="text-[10px] text-white/20 truncate">
                      Image: {zone.imageId}
                    </div>
                  )}
                </div>
              </motion.div>
            )
          })}
        </div>

        {!isLoading && zones.length === 0 && (
          <div className="text-center py-20">
            <Satellite className="w-12 h-12 text-white/[0.08] mx-auto mb-4" />
            <p className="text-white/30 text-sm">No risk zones matching current filters</p>
          </div>
        )}
      </div>
    </div>
  )
}