import { chromium, request } from 'playwright'
import { mkdir, writeFile } from 'node:fs/promises'
import assert from 'node:assert/strict'

const expected = process.argv[2]
assert.match(expected ?? '', /^[0-9a-f]{40}$/)
const root = 'https://app.112233.es'
const directory = 'artifacts/municipality-release-2026-10-21'
await mkdir(directory, { recursive: true })
const client = await request.newContext({ baseURL: root })
const build = await (await client.get(`/build-info.json?release=${expected}`)).json()
assert.equal(build.commit, expected)
const results = []
for (const [code, name] of [['38001', 'Adeje'], ['38004', 'Arafo']]) {
  const response = await client.post('/api/v1/listings/search/cards', {
    data: { query: name, provinceCode: '38', municipalityCode: code, rentalMode: 'long', limit: 50 },
  })
  assert.equal(response.status(), 200, await response.text())
  const body = await response.json()
  for (const item of body.items) {
    assert.equal(item.city.toLowerCase(), name.toLowerCase())
    assert.ok(item.provinceCode == null || item.provinceCode === '38')
  }
  results.push({ name, code, total: body.total, checkedCards: body.items.length })
  console.log(JSON.stringify(results.at(-1)))
}
const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
try {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
  await context.addInitScript(() => {
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    localStorage.setItem('112233:language:v1', 'es')
  })
  const page = await context.newPage()
  for (const [code, name] of [['38004', 'Arafo'], ['38001', 'Adeje']]) {
    await page.goto(`${root}/#/?panel=ubicacion`, { waitUntil: 'domcontentloaded' })
    const input = page.getByRole('searchbox')
    await input.fill('a')
    await page.getByTestId(`municipality-option-${code}`).waitFor({ state: 'attached' })
    await input.fill(name)
    await page.getByTestId(`municipality-option-${code}`).waitFor({ state: 'visible' })
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: `${directory}/production-${name.toLowerCase()}.png` })
    await page.getByTestId(`municipality-option-${code}`).click()
    await page.waitForURL(new RegExp(`municipio=${code}`))
    await page.locator('.m2-results__header').filter({ hasText: name }).waitFor({ state: 'visible' })
  }
} finally {
  await browser.close()
  await client.dispose()
}
const evidence = { commit: expected, results, browser: 'Adeje and Arafo prefix suggestions and selection passed' }
await writeFile(`${directory}/production-smoke.json`, JSON.stringify(evidence, null, 2))
console.log(JSON.stringify(evidence))
