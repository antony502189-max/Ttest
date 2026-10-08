import { expect, test } from '@playwright/test'
import { card, changeSearch, deferred, fixtures, id, result } from './fixtures'

test('one in-flight page, 20-card batches, within-page dedup, ordering and promotion survive Back', async ({ page }) => {
  const gate = deferred()
  let inFlight = 0
  let maximum = 0
  const cursors: Array<string | undefined> = []
  const batch = Array.from({ length: 20 }, (_, i) => ({ ...card(5, i === 0 ? id : `10000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`), promoted: i === 0 }))
  const second = Array.from({ length: 20 }, (_, i) => card(5, `10000000-0000-4000-8000-${String(i + 21).padStart(12, '0')}`))
  await fixtures(page, async (body, route) => {
    expect(body.limit).toBe(20)
    cursors.push(body.cursor)
    inFlight++; maximum = Math.max(maximum, inFlight)
    if (body.cursor) await gate.promise
    await route.fulfill({ json: body.cursor ? result(second, null, 40) : result(batch, 'next', 40) })
    inFlight--
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  await expect(page.locator('.m2-result-card')).toHaveCount(20)
  await expect(page.locator('.m2-result-card').first()).toHaveAttribute('data-listing-id', id)
  await page.getByTestId('mobile-results').evaluate(el => { el.scrollTop = el.scrollHeight })
  await expect.poll(() => cursors.length).toBe(2)
  for (let i = 0; i < 3; i++) await page.getByTestId('mobile-results').evaluate(el => { el.scrollTop -= 10; el.scrollTop += 10 })
  expect(cursors).toEqual([undefined, 'next'])
  gate.resolve()
  await expect(page.locator('.m2-result-card')).toHaveCount(40)
  expect(await page.locator('.m2-result-card').evaluateAll(cards => cards.map(card => card.getAttribute('data-listing-id')))).toEqual([...batch, ...second].map(card => card.id))
  expect(maximum).toBe(1)
  await page.getByTestId('mobile-results').evaluate(el => { el.scrollTop = 0 })
  await page.locator('.m2-result-card__image-button').first().click()
  await expect(page.locator('.listing-page')).toBeVisible()
  await page.goBack()
  await expect(page.locator('.m2-result-card')).toHaveCount(40)
  expect(cursors).toEqual([undefined, 'next'])
})

test('duplicates in a malformed page do not produce duplicate cards or recovery calls', async ({ page }) => {
  const duplicate = card(5)
  await fixtures(page, async (body, route) => {
    await route.fulfill({ json: body.cursor ? result([duplicate, card(5, '10000000-0000-4000-8000-000000000002'), card(5, '10000000-0000-4000-8000-000000000002')], null, 2) : result([duplicate, duplicate], 'next', 2) })
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  await expect(page.locator('.m2-result-card')).toHaveCount(2)
  expect(await page.locator('.m2-result-card').evaluateAll(cards => new Set(cards.map(card => card.getAttribute('data-listing-id'))).size)).toBe(2)
})

test('failed initial search and failed page retry retain coherent session state', async ({ page }) => {
  let initial = 0
  let pagination = 0
  const batch = Array.from({ length: 20 }, (_, i) => card(5, `10000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`))
  await fixtures(page, async (body, route) => {
    const fail = body.cursor ? ++pagination === 1 : ++initial === 1
    if (fail) return route.fulfill({ status: 503, json: {} })
    await route.fulfill({ json: body.cursor ? result([card(5)], null, 21) : result(batch, 'next', 21) })
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  await page.getByRole('button', { name: 'Reintentar', exact: true }).click()
  await expect(page.locator('.m2-result-card')).toHaveCount(20)
  await page.getByTestId('mobile-results').evaluate(el => { el.scrollTop = el.scrollHeight })
  await page.getByTestId('mobile-results-load-more').getByRole('button', { name: 'Reintentar' }).click()
  await expect(page.locator('.m2-result-card')).toHaveCount(21)
  expect(initial).toBe(2)
  expect(pagination).toBe(2)
  await changeSearch(page, 'q=Tenerife&alquiler=long')
  await expect(page.locator('.m2-result-card')).toHaveCount(20)
})
