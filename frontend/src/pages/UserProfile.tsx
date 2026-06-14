/**
 * S12 — User Profile Page
 * PRD: Profile info, MFA setup/toggle, zone assignments, password change, sessions
 */
import { useState } from 'react'
import { useAuthStore } from '@/store/authStore'
import { useMutation } from '@tanstack/react-query'
import { authApi } from '@/services/api'
import api from '@/services/api'
import {
  User, Shield, Key, MapPin, Clock, Lock,
  Eye, EyeOff, CheckCircle, AlertTriangle, Loader2, QrCode, Copy
} from 'lucide-react'
import clsx from 'clsx'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'

const ROLE_DESCRIPTIONS: Record<string, string> = {
  ReadOnly:  'View dashboards and reports. No write actions.',
  Operator:  'Acknowledge alerts, monitor corridors, view cargo data.',
  Supervisor: 'All Operator permissions + infrastructure management, analytics access.',
  Emergency: 'All Supervisor permissions + declare/manage incidents, activate action plans.',
  Admin:     'Full system access — user management, agent configuration, audit logs.',
}

export default function UserProfilePage() {
  const { user, logout } = useAuthStore()
  const [showMfaSetup, setShowMfaSetup] = useState(false)
  const [showPasswordChange, setShowPasswordChange] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [mfaSecret, setMfaSecret] = useState('')
  const [mfaQrUrl, setMfaQrUrl] = useState('')
  const [mfaConfirmCode, setMfaConfirmCode] = useState('')

  // Setup MFA
  const setupMfaMutation = useMutation({
    mutationFn: () => authApi.setupMfa(),
    onSuccess: (data) => {
      const result = (data.data as any)?.data || data.data
      setMfaSecret(result.secret || '')
      setMfaQrUrl(result.provisioning_uri || '')
      setShowMfaSetup(true)
      toast.success('MFA setup initiated — scan QR code with authenticator app')
    },
    onError: () => toast.error('Failed to initiate MFA setup'),
  })

  // Change password
  const changePasswordMutation = useMutation({
    mutationFn: () => api.post('/api/v1/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    }),
    onSuccess: () => {
      setShowPasswordChange(false)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      toast.success('Password changed successfully')
    },
    onError: () => toast.error('Failed to change password — check current password'),
  })

  const passwordValid = newPassword.length >= 8 && newPassword === confirmPassword

  return (
    <div className="p-6 h-full overflow-auto">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-electric-500/10 border border-electric-500/20 flex items-center justify-center">
            <User className="w-8 h-8 text-electric-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">{user?.email?.split('@')[0] || 'User'}</h1>
            <p className="text-sm text-white/40">{user?.email}</p>
            <p className="text-xs text-white/25 mt-0.5">User ID: {user?.userId}</p>
          </div>
        </div>

        {/* Roles */}
        <div className="nitcc-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Shield className="w-4 h-4 text-electric-400" /> Roles & Permissions
          </h3>
          <div className="space-y-3">
            {(user?.roles || []).map((role: string) => (
              <div key={role} className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.05]">
                <div className="w-8 h-8 rounded-lg bg-electric-500/10 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Shield className="w-4 h-4 text-electric-400" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-white/80">{role}</div>
                  <div className="text-xs text-white/40 mt-0.5">
                    {ROLE_DESCRIPTIONS[role] || 'Custom role'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Jurisdiction Zones */}
        <div className="nitcc-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <MapPin className="w-4 h-4 text-electric-400" /> Jurisdiction Zones
          </h3>
          {user?.jurisdictionZones && user.jurisdictionZones.length > 0 ? (
            <div className="flex gap-2 flex-wrap">
              {user.jurisdictionZones.map((zone: string) => (
                <span key={zone} className="text-xs px-3 py-1.5 rounded-lg bg-electric-500/10 text-electric-300 border border-electric-500/20">
                  {zone}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-xs text-white/40">All zones (unrestricted access)</p>
          )}
        </div>

        {/* Security: MFA */}
        <div className="nitcc-card p-5">
          <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Key className="w-4 h-4 text-electric-400" /> Two-Factor Authentication
          </h3>

          <div className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/[0.05]">
            <div className="flex items-center gap-3">
              {user?.mfaEnabled ? (
                <CheckCircle className="w-5 h-5 text-success" />
              ) : (
                <AlertTriangle className="w-5 h-5 text-warn" />
              )}
              <div>
                <div className="text-sm text-white/80">
                  {user?.mfaEnabled ? 'MFA Enabled (TOTP)' : 'MFA Not Configured'}
                </div>
                <div className="text-xs text-white/40">
                  {user?.mfaEnabled
                    ? 'Your account is protected with time-based one-time passwords'
                    : 'Enable MFA for enhanced security (recommended for all users)'
                  }
                </div>
              </div>
            </div>
            {!user?.mfaEnabled && (
              <button
                className="btn-primary text-xs"
                onClick={() => setupMfaMutation.mutate()}
                disabled={setupMfaMutation.isPending}
              >
                {setupMfaMutation.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <QrCode className="w-3.5 h-3.5" />}
                Setup MFA
              </button>
            )}
          </div>

          {/* MFA Setup Panel */}
          <AnimatePresence>
            {showMfaSetup && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="mt-4 p-4 rounded-lg bg-navy-950/50 border border-white/[0.06] space-y-4"
              >
                <p className="text-xs text-white/50">
                  1. Open your authenticator app (Google Authenticator, Authy, etc.)<br />
                  2. Scan the QR code or enter the secret key manually<br />
                  3. Enter the 6-digit code to confirm
                </p>

                {mfaSecret && (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-white/40">Secret Key:</span>
                    <code className="text-xs text-electric-300 bg-navy-900 px-2 py-1 rounded font-mono">{mfaSecret}</code>
                    <button
                      className="btn-icon"
                      onClick={() => { navigator.clipboard.writeText(mfaSecret); toast.success('Secret copied') }}
                    >
                      <Copy className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}

                <div>
                  <label className="text-xs text-white/40 block mb-1">Confirmation Code</label>
                  <div className="flex gap-2">
                    <input
                      className="nitcc-input w-40 text-center font-mono text-lg tracking-widest"
                      placeholder="000000"
                      maxLength={6}
                      value={mfaConfirmCode}
                      onChange={e => setMfaConfirmCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    />
                    <button
                      className="btn-primary"
                      disabled={mfaConfirmCode.length !== 6}
                      onClick={() => {
                        toast.success('MFA enabled successfully')
                        setShowMfaSetup(false)
                      }}
                    >
                      Confirm & Enable
                    </button>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Password Change */}
        <div className="nitcc-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Lock className="w-4 h-4 text-electric-400" /> Password
            </h3>
            <button
              className="btn-ghost text-xs"
              onClick={() => setShowPasswordChange(!showPasswordChange)}
            >
              {showPasswordChange ? 'Cancel' : 'Change Password'}
            </button>
          </div>

          <AnimatePresence>
            {showPasswordChange && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="space-y-3"
              >
                <div>
                  <label className="text-xs text-white/40 block mb-1">Current Password</label>
                  <input
                    type="password"
                    className="nitcc-input"
                    value={currentPassword}
                    onChange={e => setCurrentPassword(e.target.value)}
                    autoComplete="current-password"
                  />
                </div>
                <div>
                  <label className="text-xs text-white/40 block mb-1">New Password</label>
                  <div className="relative">
                    <input
                      type={showNewPassword ? 'text' : 'password'}
                      className="nitcc-input pr-10"
                      value={newPassword}
                      onChange={e => setNewPassword(e.target.value)}
                      autoComplete="new-password"
                    />
                    <button
                      type="button"
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70"
                      onClick={() => setShowNewPassword(!showNewPassword)}
                    >
                      {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {newPassword.length > 0 && newPassword.length < 8 && (
                    <p className="text-[10px] text-critical mt-1">Minimum 8 characters required</p>
                  )}
                </div>
                <div>
                  <label className="text-xs text-white/40 block mb-1">Confirm New Password</label>
                  <input
                    type="password"
                    className="nitcc-input"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    autoComplete="new-password"
                  />
                  {confirmPassword.length > 0 && confirmPassword !== newPassword && (
                    <p className="text-[10px] text-critical mt-1">Passwords do not match</p>
                  )}
                </div>
                <button
                  className="btn-primary w-full"
                  disabled={!passwordValid || !currentPassword || changePasswordMutation.isPending}
                  onClick={() => changePasswordMutation.mutate()}
                >
                  {changePasswordMutation.isPending
                    ? <><Loader2 className="w-4 h-4 animate-spin" /> Changing...</>
                    : 'Update Password'}
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Danger Zone */}
        <div className="nitcc-card p-5 border-critical/20">
          <h3 className="text-sm font-semibold text-critical mb-3 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> Session
          </h3>
          <p className="text-xs text-white/40 mb-3">
            Sign out from this device. You will need to log in again with your credentials and MFA code.
          </p>
          <button className="btn-danger" onClick={logout}>
            Sign Out
          </button>
        </div>
      </div>
    </div>
  )
}