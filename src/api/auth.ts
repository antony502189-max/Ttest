import { api, setAccessToken } from './client'
import type { UserRole } from '@/types'
import type { RemoteUser } from './users'

type Session = { accessToken: string; user: RemoteUser }

const SESSION_HINT = '112233:has-session'
export const AUTH_READY_EVENT = '112233:auth-ready'

export function hasSessionHint() {
  try { return localStorage.getItem(SESSION_HINT) === '1' } catch { return false }
}

function rememberSession() {
  try { localStorage.setItem(SESSION_HINT, '1') } catch { /* Session still works for the current tab. */ }
}

function forgetSession() {
  try { localStorage.removeItem(SESSION_HINT) } catch { /* Storage can be unavailable in private mode. */ }
}

function announceAuthReady() {
  window.setTimeout(() => window.dispatchEvent(new Event(AUTH_READY_EVENT)), 0)
}

export async function loginWithPassword(email: string, password: string) {
  const session = await api<Session>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
  setAccessToken(session.accessToken)
  rememberSession()
  return session.user
}

export async function loginWithGoogle(credential: string) {
  const session = await api<Session>('/auth/google', { method: 'POST', body: JSON.stringify({ credential }) })
  setAccessToken(session.accessToken)
  rememberSession()
  return session.user
}

export const selectGoogleRole = (role: 'tenant' | 'host') =>
  api<RemoteUser>('/auth/google/role', { method: 'POST', body: JSON.stringify({ role }) })

export async function registerAccount(input: { name: string; email: string; password: string; role: UserRole }) {
  const session = await api<Session>('/auth/register', { method: 'POST', body: JSON.stringify(input) })
  setAccessToken(session.accessToken)
  rememberSession()
  return session.user
}

export const requestPasswordReset = (email: string) => api<{ message: string; resetToken?: string }>('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) })
export const resetPassword = (token: string, password: string) => api<void>('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, password }) })
export const requestEmailVerification = () => api<{ message: string; email: string; cooldownSeconds: number }>('/auth/email-verification/request', { method: 'POST' })
export const verifyEmail = (code: string) => api<void>('/auth/email-verification/confirm', { method: 'POST', body: JSON.stringify({ code }) })
export const getEmailVerificationStatus = () => api<{ verified: boolean; email: string }>('/auth/email-verification/status')

export async function hydrateSession() {
  if (!hasSessionHint()) {
    announceAuthReady()
    return null
  }
  try {
    const session = await api<Session>('/auth/refresh', { method: 'POST' })
    setAccessToken(session.accessToken)
    return session.user
  } catch (error) {
    forgetSession()
    setAccessToken(null)
    throw error
  } finally {
    announceAuthReady()
  }
}

export async function logoutSession() {
  if (!hasSessionHint()) {
    setAccessToken(null)
    return
  }
  try {
    await api<void>('/auth/logout', { method: 'POST' })
  } catch {
    // Server-side revocation is best-effort during an outage. Local logout is
    // still authoritative, so callers must be allowed to clear UI state and
    // navigate away instead of keeping a stale authenticated screen mounted.
  } finally {
    forgetSession()
    setAccessToken(null)
  }
}
