/**
 * S4 — Alert Center
 * PRD FR-03.2: Paginated alerts, severity filter, dismiss/escalate, deduplication
 */
import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { alertsApi } from '@/services/api'
import { useDashboardStore } from '@/store/dashboardStore'
import { Bell, AlertTriangle, Info, Filter, CheckCircle } from 'lucide-react'
import clsx from 'clsx'
import toast from 'react-hot-toast'
import { format } from 'date-fns'
import { motion, AnimatePresence } from 'framer-motion'

const SEVERITY_CONFIG = {
  CRITICAL: { label: 'CRITICAL', badgeClass: 'alert-badge-critical', icon: AlertTriangle },
  WARN:     { label: 'WARN',     badgeClass: 'alert-badge-warn',     icon: AlertTriangle },
  INFO:     { label: 'INFO',     badgeClass: 'alert-badge-info',     icon: Info },
}

export default function AlertCenterPage() {
  const [severityFilter, setSeverityFilter] = useState<string | null>(null)
  const [domainFilter, setDomainFilter] = useState<string | null>(null)
  const [showDismissed, setShowDismissed] = useState(false)
  const [page, setPage] = useState(1)
  const { dismissAlertLocally } = useDashboardStore()
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['alerts', severityFilter, domainFilter, showDismissed, page],
    queryFn: () => alertsApi.list({
      severity: severityFilter || undefined,
      domain: domainFilter || undefined,
      dismissed: showDismissed ? undefined : false,
      page,
      page_size: 50,
    }),
    refetchInterval: 15_000,
  })

  const dismissMutation = useMutation({
    mutationFn: ({ alertId }: { alertId: string }) =>
      alertsApi.dismiss(alertId, 'Acknowledged by operator'),
    onSuccess: (_, { alertId }) => {
      dismissAlertLocally(alertId)
      queryClient.invalidateQueries({ queryKey: ['alerts'] })
      toast.success('Alert dismissed and logged to audit trail')
    },
    onError: () => toast.error('Failed to dismiss alert — check permissions'),
  })

  const alerts = (data?.data as any)?.data || []
  const total = (data?.data as any)?.total || 0

  return (
    <div className="p-6 h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <Bell className="w-5 h-5 text-electric-400" />
            Alert Center
          </h1>
          <p className="text-sm text-white/40 mt-0.5">{total} alerts · Operator+ access</p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-white/40" />
          {(['CRITICAL', 'WARN', 'INFO'] as const).map(sev => (
            <button
              key={sev}
              id={`alert-filter-${sev.toLowerCase()}`}
              onClick={() => setSeverityFilter(severityFilter === sev ? null : sev)}
              className={clsx(
                'text-xs px-3 py-1.5 rounded-full border font-medium transition-all cursor-pointer',
                severityFilter === sev
                  ? SEVERITY_CONFIG[sev].badgeClass
                  : 'bg-white/[0.04] text-white/40 border-white/10 hover:border-white/20 hover:text-white/60'
              )}
            >
              {sev}
            </button>
          ))}
          <button
            onClick={() => setShowDismissed(!showDismissed)}
            className={clsx('text-xs px-3 py-1.5 rounded-full border transition-all',
              showDismissed ? 'bg-success/10 text-success border-success/20' : 'text-white/40 border-white/10'
            )}
          >
            {showDismissed ? 'Hide Dismissed' : 'Show Dismissed'}
          </button>
        </div>
      </div>

      {/* Alert Table */}
      <div className="flex-1 overflow-y-auto space-y-2 scrollbar-thin">
        {isLoading && (
          <div className="text-center text-white/40 py-12 text-sm">Loading alerts...</div>
        )}

        <AnimatePresence initial={false}>
          {alerts.map((alert: any) => {
            const cfg = SEVERITY_CONFIG[alert.severity as keyof typeof SEVERITY_CONFIG] || SEVERITY_CONFIG.INFO
            const Icon = cfg.icon
            const dismissed = !!alert.dismissedAt

            return (
              <motion.div
                key={alert.alertId}
                layout
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: dismissed ? 0.45 : 1, y: 0 }}
                exit={{ opacity: 0, height: 0 }}
                className={clsx(
                  'nitcc-card p-4 flex items-start gap-4',
                  !dismissed && alert.severity === 'CRITICAL' && 'border-critical/25'
                )}
              >
                <Icon className={clsx(
                  'w-4 h-4 mt-0.5 flex-shrink-0',
                  alert.severity === 'CRITICAL' ? 'text-critical' :
                  alert.severity === 'WARN' ? 'text-warn' : 'text-info'
                )} />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className={clsx('alert-badge text-[11px]', cfg.badgeClass)}>
                      {alert.severity}
                    </span>
                    <span className="text-[11px] text-white/30 capitalize">{alert.domain}</span>
                    <span className="text-[11px] text-white/20">·</span>
                    <span className="text-[11px] text-white/30">{alert.sourceAgent}</span>
                    {alert.trainId && (
                      <span className="text-[11px] text-electric-400">Train: {alert.trainId}</span>
                    )}
                    {dismissed && (
                      <span className="text-[11px] text-success flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" /> Dismissed by {alert.dismissedBy}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-white/80">{alert.message}</p>
                  <p className="text-xs text-white/30 mt-1.5">
                    {format(new Date(alert.createdAt), 'dd MMM yyyy, HH:mm:ss')} IST
                  </p>
                </div>

                {!dismissed && (
                  <button
                    id={`dismiss-btn-${alert.alertId}`}
                    onClick={() => dismissMutation.mutate({ alertId: alert.alertId })}
                    disabled={dismissMutation.isPending}
                    className="btn-ghost text-xs px-2.5 py-1.5 flex items-center gap-1.5 flex-shrink-0"
                    title="Dismiss alert (logged to audit trail)"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    Dismiss
                  </button>
                )}
              </motion.div>
            )
          })}
        </AnimatePresence>

        {!isLoading && alerts.length === 0 && (
          <div className="text-center py-20">
            <Bell className="w-12 h-12 text-white/10 mx-auto mb-4" />
            <p className="text-white/30 text-sm">No alerts matching current filters</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="flex items-center justify-between pt-3 border-t border-white/[0.06] flex-shrink-0">
          <span className="text-xs text-white/40">
            Showing {(page - 1) * 50 + 1}–{Math.min(page * 50, total)} of {total}
          </span>
          <div className="flex gap-2">
            <button
              className="btn-ghost text-xs px-3 py-1.5"
              disabled={page === 1}
              onClick={() => setPage(p => p - 1)}
            >
              ← Previous
            </button>
            <button
              className="btn-ghost text-xs px-3 py-1.5"
              disabled={page >= Math.ceil(total / 50)}
              onClick={() => setPage(p => p + 1)}
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
