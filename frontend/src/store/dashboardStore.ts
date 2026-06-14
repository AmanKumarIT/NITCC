/**
 * NITCC Dashboard Store (Zustand)
 * Real-time state for live map, alerts, KPIs, incidents — fed by WebSocket.
 */

import { create } from 'zustand'

// Types (matching backend Pydantic models)
export interface Train {
  trainId: string
  corridorId: string
  currentPosition: { type: 'Point'; coordinates: [number, number] }
  speedKmh: number
  riskScore: number
  riskComponents: Record<string, number>
  status: 'moving' | 'halted' | 'delayed' | 'cancelled'
  lastUpdated: string
}

export interface Alert {
  alertId: string
  domain: 'operational' | 'environmental' | 'logistics' | 'emergency'
  severity: 'INFO' | 'WARN' | 'CRITICAL'
  sourceAgent: string
  trainId?: string
  segmentId?: string
  message: string
  metadata: Record<string, unknown>
  createdAt: string
  dismissedAt?: string
  dismissedBy?: string
}

export interface Incident {
  incidentId: string
  type: string
  severity: 'P1' | 'P2' | 'P3' | 'P4'
  location: { type: 'Point'; coordinates: [number, number] }
  status: 'detected' | 'active' | 'resolved'
  affectedTrains: string[]
  affectedSegments: string[]
  actionPlan?: unknown
  createdAt: string
}

export interface WeatherReading {
  readingId: string
  corridorId: string
  waypoint: { type: 'Point'; coordinates: [number, number] }
  temperature: number
  precipitation: number
  windSpeed: number
  visibility: number
  floodRisk: number
  impactCode?: string
  forecastedAt: string
}

export interface NRIData {
  nri: number
  components: Record<string, number>
  updatedAt: string
  p1_active: boolean
  p2_active: boolean
}

export interface KPISummary {
  activeTrains: number
  activeIncidents: number
  criticalAlerts: number
  warnAlerts: number
  systemUptime: number   // percentage
  nri: number
}

interface DashboardState {
  // Live data
  trains: Train[]
  alerts: Alert[]
  incidents: Incident[]
  weatherReadings: WeatherReading[]
  nriData: NRIData | null
  kpis: KPISummary

  // WebSocket status
  wsConnected: boolean
  lastEventAt: string | null

  // Map overlays (toggleable)
  overlays: {
    precipitation: boolean
    wind: boolean
    temperature: boolean
    visibility: boolean
    floodRisk: boolean
    satelliteRiskZones: boolean
    trackHealth: boolean
  }

  // Actions
  setWsConnected: (connected: boolean) => void
  processWsEvent: (event: Record<string, unknown>) => void
  updateTrain: (train: Train) => void
  addAlert: (alert: Alert) => void
  dismissAlertLocally: (alertId: string) => void
  addIncident: (incident: Incident) => void
  updateNRI: (nri: NRIData) => void
  toggleOverlay: (key: keyof DashboardState['overlays']) => void
  setTrains: (trains: Train[]) => void
  setAlerts: (alerts: Alert[]) => void
  setIncidents: (incidents: Incident[]) => void
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  trains: [],
  alerts: [],
  incidents: [],
  weatherReadings: [],
  nriData: null,
  kpis: {
    activeTrains: 0,
    activeIncidents: 0,
    criticalAlerts: 0,
    warnAlerts: 0,
    systemUptime: 99.9,
    nri: 0,
  },
  wsConnected: false,
  lastEventAt: null,
  overlays: {
    precipitation: false,
    wind: false,
    temperature: false,
    visibility: false,
    floodRisk: false,
    satelliteRiskZones: true,
    trackHealth: true,
  },

  setWsConnected: (connected) => set({ wsConnected: connected }),

  processWsEvent: (event) => {
    const type = event.type as string
    const now = new Date().toISOString()

    switch (type) {
      case 'RISK_UPDATE':
        get().updateTrain(event as unknown as Train)
        break
      case 'ALERT_CREATED':
        get().addAlert(event as unknown as Alert)
        break
      case 'INCIDENT_DETECTED':
      case 'INCIDENT_DECLARED':
        get().addIncident(event as unknown as Incident)
        break
      case 'ORCHESTRATION_CYCLE':
        get().updateNRI({
          nri: (event.nri as number) ?? 0,
          components: (event.risk_by_zone as Record<string, number>) ?? {},
          updatedAt: now,
          p1_active: (event.p1_active as boolean) ?? false,
          p2_active: (event.p2_active as boolean) ?? false,
        })
        break
    }
    set({ lastEventAt: now })
  },

  updateTrain: (update) =>
    set((state) => {
      const idx = state.trains.findIndex((t) => t.trainId === update.trainId)
      if (idx >= 0) {
        const updated = [...state.trains]
        updated[idx] = { ...updated[idx], ...update }
        return { trains: updated }
      }
      return {}
    }),

  addAlert: (alert) =>
    set((state) => {
      // Avoid duplicates
      if (state.alerts.some((a) => a.alertId === alert.alertId)) return {}
      const newAlerts = [alert, ...state.alerts].slice(0, 500) // Keep latest 500
      const criticalAlerts = newAlerts.filter((a) => a.severity === 'CRITICAL' && !a.dismissedAt).length
      const warnAlerts = newAlerts.filter((a) => a.severity === 'WARN' && !a.dismissedAt).length
      return {
        alerts: newAlerts,
        kpis: { ...state.kpis, criticalAlerts, warnAlerts },
      }
    }),

  dismissAlertLocally: (alertId) =>
    set((state) => ({
      alerts: state.alerts.map((a) =>
        a.alertId === alertId ? { ...a, dismissedAt: new Date().toISOString() } : a
      ),
    })),

  addIncident: (incident) =>
    set((state) => {
      if (state.incidents.some((i) => i.incidentId === incident.incidentId)) return {}
      const newIncidents = [incident, ...state.incidents].slice(0, 200)
      const activeIncidents = newIncidents.filter((i) => i.status !== 'resolved').length
      return {
        incidents: newIncidents,
        kpis: { ...state.kpis, activeIncidents },
      }
    }),

  updateNRI: (nri) =>
    set((state) => ({
      nriData: nri,
      kpis: { ...state.kpis, nri: nri.nri },
    })),

  toggleOverlay: (key) =>
    set((state) => ({
      overlays: { ...state.overlays, [key]: !state.overlays[key] },
    })),

  setTrains: (trains) =>
    set((state) => ({
      trains,
      kpis: { ...state.kpis, activeTrains: trains.filter((t) => t.status !== 'cancelled').length },
    })),

  setAlerts: (alerts) => set({ alerts }),
  setIncidents: (incidents) =>
    set((state) => ({
      incidents,
      kpis: {
        ...state.kpis,
        activeIncidents: incidents.filter((i) => i.status !== 'resolved').length,
      },
    })),
}))
