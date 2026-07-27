import { api, setAccessToken } from './client'
import type { DemoUser, UserRole } from '@/types'
type Session = { accessToken: string; user: Omit<DemoUser, 'password'> }
export async function loginWithPassword(email: string, password: string) { const session = await api<Session>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }); setAccessToken(session.accessToken); return session.user }
export async function registerAccount(input: { name: string; email: string; password: string; role: UserRole }) { const session = await api<Session>('/auth/register', { method: 'POST', body: JSON.stringify(input) }); setAccessToken(session.accessToken); return session.user }
export async function hydrateSession() { const session = await api<Session>('/auth/refresh', { method: 'POST' }); setAccessToken(session.accessToken); return session.user }
export async function logoutSession() { await api<void>('/auth/logout', { method: 'POST' }); setAccessToken(null) }
