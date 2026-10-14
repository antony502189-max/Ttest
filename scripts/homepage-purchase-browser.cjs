/* Local site screenshots and two real test-mode Stripe payments. */
const fs = require('node:fs')
const { chromium } = require('@playwright/test')

async function main() {
  const evidence = JSON.parse(fs.readFileSync('.stripe-tools/homepage-purchase-evidence.json', 'utf8'))
  if (!evidence.sessions.every(item => item.sessionId.startsWith('cs_test_'))) throw Error('Test sessions required')
  fs.mkdirSync('output/homepage-purchase', { recursive: true })
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
  try {
    const context = await browser.newContext({ viewport: { width: 1366, height: 1000 }, locale: 'es-ES' })
    await context.addInitScript(() => { localStorage.setItem('112233:mobile-onboarding:v1', 'done'); localStorage.setItem('112233:has-session', '1') })
    const login = await context.request.post('http://localhost:18000/api/v1/auth/login', { data: { email: evidence.email, password: evidence.password } })
    if (!login.ok()) throw Error('Test login failed')
    const page = await context.newPage()
    page.on('pageerror', error => console.log('Site error: ' + error.message))
    page.on('response', async response => { if (response.url().includes('/listings/homepage-hero')) console.log('Homepage API status: ' + response.status()) })
    if (!process.argv.includes('--capture')) {
    await page.goto(`http://localhost:5173/#/publicidad/${evidence.adId}/checkout`)
    const duration = page.locator('input[type=number]')
    await duration.waitFor()
    await duration.fill('21')
    await page.getByText(/21 días.*21/).waitFor()
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: 'output/homepage-purchase/banner-duration.png' })
    for (const item of evidence.sessions) {
      await page.goto(item.url, { waitUntil: 'domcontentloaded', timeout: 60000 })
      await page.locator('#email').fill(evidence.email, { timeout: 30000 })
      const choice = page.getByRole('button', { name: 'Pay with card', exact: true })
      if (await choice.isVisible()) await choice.click()
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
      await fill('#billingName, input[name="billingName"]', 'Homepage sandbox review')
      await fill('#billingPostalCode, input[name="billingPostalCode"], input[name="postal"]', '38001', false)
      await page.locator('button[type=submit]').filter({ hasText: /Pay|Pagar/ }).last().click()
      await page.waitForURL(url => url.hostname === 'localhost', { timeout: 60000 })
      console.log(JSON.stringify({ kind: item.kind, testCheckoutReturned: true }))
    }
    }
    const authHeaders = { Authorization: 'Bearer ' + (await login.json()).accessToken }
    const until = Date.now() + 20000
    while (Date.now() < until) {
      const response = await context.request.get(`http://localhost:18000/api/v1/payments/listings/${evidence.listingId}/homepage/status`, { headers: authHeaders })
      const status = await response.json()
      if (status.fulfillmentStatus === 'fulfilled') break
      await page.waitForTimeout(1000)
    }
    await page.goto('http://localhost:5173/#/')
    await page.locator('.home-hero-promotion__hit').waitFor()
    await page.locator('.home-hero-promotion__hit').click()
    await page.locator('.home-hero-promotion__card').waitFor()
    await page.waitForFunction(() => { const img = document.querySelector('.home-hero img'); return img && img.complete && img.naturalWidth > 0 })
    await page.evaluate(() => document.fonts.ready)
    await page.screenshot({ path: 'output/homepage-purchase/homepage-paid.png' })
    const link = page.locator('.home-hero-promotion__card a')
    if (await link.getAttribute('href') !== `#/habitacion/${evidence.listingId}`) throw Error('Homepage link mismatch')
    await link.click()
    await page.waitForURL(new RegExp(evidence.listingId))
    console.log(JSON.stringify({ homepagePaidScreenshot: true, directLinkVerified: true, bannerDurationScreenshot: true }))
  } catch (error) {
    for (const context of browser.contexts()) for (const page of context.pages()) await page.screenshot({ path: 'output/homepage-purchase/failure.png' }).catch(() => {})
    throw error
  } finally { await browser.close() }
}
main().catch(error => { console.error(error.message); process.exitCode = 1 })
