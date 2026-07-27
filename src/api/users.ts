import { api } from './client'
import type { DemoUser } from '@/types'

type ProfilePayload = Partial<Pick<DemoUser, 'name' | 'phone' | 'whatsapp' | 'telegram' | 'about' | 'showPhone' | 'showWhatsApp' | 'allowContactForm'>>

export const updateCurrentUser = (payload: ProfilePayload) =>
  api<Omit<DemoUser, 'password'>>('/users/me', { method: 'PATCH', body: JSON.stringify(payload) })

export const deleteCurrentUser = () => api<void>('/users/me', { method: 'DELETE' })
