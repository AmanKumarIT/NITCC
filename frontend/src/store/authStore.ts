/**
 * NITCC Auth Store (Zustand)
 * Manages JWT tokens, user info, and authentication state.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '@/services/api'

interface User {
  userId: string
  email: string
  roles: string[]
  jurisdictionZones: string[]
  maxRoleLevel: number
  mfaEnabled: boolean
}

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean

  // Actions
  login: (email: string, password: string) => Promise<{ requiresMfa: boolean; tempToken?: string }>
  verifyMfa: (tempToken: string, totpCode: string) => Promise<void>
  logout: () => void
  refreshAccessToken: () => Promise<boolean>
  setTokens: (accessToken: string, refreshToken: string) => void
}

const ROLE_LEVELS: Record<string, number> = {
  ReadOnly: 0,
  Operator: 1,
  Supervisor: 2,
  Emergency: 3,
  Admin: 4,
}

function parseUserFromToken(token: string): User {
  try {
    const base64 = token.split('.')[1]
    const payload = JSON.parse(atob(base64))
    const roles = payload.roles || []
    const maxRoleLevel = Math.max(...roles.map((r: string) => ROLE_LEVELS[r] ?? 0), 0)
    return {
      userId: payload.sub?.replace(':pre_mfa', '') ?? '',
      email: payload.email ?? '',
      roles,
      jurisdictionZones: payload.zones ?? [],
      maxRoleLevel,
      mfaEnabled: true,
    }
  } catch {
    return { userId: '', email: '', roles: [], jurisdictionZones: [], maxRoleLevel: 0, mfaEnabled: false }
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      login: async (email: string, password: string) => {
        const response = await api.post('/auth/login', { email, password })
        const data = response.data.data ?? response.data

        if (data.requires_mfa) {
          return { requiresMfa: true, tempToken: data.temp_token }
        }

        const { access_token, refresh_token } = data
        const user = parseUserFromToken(access_token)
        set({ user, accessToken: access_token, refreshToken: refresh_token, isAuthenticated: true })
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
        return { requiresMfa: false }
      },

      verifyMfa: async (tempToken: string, totpCode: string) => {
        const response = await api.post('/auth/mfa/verify', {
          temp_token: tempToken,
          totp_code: totpCode,
        })
        const { access_token, refresh_token } = response.data
        const user = parseUserFromToken(access_token)
        set({ user, accessToken: access_token, refreshToken: refresh_token, isAuthenticated: true })
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
      },

      logout: () => {
        set({ user: null, accessToken: null, refreshToken: null, isAuthenticated: false })
        delete api.defaults.headers.common['Authorization']
      },

      refreshAccessToken: async () => {
        const { refreshToken } = get()
        if (!refreshToken) return false
        try {
          const response = await api.post('/auth/refresh', { refresh_token: refreshToken })
          const { access_token, refresh_token: newRefresh } = response.data
          const user = parseUserFromToken(access_token)
          set({ user, accessToken: access_token, refreshToken: newRefresh })
          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
          return true
        } catch {
          get().logout()
          return false
        }
      },

      setTokens: (accessToken: string, refreshToken: string) => {
        const user = parseUserFromToken(accessToken)
        set({ user, accessToken, refreshToken, isAuthenticated: true })
        api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`
      },
    }),
    {
      name: 'nitcc-auth',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
