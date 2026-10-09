import { expect, test } from '@playwright/test'
import { card, deferred, fixtures, id, result, rows, urls } from './fixtures'

test.use({ viewport: { width: 1440, height: 900 } })

for (const count of [1, 5, 8, 15]) for (const external of [false, true]) {
  test(`desktop ${external ? 'external' : 'native'} ${count} photos keep rapid counter/source changes and wraparound`, async ({ page }) => {
    await fixtures(page, (_, route) => route.fulfill({ json: result([card(count, id, 'long', external)]) }), route => route.fulfill({ json: rows(count) }))
    await page.goto('/#/buscar?q=Tenerife&alquiler=long')
    const first = page.locator('.property-card').first()
    await expect(first.locator('.image-counter')).toHaveText(`1/${count}`)
    if (count === 1) {
      await expect(first.locator('.card-gallery-arrow')).toHaveCount(0)
      await expect(first.locator('img')).toHaveAttribute('src', new RegExp(`${urls[0]}\\?variant=card$`))
    } else {
      const observed = await first.evaluate(async (card, count) => {
        const states: Array<{ counter: string; source: string }> = []
        const next = card.querySelector<HTMLButtonElement>('.card-gallery-arrow--next')!

        for (let i = 0; i <= count; i++) {
          states.push({ counter: card.querySelector('.image-counter')!.textContent!.trim(), source: card.querySelector('img')!.getAttribute('src')! })
          next.click()
          await new Promise<void>(r => requestAnimationFrame(() => r()))
        }
        return states
      }, count)
      expect(observed.map(state => state.counter)).toEqual(Array.from({ length: count + 1 }, (_, i) => `${i % count + 1}/${count}`))
      observed.forEach((state, i) => expect(state.source).toMatch(new RegExp(`${urls[i % count]}\\?variant=card$`)))
    }
  })
}

test('desktop authoritative removal clamps the card index synchronously', async ({ page }) => {
  const gate = deferred()
  await fixtures(page, (_, route) => route.fulfill({ json: result([card(4)]) }), async route => { await gate.promise; await route.fulfill({ json: rows(1) }).catch(() => undefined) })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const first = page.locator('.property-card').first()
  await expect(first.locator('.image-counter')).toHaveText('1/4')
  for (let i = 0; i < 3; i++) await first.locator('.card-gallery-arrow--next').click()
  await expect(first.locator('.image-counter')).toHaveText('4/4')
  gate.resolve()
  await expect(first.locator('.image-counter')).toHaveText('1/1')
  await expect(first.locator('img')).toHaveAttribute('src', new RegExp(`${urls[0]}\\?variant=card$`))
})


test('desktop listing card advances past an unavailable cover while previous/next skip the broken URL', async ({ page }) => {
  const errors = await fixtures(page, (_, route) =>
    route.fulfill({ json: result([card(5, id, 'long', true)]) }))
  await page.route('**/api/v1/media/**', (route) => {
    if (new URL(route.request().url()).pathname === urls[0]) {
      return route.fulfill({ status: 404, body: 'unavailable' })
    }
    return route.fulfill({
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640"><rect width="960" height="640" fill="#789"/></svg>',
    })
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const first = page.locator('.property-card').first()
  await expect(first.locator('.image-counter')).toHaveText('2/5')
  await expect(first.locator('img')).toHaveAttribute('src', new RegExp(`${urls[1]}\\\\?variant=card$`))
  await expect.poll(() => first.locator('img').evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(960)
  await first.locator('.card-gallery-arrow--previous').click()
  await expect(first.locator('.image-counter')).toHaveText('5/5')
  await first.locator('.card-gallery-arrow--next').click()
  await expect(first.locator('.image-counter')).toHaveText('2/5')
  expect(errors).toEqual([])
})
