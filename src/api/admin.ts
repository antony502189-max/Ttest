import { api } from '@/api/client'
import type { DemoUser, ListingStatus } from '@/types'

const statusMap: Record<ListingStatus, string> = {
  Borrador: 'draft', Pendiente: 'pending', Publicado: 'published', Oculto: 'hidden', Finalizado: 'closed', Rechazado: 'rejected',
}

type AdminUserDto = { id: string; email: string; name: string; role: DemoUser['role']; blocked: boolean }

export const moderateRemoteListing = (id: string, status: ListingStatus) =>
  api(`/admin/listings/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status: statusMap[status] }) })

export const setRemoteUserBlocked = (id: string, blocked: boolean) =>
  api<AdminUserDto>(`/admin/users/${id}/blocked`, { method: 'PATCH', body: JSON.stringify({ blocked }) })

export async function getAdminUsers(): Promise<DemoUser[]> {
  const users = await api<AdminUserDto[]>('/admin/users')
  return users.map((user) => ({ ...user, password: '', initials: user.name.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase(), phone: '', whatsapp: '', telegram: '', about: '', showPhone: false, showWhatsApp: false, allowContactForm: true, allowMessaging: true }))
}
