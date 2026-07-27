import { api } from './client'
import { uploadMediaReference } from './media'
import type { DemoUser } from '@/types'

type ProfilePayload = Partial<Pick<DemoUser, 'name' | 'phone' | 'whatsapp' | 'telegram' | 'about' | 'showPhone' | 'showWhatsApp' | 'allowContactForm'>>
export type RemoteUser = Omit<DemoUser, 'password' | 'avatarRef'> & { avatarUrl?: string | null }

export const updateCurrentUser = (payload: ProfilePayload) =>
  api<RemoteUser>('/users/me', { method: 'PATCH', body: JSON.stringify(payload) })

export async function updateCurrentAvatar(reference: string | undefined) {
  if (!reference) return api<RemoteUser>('/users/me/avatar', { method: 'PUT', body: JSON.stringify({ assetId: null }) })
  const asset = await uploadMediaReference(reference)
  return api<RemoteUser>('/users/me/avatar', { method: 'PUT', body: JSON.stringify({ assetId: asset.id }) })
}

export const deleteCurrentUser = () => api<void>('/users/me', { method: 'DELETE' })
