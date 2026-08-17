import { expect, test, type Page } from '@playwright/test'
import { translateText } from '../src/contexts/i18n-context'

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