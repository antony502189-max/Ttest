import { expect, test } from '@playwright/test'
import { card, changeSearch, deferred, fixtures, id, result, rows, urls, type SearchBody } from './fixtures'

const cardSelector = '.m2-result-card'

for (const count of [1, 5, 8, 15]) for (const external of [false, true]) {
  test(`${external ? 'external' : 'native'} ${count} photos preserve every URL, order, cover and wraparound`, async ({ page }) => {
    let galleryCalls = 0
    const errors = await fixtures(page, (_, route) => route.fulfill({ json: result([card(count, id, 'holiday', external)]) }), async route => {
      galleryCalls++
      await route.fulfill({ json: rows(count) })
    })
    await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
    const first = page.locator(cardSelector).first()
    for (let i = 0; i <= count; i++) {
      await expect(first.locator('.m2-result-card__counter')).toHaveText(`${i % count + 1}/${count}`)
      await expect(first.locator('img')).toHaveAttribute('src', new RegExp(`${urls[i % count]}\\?variant=card$`))
      if (count > 1) await first.locator('.m2-result-card__next').click()
    }
    expect(galleryCalls).toBe(external || count >= 5 ? 0 : 1)
    expect(errors).toEqual([])
  })
}

for (const toggles of [1, 5]) {
  test(`${toggles} favorite toggles do not cancel delayed recovery or refetch newest results`, async ({ page }) => {
    const gate = deferred()
    const searches: SearchBody[] = []
    let galleryCalls = 0
    await fixtures(page, async (body, route) => { searches.push(body); await route.fulfill({ json: result() }) }, async route => {
      galleryCalls++
      await gate.promise
      await route.fulfill({ json: rows(5) })
    })
    await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
    const first = page.locator(cardSelector).first()
    await expect(first.locator('.m2-result-card__counter')).toHaveText('1/1')
    for (let i = 0; i < toggles; i++) await first.locator('.m2-result-card__favorite').click()
    gate.resolve()
    await expect(first.locator('.m2-result-card__counter')).toHaveText('1/5')
    expect(searches).toHaveLength(1)
    expect(galleryCalls).toBe(1)
  })
}

test('saved sorting legitimately starts a new generation when favorites change', async ({ page }) => {
  const searches: SearchBody[] = []
  await fixtures(page, async (body, route) => { searches.push(body); await route.fulfill({ json: result([card(5)]) }) })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday&mobileOrden=saved-new')
  await page.locator('.m2-result-card__favorite').click()
  await expect.poll(() => searches.length).toBe(2)
  expect(searches[1].sort).toBe('saved_new')
  expect(searches[1].favoriteIds).toEqual([id])
})

for (const rentalMode of ['holiday', 'long']) for (const back of ['browser', 'application']) {
  test(`${rentalMode} detail and ${back} Back preserve session, delayed recovery, filters and scroll`, async ({ page }) => {
    const gate = deferred()
    const searches: SearchBody[] = []
    await fixtures(page, async (body, route) => { searches.push(body); await route.fulfill({ json: result(Array.from({ length: 20 }, (_, i) => card(i === 0 ? 1 : 5, i === 0 ? id : `20000000-0000-4000-8000-${String(i + 2).padStart(12, '0')}`, rentalMode))) }) }, async route => {
      await gate.promise
      await route.fulfill({ json: rows(5) })
    })
    await page.goto(`/#/buscar?q=Adeje&alquiler=${rentalMode}&precioMax=900`)
    const results = page.getByTestId('mobile-results')
    const first = page.locator(cardSelector).first()
    await expect(first.locator('.m2-result-card__counter')).toHaveText('1/1')
    await results.evaluate(el => { el.scrollTop = 180 })
    const scroll = await results.evaluate(el => el.scrollTop)
    const searchUrl = page.url()
    await first.locator('.m2-result-card__image-button').click()
    await expect(page.locator('.listing-page h1')).toBeVisible()
    expect(searches).toHaveLength(1)
    gate.resolve()
    if (back === 'browser') await page.goBack()
    else await page.getByRole('button', { name: 'Volver', exact: true }).click()
    await expect(page).toHaveURL(searchUrl)
    await expect(first.locator('.m2-result-card__counter')).toHaveText('1/5')
    await expect.poll(() => results.evaluate(el => el.scrollTop)).toBe(scroll)
    expect(searches).toHaveLength(1)
    expect(searches[0].rentalMode).toBe(rentalMode)
    expect(searches[0].query).toBe('Adeje')
    await expect(page.locator(cardSelector)).toHaveCount(20)
  })
}

for (const replacement of ['q=Arona&alquiler=holiday', 'q=Tenerife&alquiler=long', 'q=Tenerife&alquiler=holiday&mobileOrden=cheap']) {
  test(`replacement ${replacement} rejects obsolete recovery with overlapping listing IDs`, async ({ page }) => {
    const gate = deferred()
    let calls = 0
    let finished = false
    await fixtures(page, async (_, route) => { calls++; await route.fulfill({ json: result([card(calls === 1 ? 1 : 15)]) }) }, async route => {
      await gate.promise
      await route.fulfill({ json: rows(8) }).catch(() => undefined)
      finished = true
    })
    await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
    const first = page.locator(cardSelector).first()
    await expect(first.locator('.m2-result-card__counter')).toHaveText('1/1')
    await changeSearch(page, replacement)
    await expect(first.locator('.m2-result-card__counter')).toHaveText('1/15')
    gate.resolve()
    await expect.poll(() => finished).toBe(true)
    await expect(first.locator('.m2-result-card__counter')).toHaveText('1/15')
    expect(calls).toBe(2)
  })
}

test('page-two recovery cannot replace a newer complete gallery; pagination uses 20, one request and correct cursor', async ({ page }) => {
  const galleryGate = deferred()
  const searches: SearchBody[] = []
  let finished = false
  await fixtures(page, async (body, route) => {
    searches.push(body)
    if (body.query === 'Arona') return route.fulfill({ json: result([card(15)]) })
    if (body.cursor) return route.fulfill({ json: result([card()], null, 21) })
    await route.fulfill({ json: result(Array.from({ length: 20 }, (_, i) => card(5, `10000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`)), 'page-two', 21) })
  }, async route => { await galleryGate.promise; await route.fulfill({ json: rows(8) }).catch(() => undefined); finished = true })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  await expect(page.locator(cardSelector)).toHaveCount(20)
  await page.getByTestId('mobile-results').evaluate(el => { el.scrollTop = el.scrollHeight })
  await expect(page.locator(cardSelector)).toHaveCount(21)
  await changeSearch(page, 'q=Arona&alquiler=holiday')
  await expect(page.locator(cardSelector)).toHaveCount(1)
  await expect(page.locator('.m2-result-card__counter')).toHaveText('1/15')
  galleryGate.resolve()
  await expect.poll(() => finished).toBe(true)
  await expect(page.locator('.m2-result-card__counter')).toHaveText('1/15')
  expect(searches.map(body => body.limit)).toEqual([20, 20, 20])
  expect(searches.map(body => body.cursor)).toEqual([undefined, 'page-two', undefined])
})

test('obsolete delayed page cannot append after a new search', async ({ page }) => {
  const gate = deferred()
  let pageRequested = false
  let finished = false
  await fixtures(page, async (body, route) => {
    if (body.query === 'Arona') return route.fulfill({ json: result([card(15)]) })
    if (body.cursor) { pageRequested = true; await gate.promise; await route.fulfill({ json: result([card(5)], null, 21) }).catch(() => undefined); finished = true; return }
    await route.fulfill({ json: result(Array.from({ length: 20 }, (_, i) => card(5, `10000000-0000-4000-8000-${String(i + 1).padStart(12, '0')}`)), 'next', 21) })
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  await page.getByTestId('mobile-results').evaluate(el => { el.scrollTop = el.scrollHeight })
  await expect.poll(() => pageRequested).toBe(true)
  await changeSearch(page, 'q=Arona&alquiler=holiday')
  await expect(page.locator(cardSelector)).toHaveCount(1)
  await expect(page.locator('.m2-result-card__counter')).toHaveText('1/15')
  gate.resolve()
  await expect.poll(() => finished).toBe(true)
  await expect(page.locator(cardSelector)).toHaveCount(1)
})

for (const failure of ['503', 'abort', 'empty']) {
  test(`gallery ${failure} preserves cover and catalogue refresh retries successfully`, async ({ page }) => {
    let calls = 0
    await fixtures(page, (_, route) => route.fulfill({ json: result() }), async route => {
      calls++
      if (calls > 1) return route.fulfill({ json: rows(5) })
      if (failure === 'abort') return route.abort('failed')
      await route.fulfill(failure === '503' ? { status: 503, json: {} } : { json: [] })
    })
    await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
    const first = page.locator(cardSelector).first()
    await expect(first.locator('.m2-result-card__counter')).toHaveText('1/1')
    await expect(first.locator('img')).toHaveAttribute('src', new RegExp(`${urls[0]}\\?variant=card$`))
    await page.evaluate(() => window.dispatchEvent(new Event('catalog:updated')))
    await expect(first.locator('.m2-result-card__counter')).toHaveText('1/5')
    expect(calls).toBe(2)
  })
}

test('immediate recovery preserves the cover and sorts the full gallery by cover then sortOrder', async ({ page }) => {
  await fixtures(page, (_, route) => route.fulfill({ json: result() }), route => route.fulfill({ json: rows(5).reverse() }))
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  const first = page.locator(cardSelector).first()
  await expect(first.locator('.m2-result-card__counter')).toHaveText('1/5')
  for (let i = 0; i < 5; i++) {
    await expect(first.locator('img')).toHaveAttribute('src', new RegExp(`${urls[i]}\\?variant=card$`))
    await first.locator('.m2-result-card__next').click()
  }
})

test('a legitimate newer removal shrinks the gallery and clamps the selected index', async ({ page }) => {
  const gate = deferred()
  await fixtures(page, (_, route) => route.fulfill({ json: result([card(4)]) }), async route => { await gate.promise; await route.fulfill({ json: rows(1) }) })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  const first = page.locator(cardSelector).first()
  await expect(first.locator('.m2-result-card__counter')).toHaveText('1/4')
  for (let i = 0; i < 3; i++) await first.locator('.m2-result-card__next').click()
  await expect(first.locator('.m2-result-card__counter')).toHaveText('4/4')
  gate.resolve()
  await expect(first.locator('.m2-result-card__counter')).toHaveText('1/1')
  await expect(first.locator('img')).toHaveAttribute('src', new RegExp(`${urls[0]}\\?variant=card$`))
})

test('concurrent recoveries can finish in reverse order without duplicate requests', async ({ page }) => {
  const gates = [deferred(), deferred()]
  const ids = [id, '20000000-0000-4000-8000-000000000002']
  const counts = [5, 8]
  const calls = [0, 0]
  await fixtures(page, (_, route) => route.fulfill({ json: result(ids.map(item => card(1, item))) }), async route => {
    const i = ids.findIndex(item => route.request().url().includes(item))
    calls[i]++
    await gates[i].promise
    await route.fulfill({ json: rows(counts[i]) })
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  await expect(page.locator(cardSelector)).toHaveCount(2)
  gates[1].resolve()
  await expect(page.locator('.m2-result-card__counter').nth(1)).toHaveText('1/8')
  await expect(page.locator('.m2-result-card__counter').nth(0)).toHaveText('1/1')
  gates[0].resolve()
  await expect(page.locator('.m2-result-card__counter').nth(0)).toHaveText('1/5')
  expect(calls).toEqual([1, 1])
})

test('unmount aborts recovery and a remount starts a fresh usable generation', async ({ page }) => {
  const gate = deferred()
  let calls = 0
  await fixtures(page, (_, route) => route.fulfill({ json: result() }), async route => {
    calls++
    if (calls === 1) await gate.promise
    await route.fulfill({ json: rows(calls === 1 ? 8 : 5) }).catch(() => undefined)
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  await expect(page.locator(cardSelector)).toHaveCount(1)
  await page.setViewportSize({ width: 1440, height: 900 })
  await expect(page.getByTestId('mobile-results')).toHaveCount(0)
  gate.resolve()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.locator('.m2-result-card__counter')).toHaveText('1/5')
})

for (const destination of ['map', 'favorites']) {
  test(`search → ${destination} → Back preserves delayed recovery through repeated navigation`, async ({ page }) => {
    const gate = deferred()
    let calls = 0
    await fixtures(page, async (_, route) => { calls++; await route.fulfill({ json: result() }) }, async route => { await gate.promise; await route.fulfill({ json: rows(5) }) })
    await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
    await expect(page.locator('.m2-result-card__counter')).toHaveText('1/1')
    for (let i = 0; i < 2; i++) {
      if (destination === 'map') {
        await page.getByTestId('mobile-results').getByRole('button', { name: 'Mapa', exact: true }).click()
        await expect(page.getByTestId('google-map')).toBeVisible()
      } else {
        await page.evaluate(() => { location.hash = '#/favoritos' })
        await expect(page).toHaveURL(/#\/favoritos/)
      }
      await page.goBack()
      await expect(page.getByTestId('mobile-results')).toBeVisible()
    }
    gate.resolve()
    await expect(page.locator('.m2-result-card__counter')).toHaveText('1/5')
    expect(calls).toBe(1)
  })
}

test('CPU constrained mobile still renders cards before delayed recovery and preserves favorite intent', async ({ page }) => {
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
  const gate = deferred()
  await fixtures(page, (_, route) => route.fulfill({ json: result() }), async route => { await gate.promise; await route.fulfill({ json: rows(15) }) })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  await expect(page.locator('.m2-result-card__counter')).toHaveText('1/1')
  await page.locator('.m2-result-card__favorite').click()
  gate.resolve()
  await expect(page.locator('.m2-result-card__counter')).toHaveText('1/15')
  await expect(page.locator('.m2-result-card__favorite')).toHaveAttribute('aria-pressed', 'true')
})


for (const external of [false, true]) {
  test(`mobile ${external ? 'external' : 'native'} gallery skips a broken cover but retains all working photos`, async ({ page }) => {
    const errors = await fixtures(page, (_, route) =>
      route.fulfill({ json: result([card(5, id, 'holiday', external)]) }))
    await page.route('**/api/v1/media/**', (route) => {
      if (new URL(route.request().url()).pathname === urls[0]) {
        return route.fulfill({ status: 404, body: 'missing cover' })
      }
      return route.fulfill({
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640"><rect width="960" height="640" fill="#789"/></svg>',
      })
    })
    await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
    const first = page.locator(cardSelector).first()
    await expect(first.locator('.m2-result-card__counter')).toHaveText('2/5')
    await expect(first.locator('img')).toHaveAttribute('src', new RegExp(`${urls[1]}\\?variant=card$`))
    await expect.poll(() => first.locator('img').evaluate((img: HTMLImageElement) => img.naturalWidth)).toBe(960)
    for (const expected of ['3/5', '4/5', '5/5', '2/5']) {
      await first.locator('.m2-result-card__next').click()
      await expect(first.locator('.m2-result-card__counter')).toHaveText(expected)
    }
    expect(errors).toEqual([])
  })
}

test('mobile gallery uses its fallback only if all images are broken, without retry loops', async ({ page }) => {
  const errors = await fixtures(page, (_, route) =>
    route.fulfill({ json: result([card(2, id, 'holiday', true)]) }))
  const attempts = new Map<string, number>()
  await page.route('**/api/v1/media/**', (route) => {
    const url = new URL(route.request().url()).pathname
    attempts.set(url, (attempts.get(url) ?? 0) + 1)
    return route.fulfill({ status: 404, body: '' })
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=holiday')
  const first = page.locator(cardSelector).first()
  await expect(first.locator('img')).toHaveAttribute('src', /^data:image\/svg\+xml/)
  await first.locator('.m2-result-card__next').click()
  await expect(first.locator('img')).toHaveAttribute('src', /^data:image\/svg\+xml/)
  expect(attempts.get(urls[0])).toBe(1)
  expect(attempts.get(urls[1])).toBe(1)
  expect(errors).toEqual([])
})
