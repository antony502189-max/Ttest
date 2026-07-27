import { api, resolveApiUrl } from '@/api/client'
import { getMediaBlob, isMediaReference } from '@/lib/media-storage'

type MediaAssetDto = { id: string; url: string }
type ListingImageDto = { assetId: string; url: string; sortOrder: number; isCover: boolean }

const assetIdFromUrl = (reference: string) => reference.match(/\/media\/([0-9a-f-]{36})(?:$|[?#])/i)?.[1]

export async function uploadMediaReference(reference: string) {
  const blob = await getMediaBlob(reference)
  if (!blob) throw new Error('No se encontró una de las imágenes locales.')
  const body = new FormData()
  body.append('file', new File([blob], 'listing-image.webp', { type: blob.type || 'image/webp' }))
  return api<MediaAssetDto>('/uploads', { method: 'POST', body })
}

export async function syncListingImages(listingId: string, references: string[]) {
  const assetIds: string[] = []
  for (const reference of references) {
    const existingId = assetIdFromUrl(reference)
    if (existingId) assetIds.push(existingId)
    else if (isMediaReference(reference)) assetIds.push((await uploadMediaReference(reference)).id)
  }
  const images = await api<ListingImageDto[]>(`/listings/${listingId}/images`, {
    method: 'PUT', body: JSON.stringify({ assetIds }),
  })
  return images.sort((a, b) => a.sortOrder - b.sortOrder).map((image) => resolveApiUrl(image.url))
}
