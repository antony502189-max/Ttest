import { expect, test } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import { mockAdmin } from './fixtures'

const phase = process.env.ADMIN_BENCHMARK_PHASE
const results: unknown[] = []
test.skip(!phase, 'Opt-in reproducible before/after benchmark')

test.afterAll(() => {
  if (!phase) return
  mkdirSync(`output/admin-performance/${phase}`, { recursive: true })
  writeFileSync(`output/admin-performance/${phase}/metrics.json`, JSON.stringify(results, null, 2))
})

for (const count of [100, 1000, 5000, 10000]) {
  test(`${count} listings initial and repeated visits`, async ({ page }) => {
    const fixture = await mockAdmin(page, count)
    const adminStart = performance.now()
    await page.goto('/#/admin')
    await expect(page.locator('.admin-user-row')).toHaveCount(1)
    const initialAdminUsableMs = performance.now() - adminStart
    for (const visit of ['initial', 'repeated']) {
      const requestStart = fixture.requests.length
      const bytesStart = fixture.bytes()
      await page.evaluate(() => {
        const metrics = (window as unknown as { adminMetrics: { longTasks: number[]; reactCommits: number[] } }).adminMetrics
        metrics.longTasks.length = 0; metrics.reactCommits.length = 0
      })
      const start = performance.now()
      await page.getByRole('button', { name: 'Anuncios', exact: true }).click()
      await expect(page.locator('.admin-listing-row').first()).toBeVisible({ timeout: 120_000 })
      const usableMs = performance.now() - start
      const requestsToUsable = fixture.requests.length - requestStart
      const payloadBytesToUsable = fixture.bytes() - bytesStart
      const apiDurationsMs = fixture.durations.slice(requestStart)
      const session = await page.context().newCDPSession(page)
      const heap = await session.send('Runtime.getHeapUsage')
      const metrics = await page.evaluate(() => {
        const values = (window as unknown as { adminMetrics: { longTasks: number[]; reactCommits: number[] } }).adminMetrics
        return { ...values, domElements: document.querySelectorAll('*').length, renderedListings: document.querySelectorAll('.admin-listing-row').length }
      })
      const input = page.getByPlaceholder('Título, usuario, zona o Ref.…')
      const searchStart = performance.now()
      await input.fill(`Habitación ${String(count - 1).padStart(5, '0')}`)
      await expect(page.locator('.admin-listing-row')).toHaveCount(1)
      await expect(page.locator('.admin-listing-row strong')).toHaveText(`Habitación ${String(count - 1).padStart(5, '0')}`)
      results.push({ count, visit, initialAdminUsableMs, usableMs, requestsToUsable, apiDurationsMs,
        payloadBytesToUsable, heapBytes: heap.usedSize, searchMs: performance.now() - searchStart, ...metrics })
      mkdirSync(`output/admin-performance/${phase}`, { recursive: true })
      writeFileSync(`output/admin-performance/${phase}/${count}-${visit}.json`, JSON.stringify(results.at(-1), null, 2))
      await page.getByRole('button', { name: 'Usuarios', exact: true }).click()
    }
    expect(fixture.errors).toEqual([])
  })
}

for (const width of [320, 390, 768, 1440]) {
  for (const language of ['es', 'ru', 'en']) {
    test(`visual capture ${width}px ${language}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await page.clock.setFixedTime(new Date('2026-10-13T12:00:00Z'))
      await mockAdmin(page, 9, 0)
      await page.addInitScript((lang) => localStorage.setItem('112233:language:v1', lang), language)
      await page.goto('/#/admin')
      await expect(page.locator('.admin-user-row')).toHaveCount(1)
      const nav = page.locator('.admin-sidebar nav button')
      const output = `output/admin-performance/${phase}`
      mkdirSync(output, { recursive: true })
      for (const [index, name] of [[0, 'users'], [1, 'reports'], [2, 'listings'], [3, 'advertisements'], [4, 'activity'], [5, 'settings']] as const) {
        await nav.nth(index).click()
        await expect(page.locator('.admin-detail-loading')).toHaveCount(0)
        if (name === 'listings') await expect(page.locator('.admin-listing-row')).toHaveCount(9)
        await page.mouse.move(0, 0)
        await page.evaluate(async () => {
          await document.fonts.ready
          window.scrollTo(0, 0)
          await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
        })
        await page.screenshot({ path: `${output}/${name}-${width}-${language}.png`, fullPage: true, animations: 'disabled' })
      }
      await expect(page.locator('.admin-load-error')).toHaveCount(0)
    })
  }
}
