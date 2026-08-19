import { expect, test, type Page } from '@playwright/test'

// Customer acceptance contract: keep the requested priority, privacy combinations,
// structured floor, and address-resolution flow covered as one regression surface.
// This suite is also the exact-head regression gate after compatibility fixes.
async function openAsHost(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
})

test('CUSTOMER-PRIORITY mobile filters follow the requested decision order and persist to URL', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&panel=filtros')
  const panel = page.locator('.m2-results-filter')
  await expect(panel).toBeVisible()
  const text = await panel.locator('.m2-results-filter__scroll').innerText()
  const ordered = ['Precio', 'Fecha de entrada', 'Ducha / baño privado en la habitación', 'Aseo / WC privado en la habitación', 'Cocina / mini-cocina privada en la habitación', 'Zona totalmente privada', 'Aire acondicionado', 'Tipo de cama', 'Ventana a la calle', 'Se permite fumar']
  for (let index = 1; index < ordered.length; index += 1) expect(text.indexOf(ordered[index - 1])).toBeLessThan(text.indexOf(ordered[index]))

  await panel.getByText('Zona totalmente privada', { exact: false }).click()
  await panel.getByText('Aire acondicionado', { exact: true }).click()
  await panel.getByLabel('Tipo de cama').selectOption('double')
  await panel.getByText('Ventana a la calle', { exact: true }).click()
  await panel.getByText('Se permite fumar', { exact: true }).click()
  await panel.getByText('Ascensor', { exact: true }).click()
  await panel.getByLabel('Planta').selectOption('top')
  await panel.getByRole('button', { name: /Ver anuncios/ }).click()

  await expect(page).toHaveURL(/ducha=Ducha(?:\+|%20)privada/)
  await expect(page).toHaveURL(/aseo=Aseo(?:\+|%20)privado/)
  await expect(page).toHaveURL(/cocina=Cocina(?:\+|%20)privada/)
  await expect(page).toHaveURL(/cama=double/)
  await expect(page).toHaveURL(/fumar=S%C3%AD/)
  await expect(page).toHaveURL(/planta=top/)
  await expect(page).toHaveURL(/servicios=/)
})

test('CUSTOMER-PRIORITY bathroom profile supports private toilet with shared shower', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&panel=filtros')
  const panel = page.locator('.m2-results-filter')
  await panel.getByLabel('Tipo de baño / aseo').selectOption('private-toilet')
  await expect(panel.getByText('Ducha / baño privado en la habitación', { exact: true }).locator('..').locator('input')).not.toBeChecked()
  await expect(panel.getByText('Aseo / WC privado en la habitación', { exact: true }).locator('..').locator('input')).toBeChecked()
  await panel.getByRole('button', { name: /Ver anuncios/ }).click()
  await expect(page).toHaveURL(/ducha=Ducha(?:\+|%20)compartida/)
  await expect(page).toHaveURL(/aseo=Aseo(?:\+|%20)privado/)
})

test('CUSTOMER-LOCATION map/geocoder resolves Tenerife municipality and locality and floor is in publication data', async ({ page }) => {
  await openAsHost(page)
  await page.goto('/#/publicar')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await expect(page.getByLabel('Calle')).toBeVisible()
  await page.evaluate(() => {
    window.dispatchEvent(new CustomEvent('112233:map-address-resolved', { detail: {
      formattedAddress: 'Calle del Valle Menéndez 20, 38650 Los Cristianos, España',
      coordinates: { lat: 28.0521, lng: -16.7177 },
      addressComponents: [
        { long_name: 'Calle del Valle Menéndez', types: ['route'] },
        { long_name: '20', types: ['street_number'] },
        { long_name: '38650', types: ['postal_code'] },
        { long_name: 'Los Cristianos', types: ['locality'] },
        { long_name: 'Arona', types: ['administrative_area_level_3'] },
      ],
    } }))
  })
  await expect(page.getByLabel('Calle')).toHaveValue('Calle del Valle Menéndez 20')
  await expect(page.getByLabel('Código postal')).toHaveValue('38650')
  await expect(page.getByLabel('Municipio')).toHaveValue('Arona')
  await expect(page.getByLabel('Zona o barrio')).toHaveValue('Los Cristianos')

  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByLabel('Planta').selectOption('top')
  await expect(page.getByText('Piscina', { exact: true })).toBeVisible()
  await expect(page.getByText('Jardín', { exact: true })).toBeVisible()
  await expect(page.getByText('Limpieza incluida', { exact: true })).toBeVisible()
  await expect(page.getByText('Ventana a la calle', { exact: true })).toBeVisible()
  const draft = await page.evaluate(() => JSON.parse(localStorage.getItem('112233:listing-draft:v3') ?? '{}').data)
  expect(draft.floor).toBe('top')
})
