import { useLayoutEffect } from 'react'
import { loadGoogleMaps } from '@/lib/google-maps/loader'
import '@/freehand-map-drawing.css'

type MapListener = (
  this: google.maps.Map,
  eventName: string,
  handler: (...args: unknown[]) => void,
) => google.maps.MapsEventListener

type MapInteractionState = {
  gestureHandling: google.maps.MapOptions['gestureHandling']
  draggable: google.maps.MapOptions['draggable']
  scrollwheel: google.maps.MapOptions['scrollwheel']
  disableDoubleClickZoom: google.maps.MapOptions['disableDoubleClickZoom']
  keyboardShortcuts: google.maps.MapOptions['keyboardShortcuts']
}

type DrawingStroke = {
  pointerId: number
  lastX: number
  lastY: number
  pointCount: number
}

type ActiveDrawing = {
  root: HTMLElement
  canvas: HTMLElement
  map: google.maps.Map
  overlay: HTMLDivElement
  previousInteractions: MapInteractionState
  destroy: () => void
}

const mapByCanvas = new WeakMap<HTMLElement, google.maps.Map>()
let captureInstallPromise: Promise<void> | null = null

function installMapCapture() {
  if (captureInstallPromise) return captureInstallPromise

  captureInstallPromise = loadGoogleMaps().then(({ maps }) => {
    const prototype = maps.Map.prototype as unknown as {
      addListener: MapListener
      __freehandCaptureInstalled?: boolean
    }
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

function captureInteractionState(map: google.maps.Map): MapInteractionState {
  return {
    gestureHandling: map.get('gestureHandling') as MapInteractionState['gestureHandling'],
    draggable: map.get('draggable') as MapInteractionState['draggable'],
    scrollwheel: map.get('scrollwheel') as MapInteractionState['scrollwheel'],
    disableDoubleClickZoom: map.get('disableDoubleClickZoom') as MapInteractionState['disableDoubleClickZoom'],
    keyboardShortcuts: map.get('keyboardShortcuts') as MapInteractionState['keyboardShortcuts'],
  }
}

function lockMap(map: google.maps.Map) {
  map.setOptions({
    gestureHandling: 'none',
    draggable: false,
    scrollwheel: false,
    disableDoubleClickZoom: true,
    keyboardShortcuts: false,
  })
}

function restoreMap(map: google.maps.Map, state: MapInteractionState) {
  map.setOptions(state)
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
  if (attempts < 30) requestAnimationFrame(() => finishWhenReactIsReady(root, attempts + 1))
}

function activateDrawing(root: HTMLElement, canvas: HTMLElement, map: google.maps.Map): ActiveDrawing {
  const previousInteractions = captureInteractionState(map)
  const overlay = document.createElement('div')
  const hint = document.createElement('span')
  let stroke: DrawingStroke | null = null

  overlay.className = 'freehand-map-overlay'
  overlay.setAttribute('aria-label', 'Mantén pulsado y dibuja el contorno de la zona')
  hint.className = 'freehand-map-overlay__hint'
  hint.textContent = 'Mantén pulsado y dibuja el contorno'
  overlay.append(hint)
  root.append(overlay)

  root.classList.add('is-freehand-locked')
  lockMap(map)

  const emitPoint = (current: DrawingStroke, clientX: number, clientY: number, event: PointerEvent) => {
    const latLng = pointOnMap(map, canvas, clientX, clientY)
    if (!latLng) return false

    google.maps.event.trigger(map, 'click', { latLng, domEvent: event })
    current.lastX = clientX
    current.lastY = clientY
    current.pointCount += 1
    return true
  }

  const pointerDown = (event: PointerEvent) => {
    if (!event.isPrimary || (event.pointerType === 'mouse' && event.button !== 0)) return

    event.preventDefault()
    event.stopPropagation()
    overlay.setPointerCapture(event.pointerId)
    root.classList.add('is-freehand-stroking')
    hint.textContent = 'Обведи нужную территорию и отпусти'

    stroke = {
      pointerId: event.pointerId,
      lastX: event.clientX,
      lastY: event.clientY,
      pointCount: 0,
    }
    emitPoint(stroke, event.clientX, event.clientY, event)
  }

  const pointerMove = (event: PointerEvent) => {
    if (!stroke || event.pointerId !== stroke.pointerId) return

    event.preventDefault()
    event.stopPropagation()
    const samples = event.getCoalescedEvents?.() ?? [event]
    const minimumDistance = event.pointerType === 'touch' ? 7 : 5

    samples.forEach((sample) => {
      if (!stroke) return
      const distance = Math.hypot(sample.clientX - stroke.lastX, sample.clientY - stroke.lastY)
      if (distance >= minimumDistance) emitPoint(stroke, sample.clientX, sample.clientY, event)
    })
  }

  const pointerUp = (event: PointerEvent) => {
    if (!stroke || event.pointerId !== stroke.pointerId) return

    event.preventDefault()
    event.stopPropagation()
    const completedStroke = stroke
    const distance = Math.hypot(event.clientX - completedStroke.lastX, event.clientY - completedStroke.lastY)
    if (distance >= 3) emitPoint(completedStroke, event.clientX, event.clientY, event)

    stroke = null
    root.classList.remove('is-freehand-stroking')
    try { overlay.releasePointerCapture(event.pointerId) } catch { /* Capture may already be released. */ }

    if (completedStroke.pointCount >= 3) {
      hint.textContent = 'Применяем выделенную область…'
      requestAnimationFrame(() => finishWhenReactIsReady(root))
    } else {
      hint.textContent = 'Нарисуй область одним непрерывным движением'
    }
  }

  const pointerCancel = (event: PointerEvent) => {
    if (!stroke || event.pointerId !== stroke.pointerId) return
    stroke = null
    root.classList.remove('is-freehand-stroking')
    root.querySelector<HTMLButtonElement>('.map-toolbar__cancel')?.click()
  }

  const contextMenu = (event: MouseEvent) => event.preventDefault()

  overlay.addEventListener('pointerdown', pointerDown, { passive: false })
  overlay.addEventListener('pointermove', pointerMove, { passive: false })
  overlay.addEventListener('pointerup', pointerUp, { passive: false })
  overlay.addEventListener('pointercancel', pointerCancel)
  overlay.addEventListener('contextmenu', contextMenu)

  return {
    root,
    canvas,
    map,
    overlay,
    previousInteractions,
    destroy: () => {
      overlay.removeEventListener('pointerdown', pointerDown)
      overlay.removeEventListener('pointermove', pointerMove)
      overlay.removeEventListener('pointerup', pointerUp)
      overlay.removeEventListener('pointercancel', pointerCancel)
      overlay.removeEventListener('contextmenu', contextMenu)
      overlay.remove()
      root.classList.remove('is-freehand-locked', 'is-freehand-stroking')
      restoreMap(map, previousInteractions)
    },
  }
}

export function FreehandMapDrawing() {
  useLayoutEffect(() => {
    let activeDrawing: ActiveDrawing | null = null
    let scheduledFrame = 0
    let disposed = false

    const deactivate = () => {
      activeDrawing?.destroy()
      activeDrawing = null
    }

    const synchronize = () => {
      scheduledFrame = 0
      if (disposed) return

      const root = document.querySelector<HTMLElement>('.results-map.is-drawing')
      if (!root) {
        deactivate()
        return
      }

      const canvas = root.querySelector<HTMLElement>('.results-map__canvas')
      const map = canvas ? mapByCanvas.get(canvas) : undefined
      if (!canvas || !map) {
        scheduledFrame = requestAnimationFrame(synchronize)
        return
      }

      if (activeDrawing?.root === root && activeDrawing.canvas === canvas) return
      deactivate()
      activeDrawing = activateDrawing(root, canvas, map)
    }

    const scheduleSynchronize = () => {
      if (scheduledFrame) return
      scheduledFrame = requestAnimationFrame(synchronize)
    }

    void installMapCapture().then(scheduleSynchronize).catch(() => undefined)

    const observer = new MutationObserver(scheduleSynchronize)
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['class'],
    })
    scheduleSynchronize()

    return () => {
      disposed = true
      observer.disconnect()
      if (scheduledFrame) cancelAnimationFrame(scheduledFrame)
      deactivate()
    }
  }, [])

  return null
}
