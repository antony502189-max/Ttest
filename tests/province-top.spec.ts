import { expect, test } from '@playwright/test'

for (const width of [320, 1280]) {
  test(`full province blocks payment and counts down without changing the dialog at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => {
      localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:language:v1', 'ru')
    })
    let requests = 0
    let released = false
    await page.route('**/payments/listings/*/top/availability?*', (route) => {
      requests++
      const now = new Date()
      return route.fulfill({ json: { provinceCode: '28', province: 'Madrid', capacity: 3,
        available: released, availableSlots: released ? 1 : 0, serverNow: now.toISOString(),
        availableAt: new Date(now.getTime() + (released ? 0 : 3665000)).toISOString() } })
    })
    let checkouts = 0
    await page.route('**/payments/listings/*/top/checkout', (route) => { checkouts++; return route.fulfill({ status: 503, json: { detail: 'Test checkout' } }) })
    await page.goto('/#/mis-anuncios')
    await page.getByTestId('owner-top-promote-button').first().click()
    await page.getByTestId('owner-promotion-choices').getByRole('button').last().click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toHaveClass(/owner-top-dialog/)
    await expect(dialog.getByTestId('province-top-availability')).toContainText('Madrid')
    await expect(dialog.getByRole('status')).toContainText('все места TOP')
    await expect(dialog.getByRole('timer')).toHaveText(/01:01:0[45]/)
    const before = await dialog.getByRole('timer').innerText()
    await expect.poll(() => dialog.getByRole('timer').innerText()).not.toBe(before)
    const continueButton = dialog.getByRole('button', { name: 'Продолжить', exact: true })
    await expect(continueButton).toBeDisabled()
    expect(checkouts).toBe(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await dialog.screenshot({ path: `output/province-top/full-${width}.png` })
    released = true
    await expect(continueButton).toBeEnabled({ timeout: 20000 })
    expect(requests).toBeGreaterThan(1)
    await continueButton.click()
    await expect(dialog.getByRole('button', { name: 'Оплатить через Stripe' })).toBeEnabled()
    expect(checkouts).toBe(0)
  })
}

test('province search keeps the existing location rows and separates both Canary provinces', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => localStorage.setItem('112233:mobile-onboarding:v1', 'done'))
  await page.goto('/#/?panel=ubicacion')
  await expect(page.getByTestId('province-suggestions').locator('.m2-community-option')).toHaveCount(52)
  const input = page.getByRole('searchbox')
  await input.fill('Tenerife')
  await expect(page.getByTestId('province-option-38')).toBeVisible()
  await page.getByTestId('province-option-38').click()
  await expect(page).toHaveURL(/provincia=38/)
  await expect(page.locator('.m2-results__header')).toContainText('Santa Cruz de Tenerife')
  await page.goto('/#/?panel=ubicacion')
  await page.getByRole('searchbox').fill('Las Palmas')
  await page.getByTestId('province-option-35').click()
  await expect(page).toHaveURL(/provincia=35/)
  await expect(page.locator('.m2-results__header')).toContainText('Las Palmas')
})

test('publication derives the province from the selected address without a manual city selector', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
  await page.goto('/#/publicar')
  const province = page.getByLabel('Provincia', { exact: true })
  await expect(province).toHaveAttribute('readonly', '')
  await expect(page.locator('#publish-city')).toHaveAttribute('type', 'hidden')
  await expect(page.locator('select#publish-city')).toHaveCount(0)
  await expect(page.locator('.approximate-location-map [data-test-map-sdk="1"]')).toHaveCount(1)
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('112233:publish-location-selected', {
    detail: { coordinates: { lat: 40.4168, lng: -3.7038 }, address: {
      formattedAddress: 'Calle Mayor, Madrid, España', coordinates: { lat: 40.4168, lng: -3.7038 },
      city: 'Madrid', postcode: '28013', street: 'Calle Mayor, 1', area: 'Centro',
    } },
  })))
  await expect(province).toHaveValue('Madrid')
  await expect(page.locator('#publish-city')).toHaveValue('Madrid')
  await expect(page.locator('#publish-postcode')).toHaveValue('28013')
  await page.goto('/#/mis-anuncios')
  const edit = page.locator('a[href*="/editar"]').first()
  await expect(edit).toBeVisible()
  await edit.click()
  await expect(page.getByLabel('Provincia', { exact: true })).toHaveAttribute('readonly', '')
  await expect(page.locator('select#publish-city')).toHaveCount(0)
})
