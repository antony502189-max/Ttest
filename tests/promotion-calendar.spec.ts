import { expect, test, type Page } from '@playwright/test'

test.use({ timezoneId: 'Europe/Madrid' })
async function openCalendar(page: Page, time: string) {
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
  await page.goto('/?calendar-check=1#/mis-anuncios')
  await page.getByTestId('owner-top-promote-button').first().click()
  await page.getByRole('button', { name: /Поднять свое объявление в TOP/ }).click()
  return page.getByRole('dialog')
}

test('native calendar crosses daylight saving without changing the paid day count', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 })
  const dialog = await openCalendar(page, '2026-03-28T12:00:00Z')
  await expect(dialog.getByLabel('От', { exact: true })).toHaveAttribute('readonly', '')
  await expect(dialog.getByLabel('От', { exact: true })).toHaveValue('2026-03-28')
  const until = dialog.getByLabel('До', { exact: true })
  await expect(until).toHaveAttribute('type', 'date')
  await expect(until).toHaveValue('2026-04-07')
  await dialog.getByRole('button', { name: '14 дн.', exact: true }).click()
  await expect(until).toHaveValue('2026-04-11')
  await until.fill('2026-04-20')
  await expect(dialog.locator('.promotion-period__summary strong')).toHaveText('23 дн.')
  await expect(dialog).not.toContainText('1 €')
  await dialog.screenshot({ path: 'output/advertising/top-calendar-ru-320.png' })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  let paid = 0
  await page.route('**/payments/listings/*/top/checkout', async route => {
    expect(route.request().postDataJSON()).toEqual({ days: 23 })
    paid++
    return route.fulfill({ status: 503, json: { detail: 'Test checkout' } })
  })
  await dialog.getByRole('button', { name: 'Продолжить', exact: true }).click()
  await expect(dialog).toContainText('23,00')
  expect(paid).toBe(0)
  await dialog.getByRole('button', { name: 'Pagar con Stripe' }).click()
  await expect(dialog.getByRole('alert')).toHaveText('Test checkout')
  expect(paid).toBe(1)
})

test('calendar supports leap day, enforces 10–365 days and preserves selection on Back', async ({ page }) => {
  const dialog = await openCalendar(page, '2028-02-20T12:00:00Z')
  const until = dialog.getByLabel('До', { exact: true })
  await expect(until).toHaveValue('2028-03-01')
  await until.fill('2028-02-29')
  await expect(dialog.getByRole('button', { name: 'Продолжить', exact: true })).toBeDisabled()
  await until.fill('2029-02-20')
  await expect(dialog.getByRole('button', { name: 'Продолжить', exact: true })).toBeDisabled()
  await until.fill('2029-02-19')
  await expect(dialog.locator('.promotion-period__summary strong')).toHaveText('365 дн.')
  await dialog.getByRole('button', { name: 'Продолжить', exact: true }).click()
  await expect(dialog).toContainText('365,00')
  await dialog.getByRole('button', { name: 'Назад', exact: true }).click()
  await expect(dialog.getByLabel('До', { exact: true })).toHaveValue('2029-02-19')
  await expect(dialog).not.toContainText('365,00')
})

for (const timezoneId of ['UTC', 'America/Los_Angeles', 'Pacific/Kiritimati']) {
  test.describe(`calendar integration in ${timezoneId}`, () => {
    test.use({ timezoneId })
    test('presets cross the year boundary and an empty date cannot start Checkout', async ({ page }) => {
      const dialog = await openCalendar(page, '2026-12-27T23:30:00Z')
      const start = await dialog.getByLabel('От', { exact: true }).inputValue()
      expect(start).toBe(timezoneId === 'Pacific/Kiritimati' ? '2026-12-28' : '2026-12-27')
      const until = dialog.getByLabel('До', { exact: true })
      for (const days of [10, 14, 21, 30]) {
        await dialog.getByRole('button', { name: `${days} дн.`, exact: true }).click()
        const expected = new Date(Date.parse(`${start}T00:00:00Z`) + days * 86400000).toISOString().slice(0, 10)
        await expect(until).toHaveValue(expected)
        await expect(dialog.locator('.promotion-period__summary strong')).toHaveText(`${days} дн.`)
      }
      let purchases = 0
      await page.route('**/payments/listings/*/top/checkout', route => {
        purchases++
        return route.fulfill({ status: 503, json: { detail: 'Synthetic checkout' } })
      })
      await until.fill('')
      await expect(dialog.getByRole('button', { name: 'Продолжить', exact: true })).toBeDisabled()
      expect(purchases).toBe(0)
    })
  })
}
