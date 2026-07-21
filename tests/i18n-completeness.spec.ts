import { expect, test, type Browser, type BrowserContext, type Page } from '@playwright/test'

async function createLocalizedContext(browser: Browser, session: string | null = null, language = 'es') {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } }) as BrowserContext
  await context.addInitScript(({ sessionId, locale }) => {
    localStorage.setItem('112233:session:v1', JSON.stringify(sessionId))
    localStorage.setItem('112233:language:v1', locale)
  }, { sessionId: session, locale: language })
  return context
}

async function waitForRoute(page: Page) {
  await page.locator('.route-loading').waitFor({ state: 'detached', timeout: 10_000 }).catch(() => undefined)
}

async function expectCompleteCoverage(page: Page, label: string) {
  await waitForRoute(page)
  const missing = await page.evaluate(async () => {
    const { hasTranslation } = await import('/src/contexts/i18n-context.tsx')
    const visible = (element: Element) => {
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    }
    const values: string[] = []
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
    let node = walker.nextNode()
    while (node) {
      if (node.parentElement && visible(node.parentElement)) {
        const value = node.textContent?.trim().replace(/\s+/g, ' ')
        if (value) values.push(value)
      }
      node = walker.nextNode()
    }
    for (const element of [...document.querySelectorAll('body *')].filter(visible)) {
      for (const attribute of ['aria-label', 'placeholder', 'title', 'alt']) {
        const value = element.getAttribute(attribute)?.trim()
        if (value) values.push(value)
      }
    }
    return [...new Set(values)].filter((value) => !hasTranslation(value, 'ru') || !hasTranslation(value, 'en'))
  })
  expect(missing, `${label} should have complete RU and EN coverage`).toEqual([])
}

test('all audited guest, host, admin and publish states have complete locale coverage', async ({ browser }) => {
  test.setTimeout(180_000)

  const guestContext = await createLocalizedContext(browser)
  const guest = await guestContext.newPage()
  for (const route of [
    '/', '/buscar?q=Tenerife', '/buscar?q=Tenerife&vista=mapa', '/habitacion/arme%C3%B1ime-luminosa-01',
    '/registro', '/acceso', '/recuperar-contrasena', '/restablecer-contrasena', '/favoritos', '/mensajes', '/menu',
    '/sobre-nosotros', '/como-funciona', '/ayuda', '/contacto', '/terminos', '/privacidad', '/cookies', '/normas-de-publicacion',
  ]) {
    await guest.goto(`/#${route}`)
    await expectCompleteCoverage(guest, route)
  }

  await guest.goto('/#/')
  await guest.getByRole('button', { name: /Abrir selección de ubicación/i }).first().click()
  await expectCompleteCoverage(guest, 'location dialog')

  await guest.goto('/#/buscar?q=Tenerife')
  await guest.getByRole('button', { name: /Todos los filtros/i }).click()
  await expectCompleteCoverage(guest, 'filter dialog')
  await guest.keyboard.press('Escape')
  await guest.locator('.mobile-sort-control').click()
  await expectCompleteCoverage(guest, 'sort dialog')
  await guest.keyboard.press('Escape')

  await guest.goto('/#/habitacion/arme%C3%B1ime-luminosa-01')
  await guest.getByRole('button', { name: /Ver todas las fotos/i }).click()
  await expectCompleteCoverage(guest, 'gallery dialog')
  await guest.keyboard.press('Escape')
  await guest.getByRole('button', { name: 'Enviar mensaje' }).click()
  await expectCompleteCoverage(guest, 'contact dialog')
  await guestContext.close()

  const hostContext = await createLocalizedContext(browser, 'host-demo')
  const host = await hostContext.newPage()
  for (const route of ['/perfil', '/mis-anuncios']) {
    await host.goto(`/#${route}`)
    await expectCompleteCoverage(host, route)
  }
  await host.goto('/#/publicar')
  for (let step = 1; step <= 10; step += 1) {
    await expectCompleteCoverage(host, `publish step ${step}`)
    if (step < 10) await host.locator('.wizard-actions button').last().click()
  }
  await hostContext.close()

  const adminContext = await createLocalizedContext(browser, 'admin-demo')
  const admin = await adminContext.newPage()
  await admin.goto('/#/admin')
  await expectCompleteCoverage(admin, 'admin')
  await adminContext.close()
})

test('approximate publish map uses a bundled marker and selected locale throughout', async ({ browser }) => {
  for (const language of ['ru', 'en']) {
    const context = await createLocalizedContext(browser, 'host-demo', language)
    const page = await context.newPage()
    const failedFirstParty: string[] = []
    page.on('requestfailed', (request) => {
      if (request.url().startsWith('http://127.0.0.1:4173')) failedFirstParty.push(request.url())
    })
    await page.goto('/#/publicar')
    await page.locator('.wizard-actions button').last().click()
    await expect(page.locator('html')).toHaveAttribute('lang', language)
    await expect(page.locator('.approximate-location-marker')).toBeVisible()
    await expect(page.locator('.approximate-location-map img.leaflet-marker-icon')).toHaveCount(0)
    await expect(page.getByText('La dirección exacta no se muestra públicamente.')).toHaveCount(0)
    await expect(page.getByText('El marcador se centra en la zona. Muévelo ligeramente sin publicar la calle exacta.')).toHaveCount(0)
    expect(failedFirstParty).toEqual([])
    await context.close()
  }
})
