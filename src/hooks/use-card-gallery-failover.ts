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
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [failureState, setFailureState] = useState<{ listingId: string; urls: string[] }>({
    listingId, urls: [],
  })
  // A card may be reused for a different listing or an updated gallery.
  const failed = new Set(failureState.listingId === listingId ? failureState.urls : [])
  const imageIndex = Math.min(selectedIndex, images.length - 1)
  if (imageIndex !== selectedIndex) setSelectedIndex(imageIndex)

  const move = (direction: 1 | -1) => {
    const index = nextUsableIndex(images, failed, imageIndex, direction)
    if (index !== null) setSelectedIndex(index)
    return index
  }

  const onImageError = (event: SyntheticEvent<HTMLImageElement>) => {
    const url = images[imageIndex]
    // Do not interpret a late failure from a previous carousel frame as
    // failure of the newly selected image. Do not retry the fallback itself.
    if (!url || url === fallback || event.currentTarget.getAttribute('src') !== mediaVariantUrl(url, 'card')) return
    const rejected = new Set(failed)
    rejected.add(url)
    setFailureState({ listingId, urls: [...rejected] })
    const next = nextUsableIndex(images, rejected, imageIndex, 1)
    if (next !== null) setSelectedIndex(next)
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
