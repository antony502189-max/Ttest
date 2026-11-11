import { chromium, request } from '@playwright/test'
import assert from 'node:assert/strict'

const sha = process.argv[2]
assert.match(sha ?? '', /^[0-9a-f]{40}$/)
const origin = 'https://app.112233.es'
const client = await request.newContext()
const response = await client.get(`${origin}/build-info.json?release=${sha}`)
assert.equal(response.status(), 200)
const build = await response.json()
assert.equal(build.commit, sha)
console.log(JSON.stringify({ build }))
const browser = await chromium.launch({ headless: true })
try {
  for (const width of [320, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 844 } })
    await page.addInitScript(() => {
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:language:v1', 'es')
    })
    await page.goto(`${origin}/#/?panel=ubicacion`, { waitUntil: 'domcontentloaded' })
    const input = page.getByRole('searchbox')
    await input.focus()
    const style = await input.evaluate(element => {
      const css = getComputedStyle(element)
      const form = element.closest('form')
      return { fontSize: css.fontSize, outlineStyle: css.outlineStyle,
        border: getComputedStyle(form).borderColor,
        width: form.getBoundingClientRect().width,
        overflow: document.documentElement.scrollWidth > innerWidth }
    })
    assert.equal(style.fontSize, '16px')
    assert.equal(style.outlineStyle, 'none')
    assert.equal(style.border, 'rgb(207, 210, 205)')
    assert.equal(style.overflow, false)
    await page.screenshot({ path: `artifacts/customer-frame-2026-10-23/production-${width}.png` })
    await input.fill('Adeje')
    await page.getByTestId('municipality-option-38001').waitFor()
    console.log(JSON.stringify({ width, ...style, suggestions: 'passed' }))
    await page.close()
  }
} finally {
  await browser.close()
  await client.dispose()
}
