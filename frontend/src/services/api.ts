/**
 * NITCC API Service Layer
 * Axios instance with JWT auth, token refresh, and standard error handling.
 */

import axios from 'axios'

const api = axios.create({
  baseURL: `${import.meta.env.VITE_API_URL}/api/v1`,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor — attach JWT Bearer token
api.interceptors.request.use(
  (config) => {
    // Token is set directly on defaults from authStore
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor — handle 401 with token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (
      error.response?.status === 401
      && !originalRequest._retry
      && originalRequest.url !== '/auth/refresh'
    ) {
      originalRequest._retry = true
      try {
        // Dynamic import to avoid circular dependency
        const { useAuthStore } = await import('@/store/authStore')
        const refreshed = await useAuthStore.getState().refreshAccessToken()
        if (refreshed) {
          return api(originalRequest)
        }
      } catch {
        const { useAuthStore } = await import('@/store/authStore')
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api

// ─── API Methods ──────────────────────────────────────────────────────────────

export const trainsApi = {
  list: (params?: Record<string, unknown>) => api.get('/trains', { params }),
  telemetry: (trainId: string) => `/api/v1/trains/${trainId}/telemetry`,  // SSE URL
}

export const tracksApi = {
  list: (params?: Record<string, unknown>) => api.get('/tracks', { params }),
  history: (segmentId: string, days = 30) =>
    api.get(`/tracks/${segmentId}/history`, { params: { days } }),
  workOrders: (segmentId: string) => api.get(`/tracks/${segmentId}/work-orders`),
}

export const alertsApi = {
  list: (params?: Record<string, unknown>) => api.get('/alerts', { params }),
  dismiss: (alertId: string, reason?: string) =>
    api.post(`/alerts/${alertId}/dismiss`, { reason }),
}

export const incidentsApi = {
  list: (params?: Record<string, unknown>) => api.get('/incidents', { params }),
  declare: (body: Record<string, unknown>) => api.post('/incidents', body),
  getActionPlan: (incidentId: string) => api.get(`/incidents/${incidentId}/action-plan`),
  editActionPlan: (incidentId: string, updates: Record<string, unknown>, rationale: string) =>
    api.patch(`/incidents/${incidentId}/action-plan`, updates, { params: { rationale } }),
}

export const weatherApi = {
  corridors: (params?: Record<string, unknown>) => api.get('/weather/corridors', { params }),
}

export const satelliteApi = {
  riskZones: (params?: Record<string, unknown>) => api.get('/satellite/risk-zones', { params }),
}

export const cargoApi = {
  wagons: (params?: Record<string, unknown>) => api.get('/cargo/wagons', { params }),
  recommend: (body: Record<string, unknown>) => api.post('/cargo/routes/recommend', body),
}

export const agentsApi = {
  status: () => api.get('/agents/status'),
}

export const reportsApi = {
  generate: (body: Record<string, unknown>) => api.post('/reports/generate', body),
  get: (reportId: string) => api.get(`/reports/${reportId}`),
}

export const authApi = {
  login: (email: string, password: string) => api.post('/auth/login', { email, password }),
  verifyMfa: (tempToken: string, totpCode: string) =>
    api.post('/auth/mfa/verify', { temp_token: tempToken, totp_code: totpCode }),
  refresh: (refreshToken: string) => api.post('/auth/refresh', { refresh_token: refreshToken }),
  me: () => api.get('/auth/me'),
  setupMfa: () => api.post('/auth/mfa/setup'),
}
