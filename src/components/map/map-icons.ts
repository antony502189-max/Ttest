import type { Renderer } from '@googlemaps/markerclusterer'
import { getPrimaryPrice } from '@/lib/listings'
import type { Listing } from '@/types'
import '@/promoted-map-like.css'

export const priceLabel = (listing: Listing) => listing.sourcePriceText ?? `${getPrimaryPrice(listing)} €`

export function createPriceMarkerContent(listing: Listing) {
  const shell = document.createElement('div')
  shell.className = 'map-price-marker-shell price-marker-shell'
  shell.setAttribute('aria-label', `${listing.area}, ${priceLabel(listing)}`)
  const marker = document.createElement('span')
  marker.className = `map-price-marker price-marker${listing.promoted ? ' is-promoted' : ''}`
  const label = document.createElement('span')
  label.className = 'map-price-marker__label'
  const price = document.createElement('span')
  price.textContent = priceLabel(listing)
  const promotion = document.createElement('span')
  promotion.className = 'map-price-marker__promotion'
  promotion.setAttribute('aria-hidden', 'true')
  promotion.textContent = '👍'
  label.append(price, promotion)
  const tail = document.createElement('i')
  tail.setAttribute('aria-hidden', 'true')
  marker.append(label, tail)
  shell.append(marker)
  return shell
}

export function setPriceMarkerState(content: HTMLElement, selected: boolean, highlighted: boolean, promoted: boolean) {
  const marker = content.querySelector('.map-price-marker')
  marker?.classList.toggle('is-promoted', promoted)
  marker?.classList.toggle('is-selected', selected)
  marker?.classList.toggle('is-highlighted', highlighted)
  content.setAttribute('aria-pressed', String(selected))
}

export function setClusterPromotionState(content: HTMLElement, promoted: boolean) {
  const marker = content.querySelector('.map-cluster-marker')
  if (!(marker instanceof HTMLElement)) return
  marker.classList.toggle('is-promoted', promoted)
  content.dataset.promoted = String(promoted)
  const currentPromotion = marker.querySelector('.map-cluster-marker__promotion')
  if (promoted && !currentPromotion) {
    const promotion = document.createElement('span')
    promotion.className = 'map-cluster-marker__promotion'
    promotion.setAttribute('aria-hidden', 'true')
    promotion.textContent = '👍'
    marker.append(promotion)
  } else if (!promoted) {
    currentPromotion?.remove()
  }
}

export function createClusterContent(count: number, promoted = false) {
  const size = count < 10 ? 42 : count < 50 ? 50 : 58
  const scale = count < 10 ? 'small' : count < 50 ? 'medium' : 'large'
  const shell = document.createElement('div')
  shell.className = 'map-cluster-marker-shell room-cluster-shell'
  shell.style.width = `${size}px`
  shell.style.height = `${size}px`
  shell.setAttribute('aria-label', `${count} habitaciones en esta zona${promoted ? ', incluye anuncio TOP' : ''}`)
  shell.dataset.promoted = String(promoted)
  const marker = document.createElement('span')
  marker.className = `map-cluster-marker room-cluster map-cluster-marker--${scale}${promoted ? ' is-promoted' : ''}`
  const label = document.createElement('span')
  label.textContent = String(count)
  marker.append(label)
  shell.append(marker)
  setClusterPromotionState(shell, promoted)
  return shell
}

export class AdvancedClusterRenderer implements Renderer {
  render({ count, position, markers }: Parameters<Renderer['render']>[0]) {
    const promoted = markers.some((candidate) => {
      if (!(candidate instanceof google.maps.marker.AdvancedMarkerElement)) return false
      const content = candidate.content
      return content instanceof HTMLElement && Boolean(content.querySelector('.map-price-marker.is-promoted'))
    })
    return new google.maps.marker.AdvancedMarkerElement({
      position,
      content: createClusterContent(count, promoted),
      title: `${count} habitaciones${promoted ? ', incluye anuncio TOP' : ''}`,
      gmpClickable: true,
      zIndex: (promoted ? 2000 : 1000) + count,
    })
  }
}
