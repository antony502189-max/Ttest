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

export const getNotifications = () => api<NotificationPage>('/notifications')
export const markNotificationRead = (id: string) => api<void>(`/notifications/${id}/read`, { method: 'PATCH' })
export const markAllNotificationsRead = () => api<void>('/notifications/read-all', { method: 'PATCH' })
