import { expect, test, type Page } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/payments/listings/*/top/availability?*', route => {
    const hours = Number(new URL(route.request().url()).searchParams.get('durationHours'))
    expect([12, 24, 72]).toContain(hours)
    return route.fulfill({ json: { municipalityCode: '28079', municipality: 'Madrid', capacity: 3,
      available: true, availableSlots: 3, availableAt: null, serverNow: new Date().toISOString() } })
  })
})

async function openHourlyOffers(page: Page, time: string) {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'ru')
  })
  await page.goto('/#/')
  await page.waitForFunction(() => Boolean(localStorage.getItem('112233:listings:v3')))
  await page.evaluate(() => {
    const stored = JSON.parse(localStorage.getItem('112233:listings:v3')!)
    for (const item of stored.data) { item.status = 'Publicado'; item.expiresAt = '2035-01-01T00:00:00Z' }
    localStorage.setItem('112233:listings:v3', JSON.stringify(stored))
  })
  await page.clock.install({ time: new Date(time) })
  await page.goto('/?hourly-check=1#/mis-anuncios')
  await page.getByTestId('owner-top-promote-button').first().click()
  await page.getByRole('button', { name: /Поднять свое объявление в (?:TOP|ТОП)/ }).click()
  return page.getByRole('dialog')
}

test('hourly promotion tiers do not expose legacy date or day-range controls across DST', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 })
  const dialog = await openHourlyOffers(page, '2026-03-28T12:00:00Z')
  await expect(dialog.locator('input[type="date"]')).toHaveCount(0)
  const choices = dialog.locator('.owner-promotion-duration-option')
  await expect(choices).toHaveCount(3)
  for (const [index, label, amount] of [[0, '12 часов', '0,99'], [1, '24 часа', '1,70'], [2, '3 дня', '4,50']] as const) {
    await expect(choices.nth(index)).toContainText(label)
    await expect(choices.nth(index)).toContainText(amount)
  }
  await choices.nth(1).click()
  await expect(choices.nth(1)).toHaveAttribute('aria-pressed', 'true')
  let checkouts = 0
  await page.route('**/payments/listings/*/top/checkout', route => {
    expect(route.request().postDataJSON()).toEqual({ durationHours: 24 })
    checkouts++
    return route.fulfill({ status: 503, json: { detail: 'Test checkout' } })
  })
  await dialog.getByRole('button', { name: 'Продолжить', exact: true }).click()
  await expect(dialog).toContainText('1,70')
  expect(checkouts).toBe(0)
  await dialog.getByRole('button', { name: 'Оплатить через Stripe' }).click()
  await expect(dialog.getByRole('alert')).toHaveText('Test checkout')
  expect(checkouts).toBe(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('going back preserves the chosen duration without creating Stripe checkout', async ({ page }) => {
  const dialog = await openHourlyOffers(page, '2028-02-29T12:00:00Z')
  const choices = dialog.locator('.owner-promotion-duration-option')
  await choices.nth(2).click()
  await dialog.getByRole('button', { name: 'Продолжить', exact: true }).click()
  await expect(dialog).toContainText('4,50')
  await dialog.getByRole('button', { name: 'Назад', exact: true }).click()
  await expect(choices.nth(2)).toHaveAttribute('aria-pressed', 'true')
  await expect(dialog.getByRole('button', { name: 'Оплатить через Stripe' })).toHaveCount(0)
})

for (const timezoneId of ['UTC', 'America/Los_Angeles', 'Pacific/Kiritimati']) {
  test.describe(`hourly packages in ${timezoneId}`, () => {
    test.use({ timezoneId })
    test('12, 24 and 72-hour choices are date independent', async ({ page }) => {
      const dialog = await openHourlyOffers(page, '2026-12-27T23:30:00Z')
      const choices = dialog.locator('.owner-promotion-duration-option')
      for (const i of [0, 1, 2]) {
        await choices.nth(i).click()
        await expect(choices.nth(i)).toHaveAttribute('aria-pressed', 'true')
      }
      await expect(dialog.locator('input[type="date"]')).toHaveCount(0)
    })
  })
}
