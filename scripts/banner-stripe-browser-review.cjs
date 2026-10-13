/* Real Stripe hosted Checkout with the documented 4242 test card only. */
const fs = require('node:fs')
const { chromium } = require('@playwright/test')

async function main() {
  const checkouts = JSON.parse(fs.readFileSync('.stripe-tools/banner-review-checkouts.json', 'utf8'))
  if (!checkouts.every(item => item.sessionId.startsWith('cs_test_'))) throw Error('Test sessions required')
  const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true })
  const results = []
  try {
    for (let index = 0; index < checkouts.length; index++) {
      const page = await browser.newPage({ locale: 'en-US' })
      // Confirmation is verified independently through authenticated Stripe GET.
      await page.route('http://localhost:5173/**', route => route.fulfill({ contentType: 'text/html', body: '<p>Sandbox payment return</p>' }))
      try {
        await page.goto(checkouts[index].url, { waitUntil: 'domcontentloaded', timeout: 60000 })
        const email = page.locator('#email')
        await email.fill('banner-sandbox-review@example.org', { timeout: 30000 })
        const cardChoice = page.getByRole('button', { name: 'Pay with card', exact: true })
        if (await cardChoice.isVisible()) await cardChoice.click()
        async function fill(selectors, value, required = true) {
          const deadline = Date.now() + (required ? 20000 : 1500)
          while (Date.now() < deadline) {
            for (const frame of page.frames()) {
              const input = frame.locator(selectors).first()
              if (await input.isVisible().catch(() => false)) { await input.fill(value); return true }
            }
            await page.waitForTimeout(250)
          }
          if (required) throw Error('Required Checkout field unavailable: ' + selectors)
          return false
        }
        await fill('#cardNumber, input[name="cardnumber"], input[name="cardNumber"]', '4242424242424242')
        await fill('#cardExpiry, input[name="exp-date"], input[name="cardExpiry"]', '12/29')
        await fill('#cardCvc, input[name="cvc"], input[name="cardCvc"]', '123')
        await fill('#billingName, input[name="billingName"]', 'Banner sandbox review')
        await fill('#billingPostalCode, input[name="billingPostalCode"], input[name="postal"]', '38001', false)
        const pay = page.locator('button[type="submit"]').filter({ hasText: /Pay|Pagar/ }).last()
        await pay.click({ timeout: 15000 })
        await page.waitForURL(url => url.hostname === 'localhost', { timeout: 45000 })
        results.push({ index: index + 1, returned: true })
        console.log(JSON.stringify({ banner: index + 1, hostedCheckoutReturned: true }))
      } catch (error) {
        await page.screenshot({ path: '.stripe-tools/banner-review-checkout-failure.png', fullPage: true }).catch(() => {})
        const fields = await page.locator('input').evaluateAll(inputs => inputs.map(input => ({ id: input.id, name: input.name, type: input.type }))).catch(() => [])
        results.push({ index: index + 1, returned: false, reason: error.message, fields })
        console.log(JSON.stringify(results.at(-1)))
        break
      } finally { await page.close() }
    }
  } finally { await browser.close() }
  fs.writeFileSync('.stripe-tools/banner-review-browser-results.json', JSON.stringify(results, null, 2))
  if (results.filter(item => item.returned).length !== 7) process.exitCode = 1
}
main().catch(error => { console.error(error.message); process.exitCode = 1 })
