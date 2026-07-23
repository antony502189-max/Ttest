import { useLayoutEffect } from 'react'
import { loadGoogleMaps } from '@/lib/google-maps/loader'
import '@/freehand-map-drawing.css'

type MapListener = (
  this: google.maps.Map,
  eventName: string,
  handler: (...args: unknown[]) => void,
) => google.maps.MapsEventListener

type CapturedStroke = {
  canvas: HTMLElement
  root: HTMLElement
  map: google.maps.Map
  pointerId: number
  lastX: number
  lastY: number
  pointCount: number
}

const mapByCanvas = new WeakMap<HTMLElement, google.maps.Map>()
let captureInstallPromise: Promise<void> | null = null

function installMapCapture() {
  if (captureInstallPromise) return captureInstallPromise

  captureInstallPromise = loadGoogleMaps().then(({ maps }) => {
    const prototype = maps.Map.prototype as unknown as { addListener: MapListener; __freehandCaptureInstalled?: boolean }
    if (prototype.__freehandCaptureInstalled) return

    const originalAddListener = prototype.addListener
    prototype.addListener = function addListener(eventName, handler) {
      const container = this.getDiv()
      if (container instanceof HTMLElement && container.classList.contains('results-map__canvas')) {
        mapByCanvas.set(container, this)
      }
      return Reflect.apply(originalAddListener, this, [eventName, handler]) as google.maps.MapsEventListener
    }
    prototype.__freehandCaptureInstalled = true
  })

  return captureInstallPromise
}

function pointOnMap(map: google.maps.Map, canvas: HTMLElement, clientX: number, clientY: number) {
  const projection = map.getProjection()
  const center = map.getCenter()
  const zoom = map.getZoom()
  if (!projection || !center || zoom === undefined) return null

  const centerPoint = projection.fromLatLngToPoint(center)
  if (!centerPoint) return null

  const bounds = canvas.getBoundingClientRect()
  const scale = 2 ** zoom
  const worldPoint = new google.maps.Point(
    centerPoint.x + (clientX - bounds.left - bounds.width / 2) / scale,
    centerPoint.y + (clientY - bounds.top - bounds.height / 2) / scale,
  )

  return projection.fromPointToLatLng(worldPoint, true)
}

function finishWhenReactIsReady(root: HTMLElement, attempts = 0) {
  const finishButton = root.querySelector<HTMLButtonElement>('.map-toolbar__finish')
  if (finishButton && !finishButton.disabled) {
    finishButton.click()
    return
  }
  if (attempts < 10) requestAnimationFrame(() => finishWhenReactIsReady(root, attempts + 1))
}

export function FreehandMapDrawing() {
  useLayoutEffect(() => {
    void installMapCapture().catch(() => undefined)

    let stroke: CapturedStroke | null = null
    let suppressCanvasClickUntil = 0

    const emitPoint = (current: CapturedStroke, clientX: number, clientY: number, event: PointerEvent) => {
      const latLng = pointOnMap(current.map, current.canvas, clientX, clientY)
      if (!latLng) return false

      google.maps.event.trigger(current.map, 'click', { latLng, domEvent: event })
      current.lastX = clientX
      current.lastY = clientY
      current.pointCount += 1
      return true
    }

    const handlePointerDown = (event: PointerEvent) => {
      if (!event.isPrimary || (event.pointerType === 'mouse' && event.button !== 0)) return
      if (!(event.target instanceof Element)) return

      const canvas = event.target.closest<HTMLElement>('.results-map.is-drawing .results-map__canvas')
      const root = canvas?.closest<HTMLElement>('.results-map')
      const map = canvas ? mapByCanvas.get(canvas) : undefined
      if (!canvas || !root || !map) return

      event.preventDefault()
      event.stopImmediatePropagation()
      try { canvas.setPointerCapture(event.pointerId) } catch { /* Pointer capture is optional. */ }

      stroke = {
        canvas,
        root,
        map,
        pointerId: event.pointerId,
        lastX: event.clientX,
        lastY: event.clientY,
        pointCount: 0,
      }
      emitPoint(stroke, event.clientX, event.clientY, event)
    }

    const handlePointerMove = (event: PointerEvent) => {
      if (!stroke || event.pointerId !== stroke.pointerId) return
      event.preventDefault()
      event.stopImmediatePropagation()

      const distance = Math.hypot(event.clientX - stroke.lastX, event.clientY - stroke.lastY)
      if (distance < 7) return
      emitPoint(stroke, event.clientX, event.clientY, event)
    }

    const handlePointerUp = (event: PointerEvent) => {
      if (!stroke || event.pointerId !== stroke.pointerId) return
      event.preventDefault()
      event.stopImmediatePropagation()

      const current = stroke
      const distance = Math.hypot(event.clientX - current.lastX, event.clientY - current.lastY)
      if (distance >= 3) emitPoint(current, event.clientX, event.clientY, event)
      try { current.canvas.releasePointerCapture(event.pointerId) } catch { /* Pointer capture may already be released. */ }

      stroke = null
      suppressCanvasClickUntil = performance.now() + 500
      if (current.pointCount >= 3) requestAnimationFrame(() => finishWhenReactIsReady(current.root))
    }

    const handlePointerCancel = (event: PointerEvent) => {
      if (!stroke || event.pointerId !== stroke.pointerId) return
      const current = stroke
      stroke = null
      current.root.querySelector<HTMLButtonElement>('.map-toolbar__cancel')?.click()
    }

    const suppressGeneratedClick = (event: MouseEvent) => {
      if (performance.now() > suppressCanvasClickUntil || !(event.target instanceof Element)) return
      if (!event.target.closest('.results-map__canvas')) return
      event.preventDefault()
      event.stopImmediatePropagation()
    }

    document.addEventListener('pointerdown', handlePointerDown, { capture: true, passive: false })
    document.addEventListener('pointermove', handlePointerMove, { capture: true, passive: false })
    document.addEventListener('pointerup', handlePointerUp, { capture: true, passive: false })
    document.addEventListener('pointercancel', handlePointerCancel, true)
    document.addEventListener('click', suppressGeneratedClick, true)

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown, true)
      document.removeEventListener('pointermove', handlePointerMove, true)
      document.removeEventListener('pointerup', handlePointerUp, true)
      document.removeEventListener('pointercancel', handlePointerCancel, true)
      document.removeEventListener('click', suppressGeneratedClick, true)
    }
  }, [])

  return null
}
