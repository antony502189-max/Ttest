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
const ADMIN_REPORT_MAX_OFFSET = 10_000

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
  let cursor: AdminReport | null = null
  while (true) {
    const params = new URLSearchParams({ limit: String(ADMIN_REPORT_PAGE_SIZE) })
    if (cursor) {
      params.set('offset', '0')
      params.set('afterCreatedAt', cursor.createdAt)
      params.set('afterId', cursor.id)
    } else {
      params.set('offset', String(offset))
    }
    const page = await api<AdminReport[]>(`/reports?${params}`)
    result.push(...page)
    if (page.length < ADMIN_REPORT_PAGE_SIZE) return result

    const last = page.at(-1)
    if (!last) return result
    if (cursor || offset >= ADMIN_REPORT_MAX_OFFSET) {
      cursor = last
    } else {
      offset += ADMIN_REPORT_PAGE_SIZE
    }
  }
}

export const updateAdminReport = (id: string, status: AdminReport['status']) =>
  api<AdminReport>(`/reports/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) })
