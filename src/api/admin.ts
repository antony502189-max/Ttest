import { api, resolveApiUrl } from '@/api/client'
import type { DemoUser, ListingStatus } from '@/types'

const statusMap: Record<ListingStatus, string> = {
  Borrador: 'draft', Pendiente: 'pending', Publicado: 'published', Oculto: 'hidden', Finalizado: 'closed', Rechazado: 'rejected',
}

type AdminUserDto = {
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
}

export const moderateRemoteListing = (id: string, status: ListingStatus) =>
  api(`/admin/listings/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status: statusMap[status] }) })

export const setRemoteUserBlocked = (id: string, blocked: boolean) =>
  api<AdminUserDto>(`/admin/users/${id}/blocked`, { method: 'PATCH', body: JSON.stringify({ blocked }) })

const ADMIN_USER_PAGE_SIZE = 200

async function getAllAdminUserDtos(): Promise<AdminUserDto[]> {
  const users: AdminUserDto[] = []
  const seen = new Set<string>()
  let offset = 0

  while (true) {
    const page = await api<AdminUserDto[]>(`/admin/users?limit=${ADMIN_USER_PAGE_SIZE}&offset=${offset}`)
    let added = 0
    for (const user of page) {
      if (seen.has(user.id)) continue
      seen.add(user.id)
      users.push(user)
      added += 1
    }
    if (page.length < ADMIN_USER_PAGE_SIZE) return users
    if (added === 0) throw new Error('La paginación de usuarios no avanzó.')
    offset += page.length
  }
}

export async function getAdminUsers(): Promise<DemoUser[]> {
  const users = await getAllAdminUserDtos()
  return users.map((user) => ({
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    blocked: user.blocked,
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
