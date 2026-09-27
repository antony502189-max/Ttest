export const googleMapsTestSdkEnabled = import.meta.env.VITE_GOOGLE_MAPS_TEST_SDK === '1'

export async function loadGoogleMapsOnDemand() {
  const { loadGoogleMaps } = await import('@/lib/google-maps/loader')
  return loadGoogleMaps()
}
