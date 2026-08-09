import { api } from '@/api/client'
import type { ReportRecord } from '@/types'

export type AdminReport = {
  id: string
  publicReference: string
  listingId: string
  reporterId: string | null
  reason: string
  comment: string
  status: 'open' | 'in_review' | 'resolved' | 'rejected'
  handledBy: string | null
  handledAt: string | null
  createdAt: string
}

type ReportDto = AdminReport

function toReport(dto: ReportDto): ReportRecord {
  return {
    id: dto.publicReference || dto.id,
    listingId: dto.listingId,
    reason: dto.reason,
    comment: dto.comment,
    createdAt: dto.createdAt,
    status: dto.status === 'resolved' || dto.status === 'rejected' ? 'Resuelta' : 'Abierta',
  }
}

export const createRemoteReport = async (listingId: string, reason: string, comment: string) =>
  toReport(await api<ReportDto>('/reports', { method: 'POST', body: JSON.stringify({ listingId, reason, comment }) }))

export const getRemoteReports = async () => (await api<ReportDto[]>('/reports')).map(toReport)

export const getAdminReports = () => api<AdminReport[]>('/reports?limit=200&offset=0')

export const updateAdminReport = (id: string, status: AdminReport['status']) =>
  api<AdminReport>(`/reports/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) })
