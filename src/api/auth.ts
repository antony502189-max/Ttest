import { api, setAccessToken } from './client'
import type { UserRole } from '@/types'
import type { RemoteUser } from './users'
type Session = { accessToken: string; user: RemoteUser }
const SESSION_HINT = '112233:has-session'

export async function loginWithPassword(email: string, password: string) { const session = await api<Session>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }); setAccessToken(session.accessToken); localStorage.setItem(SESSION_HINT, '1'); return session.user }
export async function loginWithGoogle(credential: string) { const session = await api<Session>('/auth/google', { method: 'POST', body: JSON.stringify({ credential }) }); setAccessToken(session.accessToken); localStorage.setItem(SESSION_HINT, '1'); return session.user }
export async function registerAccount(input: { name: string; email: string; password: string; role: UserRole }) { const session = await api<Session>('/auth/register', { method: 'POST', body: JSON.stringify(input) }); setAccessToken(session.accessToken); localStorage.setItem(SESSION_HINT, '1'); return session.user }
export const requestPasswordReset = (email: string) => api<{ message: string; resetToken?: string }>('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email }) })
export const resetPassword = (token: string, password: string) => api<void>('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, password }) })
export const verifyEmail = (token: string) => api<void>('/auth/verify-email', { method: 'POST', body: JSON.stringify({ token }) })
export async function hydrateSession() {
  if (!localStorage.getItem(SESSION_HINT)) return null
  try { const session = await api<Session>('/auth/refresh', { method: 'POST' }); setAccessToken(session.accessToken); return session.user }
  catch (error) { localStorage.removeItem(SESSION_HINT); throw error }
}
export async function logoutSession() { try { await api<void>('/auth/logout', { method: 'POST' }) } finally { localStorage.removeItem(SESSION_HINT); setAccessToken(null) } }
