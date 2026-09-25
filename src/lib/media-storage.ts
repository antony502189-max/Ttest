const DATABASE_NAME = '112233-media'
const DATABASE_VERSION = 1
const STORE_NAME = 'media'
const MEDIA_PREFIX = 'idb-media:'
const DRAFT_KEYS = new Set(['112233:listing-draft:v3', '112233:listing-draft:v2'])
const EDIT_DRAFT_PREFIX = '112233:listing-edit-draft:v1:'

export const acceptedImageTypes = ['image/jpeg', 'image/png', 'image/webp'] as const


const LOCAL_MEDIA_MAX_DIMENSION = 2048
const LOCAL_MEDIA_WEBP_QUALITY = 0.84

async function optimizeMediaFile(file: File) {
  if (typeof createImageBitmap !== 'function' || typeof document === 'undefined') return file

  let bitmap: ImageBitmap | null = null
  try {
    bitmap = await createImageBitmap(file)
    if (!bitmap.width || !bitmap.height) return file

    const scale = Math.min(1, LOCAL_MEDIA_MAX_DIMENSION / Math.max(bitmap.width, bitmap.height))
    const width = Math.max(1, Math.round(bitmap.width * scale))
    const height = Math.max(1, Math.round(bitmap.height * scale))
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d', { alpha: true })
    if (!context) return file
    context.drawImage(bitmap, 0, 0, width, height)

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, 'image/webp', LOCAL_MEDIA_WEBP_QUALITY)
    })
    if (!blob) return file

    // Do not replace a small source with a larger derivative. Resizing always
    // wins because it reduces upload, decode and rendered-memory costs.
    if (scale === 1 && blob.size >= file.size) return file
    const baseName = file.name.replace(/\.[^.]+$/, '') || 'listing-image'
    return new File([blob], `${baseName}.webp`, {
      type: 'image/webp',
      lastModified: file.lastModified,
    })
  } catch {
    // Browser-side optimization is best effort; backend validation and
    // normalization remains authoritative.
    return file
  } finally {
    bitmap?.close()
  }
}

export class MediaStorageError extends Error {
  readonly code: 'type' | 'read' | 'quota' | 'unavailable'

  constructor(code: 'type' | 'read' | 'quota' | 'unavailable', message: string) {
    super(message)
    this.name = 'MediaStorageError'
    this.code = code
  }
}

let databasePromise: Promise<IDBDatabase> | null = null

function openDatabase() {
  if (databasePromise) return databasePromise
  databasePromise = new Promise<IDBDatabase>((resolve, reject) => {
    if (!('indexedDB' in window)) {
      databasePromise = null
      reject(new MediaStorageError('unavailable', 'El almacenamiento de imágenes no está disponible.'))
      return
    }
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION)
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) request.result.createObjectStore(STORE_NAME)
    }
    request.onsuccess = () => {
      const database = request.result
      database.onversionchange = () => {
        database.close()
        databasePromise = null
      }
      resolve(database)
    }
    request.onerror = () => {
      databasePromise = null
      reject(request.error ?? new MediaStorageError('unavailable', 'No se pudo abrir el almacenamiento de imágenes.'))
    }
  })
  return databasePromise
}

function mediaId(reference: string) {
  return reference.slice(MEDIA_PREFIX.length)
}

const mediaReference = (id: IDBValidKey) => `${MEDIA_PREFIX}${String(id)}`

export type MediaReference = `${typeof MEDIA_PREFIX}${string}`

export function isMediaReference(value?: string): value is MediaReference {
  return Boolean(value?.startsWith(MEDIA_PREFIX))
}

function collectDraftMediaReferences(value: unknown, found = new Set<string>()) {
  if (typeof value === 'string') {
    if (isMediaReference(value)) found.add(value)
    return found
  }
  if (Array.isArray(value)) value.forEach((item) => collectDraftMediaReferences(item, found))
  else if (value && typeof value === 'object') Object.values(value as Record<string, unknown>).forEach((item) => collectDraftMediaReferences(item, found))
  return found
}

function protectedDraftMediaReferences() {
  const protectedReferences = new Set<string>()
  try {
    for (let index = 0; index < localStorage.length; index += 1) {
      const key = localStorage.key(index)
      if (!key || (!DRAFT_KEYS.has(key) && !key.startsWith(EDIT_DRAFT_PREFIX))) continue
      const raw = localStorage.getItem(key)
      if (!raw) continue
      try {
        collectDraftMediaReferences(JSON.parse(raw), protectedReferences)
      } catch {
        // A malformed draft must not block cleanup of unrelated orphaned media.
      }
    }
  } catch {
    // Storage can be unavailable in hardened/private browser contexts.
  }
  return protectedReferences
}

export async function saveMediaFile(file: File) {
  if (!acceptedImageTypes.includes(file.type as (typeof acceptedImageTypes)[number])) {
    throw new MediaStorageError('type', 'Formato no compatible. Usa JPEG, PNG o WebP.')
  }
  const optimized = await optimizeMediaFile(file)
  const id = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`
  const database = await openDatabase()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, 'readwrite')
      transaction.objectStore(STORE_NAME).put(optimized, id)
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error)
    })
    return `${MEDIA_PREFIX}${id}`
  } catch (error) {
    if (error instanceof DOMException && (error.name === 'QuotaExceededError' || error.name === 'NS_ERROR_DOM_QUOTA_REACHED')) {
      throw new MediaStorageError('quota', 'No hay espacio suficiente para guardar la imagen.')
    }
    throw new MediaStorageError('read', 'No se pudo leer o guardar la imagen.')
  }
}

export async function getMediaBlob(reference: string) {
  if (!isMediaReference(reference)) return null
  const database = await openDatabase()
  return await new Promise<Blob | null>((resolve, reject) => {
    const request = database.transaction(STORE_NAME, 'readonly').objectStore(STORE_NAME).get(mediaId(reference))
    request.onsuccess = () => resolve(request.result instanceof Blob ? request.result : null)
    request.onerror = () => reject(request.error)
  })
}

export async function removeMedia(reference: string) {
  if (!isMediaReference(reference)) return
  const database = await openDatabase()
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite')
    transaction.objectStore(STORE_NAME).delete(mediaId(reference))
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
    transaction.onabort = () => reject(transaction.error)
  })
}

export async function removeMediaReferences(references: string[]) {
  const results = await Promise.allSettled([...new Set(references)].map(removeMedia))
  if (results.some((result) => result.status === 'rejected')) {
    throw new MediaStorageError('unavailable', 'No se pudieron limpiar algunas imágenes locales.')
  }
}

export async function getAllMediaReferences() {
  const database = await openDatabase()
  return await new Promise<string[]>((resolve, reject) => {
    const request = database.transaction(STORE_NAME, 'readonly').objectStore(STORE_NAME).getAllKeys()
    request.onsuccess = () => resolve(request.result.map(mediaReference))
    request.onerror = () => reject(request.error)
  })
}

export async function removeUnusedMediaReferences(references: string[], usedReferences: Iterable<string>) {
  const used = new Set<string>([...usedReferences].filter(isMediaReference))
  return removeMediaReferences(references.filter((reference) => isMediaReference(reference) && !used.has(reference)))
}

export async function cleanupOrphanedMedia(usedReferences: Iterable<string>) {
  const used = new Set<string>([...usedReferences].filter(isMediaReference))
  protectedDraftMediaReferences().forEach((reference) => used.add(reference))
  const stored = await getAllMediaReferences()
  await removeUnusedMediaReferences(stored, used)
  return stored.filter((reference) => !used.has(reference))
}
