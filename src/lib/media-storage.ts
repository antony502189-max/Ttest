const DATABASE_NAME = '112233-media'
const DATABASE_VERSION = 1
const STORE_NAME = 'media'
const MEDIA_PREFIX = 'idb-media:'

export const acceptedImageTypes = ['image/jpeg', 'image/png', 'image/webp'] as const

export class MediaStorageError extends Error {
  readonly code: 'type' | 'read' | 'quota' | 'unavailable'

  constructor(code: 'type' | 'read' | 'quota' | 'unavailable', message: string) {
    super(message)
    this.name = 'MediaStorageError'
    this.code = code
  }
}

function openDatabase() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    if (!('indexedDB' in window)) {
      reject(new MediaStorageError('unavailable', 'El almacenamiento de imágenes no está disponible.'))
      return
    }
    const request = indexedDB.open(DATABASE_NAME, DATABASE_VERSION)
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) request.result.createObjectStore(STORE_NAME)
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new MediaStorageError('unavailable', 'No se pudo abrir el almacenamiento de imágenes.'))
  })
}

function mediaId(reference: string) {
  return reference.slice(MEDIA_PREFIX.length)
}

export function isMediaReference(value?: string): value is string {
  return Boolean(value?.startsWith(MEDIA_PREFIX))
}

export async function saveMediaFile(file: File) {
  if (!acceptedImageTypes.includes(file.type as (typeof acceptedImageTypes)[number])) {
    throw new MediaStorageError('type', 'Formato no compatible. Usa JPEG, PNG o WebP.')
  }
  const id = typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`
  const database = await openDatabase()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, 'readwrite')
      transaction.objectStore(STORE_NAME).put(file, id)
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
  } finally {
    database.close()
  }
}

export async function getMediaBlob(reference: string) {
  if (!isMediaReference(reference)) return null
  const database = await openDatabase()
  try {
    return await new Promise<Blob | null>((resolve, reject) => {
      const request = database.transaction(STORE_NAME, 'readonly').objectStore(STORE_NAME).get(mediaId(reference))
      request.onsuccess = () => resolve(request.result instanceof Blob ? request.result : null)
      request.onerror = () => reject(request.error)
    })
  } finally {
    database.close()
  }
}

export async function removeMedia(reference: string) {
  if (!isMediaReference(reference)) return
  const database = await openDatabase()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, 'readwrite')
      transaction.objectStore(STORE_NAME).delete(mediaId(reference))
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error)
    })
  } finally {
    database.close()
  }
}

export async function removeMediaReferences(references: string[]) {
  const results = await Promise.allSettled([...new Set(references)].map(removeMedia))
  if (results.some((result) => result.status === 'rejected')) {
    throw new MediaStorageError('unavailable', 'No se pudieron limpiar algunas imágenes locales.')
  }
}
