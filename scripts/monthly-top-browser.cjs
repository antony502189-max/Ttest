/* Verify the current local site with a real test-mode €30 TOP payment. */
const fs = require('node:fs')
const { chromium } = require('@playwright/test')

async function main() {
  const evidence = JSON.parse(fs.readFileSync('.stripe-tools/monthly-top-evidence.json', 'utf8'))
  if (!evidence.top.sessionId.startsWith('cs_test_')) throw Error('Test session required')
  fs.mkdirSync('output/monthly-top', { recursive: true })
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
  try {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'es-ES' })
    await context.addInitScript(() => { localStorage.setItem('112233:mobile-onboarding:v1', 'done'); localStorage.setItem('112233:has-session', '1') })
    const login = await context.request.post('http://localhost:18000/api/v1/auth/login', { data: { email: evidence.email, password: evidence.password } })
    if (!login.ok()) throw Error('Test login failed')
    const page = await context.newPage()
    await page.goto('http://localhost:5173/#/mis-anuncios', { waitUntil: 'domcontentloaded' })
    await page.getByTestId('owner-top-promote-button').first().click()
    await page.getByText('30 € · 1 mes en TOP').waitFor()
    await page.screenshot({ path: 'output/monthly-top/purchase.png' })
    await page.goto(evidence.top.url, { waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.locator('#email').fill(evidence.email, { timeout: 30000 })
    // Stripe's decorative expanded-area button overlays the visible card row.
    const card = page.getByText('Tarjeta', { exact: true })
    await card.waitFor()
    await card.click({ force: true })
    async function fill(selectors, value, required = true) {
      const until = Date.now() + (required ? 20000 : 1500)
      while (Date.now() < until) {
        for (const frame of page.frames()) {
          const field = frame.locator(selectors).first()
          if (await field.isVisible().catch(() => false)) { await field.fill(value); return }
        }
        await page.waitForTimeout(250)
      }
      if (required) throw Error('Missing test Checkout field: ' + selectors)
    }
    await fill('#cardNumber, input[name="cardnumber"], input[name="cardNumber"]', '4242424242424242')
    await fill('#cardExpiry, input[name="exp-date"], input[name="cardExpiry"]', '12/29')
    await fill('#cardCvc, input[name="cvc"], input[name="cardCvc"]', '123')
    await fill('#billingName, input[name="billingName"]', 'Monthly TOP sandbox review')
    await fill('#billingPostalCode, input[name="billingPostalCode"], input[name="postal"]', '38001', false)
    await page.locator('button[type=submit]').filter({ hasText: /Pay|Pagar/ }).last().click()
    await page.waitForURL(url => url.hostname === 'localhost', { timeout: 60000 })
    await page.getByText('Pago confirmado · tu anuncio está en TOP').waitFor({ timeout: 60000 })
    await page.getByTestId('owner-top-status').filter({ hasText: 'Estás en TOP' }).waitFor()
    await page.screenshot({ path: 'output/monthly-top/paid.png', fullPage: true })
    const search = await context.request.post('http://localhost:18000/api/v1/listings/search', { data: { rentalMode: 'long', sort: 'newest' } })
    const data = await search.json()
    if (data.items[0].id !== evidence.listingId || !data.items[0].promoted) throw Error('Paid listing not first')
    console.log(JSON.stringify({ hostedTestPaymentReturned: true, confirmedInSite: true, listingFirstInSearch: true }))
  } catch (error) {
    for (const context of browser.contexts()) for (const page of context.pages()) await page.screenshot({ path: 'output/monthly-top/failure.png' }).catch(() => {})
    throw error
  } finally { await browser.close() }
}
main().catch(error => { console.error(error.message); process.exitCode = 1 })
