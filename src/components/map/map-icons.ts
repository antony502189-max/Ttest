import type { Renderer } from '@googlemaps/markerclusterer'
import { getPrimaryPrice } from '@/lib/listings'
import type { Listing } from '@/types'

export const priceLabel = (listing: Listing) => `${getPrimaryPrice(listing)} \u20ac`

export function createPriceMarkerContent(listing: Listing) {
  const shell = document.createElement('div')
  shell.className = 'map-price-marker-shell price-marker-shell'
  shell.setAttribute('aria-label', `${listing.area}, ${priceLabel(listing)}`)
  const marker = document.createElement('span')
  marker.className = 'map-price-marker price-marker'
  const label = document.createElement('span')
  label.textContent = priceLabel(listing)
  const tail = document.createElement('i')
  tail.setAttribute('aria-hidden', 'true')
  marker.append(label, tail)
  shell.append(marker)
  return shell
}

export function setPriceMarkerState(content: HTMLElement, selected: boolean, highlighted: boolean) {
  const marker = content.querySelector('.map-price-marker')
  marker?.classList.toggle('is-selected', selected)
  marker?.classList.toggle('is-highlighted', highlighted)
  content.setAttribute('aria-pressed', String(selected))
}

function createClusterContent(count: number) {
  const size = count < 10 ? 42 : count < 50 ? 50 : 58
  const scale = count < 10 ? 'small' : count < 50 ? 'medium' : 'large'
  const shell = document.createElement('div')
  shell.className = 'map-cluster-marker-shell room-cluster-shell'
  shell.style.width = `${size}px`
  shell.style.height = `${size}px`
  shell.setAttribute('aria-label', `${count} habitaciones en esta zona`)
  const marker = document.createElement('span')
  marker.className = `map-cluster-marker room-cluster map-cluster-marker--${scale}`
  const label = document.createElement('span')
  label.textContent = String(count)
  marker.append(label)
  shell.append(marker)
  return shell
}

export class AdvancedClusterRenderer implements Renderer {
  render({ count, position }: Parameters<Renderer['render']>[0]) {
    return new google.maps.marker.AdvancedMarkerElement({
      position,
      content: createClusterContent(count),
      title: `${count} habitaciones`,
      gmpClickable: true,
      zIndex: 1000 + count,
    })
  }
}
