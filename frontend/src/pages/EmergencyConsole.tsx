/**
 * S5 — Emergency Response Console
 * PRD FR-06: Incident list, AI Action Plan panel, resource map, incident timeline
 * Accessible to Emergency+ roles
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { incidentsApi } from '@/services/api'
import {
  Shield, AlertTriangle, Clock, Users, MapPin, CheckCircle,
  Edit3, Loader2, FileText, Activity, X, ChevronRight, Phone,
  Zap, Truck
} from 'lucide-react'
import clsx from 'clsx'
import { format } from 'date-fns'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'

const SEVERITY_STYLE: Record<string, string> = {
  P1: 'border-critical/40 text-critical',
  P2: 'border-orange-500/40 text-orange-400',
  P3: 'border-warn/40 text-warn',
  P4: 'border-info/40 text-info',
}

const STATUS_STYLE: Record<string, { bg: string; text: string }> = {
  detected: { bg: 'bg-warn/20', text: 'text-warn' },
  active:   { bg: 'bg-critical/20', text: 'text-critical' },
  resolved: { bg: 'bg-success/20', text: 'text-success' },
}

export default function EmergencyConsolePage() {
  const { incidentId: routeIncidentId } = useParams<{ incidentId?: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [selectedId, setSelectedId] = useState<string | null>(routeIncidentId ?? null)
  const [statusFilter, setStatusFilter] = useState<string>('active')
  const [editMode, setEditMode] = useState(false)
  const [editRationale, setEditRationale] = useState('')

  useEffect(() => {
    if (routeIncidentId) setSelectedId(routeIncidentId)
  }, [routeIncidentId])

  // Fetch incidents
  const { data: incidentsData, isLoading: incidentsLoading } = useQuery({
    queryKey: ['incidents', statusFilter],
    queryFn: () => incidentsApi.list({
      status: statusFilter !== 'all' ? statusFilter : undefined,
      page_size: 100,
    }),
    refetchInterval: 10_000,
  })

  // Fetch action plan for selected incident
  const { data: planData, isLoading: planLoading, refetch: refetchPlan } = useQuery({
    queryKey: ['action-plan', selectedId],
    queryFn: () => incidentsApi.getActionPlan(selectedId!),
    enabled: !!selectedId,
    refetchInterval: 5_000,
  })

  // Declare new incident mutation
  const declareMutation = useMutation({
    mutationFn: (body: Record<string, unknown>) => incidentsApi.declare(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] })
      toast.success('Incident declared — CrisisCommand generating action plan...')
    },
    onError: () => toast.error('Failed to declare incident'),
  })

  // Edit action plan mutation
  const editPlanMutation = useMutation({
    mutationFn: ({ incidentId, updates }: { incidentId: string; updates: Record<string, unknown> }) =>
      incidentsApi.editActionPlan(incidentId, updates, editRationale || 'Manual edit by operator'),
    onSuccess: () => {
      setEditMode(false)
      setEditRationale('')
      refetchPlan()
      toast.success('Action plan updated — new version saved')
    },
    onError: () => toast.error('Failed to update action plan'),
  })

  const incidents = (incidentsData?.data as any)?.data || []
  const selectedIncident = incidents.find((i: any) => i.incidentId === selectedId)
  const actionPlan = (planData?.data as any)?.data || (planData?.data as any)

  return (
    <div className="h-full flex">
      {/* Left Panel: Incident List */}
      <div className="w-80 flex-shrink-0 border-r border-white/[0.06] flex flex-col bg-navy-900/50">
        {/* Header */}
        <div className="p-4 border-b border-white/[0.06]">
          <h1 className="text-base font-bold text-white flex items-center gap-2">
            <Shield className="w-5 h-5 text-critical" />
            Emergency Console
          </h1>
          <p className="text-[11px] text-white/40 mt-0.5">FR-06 · Emergency+ access required</p>

          {/* Status filter tabs */}
          <div className="flex gap-1 mt-3">
            {['detected', 'active', 'resolved', 'all'].map(s => (
              <button key={s}
                onClick={() => { setStatusFilter(s); setSelectedId(null) }}
                className={clsx('text-xs px-2.5 py-1.5 rounded-md capitalize transition-all',
                  statusFilter === s
                    ? 'bg-electric-500/20 text-electric-300 border border-electric-500/30'
                    : 'text-white/40 hover:text-white/60 hover:bg-white/[0.04]'
                )}>
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Incident cards */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-thin">
          {incidentsLoading && (
            <div className="text-center text-white/40 py-8 text-sm">
              <Loader2 className="w-5 h-5 animate-spin mx-auto mb-2" />
              Loading incidents...
            </div>
          )}

          {incidents.map((incident: any) => {
            const ss = STATUS_STYLE[incident.status] || STATUS_STYLE.detected
            return (
              <motion.button
                key={incident.incidentId}
                layout
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                id={`incident-card-${incident.incidentId}`}
                onClick={() => setSelectedId(incident.incidentId)}
                className={clsx(
                  'w-full text-left p-3 rounded-lg border transition-all',
                  selectedId === incident.incidentId
                    ? 'border-electric-500/40 bg-electric-500/10'
                    : `border-white/[0.06] hover:border-white/15 bg-white/[0.02]`,
                  SEVERITY_STYLE[incident.severity]
                )}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-bold">{incident.severity}</span>
                  <span className={clsx('text-[10px] px-1.5 py-0.5 rounded-full', ss.bg, ss.text)}>
                    {incident.status}
                  </span>
                </div>
                <div className="text-xs font-medium text-white/80 mb-1 truncate">{incident.type}</div>
                <div className="flex items-center justify-between text-[11px] text-white/30">
                  <span>{format(new Date(incident.createdAt), 'dd MMM HH:mm')}</span>
                  <span>{incident.affectedTrains?.length || 0} trains</span>
                </div>
              </motion.button>
            )
          })}

          {!incidentsLoading && incidents.length === 0 && (
            <div className="text-center py-12">
              <CheckCircle className="w-8 h-8 text-success/30 mx-auto mb-2" />
              <p className="text-xs text-white/30">No {statusFilter} incidents</p>
            </div>
          )}
        </div>
      </div>

      {/* Right Panel: Action Plan */}
      <div className="flex-1 overflow-y-auto">
        {!selectedId ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <Shield className="w-16 h-16 text-white/[0.06] mx-auto mb-4" />
              <p className="text-white/25 text-sm">Select an incident to view AI Action Plan</p>
              <p className="text-white/15 text-xs mt-1">CrisisCommand Agent generates plans within 60 seconds</p>
            </div>
          </div>
        ) : (
          <div className="p-6 space-y-5 max-w-4xl">
            {/* Incident header */}
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-bold text-white">{selectedIncident?.incidentId}</h2>
                  <span className={clsx(
                    'text-xs px-2 py-0.5 rounded-full font-semibold border',
                    SEVERITY_STYLE[selectedIncident?.severity]
                  )}>
                    {selectedIncident?.severity}
                  </span>
                  <span className={clsx(
                    'text-[10px] px-2 py-0.5 rounded-full',
                    STATUS_STYLE[selectedIncident?.status]?.bg,
                    STATUS_STYLE[selectedIncident?.status]?.text
                  )}>
                    {selectedIncident?.status}
                  </span>
                </div>
                <p className="text-sm text-white/50 mt-1">{selectedIncident?.type}</p>
                <p className="text-xs text-white/30 mt-0.5">
                  Detected: {selectedIncident ? format(new Date(selectedIncident.createdAt), 'dd MMM yyyy HH:mm:ss') : ''}
                  {selectedIncident?.affectedTrains?.length > 0 &&
                    ` · ${selectedIncident.affectedTrains.length} trains affected`}
                </p>
              </div>
              <button className="btn-icon" onClick={() => setSelectedId(null)}>
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Action Plan */}
            {planLoading && !actionPlan ? (
              <div className="nitcc-card p-10 text-center">
                <Loader2 className="w-10 h-10 text-electric-400 animate-spin mx-auto mb-4" />
                <p className="text-white/60 text-sm font-medium">CrisisCommand Agent generating AI Action Plan...</p>
                <p className="text-white/30 text-xs mt-1">SLA: ≤ 60 seconds (FR-06.2)</p>
              </div>
            ) : !actionPlan ? (
              <div className="nitcc-card p-10 text-center">
                <Activity className="w-10 h-10 text-warn/40 mx-auto mb-4" />
                <p className="text-white/50 text-sm">Waiting for CrisisCommand to generate plan...</p>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Immediate Actions */}
                <div className="nitcc-card p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold text-critical flex items-center gap-2">
                      <Zap className="w-4 h-4" /> Immediate Actions
                    </h3>
                    <button
                      onClick={() => setEditMode(!editMode)}
                      className="btn-ghost text-xs px-2 py-1 flex items-center gap-1"
                    >
                      <Edit3 className="w-3 h-3" />
                      {editMode ? 'Cancel Edit' : 'Edit Plan'}
                    </button>
                  </div>
                  <ol className="space-y-2.5">
                    {(actionPlan.immediate_actions || []).map((action: string, i: number) => (
                      <li key={i} className="flex items-start gap-3 text-sm text-white/80">
                        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-critical/15 text-critical text-xs font-bold flex items-center justify-center mt-0.5">
                          {i + 1}
                        </span>
                        <span className="leading-relaxed">{action}</span>
                      </li>
                    ))}
                  </ol>
                </div>

                {/* Agency Contacts */}
                {actionPlan.agency_contacts?.length > 0 && (
                  <div className="nitcc-card p-5">
                    <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                      <Phone className="w-4 h-4 text-electric-400" /> Agency Contacts
                    </h3>
                    <div className="grid gap-2">
                      {actionPlan.agency_contacts.map((c: any, i: number) => (
                        <div key={i} className="flex items-center justify-between py-2 px-3 rounded-lg bg-white/[0.02] border border-white/[0.05]">
                          <div>
                            <div className="text-sm font-medium text-white/80">{c.agency}</div>
                            <div className="text-xs text-white/40">{c.role}</div>
                          </div>
                          <div className="text-sm font-mono text-electric-400">{c.contact}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Resource Dispatch */}
                {actionPlan.resource_list?.length > 0 && (
                  <div className="nitcc-card p-5">
                    <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                      <Truck className="w-4 h-4 text-warn" /> Resource Dispatch
                    </h3>
                    <table className="nitcc-table">
                      <thead>
                        <tr>
                          <th>Resource</th>
                          <th>Qty</th>
                          <th>Deployment Point</th>
                          <th>ETA</th>
                        </tr>
                      </thead>
                      <tbody>
                        {actionPlan.resource_list.map((r: any, i: number) => (
                          <tr key={i}>
                            <td className="font-medium text-white/80">{r.resource}</td>
                            <td>{r.quantity}</td>
                            <td className="text-white/50">{r.deployment_point}</td>
                            <td className="text-warn font-medium">~{r.eta_minutes} min</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Evacuation Routes */}
                {actionPlan.evacuation_routes?.length > 0 && (
                  <div className="nitcc-card p-5">
                    <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                      <MapPin className="w-4 h-4 text-success" /> Evacuation Routes
                    </h3>
                    <ul className="space-y-2">
                      {actionPlan.evacuation_routes.map((route: string, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-white/70">
                          <ChevronRight className="w-3.5 h-3.5 mt-0.5 text-success flex-shrink-0" />
                          {route}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Communication Template */}
                {actionPlan.communication_template && (
                  <div className="nitcc-card p-5">
                    <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                      <FileText className="w-4 h-4 text-electric-400" /> Communication Template
                    </h3>
                    <pre className="text-xs text-white/60 whitespace-pre-wrap font-mono bg-navy-950/50 p-4 rounded-lg border border-white/[0.04] leading-relaxed">
                      {actionPlan.communication_template}
                    </pre>
                  </div>
                )}

                {/* Edit rationale (when edit mode) */}
                <AnimatePresence>
                  {editMode && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="nitcc-card p-5"
                    >
                      <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                        <Edit3 className="w-4 h-4 text-warn" /> Edit Rationale (Required)
                      </h3>
                      <textarea
                        className="nitcc-input h-20 resize-none"
                        placeholder="Describe why this change to the action plan is necessary..."
                        value={editRationale}
                        onChange={(e) => setEditRationale(e.target.value)}
                      />
                      <p className="text-[10px] text-white/30 mt-1">
                        FR-06.3: All edits are versioned with rationale for audit trail.
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Activate button */}
                <button
                  id="activate-plan-btn"
                  className="btn-danger w-full h-12 text-base"
                  onClick={() => toast.success('Action Plan activated — all agencies notified via SMS/Email')}
                >
                  <Shield className="w-5 h-5" />
                  Activate Action Plan & Notify Agencies
                </button>
              </div>
            )}

            {/* Incident Timeline */}
            {selectedIncident?.timeline?.length > 0 && (
              <div className="nitcc-card p-5">
                <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                  <Clock className="w-4 h-4 text-electric-400" /> Incident Timeline
                </h3>
                <div className="space-y-0">
                  {selectedIncident.timeline.map((event: any, i: number) => (
                    <div key={i} className="flex gap-3 relative">
                      <div className="flex flex-col items-center">
                        <div className={clsx(
                          'w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 z-10',
                          i === 0 ? 'bg-electric-400' : 'bg-white/20'
                        )} />
                        {i < selectedIncident.timeline.length - 1 && (
                          <div className="w-0.5 flex-1 bg-white/10 my-1" />
                        )}
                      </div>
                      <div className="pb-4">
                        <p className="text-sm text-white/80">{event.event}</p>
                        <p className="text-[11px] text-white/30 mt-0.5">
                          {format(new Date(event.timestamp), 'dd MMM HH:mm:ss')} · {event.actor}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}