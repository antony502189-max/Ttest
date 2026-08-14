import { expect, test, type Page } from '@playwright/test'

const goto = async (page: Page, path: string) => {
  await page.goto(`/#${path}`)
}

const mockGeolocation = async (page: Page) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: {
        getCurrentPosition(success: PositionCallback) {
          success({
            coords: {
              latitude: 28.2916,
              longitude: -16.6291,
              accuracy: 12,
              altitude: null,
              altitudeAccuracy: null,
              heading: null,
              speed: null,
              toJSON: () => ({}),
            },
            timestamp: Date.now(),
            toJSON: () => ({}),
          } as GeolocationPosition)
        },
        watchPosition() { return 1 },
        clearWatch() {},
      },
    })
  })
}

const longListings = () => JSON.stringify([
  {
    id: 'legacy-one',
    title: 'Legacy room',
    city: 'Adeje',
    area: 'Armeñime',
    approximateAddress: 'Centro',
    price: 500,
    cadence: 'mes',
    monthlyPrice: 500,
    rentalMode: 'long',
    roomType: 'Habitación individual',
    available: 'Ahora',
    availableFrom: '2026-07-01',
    minimumStay: '1 mes',
    minimumStayMonths: 1,
    deposit: 'Sin fianza',
    depositAmount: 0,
    bills: 'Incluidos',
    billsIncluded: true,
    bathroom: 'Baño compartido',
    kitchen: 'Cocina compartida',
    furnished: true,
    size: 14,
    occupants: 2,
    genderPreference: 'Solo mujer',
    couplesAllowed: false,
    restrictions: ['Solo mujer', 'Sin mascotas'],
    amenities: ['Fibra'],
    description: 'Descripción antigua',
    homeDescription: 'Casa compartida',
    images: ['https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1200&q=82'],
    owner: { name: 'Legacy', initials: 'LG', since: '2022', response: 'Hoy', verified: true },
    advertiserType: 'Particular',
    status: 'Publicado',
    publishedAt: '2026-07-01T00:00:00Z',
    views: 1,
    expiresAt: '2027-01-01',
    coordinates: { lat: 28.12, lng: -16.72 },
    showPhone: false,
    showWhatsApp: false,
    allowContactForm: true,
  },
])

test('legacy localStorage listing migrates to canonical tenant requirement', async ({ page }) => {
  await page.addInitScript((payload) => localStorage.setItem('112233:listings', payload), longListings())
  await goto(page, '/habitacion/legacy-one')
  await expect(page.getByText('Solo mujer').first()).toBeVisible()
  const migrated = await page.evaluate(() => JSON.parse(localStorage.getItem('112233:listings') || '[]')[0])
  expect(migrated.tenantRequirement).toBe('single-woman')
  expect(migrated.roomCapacity).toBe(1)
  expect(migrated.shower).toBe('Ducha compartida')
  expect(migrated.smokingAllowed).toBeNull()
  expect(migrated.petsAllowed).toBe(false)
  expect(migrated.childrenAllowed).toBeNull()
  expect(migrated.empadronamientoAllowed).toBeNull()
})

test('holiday wizard values persist and filter against the same meaning', async ({ page }) => {
  await mockGeolocation(page)
  await goto(page, '/publicar')
  await page.getByText('Alquiler vacacional', { exact: true }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByLabel('Superficie de la habitación (m²)').fill('18')
  await page.getByLabel('Personas que ya viven en la vivienda').fill('2')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByLabel('Precio por noche (€)').fill('70')
  await page.getByLabel('Precio por semana (€)').fill('420')
  await page.getByLabel('Precio por mes (€)').fill('1500')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByLabel('Disponible desde').fill('2026-09-01')
  await page.getByLabel('Disponible hasta').fill('2026-09-30')
  await page.getByLabel('Estancia mínima (noches)').fill('4')
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByLabel('Condición principal para la persona inquilina').selectOption('couple')
  await page.getByLabel('Se puede fumar').check()
  await page.getByLabel('Mascotas permitidas').check()
  await page.getByLabel('Empadronamiento posible').check()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Continuar' }).click()
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()

  const published = await page.evaluate(() => JSON.parse(localStorage.getItem('112233:listings') || '[]')[0])
  expect(published.rentalMode).toBe('holiday')
  expect(published.nightlyPrice).toBe(70)
  expect(published.weeklyPrice).toBe(420)
  expect(published.monthlyPrice).toBe(1500)
  expect(published.minimumNights).toBe(4)
  expect(published.availableUntil).toBe('2026-09-30')
  expect(published.tenantRequirement).toBe('couple')
  expect(published.roomCapacity).toBe(2)
  expect(published.shower).toBe('Ducha compartida')
  expect(published.smokingAllowed).toBe(true)
  expect(published.petsAllowed).toBe(true)
  expect(published.empadronamientoAllowed).toBe(true)
  expect(published).toHaveProperty('couplesAllowed', true)

  await goto(page, '/buscar')
  await page.getByRole('button', { name: /Filtros/i }).click()
  const drawer = page.locator('[data-slot="sheet-content"]')
  await drawer.getByLabel('Requisito para la persona inquilina').selectOption('couple')
  await drawer.getByLabel('Ducha').selectOption('Ducha compartida')
  await drawer.getByLabel('Residentes actuales').selectOption('2')
  await drawer.getByLabel('Estancia mínima: hasta (noches)').fill('4')
  await drawer.getByLabel('Disponible hasta al menos').fill('2026-09-30')
  await drawer.getByLabel('Se puede fumar').selectOption('Sí')
  await drawer.getByLabel('Mascotas').selectOption('Sí')
  await drawer.getByLabel('Empadronamiento').selectOption('Sí')
  await drawer.getByRole('button', { name: /Mostrar \d+ habitaciones/ }).click()

  const params = await page.evaluate(() => Object.fromEntries(new URLSearchParams(location.hash.split('?')[1] || '').entries()))
  expect(params.requisito).toBe('couple')
  expect(params.ducha).toBe('Ducha compartida')
  expect(params.residentes).toBe('2')
  expect(params.nochesMin).toBe('4')
  expect(params.hasta).toBe('2026-09-30')
  expect(params.fumar).toBe('Sí')
  expect(params.mascotas).toBe('Sí')
  expect(params.padron).toBe('Sí')

  await page.reload()
  await expect(page.getByRole('button', { name: /Filtros/i })).toBeVisible()
  expect((await page.evaluate(() => Object.fromEntries(new URLSearchParams(location.hash.split('?')[1] || '').entries()))).requisito).toBe('couple')
})

test('filter chips use explicit semantic labels and reset survives reload/history', async ({ page }) => {
  await goto(page, '/buscar?requisito=single-man&ducha=Ducha%20privada&residentes=5%2B&nochesMin=6&fumar=No&mascotas=Sí&ninos=No&padron=Sí&publicado=7d&anunciante=Particular')
  const chipLabels = await page.locator('.m2-results-toolbar__chips button').allTextContents()
  expect(chipLabels.some((label) => label.includes('Solo un hombre'))).toBeTruthy()
  expect(chipLabels.some((label) => label.includes('Ducha privada'))).toBeTruthy()
  expect(chipLabels.some((label) => label.includes('5+'))).toBeTruthy()
  expect(chipLabels.some((label) => label.includes('6 noches'))).toBeTruthy()

  await page.getByRole('button', { name: 'Limpiar todos los filtros' }).click()
  expect(await page.evaluate(() => location.hash)).toBe('#/buscar')
  await page.reload()
  expect(await page.evaluate(() => location.hash)).toBe('#/buscar')

  await page.goBack()
  await expect(page).toHaveURL(/#\/buscar\?requisito=single-man/)
  await page.goForward()
  await expect(page).toHaveURL(/#\/buscar$/)
})

test('legacy search params migrate once to canonical URL values', async ({ page }) => {
  await goto(page, '/buscar?genero=Solo%20mujer&parejas=Sí&ocupantes=5%20o%20más')
  await expect(page).toHaveURL(/requisito=single-woman/)
  await expect(page).toHaveURL(/residentes=5%2B/)
  await expect(page).not.toHaveURL(/genero=/)
  await expect(page).not.toHaveURL(/parejas=/)
  await expect(page).not.toHaveURL(/ocupantes=/)
})

test('registered user cannot enter or publish through pending host role', async ({ page }) => {
  await goto(page, '/registro')
  await page.getByLabel('Nombre completo').fill('Nuevo Usuario')
  await page.getByLabel('Email').fill('nuevo@example.es')
  await page.getByLabel('Contraseña').fill('password123')
  await page.getByLabel('Acepto los').check()
  await page.getByRole('button', { name: 'Crear cuenta' }).click()
  await expect(page.getByText('¿Qué quieres hacer primero?')).toBeVisible()
  await page.getByText('Buscar habitación').click()
  await expect(page).toHaveURL(/#\/buscar$/)

  await goto(page, '/menu')
  await expect(page.getByText('Publicar anuncio')).toBeVisible()
  await page.getByText('Publicar anuncio').click()
  await expect(page).toHaveURL(/#\/publicar$/)
  await expect(page.getByText('¿Qué tipo de estancia ofreces?')).toBeVisible()
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('112233:user') || '{}').role)).toBe('host')
})

test('mobile slide-out menu hides direct contact settings and still supports account deletion', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await goto(page, '/acceso')
  await page.getByLabel('Email').fill('maria@demo.es')
  await page.getByLabel('Contraseña').fill('demo123')
  await page.getByRole('button', { name: 'Acceder', exact: true }).click()
  await expect(page).toHaveURL(/#\/$/)

  await page.getByRole('button', { name: 'Abrir menú' }).click()
  await expect(page.getByRole('dialog', { name: 'Menú de cuenta' })).toBeVisible()
  await page.getByRole('dialog', { name: 'Menú de cuenta' }).getByRole('button', { name: 'Contacto y mensajes' }).click()
  await expect(page.getByText('Usamos la configuración guardada en tu perfil para mostrar los canales permitidos en tus anuncios.')).toBeVisible()
  await expect(page.getByText('Mostrar mi teléfono')).toHaveCount(0)
  await expect(page.getByText('Permitir WhatsApp')).toHaveCount(0)
  await expect(page.getByText('Permitir mensajes internos')).toHaveCount(0)
  await page.getByRole('button', { name: 'Atrás' }).click()
  await page.getByRole('button', { name: 'Cuenta y privacidad' }).click()
  await expect(page.getByRole('button', { name: 'Eliminar cuenta' })).toBeVisible()
  await page.getByRole('button', { name: 'Eliminar cuenta' }).click()
  await expect(page.getByRole('heading', { name: 'Eliminar cuenta' })).toBeVisible()
  await page.getByLabel('Escribe ELIMINAR para confirmar').fill('ELIMINAR')
  await page.getByRole('button', { name: 'Eliminar definitivamente' }).click()
  await expect(page).toHaveURL(/#\/$/)
  expect(await page.evaluate(() => localStorage.getItem('112233:user'))).toBeNull()
})

test('mobile map renders and requests structured API-like data without DOM scraping', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await goto(page, '/buscar')
  await expect(page.locator('.m2-map')).toBeVisible()
  await expect(page.locator('.m2-map .m2-map__map')).toBeVisible()
  const markers = page.locator('.m2-map-marker')
  await expect(markers.first()).toBeVisible()
  const markerCount = await markers.count()
  expect(markerCount).toBeGreaterThan(1)
})
