/**
 * S9 — Weather Intelligence Panel
 * PRD FR-05: Corridor weather conditions, IMD alerts,
 * impact forecast, advisory generation status
 */
import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { weatherApi } from '@/services/api'
import {
  Cloud, Thermometer, Wind, Eye, Droplets, AlertTriangle,
  Loader2, Waves, Sun, Snowflake, CloudRain, CloudLightning,
  MapPin, RefreshCw
} from 'lucide-react'
import clsx from 'clsx'
import { format } from 'date-fns'
import { motion } from 'framer-motion'

function getWindSeverity(speed: number): { color: string; label: string } {
  if (speed > 100) return { color: 'text-critical', label: 'Extreme' }
  if (speed > 60) return { color: 'text-warn', label: 'High' }
  if (speed > 30) return { color: 'text-electric-400', label: 'Moderate' }
  return { color: 'text-success', label: 'Calm' }
}

function getVisibilitySeverity(km: number): { color: string; label: string } {
  if (km < 0.5) return { color: 'text-critical', label: 'Dense Fog' }
  if (km < 1) return { color: 'text-warn', label: 'Low' }
  if (km < 3) return { color: 'text-electric-400', label: 'Reduced' }
  return { color: 'text-success', label: 'Clear' }
}

function getPrecipSeverity(mm: number): { color: string; label: string } {
  if (mm > 50) return { color: 'text-critical', label: 'Extreme Rain' }
  if (mm > 20) return { color: 'text-warn', label: 'Heavy Rain' }
  if (mm > 5) return { color: 'text-electric-400', label: 'Moderate' }
  if (mm > 0) return { color: 'text-white/60', label: 'Light' }
  return { color: 'text-success', label: 'Dry' }
}

function getFloodColor(risk: number): string {
  if (risk > 0.75) return '#EF4444'
  if (risk > 0.5) return '#F97316'
  if (risk > 0.25) return '#F59E0B'
  return '#10B981'
}

export default function WeatherPanelPage() {
  const [selectedCorridor, setSelectedCorridor] = useState<string>('')

  // Fetch corridor weather readings
  const { data: weatherData, isLoading, refetch } = useQuery({
    queryKey: ['weather-corridors', selectedCorridor],
    queryFn: () => weatherApi.corridors({
      corridorId: selectedCorridor || undefined,
      page_size: 200,
    }),
    refetchInterval: 60_000,  // 1 minute
  })

  const readings: any[] = (weatherData?.data as any)?.data || []

  // Group by corridor
  const corridorGroups = useMemo(() => {
    const groups: Record<string, any[]> = {}
    readings.forEach(r => {
      const key = r.corridorId || 'Unknown'
      if (!groups[key]) groups[key] = []
      groups[key].push(r)
    })
    return groups
  }, [readings])

  // Aggregate stats
  const maxWind = readings.length > 0 ? Math.max(...readings.map(r => r.windSpeed || 0)) : 0
  const maxPrecip = readings.length > 0 ? Math.max(...readings.map(r => r.precipitation || 0)) : 0
  const minVisibility = readings.length > 0 ? Math.min(...readings.map(r => r.visibility || 15)) : 15
  const maxFloodRisk = readings.length > 0 ? Math.max(...readings.map(r => r.floodRisk || 0)) : 0
  const avgTemp = readings.length > 0
    ? readings.reduce((s, r) => s + (r.temperature || 0), 0) / readings.length : 0

  const corridors = Object.keys(corridorGroups)

  return (
    <div className="p-6 h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Cloud className="w-5 h-5 text-electric-400" />
            Weather Intelligence
          </h1>
          <p className="text-sm text-white/40 mt-0.5">
            FR-05 · {readings.length} readings across {corridors.length} corridors · 15-min refresh · Operator+ access
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select className="nitcc-input w-44" value={selectedCorridor} onChange={e => setSelectedCorridor(e.target.value)}>
            <option value="">All Corridors</option>
            {corridors.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <button onClick={() => refetch()} className="btn-ghost">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* KPI Summary */}
      <div className="grid grid-cols-5 gap-3 flex-shrink-0">
        <div className="nitcc-card p-3 flex items-center gap-3">
          <Thermometer className="w-4 h-4 text-orange-400" />
          <div>
            <div className="text-lg font-bold text-orange-400">{avgTemp.toFixed(0)}°C</div>
            <div className="text-[10px] text-white/40">Avg Temperature</div>
          </div>
        </div>
        <div className="nitcc-card p-3 flex items-center gap-3">
          <Wind className={clsx('w-4 h-4', getWindSeverity(maxWind).color)} />
          <div>
            <div className={clsx('text-lg font-bold', getWindSeverity(maxWind).color)}>{maxWind.toFixed(0)} km/h</div>
            <div className="text-[10px] text-white/40">Max Wind Speed</div>
          </div>
        </div>
        <div className="nitcc-card p-3 flex items-center gap-3">
          <CloudRain className={clsx('w-4 h-4', getPrecipSeverity(maxPrecip).color)} />
          <div>
            <div className={clsx('text-lg font-bold', getPrecipSeverity(maxPrecip).color)}>{maxPrecip.toFixed(0)} mm/h</div>
            <div className="text-[10px] text-white/40">Max Precipitation</div>
          </div>
        </div>
        <div className="nitcc-card p-3 flex items-center gap-3">
          <Eye className={clsx('w-4 h-4', getVisibilitySeverity(minVisibility).color)} />
          <div>
            <div className={clsx('text-lg font-bold', getVisibilitySeverity(minVisibility).color)}>{minVisibility.toFixed(1)} km</div>
            <div className="text-[10px] text-white/40">Min Visibility</div>
          </div>
        </div>
        <div className="nitcc-card p-3 flex items-center gap-3">
          <Waves className="w-4 h-4" style={{ color: getFloodColor(maxFloodRisk) }} />
          <div>
            <div className="text-lg font-bold" style={{ color: getFloodColor(maxFloodRisk) }}>
              {(maxFloodRisk * 100).toFixed(0)}%
            </div>
            <div className="text-[10px] text-white/40">Max Flood Risk</div>
          </div>
        </div>
      </div>

      {/* Corridor Weather Cards */}
      <div className="flex-1 overflow-auto">
        {isLoading && (
          <div className="text-center py-16 text-white/40">
            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-3" />
            Fetching weather data from WeatherMind Agent...
          </div>
        )}

        <div className="space-y-5">
          {Object.entries(corridorGroups).map(([corridorId, waypoints]) => (
            <div key={corridorId}>
              <h3 className="text-sm font-semibold text-white/60 mb-3 flex items-center gap-2">
                <MapPin className="w-3.5 h-3.5 text-electric-400" />
                {corridorId}
                <span className="text-[10px] text-white/30 ml-1">{waypoints.length} waypoints</span>
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                {waypoints.map((reading: any, i: number) => {
                  const hasWarning = (reading.windSpeed > 60) || (reading.precipitation > 20) ||
                    (reading.visibility < 1) || (reading.floodRisk > 0.5)
                  return (
                    <motion.div
                      key={reading.readingId || i}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.03 }}
                      className={clsx('nitcc-card p-4', hasWarning && 'border-warn/20')}
                    >
                      {/* Impact code badge */}
                      {reading.impactCode && (
                        <div className="text-[10px] text-critical font-semibold mb-2 flex items-center gap-1">
                          <CloudLightning className="w-3 h-3" />
                          {reading.impactCode.replace(/_/g, ' ')}
                        </div>
                      )}

                      {/* Weather metrics grid */}
                      <div className="grid grid-cols-2 gap-3">
                        <WeatherMetric
                          icon={Thermometer} label="Temp"
                          value={`${reading.temperature?.toFixed(0) ?? '—'}°C`}
                          color={reading.temperature > 45 ? 'text-critical' :
                            reading.temperature > 35 ? 'text-orange-400' :
                            reading.temperature < 5 ? 'text-cyan-400' : 'text-white/70'}
                        />
                        <WeatherMetric
                          icon={Wind} label="Wind"
                          value={`${reading.windSpeed?.toFixed(0) ?? '—'} km/h`}
                          color={getWindSeverity(reading.windSpeed || 0).color}
                        />
                        <WeatherMetric
                          icon={Droplets} label="Rain"
                          value={`${reading.precipitation?.toFixed(0) ?? '—'} mm/h`}
                          color={getPrecipSeverity(reading.precipitation || 0).color}
                        />
                        <WeatherMetric
                          icon={Eye} label="Visibility"
                          value={`${reading.visibility?.toFixed(1) ?? '—'} km`}
                          color={getVisibilitySeverity(reading.visibility || 15).color}
                        />
                      </div>

                      {/* Flood Risk bar */}
                      {reading.floodRisk > 0 && (
                        <div className="mt-3 pt-2 border-t border-white/[0.05]">
                          <div className="flex items-center justify-between text-[11px] mb-1">
                            <span className="text-white/40 flex items-center gap-1">
                              <Waves className="w-3 h-3" /> Flood Risk
                            </span>
                            <span className="font-bold tabular-nums" style={{ color: getFloodColor(reading.floodRisk) }}>
                              {(reading.floodRisk * 100).toFixed(0)}%
                            </span>
                          </div>
                          <div className="h-1.5 bg-white/10 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${reading.floodRisk * 100}%`,
                                backgroundColor: getFloodColor(reading.floodRisk),
                              }}
                            />
                          </div>
                        </div>
                      )}

                      {/* Timestamp */}
                      <div className="text-[10px] text-white/20 mt-2">
                        {reading.forecastedAt ? format(new Date(reading.forecastedAt), 'dd MMM HH:mm') : '—'}
                        {reading.source && ` · ${reading.source}`}
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        {!isLoading && readings.length === 0 && (
          <div className="text-center py-20">
            <Cloud className="w-12 h-12 text-white/[0.08] mx-auto mb-4" />
            <p className="text-white/30 text-sm">No weather data available</p>
            <p className="text-white/15 text-xs mt-1">WeatherMind Agent ingests data every 15 minutes</p>
          </div>
        )}
      </div>
    </div>
  )
}

function WeatherMetric({ icon: Icon, label, value, color }: {
  icon: React.ElementType; label: string; value: string; color: string
}) {
  return (
    <div className="flex items-center gap-2">
      <Icon className={clsx('w-3.5 h-3.5 flex-shrink-0', color)} />
      <div>
        <div className={clsx('text-sm font-medium tabular-nums', color)}>{value}</div>
        <div className="text-[10px] text-white/30">{label}</div>
      </div>
    </div>
  )
}