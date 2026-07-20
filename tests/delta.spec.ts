import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const hostSession = 'host-demo'
const firstListingId = 'armeñime-luminosa-01'

async function clearLocalState(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
}

async function openAs(page: Page, userId: string, path: string) {
  await page.goto('/#/')
  await page.evaluate((id) => localStorage.setItem('112233:session:v1', JSON.stringify(id)), userId)
  await page.reload()
  await page.goto(path)
}

async function storedListings(page: Page) {
  return page.evaluate(() => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{"data":[]}') as { data: Array<Record<string, unknown>> }
    return payload.data
  })
}

async function advanceWizard(page: Page, count: number) {
  const stepper = page.locator('.stepper')
  for (let index = 0; index < count; index += 1) {
    const currentStep = Number((await stepper.getAttribute('aria-label'))?.match(/Paso (\d+)/)?.[1])
    await page.getByRole('button', { name: 'Continuar' }).click()
    await expect(stepper).toHaveAttribute('aria-label', new RegExp(`Paso ${currentStep + 1} de`))
  }
}

test.beforeEach(async ({ page }) => clearLocalState(page))

test('OWN-01..04 owner isolation and foreign edit/actions are blocked', async ({ page }) => {
  await openAs(page, hostSession, '/#/mis-anuncios')
  await expect(page.locator('.manage-card')).toHaveCount(3)
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('tenant-demo')))
  await page.reload()
  await page.goto(`/#/mis-anuncios/${encodeURIComponent(firstListingId)}/editar`)
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  await expect(page.locator('.manage-card')).toHaveCount(0)
})

test('OWN-05 new host has an empty cabinet while demo host keeps seed listings', async ({ page }) => {
  await page.goto('/#/registro')
  await page.getByLabel('Nombre').fill('Segundo Anfitrión')
  await page.getByLabel('Email').fill('segundo@example.es')
  await page.getByLabel('Contraseña', { exact: true }).fill('seguro123')
  await page.getByLabel('Repite la contraseña').fill('seguro123')
  await page.getByLabel(/Publico habitaciones/).check()
  await page.locator('.terms-check [role="checkbox"]').click()
  await page.getByRole('button', { name: 'Crear cuenta' }).click()
  await page.goto('/#/mis-anuncios')
  await expect(page.locator('.manage-card')).toHaveCount(0)
})

test('USR-01..03 favorites, saved searches and history are user scoped', async ({ page }) => {
  await openAs(page, 'tenant-demo', `/#/habitacion/${encodeURIComponent(firstListingId)}`)
  await page.getByRole('button', { name: 'Guardar', exact: true }).click()
  await page.goto('/#/buscar?q=Adeje&alquiler=long')
  await page.getByRole('button', { name: /Guardar búsqueda/ }).first().click()
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  await page.goto(`/#/habitacion/${encodeURIComponent(firstListingId)}`)
  await expect(page.getByRole('button', { name: 'Guardar', exact: true })).toHaveAttribute('aria-pressed', 'false')
  await page.goto('/#/busquedas-guardadas')
  await expect(page.getByText(/Aún no tienes alertas/)).toBeVisible()
})

test('STORE-01..02 versioned payload survives mass deletion and migrates legacy v2', async ({ page }) => {
  await page.goto('/#/buscar')
  await expect.poll(() => storedListings(page).then((items) => items.length)).toBe(32)
  await page.evaluate(() => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}') as { version: number; data: unknown[] }
    localStorage.setItem('112233:listings:v3', JSON.stringify({ ...payload, data: payload.data.slice(0, 2) }))
  })
  await page.reload()
  await expect.poll(() => storedListings(page).then((items) => items.length)).toBe(2)
  await page.evaluate(() => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}') as { data: unknown[] }
    localStorage.setItem('112233:listings:v2', JSON.stringify(payload.data))
    localStorage.removeItem('112233:listings:v3')
  })
  await page.reload()
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}').version)).toBe(3)
})

test('STORE-03..04 corrupted JSON falls back and quota errors are visible', async ({ page }) => {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:listings:v3', '{broken'))
  await page.reload()
  await expect(page.getByRole('alert').filter({ hasText: /datos locales dañados/ })).toBeVisible()
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem
    Storage.prototype.setItem = function (key, value) {
      if (key === '112233:listings:v3') throw new DOMException('quota', 'QuotaExceededError')
      return original.call(this, key, value)
    }
  })
  await openAs(page, hostSession, '/#/mis-anuncios')
  await page.getByRole('button', { name: /Más acciones/ }).first().click()
  await page.getByRole('menuitem', { name: 'Ocultar' }).click()
  await expect(page.getByRole('alert').filter({ hasText: /espacio suficiente/ })).toBeVisible()
})

test('MEDIA-01..03 IndexedDB photo refs survive draft, publish and reload', async ({ page }) => {
  await openAs(page, hostSession, '/#/publicar')
  await advanceWizard(page, 6)
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2n1cAAAAASUVORK5CYII=', 'base64')
  await page.locator('#publish-images').setInputFiles({ name: 'room.png', mimeType: 'image/png', buffer: png })
  await expect.poll(() => page.evaluate(() => {
    const draft = JSON.parse(localStorage.getItem('112233:listing-draft:v3') ?? '{}') as { data?: { images?: string[] } }
    return draft.data?.images?.some((image) => image.startsWith('idb-media:')) ?? false
  })).toBe(true)
  await page.getByRole('button', { name: 'Usar como portada' }).last().click()
  await page.reload()
  await advanceWizard(page, 6)
  await expect(page.locator('.upload-grid img')).toHaveCount(7)
  await advanceWizard(page, 3)
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect(page.getByText(/ya está visible/)).toBeVisible()
  const listings = await storedListings(page)
  const createdId = String(listings[0].id)
  expect(listings[0].images[0]).toMatch(/^idb-media:/)
  await page.reload()
  await page.goto(`/#/habitacion/${encodeURIComponent(createdId)}`)
  await expect(page.locator('.property-gallery img').first()).toHaveAttribute('src', /^blob:/)
  await page.goto(`/#/mis-anuncios/${encodeURIComponent(createdId)}/editar`)
  await advanceWizard(page, 6)
  await expect(page.locator('.upload-grid img')).toHaveCount(7)
  await advanceWizard(page, 3)
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await page.reload()
  const edited = await storedListings(page)
  expect(edited.find((item) => item.id === createdId)?.images[0]).toMatch(/^idb-media:/)
})

test('MEDIA-04 avatar upload/remove persists and profile cancel restores values', async ({ page }) => {
  await openAs(page, hostSession, '/#/perfil')
  await page.getByRole('button', { name: 'Editar perfil' }).click()
  const originalName = await page.getByLabel('Nombre').inputValue()
  await page.getByLabel('Nombre').fill('Nombre temporal muy largo para comprobar el ajuste del perfil')
  await page.getByRole('button', { name: 'Cancelar' }).click()
  await expect(page.getByLabel('Nombre')).toHaveValue(originalName)
  await page.getByRole('button', { name: 'Editar perfil' }).click()
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2n1cAAAAASUVORK5CYII=', 'base64')
  await page.locator('#profile-avatar-upload').setInputFiles({ name: 'avatar.png', mimeType: 'image/png', buffer: png })
  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await page.reload()
  await expect(page.locator('.profile-avatar img')).toBeVisible()
  await page.getByRole('button', { name: 'Editar perfil' }).click()
  await page.getByRole('button', { name: 'Eliminar foto' }).click()
  await page.getByRole('button', { name: 'Guardar cambios' }).click()
  await page.reload()
  await expect(page.locator('.profile-avatar img')).toHaveCount(0)
})

test('ROOM-01..04 and MODE-01..03 migrated room and rental models render consistently', async ({ page }) => {
  await page.goto('/#/buscar?alquiler=long')
  await expect(page.locator('.property-card').first()).toContainText('m²')
  await expect(page.locator('.property-card').first()).toContainText('/mes')
  await page.goto('/#/buscar?alquiler=holiday')
  await expect(page.locator('.property-card').first()).toContainText('/noche')
  const listings = await storedListings(page)
  expect(listings.every((item) => typeof item.roomSizeM2 === 'number' && item.currentResidents !== undefined && item.roomCapacity !== undefined && item.shower)).toBeTruthy()
})

test('CONTACT-01..06 confirmation gates channels and local form handles abuse states', async ({ page }) => {
  await page.goto(`/#/habitacion/${encodeURIComponent(firstListingId)}`)
  await expect(page.locator('.property-card').first()).not.toContainText('+34 600 112 233')
  const confirmation = page.getByText(/Confirmo que cumplo estas condiciones/).first()
  await expect(confirmation).toContainText(/solo una mujer/i)
  await expect(confirmation).toContainText(/habitación para 1 persona/i)
  await expect(page.getByRole('button', { name: /Mostrar teléfono/ })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'WhatsApp' })).toBeDisabled()
  await expect(page.locator('a[href*="wa.me"]')).toHaveCount(0)
  await confirmation.click()
  await expect(page.getByRole('link', { name: 'WhatsApp' })).toHaveAttribute('href', /34611223344/)
  await page.getByRole('button', { name: /Mostrar teléfono/ }).click()
  await expect(page.getByRole('button', { name: /\+34/ })).toBeVisible()
  await page.getByRole('button', { name: 'Enviar mensaje' }).first().click()
  const dialog = page.getByRole('dialog', { name: 'Enviar un mensaje local' })
  await dialog.getByLabel('Nombre').fill('Ana')
  await dialog.getByLabel('Email o teléfono').fill('ana@example.es')
  await dialog.getByLabel('Mensaje').fill('Me interesa esta habitación y cumplo las condiciones.')
  await dialog.getByText(/Confirmo que cumplo/).click()
  await dialog.locator('.honeypot-field input').fill('bot.example')
  await page.waitForTimeout(750)
  await dialog.getByRole('button', { name: 'Registrar mensaje' }).click()
  await expect(dialog.getByRole('alert')).toContainText(/No se pudo enviar/)
  await dialog.locator('.honeypot-field input').fill('')
  await dialog.getByRole('button', { name: 'Registrar mensaje' }).click()
  await expect(dialog.getByRole('status')).toContainText('demo local')
  await dialog.getByLabel('Mensaje').fill('Me interesa esta habitación y cumplo las condiciones.')
  await dialog.getByText(/Confirmo que cumplo/).click()
  await dialog.getByRole('button', { name: 'Registrar mensaje' }).click()
  await expect(dialog.getByRole('alert')).toContainText(/30 segundos/)
})

test('LIFE-01..04 expiration hides public listing and renew republishes it', async ({ page }) => {
  await page.goto('/#/')
  await page.evaluate((id) => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}') as { version: number; data: Array<Record<string, unknown>> }
    payload.data = payload.data.map((item) => item.id === id ? { ...item, status: 'Publicado', expiresAt: '2020-01-01' } : item)
    localStorage.setItem('112233:listings:v3', JSON.stringify(payload))
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
  }, firstListingId)
  await page.reload()
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  await expect(page.locator(`[data-listing-id="${firstListingId}"]`)).toHaveCount(0)
  await page.goto('/#/mis-anuncios')
  const card = page.locator('.manage-card').first()
  await expect(card).toContainText('Finalizado automáticamente')
  await card.getByRole('button', { name: /Más acciones/ }).click()
  await page.getByRole('menuitem', { name: 'Volver a publicar' }).click()
  await expect(card).toContainText('Publicado')
  const renewed = (await storedListings(page)).find((item) => item.id === firstListingId)
  expect(renewed?.status).toBe('Publicado')
  const expectedExpiry = await page.evaluate(() => {
    const date = new Date()
    date.setHours(0, 0, 0, 0)
    date.setDate(date.getDate() + 30)
    return date.toISOString().slice(0, 10)
  })
  expect(renewed?.expiresAt).toBe(expectedExpiry)
  await card.getByRole('button', { name: /Más acciones/ }).click()
  await page.getByRole('menuitem', { name: 'Cerrar anuncio' }).click()
  await expect(card).toContainText('Finalizado')
  const closed = (await storedListings(page)).find((item) => item.id === firstListingId)
  expect(closed?.closedReason).toBe('owner')
  await page.evaluate(() => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}') as { data: Array<Record<string, unknown>> }
    payload.data[1] = { ...payload.data[1], status: 'Oculto', expiresAt: '2020-01-01' }
    localStorage.setItem('112233:listings:v3', JSON.stringify({ version: 3, data: payload.data }))
  })
  await page.reload()
  expect((await storedListings(page))[1].status).toBe('Oculto')
})

test('WIZ-01..03 dirty state warns only after edits and save clears it', async ({ page }) => {
  await openAs(page, hostSession, '/#/publicar')
  await expect(page.locator('.dirty-state')).toHaveText('Borrador guardado')
  await page.getByRole('button', { name: 'Salir' }).click()
  await expect(page).toHaveURL(/mis-anuncios/)
  await page.goto('/#/publicar')
  await page.getByRole('radio', { name: /Alquiler vacacional/ }).click()
  await expect(page.locator('.dirty-state')).toHaveText('Cambios sin guardar')
  await page.getByRole('button', { name: 'Salir' }).click()
  await expect(page.getByRole('alertdialog')).toBeVisible()
  await page.getByRole('button', { name: 'Cancelar' }).click()
  await page.getByRole('button', { name: 'Guardar borrador' }).click()
  await expect(page.locator('.dirty-state')).toHaveText('Borrador guardado')
})

test('FILTER-01 and MAP-01..03 new filters serialize and map preview shows restrictions', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long')
  const sidebar = page.locator('.filter-sidebar')
  await sidebar.getByLabel('Tamaño mínimo (m²)').fill('10')
  await sidebar.getByLabel('Ducha').selectOption('Ducha privada')
  await sidebar.getByLabel('Capacidad de la habitación').selectOption('1')
  await expect(page).toHaveURL(/tamanoMin=10/)
  await expect(page).toHaveURL(/ducha=Ducha/)
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  await page.locator('.map-results-cards .property-card').first().getByRole('link').first().focus()
  await page.locator('.price-marker.is-selected').click()
  await expect(page.locator('.map-selected-card')).toContainText(/Solo una mujer|Habitación para/)
})

test('RESP-01..05 critical routes have no horizontal overflow at the required matrix', async ({ page }) => {
  test.setTimeout(120_000)
  const viewports = [[375, 812], [390, 844], [768, 1024], [1024, 768], [1440, 900]] as const
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
  const routes = ['/#/', '/#/buscar?q=Tenerife&alquiler=long', '/#/buscar?q=Tenerife&alquiler=long&vista=mapa', `/#/habitacion/${encodeURIComponent(firstListingId)}`, '/#/publicar']
  for (const [width, height] of viewports) {
    await page.setViewportSize({ width, height })
    for (const route of routes) {
      await page.goto(route)
      await page.locator('.route-loading').waitFor({ state: 'detached' }).catch(() => undefined)
      if (route.includes('vista=mapa')) await page.locator('.leaflet-map-canvas').waitFor({ state: 'visible' })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1), `${route} at ${width}x${height}`).toBeTruthy()
    }
    if (width <= 390) {
      await page.goto(`/#/habitacion/${encodeURIComponent(firstListingId)}`)
      const contact = await page.locator('.mobile-contact-bar').boundingBox()
      const navigation = await page.locator('.bottom-nav').boundingBox()
      expect(contact && navigation && contact.y + contact.height <= navigation.y + 1).toBeTruthy()
      await page.goto('/#/publicar')
      const actions = await page.locator('.wizard-actions').boundingBox()
      const wizardNavigation = await page.locator('.bottom-nav').boundingBox()
      expect(actions && wizardNavigation && actions.y + actions.height <= wizardNavigation.y + 1).toBeTruthy()
    }
  }
})

test('A11Y-01 contact dialog has no serious or critical axe issues', async ({ page }) => {
  await page.goto(`/#/habitacion/${encodeURIComponent(firstListingId)}`)
  await page.getByRole('button', { name: 'Enviar mensaje' }).first().click()
  const results = await new AxeBuilder({ page }).include('.contact-message-dialog').analyze()
  expect(results.violations.filter((item) => item.impact === 'serious' || item.impact === 'critical')).toEqual([])
})
