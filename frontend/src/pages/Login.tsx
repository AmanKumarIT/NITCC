/**
 * S1 — Login / MFA Page
 * PRD Screen S1: Email + password, TOTP input, SSO button
 * WCAG 2.1 AA compliant
 */

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import { Shield, Eye, EyeOff, Train, Loader2, AlertCircle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import toast from 'react-hot-toast'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login, verifyMfa } = useAuthStore()

  const [step, setStep] = useState<'credentials' | 'mfa'>('credentials')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [mfaCode, setMfaCode] = useState('')
  const [tempToken, setTempToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleCredentialsSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) return
    setLoading(true)
    setError('')
    try {
      const result = await login(email, password)
      if (result.requiresMfa && result.tempToken) {
        setTempToken(result.tempToken)
        setStep('mfa')
        toast.success('Password verified. Enter your MFA code.')
      } else {
        toast.success('Login successful')
        navigate('/', { replace: true })
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Login failed'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleMfaSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (mfaCode.length !== 6) return
    setLoading(true)
    setError('')
    try {
      await verifyMfa(tempToken, mfaCode)
      toast.success('Authentication successful')
      navigate('/', { replace: true })
    } catch {
      setError('Invalid MFA code. Please try again.')
      setMfaCode('')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-navy-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 bg-gradient-command" />
      <div className="absolute inset-0">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-electric-500/5 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-electric-700/5 rounded-full blur-3xl" />
      </div>

      {/* Grid pattern overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(rgba(30,111,217,0.5) 1px, transparent 1px),
                           linear-gradient(90deg, rgba(30,111,217,0.5) 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative z-10 w-full max-w-md"
      >
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-electric-500/10 border border-electric-500/20 mb-4">
            <Train className="w-8 h-8 text-electric-400" />
          </div>
          <h1 className="text-2xl font-bold text-white mb-1">
            NITCC Command Center
          </h1>
          <p className="text-sm text-white/50">
            National Intelligent Transportation Command Center
          </p>
          <p className="text-xs text-white/30 mt-1">
            Ministry of Railways, Government of India
          </p>
        </div>

        {/* Login Card */}
        <div className="nitcc-card p-8">
          <AnimatePresence mode="wait">
            {step === 'credentials' ? (
              <motion.form
                key="credentials"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                onSubmit={handleCredentialsSubmit}
                className="space-y-5"
                aria-label="Login form"
              >
                <div>
                  <h2 className="text-lg font-semibold text-white mb-1">Sign In</h2>
                  <p className="text-xs text-white/40">Authorized personnel only</p>
                </div>

                {/* Email */}
                <div className="space-y-1.5">
                  <label htmlFor="email" className="text-xs font-medium text-white/60 uppercase tracking-wider">
                    Email Address
                  </label>
                  <input
                    id="email"
                    type="email"
                    autoComplete="email"
                    required
                    className="nitcc-input"
                    placeholder="operator@railwayzone.gov.in"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    aria-describedby={error ? 'login-error' : undefined}
                  />
                </div>

                {/* Password */}
                <div className="space-y-1.5">
                  <label htmlFor="password" className="text-xs font-medium text-white/60 uppercase tracking-wider">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      required
                      className="nitcc-input pr-10"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Error */}
                {error && (
                  <div
                    id="login-error"
                    role="alert"
                    className="flex items-center gap-2 p-3 rounded-lg bg-critical/10 border border-critical/20 text-critical text-sm"
                  >
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {error}
                  </div>
                )}

                {/* Submit */}
                <button
                  id="login-submit-btn"
                  type="submit"
                  disabled={loading || !email || !password}
                  className="btn-primary w-full h-11"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Authenticating...
                    </>
                  ) : 'Sign In'}
                </button>

                {/* SSO */}
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-white/10" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="bg-navy-800 px-2 text-white/40">or</span>
                  </div>
                </div>

                <button
                  id="sso-login-btn"
                  type="button"
                  className="btn-ghost w-full h-11"
                  onClick={() => toast('SSO integration configured via environment settings.')}
                >
                  <Shield className="w-4 h-4" />
                  Sign in with SSO (OAuth 2.0 / SAML)
                </button>
              </motion.form>

            ) : (
              <motion.form
                key="mfa"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                onSubmit={handleMfaSubmit}
                className="space-y-5"
                aria-label="MFA verification form"
              >
                <div>
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-warn/10 border border-warn/20 mb-3">
                    <Shield className="w-6 h-6 text-warn" />
                  </div>
                  <h2 className="text-lg font-semibold text-white mb-1">Two-Factor Authentication</h2>
                  <p className="text-xs text-white/50">
                    Enter the 6-digit code from your authenticator app (TOTP).
                    <br />Signed in as <span className="text-electric-400">{email}</span>
                  </p>
                </div>

                {/* TOTP Input */}
                <div className="space-y-1.5">
                  <label htmlFor="totp-code" className="text-xs font-medium text-white/60 uppercase tracking-wider">
                    Authenticator Code
                  </label>
                  <input
                    id="totp-code"
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    autoComplete="one-time-code"
                    required
                    autoFocus
                    className="nitcc-input text-center text-2xl font-mono tracking-[1rem] h-14"
                    placeholder="000000"
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  />
                </div>

                {error && (
                  <div role="alert" className="flex items-center gap-2 p-3 rounded-lg bg-critical/10 border border-critical/20 text-critical text-sm">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    {error}
                  </div>
                )}

                <button
                  id="mfa-submit-btn"
                  type="submit"
                  disabled={loading || mfaCode.length !== 6}
                  className="btn-primary w-full h-11"
                >
                  {loading ? (
                    <><Loader2 className="w-4 h-4 animate-spin" />Verifying...</>
                  ) : 'Verify & Sign In'}
                </button>

                <button
                  type="button"
                  className="text-xs text-white/40 hover:text-white/70 w-full text-center"
                  onClick={() => { setStep('credentials'); setError(''); setMfaCode('') }}
                >
                  ← Back to login
                </button>
              </motion.form>
            )}
          </AnimatePresence>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-white/25 mt-6">
          NITCC v1.0.0 · Classified System · Authorized Access Only<br />
          © 2026 Ministry of Railways, Government of India
        </p>
      </motion.div>
    </div>
  )
}
