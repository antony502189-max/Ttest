import { api } from '@/api/client'
import type { RestrictionType } from '@/api/admin'

export type MyRestriction = {
  restrictionType: RestrictionType
  reason: string
  until: string
  supportEmail: string
}

export type ModerationNotice = {
  id: string
  kind: string
  title: string
  body: string
  createdAt: string
  readAt: string | null
}

export const getMyRestriction = () => api<MyRestriction | null>('/users/me/restriction')
export const getModerationNotices = () => api<ModerationNotice[]>('/users/me/moderation-notices?limit=20')
export const markModerationNoticeRead = (id: string) =>
  api<void>(`/users/me/moderation-notices/${id}/read`, { method: 'PATCH' })
