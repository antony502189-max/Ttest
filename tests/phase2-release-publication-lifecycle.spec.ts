import { expect, test, type Page } from '@playwright/test'

test.use({ viewport: { width: 390, height: 844 } })

async function asOwner(page: Page) {
  await page.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
  })
}

const address = {
  formattedAddress: 'Calle José Espronceda 20, 38678 Armeñime, Adeje',
  addressComponents: [
    { longText: 'Calle José Espronceda', types: ['route'] },
    { longText: '20', types: ['street_number'] },
    { longText: '38678', types: ['postal_code'] },
    { longText: 'Armeñime', types: ['sublocality_level_1'] },
    { longText: 'Adeje', types: ['administrative_area_level_3'] },
  ],
  coordinates: { lat: 28.12909, lng: -16.75657 },
}

async function verifyPublicationEnhancers(page: Page) {
  const street = page.locator('#publish-street[data-address-autocomplete="native"]')
  await expect(street).toBeVisible()
  await expect(page.locator('.approximate-location-map')).toBeVisible()
  await page.evaluate((address) => {
    window.__112233TestAddressPredictions = async () => [{
      label: address.formattedAddress,
      detail: address,
    }]
  }, address)

  await street.fill('Calle José Espronceda 20')
  const suggestion = page.locator('.publish-address-prediction').first()
  await expect(suggestion).toBeVisible()
  await suggestion.click()

  await expect(street).toHaveValue('Calle José Espronceda 20')
  await expect(page.getByLabel('Código postal')).toHaveValue('38678')
  await expect(page.getByLabel('Municipio')).toHaveValue('Adeje')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Armeñime')
  await expect.poll(() => {
    return page.evaluate(() => {
      const center = window.__googleMapsTestLastMap?.getCenter()
      return center ? { lat: Number(center.lat().toFixed(5)), lng: Number(center.lng().toFixed(5)) } : null
    })
  }).toEqual(address.coordinates)
  await expect.poll(() => page.evaluate(() => window.__googleMapsTestLastMap?.getZoom())).toBe(18)
}

test('authenticated creation retains address autocomplete and exact map sync with lazily loaded enhancers', async ({ page }) => {
  await asOwner(page)
  await page.goto('/#/publicar')
  await expect(page.locator('.listing-create-page')).toBeVisible()
  await verifyPublicationEnhancers(page)
})

test('authenticated edit retains address autocomplete and exact map sync with lazily loaded enhancers', async ({ page }) => {
  await asOwner(page)
  await page.goto('/#/mis-anuncios')
  const edit = page.locator('.manage-card').first().getByRole('link', { name: /Editar/i })
  await expect(edit).toBeVisible()
  const href = await edit.getAttribute('href')
  expect(href).toBeTruthy()
  await page.goto(href!.startsWith('#') ? `/${href}` : href!)
  await expect(page.locator('.listing-edit-page')).toBeVisible()
  await verifyPublicationEnhancers(page)
})

test('unauthenticated publication remains protected and does not mount the private address form', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/publicar')
  await expect(page).toHaveURL(/#\/acceso/)
  await expect(page.locator('#publish-street')).toHaveCount(0)
})
