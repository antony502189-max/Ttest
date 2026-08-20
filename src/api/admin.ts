import { api, resolveApiUrl } from '@/api/client'
import type { DemoUser, ListingStatus } from '@/types'

export type RestrictionType = 'full' | 'publish' | 'view_listings'

export type AdminRestriction = {
  id: string
  restrictionType: RestrictionType
  reason: string
  startsAt: string
  endsAt: string | null
  revokedAt: string | null
  active: boolean
}

export type AdminListingRestriction = {
  id: string
  reason: string
  startsAt: string
  endsAt: string
  revokedAt: string | null
  active: boolean
}

export type AdminUser = {
  id: string
  email: string
  name: string
  role: DemoUser['role']
  blocked: boolean
  phone: string
  whatsapp: string
  telegram: string
  about: string
  initials: string
  showPhone: boolean
  showWhatsApp: boolean
  allowContactForm: boolean
  avatarUrl: string | null
  createdAt: string
  deletedAt: string | null
  lastLoginAt: string | null
  listingCount: number
  activeRestriction: AdminRestriction | null
  isAdmin: boolean
}

export type AdminUserDetail = AdminUser & { restrictions: AdminRestriction[] }

export type AdminListing = {
  id: string
  ownerUserId: string
  ownerName: string | null
  ownerEmail: string | null
  title: string
  city: string
  area: string
  status: string
  rentalMode: string
  views: number
  createdAt: string
  deletedAt: string | null
  activeRestriction: AdminListingRestriction | null
  promoted: boolean
  boostedAt: string | null
}

export type AdminNote = {
  id: string
  userId: string
  body: string
  createdBy: string | null
  createdByName: string | null
  createdAt: string
}

export type AdminAccount = {
  email: string
  active: boolean
  createdBy: string | null
  createdAt: string
}

export type AdminAuditLog = {
  id: string
  actorId: string | null
  actorName: string | null
  action: string
  targetType: string
  targetId: string | null
  detail: Record<string, unknown>
  createdAt: string
}

const statusMap: Record<ListingStatus, string> = {
  Borrador: 'draft',
  Pendiente: 'pending',
  Publicado: 'published',
  Oculto: 'hidden',
  Finalizado: 'closed',
  Rechazado: 'rejected',
}

const ADMIN_PAGE_SIZE = 200

type CursorRow = { id: string; createdAt: string }

async function drainAdminPages<T extends CursorRow>(path: string, params: URLSearchParams): Promise<T[]> {
  const result: T[] = []
  let cursor: T | null = null
  while (true) {
    params.set('limit', String(ADMIN_PAGE_SIZE))
    params.set('offset', '0')
    if (cursor) {
      params.set('afterCreatedAt', cursor.createdAt)
      params.set('afterId', cursor.id)
    } else {
      params.delete('afterCreatedAt')
      params.delete('afterId')
    }
    const page = await api<T[]>(`${path}?${params}`)
    result.push(...page)
    if (page.length < ADMIN_PAGE_SIZE) return result

    const last = page.at(-1)
    if (!last) return result
    cursor = last
  }
}

export const checkAdminAccess = () => api<{ isAdmin: true; email: string }>('/admin/access')

export async function getAdminUserRows(search = '', status = ''): Promise<AdminUser[]> {
  const params = new URLSearchParams()
  if (search.trim()) params.set('search', search.trim())
  if (status) params.set('status', status)
  return drainAdminPages<AdminUser>('/admin/users', params)
}

export async function getAdminUsers(): Promise<DemoUser[]> {
  const users = (await getAdminUserRows()).filter((user) => !user.deletedAt)
  return users.map((user) => ({
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    blocked: Boolean(user.blocked || user.activeRestriction?.restrictionType === 'full'),
    password: '',
    initials: user.initials || user.name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase(),
    phone: user.phone,
    whatsapp: user.whatsapp,
    telegram: user.telegram,
    about: user.about,
    showPhone: user.showPhone,
    showWhatsApp: user.showWhatsApp,
    allowContactForm: user.allowContactForm,
    allowMessaging: user.allowContactForm,
    avatarRef: user.avatarUrl ? resolveApiUrl(user.avatarUrl) : undefined,
  }))
}

export async function getAdminUser(id: string): Promise<AdminUserDetail> {
  return api<AdminUserDetail>(`/admin/users/${id}`)
}

export const restrictAdminUser = (
  id: string,
  payload: { restrictionType: RestrictionType; until: string | null; reason: string },
) => api<AdminUserDetail>(`/admin/users/${id}/restrictions`, {
  method: 'POST',
  body: JSON.stringify(payload),
})

export const unrestrictAdminUser = (id: string) =>
  api<AdminUserDetail>(`/admin/users/${id}/restrictions/active`, { method: 'DELETE' })

export const deleteAdminUser = (id: string, reason: string) =>
  api<void>(`/admin/users/${id}`, { method: 'DELETE', body: JSON.stringify({ reason }) })

export const getAdminNotes = (id: string) => api<AdminNote[]>(`/admin/users/${id}/notes`)
export const addAdminNote = (id: string, body: string) =>
  api<AdminNote>(`/admin/users/${id}/notes`, { method: 'POST', body: JSON.stringify({ body }) })

export async function getAdminListings(search = '', status = '', restricted?: boolean): Promise<AdminListing[]> {
  const params = new URLSearchParams()
  if (search.trim()) params.set('search', search.trim())
  if (status) params.set('status', status)
  if (restricted !== undefined) params.set('restricted', String(restricted))
  return drainAdminPages<AdminListing>('/admin/listings', params)
}

export const moderateRemoteListing = (id: string, status: ListingStatus) =>
  api<AdminListing>(`/admin/listings/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status: statusMap[status] }),
  })

export const restrictAdminListing = (id: string, payload: { until: string; reason: string }) =>
  api<AdminListing>(`/admin/listings/${id}/restrictions`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })

export const unrestrictAdminListing = (id: string) =>
  api<AdminListing>(`/admin/listings/${id}/restrictions/active`, { method: 'DELETE' })

export const promoteAdminListing = (id: string) =>
  api<AdminListing>(`/admin/listings/${id}/promotion`, { method: 'PUT' })

export const removeAdminListingPromotion = (id: string) =>
  api<AdminListing>(`/admin/listings/${id}/promotion`, { method: 'DELETE' })

export const getAdmins = () => api<AdminAccount[]>('/admin/admins')
export const addAdministrator = (email: string) =>
  api<AdminAccount>('/admin/admins', { method: 'POST', body: JSON.stringify({ email }) })
export const revokeAdministrator = (email: string) =>
  api<void>(`/admin/admins/${encodeURIComponent(email)}`, { method: 'DELETE' })

export const getAdminAuditLog = () => drainAdminPages<AdminAuditLog>('/admin/audit-log', new URLSearchParams())

export async function setRemoteUserBlocked(id: string, blocked: boolean) {
  if (!blocked) return unrestrictAdminUser(id)
  return restrictAdminUser(id, {
    restrictionType: 'full',
    until: null,
    reason: 'Cuenta restringida por administración',
  })
}
