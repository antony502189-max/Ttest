import { api } from './client'

export type NotificationItem = {
  id: string
  type: string
  entityListingId: string | null
  title: string
  body: string
  createdAt: string
  readAt: string | null
}

export type NotificationPage = { items: NotificationItem[]; unreadCount: number }

export const NOTIFICATIONS_UPDATED_EVENT = '112233:notifications-updated'

function announceNotificationsUpdated() {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(NOTIFICATIONS_UPDATED_EVENT))
}

export const getNotifications = () => api<NotificationPage>('/notifications')

export async function markNotificationRead(id: string) {
  await api<void>(`/notifications/${id}/read`, { method: 'PATCH' })
  announceNotificationsUpdated()
}

export async function markAllNotificationsRead() {
  await api<void>('/notifications/read-all', { method: 'PATCH' })
  announceNotificationsUpdated()
}
