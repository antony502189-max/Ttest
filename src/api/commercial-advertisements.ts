import { api, resolveApiUrl } from '@/api/client'

export type DestinationType = 'website' | 'phone' | 'whatsapp' | 'email'
export type AdvertisementWrite = {
  title: string
  description: string
  imageAssetId: string
  destinationType: DestinationType
  destination: string
  packageId: 'test_homepage_30d'
}
export type PublicAdvertisement = {
  id: string
  title: string
  description: string
  imageUrl: string
  imageWidth: number
  imageHeight: number
  destinationType: DestinationType
  destinationUrl: string
  placement: string
}
export type AdvertisementDetail = AdvertisementWrite & {
  id: string
  ownerUserId: string
  imageUrl: string
  status: string
  paymentStatus: string
  placement: string
  createdAt: string
  startsAt: string | null
  endsAt: string | null
  moderationNote: string | null
}
export type AdminAdvertisement = AdvertisementDetail & { ownerEmail: string; adminPriority: number }

export const adImageUrl = (path: string) => resolveApiUrl(path)
export const getHomepageAdvertisements = () => api<PublicAdvertisement[]>('/advertisements/homepage', { timeoutMs: 6000 })
export const getMyAdvertisements = () => api<AdvertisementDetail[]>('/advertisements/mine')
export const getAdvertisement = (id: string) => api<AdvertisementDetail>(`/advertisements/${id}`)
export const createAdvertisement = (body: AdvertisementWrite) => api<AdvertisementDetail>('/advertisements', { method: 'POST', body: JSON.stringify(body) })
export const updateAdvertisement = (id: string, body: AdvertisementWrite) => api<AdvertisementDetail>(`/advertisements/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
export const cancelAdvertisement = (id: string) => api<void>(`/advertisements/${id}`, { method: 'DELETE' })
export const createAdCheckout = (id: string) => api<{ advertisementId: string; packageId: string; displayPrice: string; paymentMode: 'test' }>(`/advertisements/${id}/checkout`, { method: 'POST' })
export const completeAdTestPayment = (id: string) => api<AdvertisementDetail>(`/advertisements/${id}/fake-payment/complete`, { method: 'POST' })
export const getAdminAdvertisements = (status?: string) => api<AdminAdvertisement[]>(`/admin/advertisements${status ? `?status_filter=${encodeURIComponent(status)}` : ''}`)
export const moderateAdvertisement = (id: string, action: 'approve' | 'reject' | 'deactivate', note?: string) => api<AdvertisementDetail>(`/admin/advertisements/${id}/${action}`, { method: 'POST', body: JSON.stringify({ note: note || null }) })

export async function uploadAdvertisementImage(file: File) {
  const body = new FormData()
  body.append('file', file)
  return api<{ id: string; url: string }>('/advertisements/uploads', { method: 'POST', body, timeoutMs: 45_000 })
}
