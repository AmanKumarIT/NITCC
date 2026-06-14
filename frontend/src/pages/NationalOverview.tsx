/**
 * S2 — National Overview Map
 * PRD FR-03.1: Live Mapbox GL JS map, train markers, track health colors,
 * weather overlays, satellite risk zones, alert banner, KPI widgets, drill-down
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import mapboxgl from 'mapbox-gl'
import { useDashboardStore } from '@/store/dashboardStore'
import { useQuery } from '@tanstack/react-query'
import { trainsApi, satelliteApi, weatherApi, tracksApi } from '@/services/api'
import {
  Layers, Thermometer, Wind, Eye, CloudRain, Triangle, Activity,
  ChevronRight, X, AlertTriangle, Bell
} from 'lucide-react'
import clsx from 'clsx'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'

// Mapbox token from environment
const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN || ''

// Track health → color (PRD FR-03.1)
const HEALTH_COLOR = {
  healthy:  '#10B981',  // Green  80–100
  watch:    '#EAB308',  // Yellow 60–79
  degraded: '#F97316',  // Orange 30–59
  critical: '#EF4444',  // Red    0–29
}

function getHealthColor(score: number): string {
  if (score >= 80) return HEALTH_COLOR.healthy
  if (score >= 60) return HEALTH_COLOR.watch
  if (score >= 30) return HEALTH_COLOR.degraded
  return HEALTH_COLOR.critical
}

function getRiskColor(risk: number): string {
  if (risk >= 90) return '#EF4444'
  if (risk >= 70) return '#F97316'
  if (risk >= 40) return '#F59E0B'
  return '#10B981'
}

export default function NationalOverviewPage() {
  const mapContainer = useRef<HTMLDivElement>(null)
  const mapRef = useRef<mapboxgl.Map | null>(null)
  const markersRef = useRef<Map<string, mapboxgl.Marker>>(new Map())
  const [mapLoaded, setMapLoaded] = useState(false)
  const [selectedTrain, setSelectedTrain] = useState<string | null>(null)
  const { trains, alerts, incidents, overlays, toggleOverlay } = useDashboardStore()

  // Fetch track segments for health overlay
  const { data: tracksData } = useQuery({
    queryKey: ['tracks'],
    queryFn: () => tracksApi.list({ page_size: 500 }),
    refetchInterval: 360_000,  // 6 hours
  })

  // Fetch satellite risk zones
  const { data: satData } = useQuery({
    queryKey: ['satellite-risk-zones'],
    queryFn: () => satelliteApi.riskZones({ page_size: 200 }),
    refetchInterval: 3_600_000,  // hourly
  })

  // Init Mapbox
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return
    if (!MAPBOX_TOKEN) {
      console.warn('VITE_MAPBOX_ACCESS_TOKEN not set — map will not load')
      return
    }

    mapboxgl.accessToken = MAPBOX_TOKEN

    const map = new mapboxgl.Map({
      container: mapContainer.current,
      style: 'mapbox://styles/mapbox/dark-v11',
      center: [78.9629, 22.5937],  // Center of India
      zoom: 4.5,
      minZoom: 3,
      maxZoom: 18,
      projection: { name: 'mercator' },
      attributionControl: false,
    })

    map.addControl(new mapboxgl.NavigationControl(), 'bottom-right')
    map.addControl(new mapboxgl.ScaleControl({ unit: 'metric' }), 'bottom-left')

    map.on('load', () => {
      setMapLoaded(true)
      // Add satellite imagery source for toggle
      map.addSource('satellite', {
        type: 'raster',
        url: 'mapbox://mapbox.satellite',
        tileSize: 256,
      })

      // Track health layer (line color by health score)
      map.addSource('track-health', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addLayer({
        id: 'track-health-lines',
        type: 'line',
        source: 'track-health',
        paint: {
          'line-color': ['get', 'color'],
          'line-width': 3,
          'line-opacity': 0.8,
        },
      })

      // Satellite risk zones (polygon overlay)
      map.addSource('sat-risk-zones', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
      map.addLayer({
        id: 'sat-risk-fill',
        type: 'fill',
        source: 'sat-risk-zones',
        paint: {
          'fill-color': [
            'match', ['get', 'riskTier'],
            'CRITICAL', 'rgba(239,68,68,0.25)',
            'HIGH',     'rgba(249,115,22,0.20)',
            'MEDIUM',   'rgba(245,158,11,0.15)',
            'LOW',      'rgba(59,130,246,0.10)',
            'rgba(0,0,0,0)',
          ],
          'fill-outline-color': [
            'match', ['get', 'riskTier'],
            'CRITICAL', '#EF4444',
            'HIGH',     '#F97316',
            'MEDIUM',   '#F59E0B',
            'LOW',      '#3B82F6',
            'transparent',
          ],
        },
      })
    })

    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
  }, [])

  // Update train markers on data change
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return
    const map = mapRef.current

    trains.forEach((train) => {
      const [lng, lat] = train.currentPosition.coordinates
      const el = document.createElement('div')
      el.className = 'train-marker'
      el.style.cssText = `
        width: 12px; height: 12px; border-radius: 50%;
        background-color: ${getRiskColor(train.riskScore)};
        border: 2px solid rgba(255,255,255,0.8);
        box-shadow: 0 0 ${train.riskScore > 70 ? '10px' : '6px'} ${getRiskColor(train.riskScore)}80;
        cursor: pointer;
        transition: transform 0.3s ease;
      `

      const popup = new mapboxgl.Popup({
        offset: 16,
        closeButton: false,
        className: 'nitcc-map-popup',
      }).setHTML(`
        <div style="min-width:180px">
          <div style="font-weight:600;margin-bottom:6px;color:white">${train.trainId}</div>
          <div style="font-size:12px;color:rgba(255,255,255,0.6)">
            Speed: <strong style="color:white">${train.speedKmh.toFixed(0)} km/h</strong><br/>
            Risk: <strong style="color:${getRiskColor(train.riskScore)}">${train.riskScore.toFixed(0)}/100</strong><br/>
            Corridor: ${train.corridorId}<br/>
            Status: ${train.status}
          </div>
        </div>
      `)

      if (markersRef.current.has(train.trainId)) {
        markersRef.current.get(train.trainId)!
          .setLngLat([lng, lat])
      } else {
        const marker = new mapboxgl.Marker(el)
          .setLngLat([lng, lat])
          .setPopup(popup)
          .addTo(map)
        el.addEventListener('click', () => setSelectedTrain(train.trainId))
        markersRef.current.set(train.trainId, marker)
      }
    })
  }, [trains, mapLoaded])

  // Update track health layer
  useEffect(() => {
    if (!mapLoaded || !mapRef.current || !tracksData?.data?.data) return
    const features = tracksData.data.data.map((seg: { geometry: unknown; healthScore: number; segmentId: string; fromStation: string; toStation: string }) => ({
      type: 'Feature',
      geometry: seg.geometry,
      properties: {
        color: getHealthColor(seg.healthScore),
        segmentId: seg.segmentId,
        healthScore: seg.healthScore,
        from: seg.fromStation,
        to: seg.toStation,
      },
    }))
    const source = mapRef.current.getSource('track-health') as mapboxgl.GeoJSONSource
    source?.setData({ type: 'FeatureCollection', features })
  }, [tracksData, mapLoaded])

  // Update satellite risk zones
  useEffect(() => {
    if (!mapLoaded || !mapRef.current || !satData?.data?.data) return
    const source = mapRef.current.getSource('sat-risk-zones') as mapboxgl.GeoJSONSource
    source?.setData(satData.data.data)
    mapRef.current.setLayoutProperty(
      'sat-risk-fill', 'visibility', overlays.satelliteRiskZones ? 'visible' : 'none'
    )
  }, [satData, mapLoaded, overlays.satelliteRiskZones])

  const activeAlerts = alerts.filter((a) => !a.dismissedAt && a.severity === 'CRITICAL')
  const selectedTrainData = trains.find((t) => t.trainId === selectedTrain)

  return (
    <div className="relative h-full flex flex-col">
      {/* Critical Alert Banner (always visible, FR-03.2) */}
      <AnimatePresence>
        {activeAlerts.length > 0 && (
          <motion.div
            initial={{ y: -60 }}
            animate={{ y: 0 }}
            exit={{ y: -60 }}
            className="flex-shrink-0 flex items-center gap-3 px-6 py-2.5 bg-critical/10 border-b border-critical/20"
          >
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-critical animate-pulse" />
              <span className="text-sm font-semibold text-critical">
                {activeAlerts.length} CRITICAL Alert{activeAlerts.length > 1 ? 's' : ''}
              </span>
            </div>
            <div className="flex-1 text-xs text-white/60 truncate">
              {activeAlerts[0]?.message}
            </div>
            <button
              className="text-xs text-critical/70 hover:text-critical underline"
              onClick={() => window.location.href = '/alerts'}
            >
              View All →
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Map Container */}
      <div className="flex-1 relative">
        <div ref={mapContainer} className="absolute inset-0" />

        {/* Overlay Controls (FR-03.1) */}
        <div className="absolute top-4 right-4 z-10 flex flex-col gap-2">
          <div className="nitcc-card p-3 space-y-2 min-w-[160px]">
            <div className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2 flex items-center gap-2">
              <Layers className="w-3.5 h-3.5" /> Overlays
            </div>
            {[
              { key: 'precipitation', icon: CloudRain, label: 'Precipitation' },
              { key: 'wind', icon: Wind, label: 'Wind' },
              { key: 'temperature', icon: Thermometer, label: 'Temperature' },
              { key: 'visibility', icon: Eye, label: 'Visibility' },
              { key: 'floodRisk', icon: CloudRain, label: 'Flood Risk' },
              { key: 'satelliteRiskZones', icon: Triangle, label: 'Sat Risk Zones' },
              { key: 'trackHealth', icon: Activity, label: 'Track Health' },
            ].map(({ key, icon: Icon, label }) => (
              <button
                key={key}
                id={`overlay-toggle-${key}`}
                onClick={() => toggleOverlay(key as keyof typeof overlays)}
                className={clsx(
                  'flex items-center gap-2 w-full px-2 py-1.5 rounded-md text-xs transition-all',
                  overlays[key as keyof typeof overlays]
                    ? 'bg-electric-500/20 text-electric-300 border border-electric-500/30'
                    : 'text-white/50 hover:text-white/70 hover:bg-white/[0.05]'
                )}
              >
                <Icon className="w-3 h-3" />
                {label}
              </button>
            ))}
          </div>

          {/* Track Health Legend */}
          <div className="nitcc-card p-3">
            <div className="text-xs font-semibold text-white/40 uppercase tracking-wider mb-2">Track Health</div>
            {[
              { label: 'Healthy (80–100)', color: HEALTH_COLOR.healthy },
              { label: 'Watch (60–79)', color: HEALTH_COLOR.watch },
              { label: 'Degraded (30–59)', color: HEALTH_COLOR.degraded },
              { label: 'Critical (0–29)', color: HEALTH_COLOR.critical },
            ].map(({ label, color }) => (
              <div key={label} className="flex items-center gap-2 mb-1.5">
                <div className="w-4 h-1.5 rounded-full" style={{ backgroundColor: color }} />
                <span className="text-[11px] text-white/50">{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Active incidents counter */}
        {incidents.filter(i => i.status !== 'resolved').length > 0 && (
          <div className="absolute bottom-16 right-4 z-10">
            <motion.div
              animate={{ scale: [1, 1.05, 1] }}
              transition={{ repeat: Infinity, duration: 2 }}
              className="nitcc-card px-3 py-2 border-critical/30 flex items-center gap-2 cursor-pointer"
              onClick={() => window.location.href = '/emergency'}
            >
              <AlertTriangle className="w-4 h-4 text-critical" />
              <span className="text-sm text-critical font-semibold">
                {incidents.filter(i => i.status !== 'resolved').length} Active Incident{incidents.filter(i => i.status !== 'resolved').length > 1 ? 's' : ''}
              </span>
              <ChevronRight className="w-3 h-3 text-critical/50" />
            </motion.div>
          </div>
        )}

        {/* No Mapbox token warning */}
        {!MAPBOX_TOKEN && (
          <div className="absolute inset-0 flex items-center justify-center bg-navy-900/80 backdrop-blur-sm">
            <div className="nitcc-card p-8 text-center max-w-sm">
              <Layers className="w-10 h-10 text-electric-400 mx-auto mb-3" />
              <h3 className="text-lg font-semibold text-white mb-2">Map Token Required</h3>
              <p className="text-sm text-white/50">
                Set <code className="text-electric-300 text-xs bg-navy-950 px-1.5 py-0.5 rounded">VITE_MAPBOX_ACCESS_TOKEN</code> in your <code className="text-electric-300 text-xs bg-navy-950 px-1.5 py-0.5 rounded">.env</code> file to enable the live map.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Train detail panel (slide-in when selected) */}
      <AnimatePresence>
        {selectedTrainData && (
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            className="absolute top-0 right-0 h-full w-80 z-20 nitcc-card rounded-none border-l border-white/[0.08] p-5 overflow-y-auto"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white">{selectedTrainData.trainId}</h3>
              <button className="btn-icon" onClick={() => setSelectedTrain(null)}>
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <Stat label="Risk Score" value={selectedTrainData.riskScore.toFixed(0)} unit="/100"
                color={getRiskColor(selectedTrainData.riskScore)} />
              <Stat label="Speed" value={selectedTrainData.speedKmh.toFixed(0)} unit=" km/h" />
              <Stat label="Status" value={selectedTrainData.status} />
              <Stat label="Corridor" value={selectedTrainData.corridorId} />
              <div className="border-t border-white/10 pt-3">
                <div className="text-xs text-white/40 mb-2 uppercase tracking-wider">Risk Components</div>
                {Object.entries(selectedTrainData.riskComponents).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-white/50 capitalize">{k.replace(/_/g, ' ')}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-20 h-1.5 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${v}%`, backgroundColor: getRiskColor(v as number) }}
                        />
                      </div>
                      <span className="text-xs tabular-nums text-white/60 w-8 text-right">{(v as number).toFixed(0)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function Stat({ label, value, unit, color }: { label: string; value: string | number; unit?: string; color?: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-white/[0.05]">
      <span className="text-white/50">{label}</span>
      <span className="font-medium" style={{ color: color || 'rgba(255,255,255,0.9)' }}>
        {value}{unit}
      </span>
    </div>
  )
}
