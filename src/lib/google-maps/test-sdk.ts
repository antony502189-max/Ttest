/**
 * Deterministic Google Maps substitute used exclusively by Playwright/CI.
 * It is loaded only when VITE_GOOGLE_MAPS_TEST_SDK=1, never by production builds.
 */

type PointLike = { lat: number; lng: number }
type Listener = { remove: () => void }
type ListenerCallback = (...args: unknown[]) => void

class TestLatLng {
  private readonly point: PointLike
  constructor(point: PointLike) { this.point = point }
  lat() { return this.point.lat }
  lng() { return this.point.lng }
}

function point(value: PointLike | TestLatLng) {
  return value instanceof TestLatLng ? { lat: value.lat(), lng: value.lng() } : value
}

class TestBounds {
  private south = 27.1
  private west = -18.2
  private north = 29.2
  private east = -15.3

  extend(value: PointLike | TestLatLng) {
    const next = point(value)
    this.south = Math.min(this.south, next.lat)
    this.west = Math.min(this.west, next.lng)
    this.north = Math.max(this.north, next.lat)
    this.east = Math.max(this.east, next.lng)
    return this
  }

  getNorthEast() { return new TestLatLng({ lat: this.north, lng: this.east }) }
  getSouthWest() { return new TestLatLng({ lat: this.south, lng: this.west }) }
  getCenter() { return new TestLatLng({ lat: (this.north + this.south) / 2, lng: (this.east + this.west) / 2 }) }
}

class TestDataLayer {
  forEach() {}
  remove() {}
  addGeoJson() { return [] }
  setStyle() {}
  addListener() { return { remove() {} } }
  revertStyle() {}
}

class TestMap {
  private readonly element: HTMLElement
  private center = new TestLatLng({ lat: 28.2916, lng: -16.6291 })
  private zoom = 10
  private readonly listeners = new Map<string, Set<ListenerCallback>>()
  private readonly options = new Map<string, unknown>()
  readonly data = new TestDataLayer()

  constructor(element: HTMLElement, options: Record<string, unknown> = {}) {
    this.element = element
    Object.entries(options).forEach(([key, value]) => this.options.set(key, value))
    const canvas = document.createElement('div')
    canvas.className = 'gm-style'
    canvas.dataset.testMapSdk = '1'
    element.append(canvas)
  }

  addListener(name: string, callback: ListenerCallback): Listener {
    const callbacks = this.listeners.get(name) ?? new Set<ListenerCallback>()
    callbacks.add(callback)
    this.listeners.set(name, callbacks)
    return { remove: () => callbacks.delete(callback) }
  }

  emit(name: string, ...args: unknown[]) { this.listeners.get(name)?.forEach((callback) => callback(...args)) }
  getCenter() { return this.center }
  setCenter(value: PointLike | TestLatLng) { this.center = new TestLatLng(point(value)); this.emit('idle') }
  getZoom() { return this.zoom }
  setZoom(value: number) { this.zoom = value; this.emit('idle') }
  getBounds() { return new TestBounds() }
  fitBounds(bounds: TestBounds) { this.center = bounds.getCenter(); this.emit('idle') }
  panTo(value: PointLike | TestLatLng) { this.setCenter(value) }
  setOptions(options: Record<string, unknown>) { Object.entries(options).forEach(([key, value]) => this.options.set(key, value)) }
  get(name: string) { return this.options.get(name) }
  setMapTypeId() {}
  getDiv() { return this.element }
  getProjection() {
    return {
      fromLatLngToPoint: (value: TestLatLng) => ({ x: (value.lng() + 180) * 256 / 360, y: (90 - value.lat()) * 256 / 180 }),
      fromPointToLatLng: (value: { x: number; y: number }) => new TestLatLng({ lat: 90 - value.y * 180 / 256, lng: value.x * 360 / 256 - 180 }),
    }
  }
}

class TestAdvancedMarker extends EventTarget {
  map: TestMap | null = null
  position: PointLike | null = null
  content: Node | null = null
  zIndex: number | undefined

  constructor(options: { map?: TestMap; position?: PointLike; content?: Node; zIndex?: number }) {
    super()
    this.position = options.position ?? null
    this.content = options.content ?? null
    this.zIndex = options.zIndex
    this.map = options.map ?? null
    if (this.map && this.content) this.map.getDiv().append(this.content)
  }
}

class TestShape {
  map: TestMap | null
  constructor(options: { map?: TestMap }) { this.map = options.map ?? null }
  setMap(map: TestMap | null) { this.map = map }
  setCenter() {}
}

class TestOverlayView {
  private map: TestMap | null = null

  setMap(map: TestMap | null) {
    if (this.map === map) return
    if (this.map) this.onRemove?.()
    this.map = map
    if (map) {
      this.onAdd?.()
      this.draw?.()
    }
  }

  getMap() { return this.map }
  getPanes() { return { floatPane: this.map?.getDiv() ?? document.createElement('div') } }
  getProjection() {
    const projection = this.map?.getProjection()
    return {
      fromLatLngToDivPixel: (value: TestLatLng) => projection?.fromLatLngToPoint(value) ?? { x: 0, y: 0 },
      fromLatLngToContainerPixel: (value: TestLatLng) => projection?.fromLatLngToPoint(value) ?? { x: 0, y: 0 },
    }
  }
  onAdd?(): void
  draw?(): void
  onRemove?(): void
}

// MarkerClusterer copies OverlayView methods with a `for...in` loop, while
// native class methods are non-enumerable. Google Maps exposes these methods
// as enumerable prototype properties, so mirror that small runtime detail.
for (const method of ['setMap', 'getMap', 'getPanes', 'getProjection'] as const) {
  const descriptor = Object.getOwnPropertyDescriptor(TestOverlayView.prototype, method)
  if (descriptor) Object.defineProperty(TestOverlayView.prototype, method, { ...descriptor, enumerable: true })
}

function noOpListener() { return { remove() {} } }

let libraries: google.maps.MapsLibrary | null = null

export function loadGoogleMapsTestSdk(): Promise<{ maps: google.maps.MapsLibrary; marker: google.maps.MarkerLibrary }> {
  if (!libraries) {
    const event = {
      addListener: (target: { addListener?: (name: string, callback: ListenerCallback) => Listener }, name: string, callback: ListenerCallback) => target.addListener?.(name, callback) ?? noOpListener(),
      addListenerOnce: (target: { addListener?: (name: string, callback: ListenerCallback) => Listener }, name: string, callback: ListenerCallback) => {
        const listener = target.addListener?.(name, (...args) => { listener?.remove(); callback(...args) }) ?? noOpListener()
        queueMicrotask(() => callback())
        return listener
      },
      removeListener: (listener: Listener) => listener.remove(),
      clearInstanceListeners() {},
      trigger: (target: unknown, name: string, ...args: unknown[]) => {
        if (target instanceof TestMap) target.emit(name, ...args)
        else if (target instanceof EventTarget) target.dispatchEvent(new Event(name))
      },
    }
    const maps = {
      Map: TestMap,
      LatLng: TestLatLng,
      LatLngBounds: TestBounds,
      Point: class {
        readonly x: number
        readonly y: number
        constructor(x: number, y: number) { this.x = x; this.y = y }
      },
      Polygon: TestShape,
      Polyline: TestShape,
      Circle: TestShape,
      OverlayView: TestOverlayView,
      event,
      marker: { AdvancedMarkerElement: TestAdvancedMarker },
      CollisionBehavior: { OPTIONAL_AND_HIDES_LOWER_PRIORITY: 'OPTIONAL_AND_HIDES_LOWER_PRIORITY' },
      importLibrary: async (name: string) => name === 'marker' ? { AdvancedMarkerElement: TestAdvancedMarker } : maps,
    }
    Object.assign(window as object, { google: { maps } })
    libraries = maps as unknown as google.maps.MapsLibrary
  }
  return Promise.resolve({ maps: libraries, marker: { AdvancedMarkerElement: TestAdvancedMarker } as unknown as google.maps.MarkerLibrary })
}
