/**
 * useWebSocket — Persistent WebSocket connection to NITCC dashboard feed
 * WS /ws/dashboard?token=<jwt>
 * Auto-reconnects with exponential backoff.
 * PRD: <500ms latency SLA.
 */

import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '@/store/authStore'
import { useDashboardStore } from '@/store/dashboardStore'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/dashboard`
const MAX_RECONNECT_DELAY = 30_000
const INITIAL_RECONNECT_DELAY = 1_000

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const { accessToken } = useAuthStore()
  const { setWsConnected, processWsEvent } = useDashboardStore()

  const connect = useCallback(() => {
    if (!accessToken) return
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const url = `${WS_URL}?token=${encodeURIComponent(accessToken)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('[NITCC WS] Connected')
      setWsConnected(true)
      reconnectDelayRef.current = INITIAL_RECONNECT_DELAY  // Reset backoff
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type !== 'heartbeat' && data.type !== 'pong') {
          processWsEvent(data)
        }
      } catch (e) {
        console.warn('[NITCC WS] Failed to parse message:', e)
      }
    }

    ws.onclose = (event) => {
      console.log(`[NITCC WS] Disconnected (code=${event.code}). Reconnecting in ${reconnectDelayRef.current}ms...`)
      setWsConnected(false)
      wsRef.current = null

      if (event.code !== 4001) {  // 4001 = unauthorized, don't retry
        reconnectTimerRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, MAX_RECONNECT_DELAY)
          connect()
        }, reconnectDelayRef.current)
      }
    }

    ws.onerror = (error) => {
      console.error('[NITCC WS] Error:', error)
      ws.close()
    }

    // Send ping every 25s to keep connection alive
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      } else {
        clearInterval(pingInterval)
      }
    }, 25_000)

  }, [accessToken, setWsConnected, processWsEvent])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current)
      wsRef.current?.close(1000, 'Component unmounted')
    }
  }, [connect])

  return { isConnected: wsRef.current?.readyState === WebSocket.OPEN }
}
