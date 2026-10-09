import { useState, type SyntheticEvent } from 'react'
import { mediaVariantUrl } from '@/components/media-image'

// A failed cover must not hide the remaining photos. Keep the authoritative
// gallery unchanged: this tracks URL failures only for the current card view.
function nextUsableIndex(images: string[], failed: Set<string>, from: number, direction: 1 | -1) {
  for (let step = 1; step <= images.length; step += 1) {
    const index = (from + direction * step + images.length) % images.length
    if (!failed.has(images[index])) return index
  }
  return null
}

export function useCardGalleryFailover(listingId: string, sources: string[], fallback: string) {
  const images = sources.length ? sources : [fallback]
  const galleryKey = JSON.stringify(sources)
  const [galleryState, setGalleryState] = useState<{
    listingId: string
    galleryKey: string
    selectedIndex: number
    failedUrls: string[]
  }>({ listingId, galleryKey, selectedIndex: 0, failedUrls: [] })
  // A card may be reused for another listing or a refreshed gallery. Neither
  // its selected frame nor URL failures should leak into that new view.
  const stateMatchesGallery = galleryState.listingId === listingId && galleryState.galleryKey === galleryKey
  const currentState = stateMatchesGallery
    ? galleryState
    : { listingId, galleryKey, selectedIndex: 0, failedUrls: [] }
  if (!stateMatchesGallery) setGalleryState(currentState)
  const failed = new Set(currentState.failedUrls)
  const selectedIndex = currentState.selectedIndex
  const imageIndex = Math.min(selectedIndex, images.length - 1)
  if (imageIndex !== selectedIndex) setGalleryState({ ...currentState, selectedIndex: imageIndex })

  const selectIndex = (index: number) => {
    setGalleryState((previous) => {
      const base = previous.listingId === listingId && previous.galleryKey === galleryKey
        ? previous
        : { listingId, galleryKey, selectedIndex: 0, failedUrls: [] }
      return { ...base, selectedIndex: index }
    })
  }

  const move = (direction: 1 | -1) => {
    const index = nextUsableIndex(images, failed, imageIndex, direction)
    if (index !== null) selectIndex(index)
    return index
  }

  const onImageError = (event: SyntheticEvent<HTMLImageElement>) => {
    const url = images[imageIndex]
    // Do not interpret a late failure from a previous carousel frame as
    // failure of the newly selected image. Do not retry the fallback itself.
    if (!url || url === fallback || event.currentTarget.getAttribute('src') !== mediaVariantUrl(url, 'card')) return
    setGalleryState((previous) => {
      // Ignore errors dispatched by an image from a listing or gallery that
      // has already been replaced while the browser was still loading it.
      if (previous.listingId !== listingId || previous.galleryKey !== galleryKey) return previous
      const rejected = new Set(previous.failedUrls)
      rejected.add(url)
      const next = nextUsableIndex(images, rejected, imageIndex, 1)
      return {
        ...previous,
        failedUrls: [...rejected],
        selectedIndex: next ?? imageIndex,
      }
    })
    // If all gallery frames fail, the render below displays the fallback.
    // Never repeatedly request the failing URL or create an error loop.
  }

  return {
    images,
    imageIndex,
    imageSrc: failed.has(images[imageIndex]) ? fallback : images[imageIndex],
    nextImage: () => move(1),
    previousImage: () => move(-1),
    onImageError,
  }
}
