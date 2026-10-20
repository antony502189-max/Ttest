import { expect, type Page } from '@playwright/test'

export async function selectResolvedAddress(page: Page, address: {
  city: string; postcode: string; area: string; street: string; coordinates: { lat: number; lng: number }
}) {
  await page.evaluate((value) => window.dispatchEvent(new CustomEvent('112233:publish-location-selected', {
    detail: { coordinates: value.coordinates, zoom: 18, address: { ...value,
      formattedAddress: `${value.street}, ${value.postcode} ${value.city}, España` } },
  })), address)
}


// Exercise compatibility with an explicitly chosen municipality restored from
// an older draft. The current publication UI obtains this metadata from addresses.
export async function restoreMunicipalityMetadata(page: Page, city: string) {
  const coordinates = await page.evaluate(() => {
    const center = window.__googleMapsTestLastMap?.getCenter()
    return center ? { lat: center.lat(), lng: center.lng() } : { lat: 28.12, lng: -16.73 }
  })
  await selectResolvedAddress(page, { city, area: '', street: '', postcode: '', coordinates })
  await expect(page.locator('#publish-city')).toHaveValue(city)
  await page.locator('#publish-city').dispatchEvent('change')
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(11)
}
