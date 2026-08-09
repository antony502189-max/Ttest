import { api } from '@/api/client'
import type { ReportRecord } from '@/types'

export type ReportTargetType = 'listing' | 'user'

export type AdminReport = {
  id: string
  publicReference: string
  listingId: string
  targetType: ReportTargetType
  targetUserId: string | null
  reporterId: string | null
  reason: string
  comment: string
  status: 'open' | 'in_review' | 'resolved' | 'rejected'
  handledBy: string | null
  handledAt: string | null
  createdAt: string
}

type ReportDto = AdminReport

const ADMIN_REPORT_PAGE_SIZE = 200

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

export const createRemoteReport = async (
  listingId: string,
  reason: string,
  comment: string,
  targetType: ReportTargetType = 'listing',
) => toReport(await api<ReportDto>('/reports', {
  method: 'POST',
  body: JSON.stringify({ listingId, targetType, reason, comment }),
}))

export const getRemoteReports = async () => (await api<ReportDto[]>('/reports')).map(toReport)

export async function getAdminReports(): Promise<AdminReport[]> {
  const result: AdminReport[] = []
  let offset = 0
  while (true) {
    const page = await api<AdminReport[]>(`/reports?limit=${ADMIN_REPORT_PAGE_SIZE}&offset=${offset}`)
    result.push(...page)
    if (page.length < ADMIN_REPORT_PAGE_SIZE) return result
    offset += ADMIN_REPORT_PAGE_SIZE
  }
}

export const updateAdminReport = (id: string, status: AdminReport['status']) =>
  api<AdminReport>(`/reports/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) })
