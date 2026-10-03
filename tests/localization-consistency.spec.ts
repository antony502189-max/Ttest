import { readFileSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'
import ts from 'typescript'
import { translateText, translationParityErrors } from '../src/contexts/i18n-context'
import { localizationAuditCatalog, localizationSourceAliases } from '../src/lib/localization-audit-catalog'
import { advertisementDestinationSource, advertisementPaymentSource, advertisementStatusSource } from '../src/lib/commercial-advertisement-labels'

const criticalFiles = [
  'components/layout.tsx', 'components/forms.tsx', 'components/marketplace.tsx',
  'components/user-report-dialog.tsx', 'components/commercial-advertisement-placement.tsx',
  'components/map/results-map.tsx', 'components/map/zone-selection-map.tsx',
  'components/map/selected-listing-sheet.tsx', 'pages/AccountPages.tsx',
  'pages/ListingCreatePage.tsx', 'pages/ListingEditPage.tsx', 'pages/ListingPage.tsx',
  'pages/SearchPage.tsx', 'pages/AuthPages.tsx', 'pages/CommercialAdvertisementPages.tsx',
  'pages/MobilePages.tsx', 'pages/InfoPages.tsx', 'pages/AdminPage.tsx',
  'pages/HomePage.tsx', 'pages/FavoritesPage.tsx', 'pages/ProfilePage.tsx',
  'pages/UnifiedAuthPage.tsx', 'pages/NotificationsPage.tsx',
  'components/mobile-app-v2.tsx', 'components/mobile-search-results-v2.tsx',
  'components/mobile-publication-gate.tsx', 'components/admin-commercial-advertisements.tsx',
]
const sharedNames = new Set(['Email', 'WhatsApp', 'Telegram', 'Wi-Fi', 'TOP', 'Tenerife', 'Tenerife · 112233.es', 'España (Tenerife)', '112233.es', 'www.112233.es', '.es', 'G', 'ES', 'WC', 'MB', 'ID', '© 2026 112233.es', 'nuevo-admin@gmail.com'])

test('critical JSX copy has translations and the complete catalog has locale parity', () => {
  const missing: string[] = []
  for (const file of criticalFiles) {
    const tree = ts.createSourceFile(file, readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'), ts.ScriptTarget.Latest, true)
    function visit(node: ts.Node) {
      const attr = node.parent && ts.isJsxAttribute(node.parent) ? node.parent.name.getText(tree) : ''
      const isUiText = ts.isJsxText(node) || ['label', 'title', 'description', 'placeholder', 'aria-label', 'alt'].includes(attr)
      if (isUiText && (ts.isStringLiteral(node) || ts.isJsxText(node))) {
        const source = node.text.trim().replace(/\s+/g, ' ')
        if (/[a-zA-Záéíóúñ]/u.test(source) && !sharedNames.has(source) && translateText(source, 'ru') === source && translateText(source, 'en') === source) {
          missing.push(`${file}:${tree.getLineAndCharacterOfPosition(node.getStart(tree)).line + 1}: ${source}`)
        }
      }
      ts.forEachChild(node, visit)
    }
    visit(tree)
  }
  expect(missing).toEqual([])
  expect(translationParityErrors()).toEqual([])
  for (const [source, value] of Object.entries(localizationAuditCatalog)) {
    expect(value.ru.trim(), source).not.toBe('')
    expect(value.en.trim(), source).not.toBe('')
    expect(translateText(source, 'es')).toBe(source)
    expect(translateText(source, 'ru')).toBe(value.ru)
    expect(translateText(source, 'en')).toBe(value.en)
  }
  for (const canonical of Object.values(localizationSourceAliases)) {
    expect(translateText(canonical, 'ru'), canonical).not.toBe(canonical)
  }
})

test('API copy and canonical campaign values render in each language', () => {
  for (const language of ['es', 'ru', 'en'] as const) {
    expect(translateText('Value error, Invalid website URL', language)).toBe(translateText('Introduce un enlace web válido.', language))
    expect(translateText('Close', language)).toBe(translateText('Cerrar', language))
    expect(translateText('Loading', language)).toBe(translateText('Cargando…', language))
    expect(translateText('String should have at least 3 characters', language)).toBe(translateText('Usa al menos 3 caracteres.', language))
    for (const source of ['Pendiente de pago', 'Pendiente de revisión', 'Activa', 'Expirada', 'Rechazada', 'Cancelada', 'Pagado (prueba)', 'Sin pagar']) {
      if (language !== 'es') expect(translateText(source, language)).not.toBe(source)
    }
  }
  expect(advertisementStatusSource('pending_review')).toBe('Pendiente de revisión')
  expect(advertisementStatusSource('active', '2000-01-01')).toBe('Expirada')
  expect(advertisementPaymentSource('paid')).toBe('Pagado (prueba)')
  expect(advertisementDestinationSource('website')).toBe('Sitio web')
  expect(translateText('Disponible desde 18 ago 2026', 'ru')).toBe('Доступно с 18 авг. 2026')
  expect(translateText('Disponible desde 18 ago 2026', 'en')).toBe('Available from 18 Aug 2026')
  expect(translateText('Revisa el tipo de cama.', 'en')).toBe('Check the bed type field.')
  expect(translateText('Mínimo 1 mes(es)', 'en')).toBe('Minimum 1 month')
  expect(translateText('Mínimo 7 noche(s)', 'ru')).toBe('Минимум 7 ноч.')
})

async function startHost(page: Page, route: string) {
  await page.addInitScript(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:language:v1', 'es')
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.goto(route)
}

async function chooseLanguage(page: Page, language: 'es' | 'ru' | 'en') {
  const trigger = page.locator('.site-header .language-switcher')
  await expect(trigger).toHaveAttribute('data-state', 'closed')
  await trigger.click()
  await expect(trigger).toHaveAttribute('data-state', 'open')
  const option = page.getByRole('menuitemradio').filter({ hasText: language.toUpperCase() })
  await expect(option).toBeVisible()
  await option.click()
  await expect(page.locator('html')).toHaveAttribute('lang', language)
  await expect(trigger).toHaveAttribute('data-state', 'closed')
  await expect(page.locator('body')).not.toHaveAttribute('data-scroll-locked', '1')
}

test('campaigns, dates, navigation and footer switch without stale copy or translated advertiser content', async ({ page }) => {
  const createdAt = '2026-08-18T12:00:00Z'
  await page.route('**/api/v1/advertisements/mine', (route) => route.fulfill({ json: [{
    id: 'campaign-test', title: 'Publicidad', description: 'Texto del anunciante', imageUrl: '/api/v1/media/ad-test',
    status: 'pending_review', paymentStatus: 'paid', createdAt, startsAt: null, endsAt: null, moderationNote: null,
  }] }))
  await startHost(page, '/#/mis-campanas')
  for (const language of ['ru', 'en', 'es', 'en', 'ru', 'es'] as const) {
    await chooseLanguage(page, language)
    await expect(page.locator('.ad-flow h1')).toHaveText(translateText('Mis campañas', language))
    await expect(page.locator('.ad-flow__row')).toContainText(translateText('Pendiente de revisión', language))
    await expect(page.locator('.ad-flow__row')).toContainText(translateText('Pagado (prueba)', language))
    await expect(page.locator('.ad-flow__row small')).toHaveText(new Date(createdAt).toLocaleDateString({ ru: 'ru-RU', en: 'en-GB', es: 'es-ES' }[language]))
    await expect(page.locator('.ad-flow__row h2')).toHaveText('Publicidad')
    await expect(page.locator('.site-footer')).toContainText(translateText('Sobre nosotros', language))
    for (const other of ['es', 'ru', 'en'] as const) {
      if (other !== language) await expect(page.locator('.ad-flow h1')).not.toHaveText(translateText('Mis campañas', other))
    }
  }
})

test('already-visible server errors and field errors follow the selected language', async ({ page }) => {
  await page.route('**/api/v1/advertisements/uploads', (route) => route.fulfill({ status: 422, json: {
    detail: [{ loc: ['body', 'imageAssetId'], msg: 'Value error, Plain text only' }],
  } }))
  await startHost(page, '/#/publicidad/nueva')
  await page.locator('input[type=file]').setInputFiles({ name: 'image.png', mimeType: 'image/png', buffer: Buffer.from('test image') })
  await expect(page.locator('.ad-flow__error')).toHaveText('Revisa los datos del formulario.')
  for (const language of ['ru', 'en', 'es'] as const) {
    await chooseLanguage(page, language)
    await expect(page.locator('.ad-flow__error')).toHaveText(translateText('Revisa los datos del formulario.', language))
    await expect(page.locator('#ad-image-error')).toHaveText(translateText('Solo se permite texto sin formato.', language))
    await expect(page.locator('#ad-image-error')).not.toContainText('Value error,')
  }
})

test('publication labels, media helpers and validation stay localized when switching a mounted form', async ({ page }) => {
  await startHost(page, '/#/publicar')
  await page.locator('#publish-title').fill('short')
  await page.locator('#publish-title').blur()
  for (const language of ['ru', 'en', 'es'] as const) {
    await chooseLanguage(page, language)
    for (const source of ['Habitación y vivienda', 'Título y descripción', 'Vídeo del anuncio', 'Arrastra o selecciona JPEG, PNG o WebP · máximo']) {
      await expect(page.locator('body')).toContainText(translateText(source, language))
    }
    await expect(page.locator('input[aria-label]')).not.toHaveCount(0)
    await expect(page.locator('#publish-title')).toHaveValue('short')
  }
})

test('a map error keeps its meaning while its displayed language changes', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: {
      getCurrentPosition: (_success: unknown, failure: (error: { code: number; PERMISSION_DENIED: number; POSITION_UNAVAILABLE: number; TIMEOUT: number }) => void) => failure({ code: 1, PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 }),
    } })
  })
  await startHost(page, '/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await page.locator('.map-toolbar__locate').click()
  const announcement = page.locator('.map-action-announcement')
  await expect(announcement).toHaveText('No has permitido acceder a tu ubicación.')
  for (const language of ['ru', 'en', 'es'] as const) {
    await chooseLanguage(page, language)
    await expect(announcement).toHaveText(translateText('No has permitido acceder a tu ubicación.', language))
  }
})

test('mobile language settings update the existing menu and navigation through every locale', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await startHost(page, '/#/menu')
  const languageLabels = { es: 'Idioma', ru: 'Язык', en: 'Language' }
  const continueLabels = { es: 'Continuar', ru: 'Продолжить', en: 'Continue' }
  let current: 'es' | 'ru' | 'en' = 'es'
  for (const language of ['ru', 'en', 'es'] as const) {
    await page.locator('.m2-menu-row').filter({ has: page.locator('span', { hasText: languageLabels[current] }) }).click()
    await page.locator('.m2-language-list button').filter({ has: page.locator(`[lang="${language}"]`) }).click()
    await expect(page.locator('html')).toHaveAttribute('lang', language)
    await page.getByRole('button', { name: continueLabels[language], exact: true }).click()
    await expect(page.locator('.m2-menu header')).toHaveText({ es: 'Menú', ru: 'Меню', en: 'Menu' }[language])
    await expect(page.locator('.m2-menu-row').filter({ hasText: languageLabels[language] })).toBeVisible()
    await expect(page.locator('.m2-bottom-nav button span')).toHaveText({
      es: ['Inicio', 'Búsquedas', 'Favoritos', 'Menú'],
      ru: ['Главная', 'Поиски', 'Избранное', 'Меню'],
      en: ['Home', 'Searches', 'Favorites', 'Menu'],
    }[language])
    await expect.poll(() => page.evaluate(() => localStorage.getItem('112233:language:v1'))).toBe(language)
    current = language
  }
})
