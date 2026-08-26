import { api, setAccessToken } from './client'
import { uploadMediaReference } from './media'
import type { DemoUser } from '@/types'

type ProfilePayload = Partial<Pick<DemoUser, 'name' | 'phone' | 'whatsapp' | 'telegram' | 'about' | 'showPhone' | 'showWhatsApp'>>
export type RemoteUser = Omit<DemoUser, 'password' | 'avatarRef'> & { avatarUrl?: string | null }
const SESSION_HINT = '112233:has-session'

export const updateCurrentUser = (payload: ProfilePayload) =>
  api<RemoteUser>('/users/me', { method: 'PATCH', body: JSON.stringify(payload) })

export async function updateCurrentAvatar(reference: string | undefined) {
  if (!reference) return api<RemoteUser>('/users/me/avatar', { method: 'PUT', body: JSON.stringify({ assetId: null }) })
  const asset = await uploadMediaReference(reference)
  return api<RemoteUser>('/users/me/avatar', { method: 'PUT', body: JSON.stringify({ assetId: asset.id }) })
}

export async function deleteCurrentUser() {
  await api<void>('/users/me', { method: 'DELETE' })
  localStorage.removeItem(SESSION_HINT)
  setAccessToken(null)
}
