import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'

const args = Object.fromEntries(process.argv.slice(2).map((arg) => {
  const [key, ...value] = arg.replace(/^--/, '').split('=')
  return [key, value.join('=')]
}))
if (!args.baseline || !args.candidate || !args.output) {
  throw Error('usage: --baseline=http://127.0.0.1:4174 --candidate=http://127.0.0.1:4175 --output=output/phase2-visual')
}

const scenarios = [
  { name: 'mobile-home', route: '/#/', selector: '.m2-home', width: 390, height: 844 },
  { name: 'mobile-search', route: '/#/buscar?q=Tenerife', selector: '[data-testid="mobile-results"]', width: 390, height: 844 },
  { name: 'mobile-menu', route: '/#/menu', selector: '.m2-menu', width: 390, height: 844 },
  { name: 'mobile-publication-gate', route: '/#/?gate=publicar', selector: '[data-testid="publication-gate"]', width: 390, height: 844 },
  { name: 'desktop-search', route: '/#/buscar?q=Tenerife', selector: '#main-content', width: 1440, height: 900 },
  { name: 'desktop-publication', route: '/#/publicar', selector: '.listing-create-page', width: 1024, height: 900, owner: true },
]

const fixture = '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900"><rect width="1200" height="900" fill="#8a8a8a"/></svg>'
const browser = await chromium.launch({ headless: true })
try {
  for (const scenario of scenarios) {
    for (const variant of ['baseline', 'candidate']) {
      const context = await browser.newContext({
        viewport: { width: scenario.width, height: scenario.height },
        deviceScaleFactor: 1, locale: 'es-ES', timezoneId: 'Europe/Madrid',
        reducedMotion: 'reduce', colorScheme: 'light',
      })
      try {
        await context.addInitScript(({ owner }) => {
          localStorage.setItem('112233:mobile-onboarding:v1', 'done')
          localStorage.setItem('112233:language:v1', 'es')
          if (owner) localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
        }, { owner: Boolean(scenario.owner) })
        await context.route('https://images.unsplash.com/**', (route) => route.fulfill({
          status: 200, contentType: 'image/svg+xml', body: fixture,
        }))
        const page = await context.newPage()
        await page.goto(`${args[variant]}${scenario.route}`, { waitUntil: 'domcontentloaded', timeout: 60000 })
        await page.locator(scenario.selector).first().waitFor({ state: 'visible', timeout: 30000 })
        await page.evaluate(() => document.fonts.ready)
        // Wait for stable React state after the first visible render.
        await page.waitForTimeout(800)
        const outDir = path.resolve(args.output, variant)
        await mkdir(outDir, { recursive: true })
        await page.screenshot({
          path: path.join(outDir, `${scenario.name}.png`),
          animations: 'disabled', caret: 'hide', fullPage: false,
        })
        console.log(`${variant} ${scenario.name} captured`)
      } finally {
        await context.close()
      }
    }
  }
} finally {
  await browser.close()
}
