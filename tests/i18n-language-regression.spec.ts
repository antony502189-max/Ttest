import { expect, test, type Page } from '@playwright/test'
import { translateText } from '../src/contexts/i18n-context'

async function openAsHost(page: Page, language: 'ru' | 'en', route = '/#/publicar') {
  await page.goto('/#/')
  await page.evaluate(({ language }) => {
    localStorage.clear()
    localStorage.setItem('112233:language:v1', language)
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  }, { language })
  await page.reload()
  await page.goto(route)
  await expect(page.locator('html')).toHaveAttribute('lang', language)
}

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
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.clear()
    localStorage.setItem('112233:language:v1', 'es')
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.locator('.property-card').first()).toBeVisible()
  const body = await page.locator('body').innerText()
  expect(body).toContain('1 residente ·')
  expect(body).not.toContain('1 residentes ·')
})

test('English search does not leak known Spanish room-first labels', async ({ page }) => {
  await openAsHost(page, 'en', '/#/buscar?q=Tenerife&alquiler=long')
  await page.waitForTimeout(300)
  const body = await page.locator('body').innerText()
  for (const spanish of ['Calefacción', 'Sin calefacción', 'Tipo de cama', 'Aseo / WC', 'Ducha', 'Habitación privada', 'Habitación completa', 'Adaptada para movilidad reducida', 'Gastos aparte: aprox.', 'Disponible desde', 'Publicado hace', ' residentes · ', 'Habitación para', ' condiciones', 'Particular', 'Anfitrión', 'Aparcamiento', 'Más antiguos', 'Precio más alto', 'Sin niños', 'Crea tu perfil', ' personas (pareja/amigos)', ' habitaciones en ']) {
    expect(body).not.toContain(spanish)
  }
})

test('publish requirement post-processing follows English instead of restoring Spanish', async ({ page }) => {
  await openAsHost(page, 'en')
  for (let step = 0; step < 5; step += 1) await page.getByRole('button', { name: 'Continue' }).click()
  const options = await page.locator('#publish-tenant-requirement option').allTextContents()
  expect(options).toEqual(['Man only', 'Woman only', '1 person', '2 people (couple/friends)', 'No restrictions'])
})
