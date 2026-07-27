import { api } from '@/api/client'
import type { ReportRecord } from '@/types'

type ReportDto = { id: string; publicReference: string; listingId: string; reason: string; comment: string; status: string; createdAt: string }

function toReport(dto: ReportDto): ReportRecord {
  return { id: dto.publicReference || dto.id, listingId: dto.listingId, reason: dto.reason, comment: dto.comment, createdAt: dto.createdAt, status: dto.status === 'resolved' ? 'Resuelta' : 'Abierta' }
}

export const createRemoteReport = async (listingId: string, reason: string, comment: string) =>
  toReport(await api<ReportDto>('/reports', { method: 'POST', body: JSON.stringify({ listingId, reason, comment }) }))

export const getRemoteReports = async () => (await api<ReportDto[]>('/reports')).map(toReport)
