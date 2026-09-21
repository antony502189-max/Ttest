import { api, resolveApiUrl } from '@/api/client'
import { getMediaBlob, isMediaReference } from '@/lib/media-storage'

type MediaAssetDto = { id: string; url: string }
type ListingImageDto = { assetId: string; url: string; sortOrder: number; isCover: boolean }

export type PreparedListingImages = {
  assetIds: string[]
  newlyUploaded: string[]
}

const UPLOAD_CONCURRENCY = 3
const assetIdFromUrl = (reference: string) => reference.match(/\/media\/([0-9a-f-]{36})(?:$|[?#])/i)?.[1]

export async function uploadMediaReference(reference: string) {
  const blob = await getMediaBlob(reference)
  if (!blob) throw new Error('No se encontró una de las imágenes locales.')
  const body = new FormData()
  body.append('file', new File([blob], 'listing-image.webp', { type: blob.type || 'image/webp' }))
  return api<MediaAssetDto>('/uploads', { method: 'POST', body, timeoutMs: 45_000 })
}

async function deleteUploadedAsset(assetId: string) {
  await api<void>(`/uploads/${assetId}`, { method: 'DELETE' })
}

export async function cleanupPreparedListingImages(prepared: PreparedListingImages) {
  await Promise.allSettled(prepared.newlyUploaded.map(deleteUploadedAsset))
}

export async function prepareListingImages(references: string[]): Promise<PreparedListingImages> {
  const assetIds = new Array<string>(references.length)
  const newlyUploaded: string[] = []
  let cursor = 0

  const worker = async () => {
    while (true) {
      const index = cursor++
      if (index >= references.length) return
      const reference = references[index]
      const existingId = assetIdFromUrl(reference)
      if (existingId) {
        assetIds[index] = existingId
        continue
      }
      if (!isMediaReference(reference)) {
        throw new Error('Una de las imágenes ya no está disponible. Vuelve a añadirla.')
      }
      const uploaded = await uploadMediaReference(reference)
      assetIds[index] = uploaded.id
      newlyUploaded.push(uploaded.id)
    }
  }

  const workers = await Promise.allSettled(
    Array.from({ length: Math.min(UPLOAD_CONCURRENCY, references.length) }, () => worker()),
  )
  const failed = workers.find((result): result is PromiseRejectedResult => result.status === 'rejected')
  if (failed) {
    await Promise.allSettled(newlyUploaded.map(deleteUploadedAsset))
    throw failed.reason
  }
  return { assetIds, newlyUploaded }
}

export async function syncListingImages(listingId: string, references: string[]) {
  const prepared = await prepareListingImages(references)
  try {
    const images = await api<ListingImageDto[]>(`/listings/${listingId}/images`, {
      method: 'PUT', body: JSON.stringify({ assetIds: prepared.assetIds }),
    })
    return images.sort((a, b) => a.sortOrder - b.sortOrder).map((image) => resolveApiUrl(image.url))
  } catch (error) {
    await cleanupPreparedListingImages(prepared)
    throw error
  }
}
