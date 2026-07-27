import { api } from '@/api/client'

export type RemoteThread = {
  id: string
  listingId: string
  tenantId: string
  hostId: string
  lastMessageAt: string
  lastMessagePreview: string | null
}

export const getRemoteThreads = () => api<RemoteThread[]>('/messages/threads')
export const sendRemoteMessage = (listingId: string, body: string) =>
  api<{ id: string; threadId: string }>('/messages', { method: 'POST', body: JSON.stringify({ listingId, body }) })
