import { useEffect, useState, type ImgHTMLAttributes } from 'react'
import { getMediaBlob, isMediaReference } from '@/lib/media-storage'

const missingMediaFallback = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 560"%3E%3Crect width="800" height="560" fill="%23eceeea"/%3E%3Cpath d="M260 360l90-95 62 65 48-44 92 96H260z" fill="%2398a19a"/%3E%3Ccircle cx="505" cy="190" r="34" fill="%23b7beb8"/%3E%3Ctext x="400" y="445" text-anchor="middle" fill="%235b635d" font-family="Arial" font-size="28"%3EFoto no disponible%3C/text%3E%3C/svg%3E'

export function useMediaUrl(source?: string) {
  const [url, setUrl] = useState(() => isMediaReference(source) ? '' : source ?? '')

  useEffect(() => {
    if (!isMediaReference(source)) {
      setUrl(source ?? '')
      return
    }
    let active = true
    let objectUrl = ''
    void getMediaBlob(source)
      .then((blob) => {
        if (!active || !blob) return
        objectUrl = URL.createObjectURL(blob)
        setUrl(objectUrl)
      })
      .catch(() => {
        if (active) setUrl('')
      })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [source])

  return url
}

export function MediaImage({ src, ...props }: ImgHTMLAttributes<HTMLImageElement>) {
  const source = typeof src === 'string' ? src : undefined
  const resolved = useMediaUrl(source)
  return <img {...props} src={resolved || (isMediaReference(source) ? missingMediaFallback : undefined)} />
}
