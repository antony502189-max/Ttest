import { api, resolveApiUrl } from '@/api/client'

export type DestinationType = 'website' | 'phone' | 'whatsapp' | 'email'
export type AdvertisementWrite = {
  title: string
  description: string
  imageAssetId: string
  destinationType: DestinationType
  destination: string
  packageId: 'homepage_1d'
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
export type AdvertisementDetail = Omit<AdvertisementWrite, 'packageId'> & {
  packageId: string
  id: string
  ownerUserId: string
  imageUrl: string
  status: string
  paymentStatus: string
  paymentOrderId?: string | null
  paymentReviewRequired?: boolean
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
export const createAdCheckout = (id: string) => api<{ url: string; amountCents: number; currency: string }>(`/payments/advertisements/${id}/checkout`, { method: 'POST', body: JSON.stringify({ days: 30 }) })
export const getAdQuote = (id: string) => api<{ days: number; amountCents: number; currency: string; available: boolean; reservedDays?: number | null }>(`/payments/advertisements/${id}/quote`)
export const getAdPaymentStatus = (id: string) => api<{ status: string; paymentStatus: string; orderStatus: string | null; fulfillmentStatus: string | null }>(`/payments/advertisements/${id}/status`)
export const cancelAdCheckout = (id: string) => api<{ cancelled: boolean; paid: boolean }>(`/payments/advertisements/${id}/checkout/cancel`, { method: 'POST' })
export type AdvertisingAvailability = { total: number; available: number; monthlyPriceCents: number; months: number; currency: string; pushEnabled: boolean; pushPublicKey: string | null }
export const getAdvertisingAvailability = () => api<AdvertisingAvailability>('/advertisements/availability', { timeoutMs: 6000 })
export const subscribeAdvertisingVacancy = (language: string, subscription: PushSubscriptionJSON | null) => api<{ subscribed: boolean; available: boolean }>('/advertisements/waitlist', { method: 'POST', body: JSON.stringify({ language, subscription }) })
export const unsubscribeAdvertisingVacancy = () => api<void>('/advertisements/waitlist', { method: 'DELETE' })
export const getAdvertisingWaitlistStatus = () => api<{ subscribed: boolean; channel: 'push' | 'site' }>('/advertisements/waitlist')
export const getAdminAdvertisements = (status?: string) => api<AdminAdvertisement[]>(`/admin/advertisements${status ? `?status_filter=${encodeURIComponent(status)}` : ''}`)
export type PaymentReview = { id: string; kind: string; targetId: string; amountCents: number; paidAt: string | null; note: string; status?: string; financialStatus?: string; stripeSessionId?: string | null }
export const getPaymentReviews = () => api<PaymentReview[]>('/payments/admin/review-required')
export const resolvePayment = (id: string, action: 'refund' | 'restore' | 'reconcile', reason: string, stripeSessionId?: string) => api<{ resolved: boolean; financialStatus?: string }>(`/payments/admin/orders/${id}/resolve`, { method: 'POST', body: JSON.stringify({ action, reason, stripeSessionId }) })
export const moderateAdvertisement = (id: string, action: 'approve' | 'reject' | 'deactivate', note?: string) => api<AdvertisementDetail>(`/admin/advertisements/${id}/${action}`, { method: 'POST', body: JSON.stringify({ note: note || null }) })

export async function uploadAdvertisementImage(file: File) {
  const body = new FormData()
  body.append('file', file)
  return api<{ id: string; url: string }>('/advertisements/uploads', { method: 'POST', body, timeoutMs: 45_000 })
}
