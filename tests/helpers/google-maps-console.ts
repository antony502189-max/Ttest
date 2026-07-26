const HEADLESS_VECTOR_FALLBACK = 'Attempted to load a Vector Map, but failed. Falling back to Raster.'

/**
 * Headless Chromium can expose WebGL without the hardware acceleration that a
 * Google vector basemap requires. Production smoke tests do not use this
 * exception; they must remain clean. Authentication, Map ID and all other
 * Google Maps messages are deliberately not accepted here.
 */
export function isExpectedHeadlessVectorFallback(message: string) {
  return message.startsWith(HEADLESS_VECTOR_FALLBACK)
}
