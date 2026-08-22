import { expect, test, type Page } from '@playwright/test'
import { translateText, translationParityErrors } from '../src/contexts/i18n-context'
import { bedTypeLabel, bedTypeOptionLabel } from '../src/lib/bed-type-label'

async function openAsHost(page: Page, language: 'ru' | 'en', route = '/#/publicar') {
  await page.addInitScript(({ language }) => {
    localStorage.setItem('112233:language:v1', language)
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  }, { language })
  await page.goto(route)
  await expect(page.locator('html')).toHaveAttribute('lang', language)
}

const spanishSearchResidues = [
  'Calefacción', 'Sin calefacción', 'Tipo de cama', 'Aseo / WC', 'Ducha',
  'Habitación privada', 'Habitación completa', 'Adaptada para movilidad reducida',
  'Gastos aparte: aprox.', 'Disponible desde', 'Publicado hace', ' residentes · ',
  'Habitación para', ' condiciones', 'Particular', 'Anfitrión', 'Aparcamiento',
  'Más antiguos', 'Precio más alto', 'Sin niños', 'Crea tu perfil',
  ' personas (pareja/amigos)', ' habitaciones en ',
]

test('room-first translation dictionary covers dynamic facts', () => {
  expect(translateText('Habitación luminosa con cama, escritorio y ventana', 'ru')).toBe('Светлая комната с кроватью, столом и окном')
  expect(translateText('Encuentra una habitación según quién vivirá y sus condiciones.', 'en')).toBe('Find a room that suits who will live there and their needs.')
  expect(translateText('Resultados adaptados', 'ru')).toBe('Подходящие результаты')
  expect(translateText('Catálogo conectado al servicio de anuncios.', 'en')).toBe('Catalog connected to the listings service.')
  expect(translateText('Configurar búsqueda de habitaciones', 'ru')).toBe('Настроить поиск комнат')
  expect(translateText('Mostrar habitaciones en el mapa', 'ru')).toBe('Показать комнаты на карте')
  expect(translateText('Abrir Habitación externa', 'ru')).toBe('Открыть: Habitación externa')
  expect(translateText('Más opciones para Habitación externa', 'en')).toBe('More options for Habitación externa')
  expect(translateText('Ventana a la calle', 'en')).toBe('Street-facing window')
  expect(translateText('Abrir selección de ubicación. Tenerife', 'ru')).toBe('Открыть выбор местоположения. Tenerife')
  expect(translateText('Abrir selección de ubicación. Tenerife', 'en')).toBe('Open location selection. Tenerife')
  expect(translateText('Calefacción', 'ru')).toBe('Отопление')
  expect(translateText('Calefacción', 'en')).toBe('Heating')
  expect(translateText('Equipamiento y accesibilidad', 'ru')).toBe('Оснащение и доступность')
  expect(translateText('Equipamiento y accesibilidad', 'en')).toBe('Equipment and accessibility')
  expect(translateText('Gastos aparte: aprox. 45 €/mes', 'ru')).toBe('Коммунальные расходы отдельно: примерно 45 €/мес.')
  expect(translateText('Gastos aparte: aprox. 45 €/mes', 'en')).toBe('Utilities extra: approx. €45/month')
  expect(translateText('Se alquila la habitación completa', 'ru')).toBe('Комната сдаётся целиком')
  expect(translateText('Se alquila la habitación completa', 'en')).toBe('Whole room for rent')
  expect(translateText('Fibra', 'ru')).toBe('Wi-Fi')
  expect(translateText('Fibra', 'en')).toBe('Wi-Fi')
  expect(translateText('1 residente · 9 m²', 'ru')).toBe('Жильцов: 1 · 9 m²')
  expect(translateText('1 residente · 9 m²', 'en')).toBe('1 resident · 9 m²')
  expect(translateText('3 residentes · 18 m²', 'ru')).toBe('Жильцов: 3 · 18 m²')
  expect(translateText('3 residentes · 18 m²', 'en')).toBe('3 residents · 18 m²')
  expect(translateText('Hasta 18 August 2026, 12:00', 'ru')).toBe('До 18 August 2026, 12:00')
  expect(translateText('Hasta 18 August 2026, 12:00', 'en')).toBe('Until 18 August 2026, 12:00')
  expect(translateText('Estancia mínima de 7 noches', 'ru')).toBe('Минимальный срок: 7 ноч.')
  expect(translateText('Estancia mínima de 7 noches', 'en')).toBe('Minimum stay: 7 nights')
  expect(translateText('Mínimo 11 meses', 'en')).toBe('Minimum 11 months')
  expect(translateText('Fuente: portal externo', 'ru')).toBe('Источник: portal externo')
  expect(translateText('Revisaremos «Habitación privada». No compartiremos tu identidad con el anunciante.', 'en')).toBe('We will review “Private room”. We will not share your identity with the advertiser.')
  expect(translateText('Tu cuenta está restringida', 'en')).toBe('Your account is restricted')
  expect(translateText('Dibujar una zona sustituirá los municipios seleccionados. ¿Continuar?', 'ru')).toBe('Нарисованная область заменит выбранные муниципалитеты. Продолжить?')
  expect(translateText('Hola, me interesa la habitación de Costa Adeje. ¿Sigue disponible?', 'en')).toBe('Hello, I am interested in the room in Costa Adeje. Is it still available?')
  expect(translateText('Hola, me interesa la habitación de Costa Adeje. ¿Sigue disponible?', 'ru')).toBe('Здравствуйте! Меня интересует комната в Costa Adeje. Она ещё доступна?')
  expect(translateText('No se pudo enviar este formulario.', 'en')).toBe('This form could not be sent.')
  expect(translateText('Corrige los campos indicados.', 'ru')).toBe('Исправьте указанные поля.')
})

for (const language of ['ru', 'en'] as const) {
  test(`publish room details stay localized in ${language}`, async ({ page }) => {
    await openAsHost(page, language)
    const continueLabel = language === 'ru' ? 'Продолжить' : 'Continue'
    await page.getByRole('button', { name: continueLabel }).click()
    await page.getByRole('button', { name: continueLabel }).click()
    const expected = language === 'ru'
      ? ['Отопление', 'Оснащение и доступность', 'Тип кровати', 'Количество кроватей', 'Туалет / WC', 'Душ']
      : ['Heating', 'Equipment and accessibility', 'Bed type', 'Number of beds', 'Toilet / WC', 'Shower']
    for (const label of expected) await expect(page.getByText(label, { exact: true }).first()).toBeVisible()
    for (const spanish of ['Calefacción', 'Equipamiento y accesibilidad', 'Tipo de cama', 'Número de camas', 'Aseo / WC', 'Ducha']) {
      await expect(page.getByText(spanish, { exact: true })).toHaveCount(0)
    }
  })
}

for (const [language, expected] of [
  ['ru', {
    hero: 'Найдите комнату с учётом жильцов и нужных условий.',
    trigger: 'Открыть выбор местоположения. Tenerife',
    trust: 'Подходящие результаты',
  }],
  ['en', {
    hero: 'Find a room that suits who will live there and their needs.',
    trigger: 'Open location selection. Tenerife',
    trust: 'Tailored results',
  }],
] as const) {
  test(`home application copy stays localized in ${language}`, async ({ page }) => {
    await openAsHost(page, language, '/#/')
    await expect(page.getByText(expected.hero, { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: expected.trigger })).toBeVisible()
    await expect(page.getByText(expected.trust, { exact: true })).toBeVisible()
    const body = await page.locator('body').innerText()
    for (const spanish of ['Configura tu búsqueda', 'Resultados adaptados']) {
      expect(body).not.toContain(spanish)
    }
  })
}

test('Spanish cards use correct singular residente grammar', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:language:v1', 'es')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.locator('.property-card').first()).toBeVisible()
  const body = await page.locator('body').innerText()
  expect(body).toContain('1 residente ·')
  expect(body).not.toContain('1 residentes ·')
})

test('Russian search does not leak known Spanish room-first labels', async ({ page }) => {
  await openAsHost(page, 'ru', '/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.locator('.property-card').first()).toBeVisible()
  const body = await page.locator('body').innerText()
  expect(body).toContain('Жильцов: 1 ·')
  for (const spanish of spanishSearchResidues) expect(body).not.toContain(spanish)
})

test('English search does not leak known Spanish room-first labels', async ({ page }) => {
  await openAsHost(page, 'en', '/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.locator('.property-card').first()).toBeVisible()
  const body = await page.locator('body').innerText()
  expect(body).toContain('1 resident ·')
  for (const spanish of spanishSearchResidues) expect(body).not.toContain(spanish)
})

test('publish requirement post-processing follows English instead of restoring Spanish', async ({ page }) => {
  await openAsHost(page, 'en')
  for (let step = 0; step < 5; step += 1) await page.getByRole('button', { name: 'Continue' }).click()
  const options = await page.locator('#publish-tenant-requirement option').allTextContents()
  expect(options).toEqual(['Man only', 'Woman only', '1 person', '2 people (couple/friends)', 'No restrictions'])
})

test('English listing contact flow does not reuse Spanish dynamic copy', async ({ page }) => {
  await openAsHost(page, 'en', '/#/buscar?q=Tenerife&alquiler=long')
  const href = await page.locator('a[href*="/habitacion/"]').first().getAttribute('href')
  expect(href).toBeTruthy()
  await page.goto(href!.startsWith('#') ? `/${href}` : href!)
  await expect(page.locator('.contact-panel').first()).toBeVisible()
  const body = await page.locator('body').innerText()
  expect(body).toContain('I confirm that I meet these conditions:')
  expect(body).not.toContain('Confirmo que cumplo estas condiciones:')
  expect(body).not.toMatch(/Estancia mínima de \d+/)
})

test('English mobile results localize data-backed room labels', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openAsHost(page, 'en', '/#/buscar?q=Tenerife&alquiler=long')
  const card = page.locator('.m2-result-card').first()
  await expect(card).toBeVisible()
  const body = await card.innerText()
  expect(body).not.toContain('Habitación individual')
  expect(body).not.toContain('Habitación compartida')
  expect(body).not.toContain('Consultar con el anunciante')
  expect(body).not.toContain('Disponible desde')
})

test('Russian mobile results localize data-backed room labels', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openAsHost(page, 'ru', '/#/buscar?q=Tenerife&alquiler=long')
  const card = page.locator('.m2-result-card').first()
  await expect(card).toBeVisible()
  const body = await card.innerText()
  expect(body).not.toContain('Habitación individual')
  expect(body).not.toContain('Habitación compartida')
  expect(body).not.toContain('Consultar con el anunciante')
  expect(body).not.toContain('Disponible desde')
})

test('the canonical locale catalog has no missing locale values', () => {
  expect(translationParityErrors()).toEqual([])
})

test('bed type API values have one complete customer-facing label per locale', () => {
  expect(bedTypeLabel('es', 'single')).toBe('Cama individual')
  expect(bedTypeLabel('en', 'double')).toBe('Double bed')
  expect(bedTypeLabel('ru', 'bunk')).toBe('Двухъярусная кровать')
  expect(bedTypeOptionLabel('es', 'bunk')).toBe('2 plazas / litera')
  expect(bedTypeOptionLabel('en', 'bunk')).toBe('2 bed spaces / Bunk bed')
  expect(bedTypeOptionLabel('ru', 'bunk')).toBe('2 места / Двухъярусная кровать')
})

async function chooseLanguage(page: Page, code: 'ES' | 'EN' | 'RU') {
  await page.locator('.site-header .language-switcher').click()
  await page.getByRole('menuitemradio').filter({ hasText: code }).click()
}

test('desktop language switching replaces application UI without translating listing content', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('112233:language:v1', 'es')
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const title = page.locator('.property-card h3').first()
  await expect(title).toBeVisible()
  const userCreatedTitle = await title.innerText()

  await chooseLanguage(page, 'RU')
  await expect(page.locator('html')).toHaveAttribute('lang', 'ru')
  await expect(page.getByText('Поиск', { exact: true }).first()).toBeVisible()
  await expect(page.locator('body')).not.toContainText('Buscar habitaciones')
  await expect(title).toHaveText(userCreatedTitle)

  await chooseLanguage(page, 'EN')
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect(page.getByText('Search', { exact: true }).first()).toBeVisible()
  await expect(page.locator('body')).not.toContainText('Поиск')

  await chooseLanguage(page, 'ES')
  await expect(page.locator('html')).toHaveAttribute('lang', 'es')
  await expect(page.getByText('Buscar', { exact: true }).first()).toBeVisible()
  await expect(page.locator('body')).not.toContainText('Search')
  await expect.poll(() => page.evaluate(() => localStorage.getItem('112233:language:v1'))).toBe('es')
})

test('mobile filters isolate locale copy and preserve the persisted bunk value', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.addInitScript(() => {
    localStorage.setItem('112233:language:v1', 'ru')
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await page.getByRole('button', { name: 'Фильтры' }).click()
  const bedType = page.locator('select').filter({ has: page.locator('option[value="bunk"]') }).first()
  await expect(bedType.locator('option[value="bunk"]')).toHaveText('Двухъярусная кровать')
  await expect(page.locator('body')).not.toContainText('Tipo de cama')
  await expect(page.locator('body')).not.toContainText('Bed type')
  await expect(page.getByText('Окно на улицу', { exact: true })).toBeVisible()
  await expect(page.getByText('Ventana a la calle', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Количество комнат', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Размер комнаты', { exact: true })).toHaveCount(0)
})
