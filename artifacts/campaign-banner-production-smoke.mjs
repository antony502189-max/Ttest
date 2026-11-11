import { chromium, request } from 'playwright'
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'

const expected = process.argv[2]
assert.match(expected ?? '', /^[0-9a-f]{40}$/)
const origin = 'https://app.112233.es'
const directory = 'output/campaign-banner-production'
await mkdir(directory, { recursive: true })
const client = await request.newContext({ baseURL: origin })
const response = await client.get(`/build-info.json?release=${expected}`)
assert.equal(response.status(), 200)
assert.equal((await response.json()).commit, expected)
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
const results = []
try {
  for (const width of [320, 390, 480]) {
    const context = await browser.newContext({ viewport: { width, height: 844 } })
    context.setDefaultTimeout(60_000)
    context.setDefaultNavigationTimeout(90_000)
    await context.addInitScript(() => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:language:v1', 'ru')
    })
    const page = await context.newPage()
    await page.goto(`${origin}/#/`, { waitUntil: 'commit' })
    console.log(JSON.stringify({ width, document: 'received' }))
    const nav = page.locator('.m2-bottom-nav')
    await nav.waitFor({ state: 'visible' })
    assert.deepEqual(await nav.locator('button').allTextContents(), ['Главная', 'Поиски', 'Избранное', 'Меню'])
    const slots = page.locator('.commercial-ad__slot')
    await slots.first().waitFor({ state: 'attached' })
    assert.equal(await slots.count(), 7)
    const offsets = await page.locator('.commercial-ad__slot--empty').evaluateAll(elements => elements.flatMap(element => {
      const bounds = element.getBoundingClientRect()
      return Array.from(element.children).map(child => {
        const rect = child.getBoundingClientRect()
        return Math.abs(rect.y + rect.height / 2 - (bounds.y + bounds.height / 2))
      })
    }))
    for (const offset of offsets) assert.ok(offset <= 1, `Placeholder offset: ${offset}`)
    await page.locator('.commercial-ad').screenshot({ path: `${directory}/banners-${width}.png` })
    await nav.getByRole('button', { name: 'Меню', exact: true }).click()
    await page.waitForURL(/#\/menu$/)
    assert.equal(await nav.getByRole('button', { name: 'Меню', exact: true }).getAttribute('aria-current'), 'page')
    await page.screenshot({ path: `${directory}/menu-${width}.png` })
    results.push({ width, slots: 7, emptySlots: offsets.length / 2, maxCenterOffset: Math.max(0, ...offsets), navigation: 'passed' })
    await context.close()
  }
} finally {
  await browser.close()
  await client.dispose()
}
await writeFile(`${directory}/results.json`, JSON.stringify({ commit: expected, results }, null, 2))
console.log(JSON.stringify({ commit: expected, results }))
