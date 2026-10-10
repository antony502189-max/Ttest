import { useEffect, useState, type ImgHTMLAttributes } from 'react'
import { fetchAuthenticatedMedia, resolveApiUrl } from '@/api/client'
import { getMediaBlob, isMediaReference } from '@/lib/media-storage'

const missingMediaFallback = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 560"%3E%3Crect width="800" height="560" fill="%23eceeea"/%3E%3Cpath d="M260 360l90-95 62 65 48-44 92 96H260z" fill="%2398a19a"/%3E%3Ccircle cx="505" cy="190" r="34" fill="%23b7beb8"/%3E%3Ctext x="400" y="445" text-anchor="middle" fill="%235b635d" font-family="Arial" font-size="28"%3EFoto no disponible%3C/text%3E%3C/svg%3E'

export type MediaVariant = 'full' | 'card' | 'thumb'

function variantUrl(source: string, variant: MediaVariant) {
  if (variant === 'full' || isMediaReference(source)) return source
  try {
    const url = new URL(source, window.location.origin)
    if (!/^\/api\/v1\/media\/[0-9a-f-]{36}$/i.test(url.pathname)) return source
    url.searchParams.set('variant', variant)
    return source.startsWith('http://') || source.startsWith('https://')
      ? url.toString()
      : `${url.pathname}${url.search}${url.hash}`
  } catch {
    return source
  }
}

export function mediaVariantUrl(source?: string, variant: MediaVariant = 'full') {
  return source ? variantUrl(source, variant) : ''
}

export function preloadMediaImages(sources: Array<string | undefined>, variant: MediaVariant = 'full') {
  if (typeof Image === 'undefined') return
  for (const source of new Set(sources.filter((value): value is string => Boolean(value)))) {
    if (isMediaReference(source)) continue
    const image = new Image()
    image.decoding = 'async'
    image.src = variantUrl(source, variant)
  }
}

function isUploadPreviewReference(source?: string) {
  if (!source || isMediaReference(source)) return false
  try {
    const url = new URL(source, window.location.origin)
    const match = url.pathname.match(/^\/api\/v1\/media\/([0-9a-f-]{36})$/i)
    if (!match) return false
    // Never send an owner bearer token to a URL on an unrelated origin,
    // even if an external URL happens to mimic the media path.
    const trusted = new URL(resolveApiUrl(`/media/${match[1]}`))
    return url.origin === trusted.origin && url.pathname === trusted.pathname
      && url.searchParams.get('uploadPreview') === '1'
  } catch {
    return false
  }
}

export function useMediaUrl(source?: string, variant: MediaVariant = 'full') {
  const [localMedia, setLocalMedia] = useState<{ reference: string; url: string } | null>(null)

  useEffect(() => {
    if (!source || (!isMediaReference(source) && !isUploadPreviewReference(source))) return
    let active = true
    let objectUrl = ''
    const imageBlob = isMediaReference(source)
      ? getMediaBlob(source)
      : fetchAuthenticatedMedia(source)
    void imageBlob
      .then((blob) => {
        if (!active || !blob) return
        objectUrl = URL.createObjectURL(blob)
        setLocalMedia({ reference: source, url: objectUrl })
      })
      .catch(() => {
        if (active) setLocalMedia(null)
      })
    return () => {
      active = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [source])

  // Public/remote gallery changes must update the rendered src in the *same*
  // render as the image counter. Keeping them in effect-driven state briefly
  // shows the previous photo when users rapidly swipe through a card.
  if (!isMediaReference(source) && !isUploadPreviewReference(source)) return mediaVariantUrl(source, variant)
  return localMedia && localMedia.reference === source ? localMedia.url : ''
}

type MediaImageProps = ImgHTMLAttributes<HTMLImageElement> & {
  variant?: MediaVariant
  responsive?: boolean
}

export function MediaImage({
  src,
  variant = 'full',
  responsive = false,
  decoding = 'async',
  srcSet,
  ...props
}: MediaImageProps) {
  const source = typeof src === 'string' ? src : undefined
  const resolved = useMediaUrl(source, variant)
  const thumb = source ? mediaVariantUrl(source, 'thumb') : ''
  const card = source ? mediaVariantUrl(source, 'card') : ''
  const full = source ? mediaVariantUrl(source, 'full') : ''
  const responsiveSet = responsive && source && !isMediaReference(source) && !isUploadPreviewReference(source) && (thumb !== source || card !== source)
    ? `${thumb} 480w, ${card} 960w, ${full} 2048w`
    : srcSet
  return (
    <img
      {...props}
      decoding={decoding}
      srcSet={responsiveSet}
      src={resolved || (isMediaReference(source) || isUploadPreviewReference(source) ? missingMediaFallback : undefined)}
    />
  )
}
