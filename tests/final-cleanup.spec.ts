import { expect, test, type Page } from '@playwright/test'

const hostSession = 'host-demo'
const firstListingId = 'armeñime-luminosa-01'
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2n1cAAAAASUVORK5CYII=', 'base64')

async function clearState(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())
  await page.reload()
}

async function openAsHost(page: Page, path: string) {
  await page.goto('/#/')
  await page.evaluate((id) => localStorage.setItem('112233:session:v1', JSON.stringify(id)), hostSession)
  await page.reload()
  await page.goto(path)
}

async function putMedia(page: Page, id: string) {
  return page.evaluate((mediaId) => new Promise<string>((resolve, reject) => {
    const open = indexedDB.open('112233-media', 1)
    open.onupgradeneeded = () => { if (!open.result.objectStoreNames.contains('media')) open.result.createObjectStore('media') }
    open.onerror = () => reject(open.error)
    open.onsuccess = () => {
      const database = open.result
      const transaction = database.transaction('media', 'readwrite')
      transaction.objectStore('media').put(new Blob(['media'], { type: 'image/png' }), mediaId)
      transaction.oncomplete = () => { database.close(); resolve(`idb-media:${mediaId}`) }
      transaction.onerror = () => { database.close(); reject(transaction.error) }
    }
  }), id)
}

async function mediaExists(page: Page, reference: string) {
  return page.evaluate((mediaReference) => new Promise<boolean>((resolve, reject) => {
    const open = indexedDB.open('112233-media', 1)
    open.onerror = () => reject(open.error)
    open.onsuccess = () => {
      const database = open.result
      const request = database.transaction('media', 'readonly').objectStore('media').get(mediaReference.slice('idb-media:'.length))
      request.onsuccess = () => { database.close(); resolve(request.result instanceof Blob) }
      request.onerror = () => { database.close(); reject(request.error) }
    }
  }), reference)
}

async function advanceWizard(page: Page, count: number) {
  for (let index = 0; index < count; index += 1) await page.getByRole('button', { name: 'Continuar' }).click()
}

test.beforeEach(async ({ page }) => clearState(page))

test('MEDIA-09 orphan cleanup removes only unreferenced blobs', async ({ page }) => {
  const used = await putMedia(page, 'used-reference')
  const orphan = await putMedia(page, 'orphan-reference')
  await page.evaluate(({ usedReference }) => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}')
    payload.data[0].images = [usedReference]
    localStorage.setItem('112233:listings:v3', JSON.stringify(payload))
  }, { usedReference: used })
  await page.reload()
  await expect.poll(() => mediaExists(page, used)).toBe(true)
  await expect.poll(() => mediaExists(page, orphan)).toBe(false)
})

test('MEDIA-10 shared listing photo survives until its final reference is deleted', async ({ page }) => {
  const shared = await putMedia(page, 'shared-listing-photo')
  await page.evaluate(({ reference }) => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}')
    payload.data[0].images = [reference]
    payload.data[1].images = [reference]
    localStorage.setItem('112233:listings:v3', JSON.stringify(payload))
  }, { reference: shared })
  await openAsHost(page, '/#/mis-anuncios')
  for (let deletion = 0; deletion < 2; deletion += 1) {
    const card = page.locator('.manage-card').first()
    await card.getByRole('button', { name: /Más acciones/ }).click()
    await page.getByRole('menuitem', { name: 'Eliminar' }).click()
    await page.getByRole('button', { name: 'Eliminar', exact: true }).click()
    await expect.poll(() => mediaExists(page, shared)).toBe(deletion === 0)
  }
})

test('MEDIA-11 replacing an edited listing photo removes the obsolete blob', async ({ page }) => {
  const obsolete = await putMedia(page, 'obsolete-edit-photo')
  await page.evaluate(({ reference }) => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}')
    payload.data[0].images = [reference, ...payload.data[0].images.slice(1)]
    localStorage.setItem('112233:listings:v3', JSON.stringify(payload))
  }, { reference: obsolete })
  await openAsHost(page, `/#/mis-anuncios/${encodeURIComponent(firstListingId)}/editar`)
  await advanceWizard(page, 6)
  await page.getByRole('button', { name: 'Eliminar foto 1' }).click()
  await page.locator('#publish-images').setInputFiles({ name: 'replacement.png', mimeType: 'image/png', buffer: png })
  const replacement = await expect.poll(() => page.evaluate(() => {
    const draft = JSON.parse(localStorage.getItem('112233:listing-draft:v3') ?? '{}')
    return draft.data.images.find((image: string) => image.startsWith('idb-media:')) ?? ''
  })).toMatch(/^idb-media:/).then(async () => page.evaluate(() => {
    const draft = JSON.parse(localStorage.getItem('112233:listing-draft:v3') ?? '{}')
    return draft.data.images.find((image: string) => image.startsWith('idb-media:')) as string
  }))
  await advanceWizard(page, 3)
  await page.getByRole('button', { name: 'Publicar anuncio' }).click()
  await expect.poll(() => mediaExists(page, obsolete)).toBe(false)
  await expect.poll(() => mediaExists(page, replacement)).toBe(true)
})

test('DRAFT-05 reset removes only draft media and preserves listing media', async ({ page }) => {
  await openAsHost(page, '/#/publicar')
  await expect.poll(() => page.evaluate(() => Boolean(JSON.parse(localStorage.getItem('112233:listing-draft:v3') ?? '{}').data))).toBe(true)
  const draftMedia = await putMedia(page, 'draft-only')
  const listingMedia = await putMedia(page, 'listing-only')
  await page.evaluate(({ draftReference, listingReference }) => {
    const draft = JSON.parse(localStorage.getItem('112233:listing-draft:v3') ?? '{}')
    draft.data.images = [draftReference, listingReference]
    localStorage.setItem('112233:listing-draft:v3', JSON.stringify(draft))
    const listings = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}')
    listings.data[0].images = [listingReference]
    localStorage.setItem('112233:listings:v3', JSON.stringify(listings))
  }, { draftReference: draftMedia, listingReference: listingMedia })
  await page.reload()
  await page.getByRole('button', { name: 'Restablecer' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Restablecer' }).click()
  await expect.poll(() => mediaExists(page, draftMedia)).toBe(false)
  await expect.poll(() => mediaExists(page, listingMedia)).toBe(true)
})

test('ACCOUNT-01 deletion clears owned local data, draft and unused media after reload', async ({ page }) => {
  const listingMedia = await putMedia(page, 'account-listing')
  const avatarMedia = await putMedia(page, 'account-avatar')
  const draftMedia = await putMedia(page, 'account-draft')
  await page.evaluate(({ listingReference, avatarReference, draftReference }) => {
    const listings = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}')
    listings.data[0].images = [listingReference]
    localStorage.setItem('112233:listings:v3', JSON.stringify(listings))
    const users = JSON.parse(localStorage.getItem('112233:users:v1') ?? '[]')
    users.find((user: { id: string }) => user.id === 'host-demo').avatarRef = avatarReference
    localStorage.setItem('112233:users:v1', JSON.stringify(users))
    localStorage.setItem('112233:listing-draft:v3', JSON.stringify({ version: 3, ownerUserId: 'host-demo', data: { images: [draftReference] } }))
    localStorage.setItem('112233:favorites:v2', JSON.stringify({ version: 2, data: { 'host-demo': ['owned'], guest: ['guest-value'] } }))
    localStorage.setItem('112233:discarded:v2', JSON.stringify({ version: 2, data: { 'host-demo': ['owned'], guest: ['guest-value'] } }))
    localStorage.setItem('112233:search-history:v2', JSON.stringify({ version: 2, data: { 'host-demo': ['Adeje'], guest: ['Arona'] } }))
    localStorage.setItem('112233:saved-searches:v3', JSON.stringify({ version: 3, data: { 'host-demo': [], guest: [] } }))
    localStorage.setItem('112233:reports:v1', JSON.stringify([{ id: 'report-owned', listingId: listings.data[0].id, reason: 'demo', comment: '', createdAt: new Date().toISOString(), status: 'Abierta' }]))
  }, { listingReference: listingMedia, avatarReference: avatarMedia, draftReference: draftMedia })
  await openAsHost(page, '/#/perfil')
  await page.getByRole('button', { name: 'Eliminar cuenta' }).click()
  const dialog = page.getByRole('alertdialog', { name: '¿Eliminar tu cuenta?' })
  await expect(dialog).toContainText('anuncios, borrador, búsquedas, favoritos, historial y archivos multimedia')
  await dialog.getByRole('button', { name: 'Eliminar definitivamente' }).click()
  await expect(page).toHaveURL(/#\/acceso/)
  await expect.poll(() => page.evaluate(() => {
    const users = JSON.parse(localStorage.getItem('112233:users:v1') ?? '[]')
    const listings = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}').data
    const favorites = JSON.parse(localStorage.getItem('112233:favorites:v2') ?? '{}').data
    return {
      userExists: users.some((user: { id: string }) => user.id === 'host-demo'),
      ownedListings: listings.filter((listing: { ownerUserId?: string }) => listing.ownerUserId === 'host-demo').length,
      session: JSON.parse(localStorage.getItem('112233:session:v1') ?? 'null'),
      draft: localStorage.getItem('112233:listing-draft:v3'),
      hostScope: favorites['host-demo'],
      guestScope: favorites.guest,
    }
  })).toEqual({ userExists: false, ownedListings: 0, session: null, draft: null, hostScope: undefined, guestScope: ['guest-value'] })
  await expect.poll(() => Promise.all([listingMedia, avatarMedia, draftMedia].map((reference) => mediaExists(page, reference)))).toEqual([false, false, false])
  await page.reload()
  await expect(page).toHaveURL(/#\/acceso/)
})

test('CONTACT-07 cooldown survives dialog close and sensitive values are cleared', async ({ page }) => {
  await page.goto(`/#/habitacion/${encodeURIComponent(firstListingId)}`)
  const open = () => page.getByRole('button', { name: 'Enviar mensaje' }).first().click()
  await open()
  let dialog = page.getByRole('dialog', { name: 'Enviar un mensaje local' })
  await dialog.getByLabel('Nombre').fill('Lucía')
  await dialog.getByLabel('Email o teléfono').fill('lucia@example.es')
  await dialog.getByLabel('Mensaje').fill('Me interesa la habitación y cumplo las condiciones.')
  await dialog.getByText(/Confirmo que cumplo/).click()
  await page.waitForTimeout(750)
  await dialog.getByRole('button', { name: 'Registrar mensaje' }).click()
  await expect(dialog.getByRole('status')).toContainText('No se ha enviado por internet')
  await page.keyboard.press('Escape')
  await open()
  dialog = page.getByRole('dialog', { name: 'Enviar un mensaje local' })
  await expect(dialog.getByLabel('Nombre')).toHaveValue('')
  await expect(dialog.getByLabel('Email o teléfono')).toHaveValue('')
  await expect(dialog.getByLabel('Mensaje')).toHaveValue('')
  await dialog.getByLabel('Nombre').fill('Lucía')
  await dialog.getByLabel('Email o teléfono').fill('lucia@example.es')
  await dialog.getByLabel('Mensaje').fill('Me interesa la habitación y cumplo las condiciones.')
  await dialog.getByText(/Confirmo que cumplo/).click()
  await page.waitForTimeout(750)
  await dialog.getByRole('button', { name: 'Registrar mensaje' }).click()
  await expect(dialog.getByRole('alert')).toContainText('30 segundos')
})

test('CONTACT-08 disabled phone and WhatsApp are absent from the DOM', async ({ page }) => {
  await page.evaluate((id) => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}')
    payload.data = payload.data.map((listing: { id: string }) => listing.id === id ? { ...listing, showPhone: false, showWhatsApp: false, contactPhone: '+34 699 999 999', contactWhatsapp: '+34 688 888 888' } : listing)
    localStorage.setItem('112233:listings:v3', JSON.stringify(payload))
  }, firstListingId)
  await page.reload()
  await page.goto(`/#/habitacion/${encodeURIComponent(firstListingId)}`)
  await expect(page.getByRole('button', { name: /Mostrar teléfono/ })).toHaveCount(0)
  await expect(page.locator('a[href^="https://wa.me/"]')).toHaveCount(0)
  await expect(page.locator('body')).not.toContainText('+34 699 999 999')
  await expect(page.locator('body')).not.toContainText('+34 688 888 888')
})

test('FILTER-07 legacy URLs migrate to one tenant requirement and distinct resident/capacity controls', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&genero=Solo%20mujer&parejas=S%C3%AD&ocupantes=5%20o%20m%C3%A1s')
  await expect(page).toHaveURL(/requisito=single-woman/)
  await expect(page).toHaveURL(/residentes=5%2B/)
  await expect(page).not.toHaveURL(/genero=|parejas=|ocupantes=/)
  const sidebar = page.locator('.filter-sidebar')
  await expect(sidebar.getByLabel('Requisito para la persona inquilina')).toHaveCount(1)
  await expect(sidebar.getByLabel('Residentes actuales')).toHaveCount(1)
  await expect(sidebar.getByLabel('Capacidad de la habitación')).toHaveCount(1)
  await expect(sidebar.getByLabel('Parejas', { exact: true })).toHaveCount(0)
  await sidebar.getByLabel('Capacidad de la habitación').selectOption('2')
  await expect(page).toHaveURL(/capacidad=2/)
})

test('LISTING-STATUS-01 user-facing status filter excludes moderation-only values', async ({ page }) => {
  await page.evaluate(() => {
    const payload = JSON.parse(localStorage.getItem('112233:listings:v3') ?? '{}')
    payload.data[0].status = 'Pendiente'
    payload.data[1].status = 'Rechazado'
    localStorage.setItem('112233:listings:v3', JSON.stringify(payload))
  })
  await openAsHost(page, '/#/mis-anuncios')
  const status = page.getByLabel('Estado')
  await expect(status.locator('option')).toHaveText(['Todos', 'Publicado', 'Oculto', 'Borrador', 'Finalizado'])
  await expect(page.locator('main')).not.toContainText('Pendiente')
  await expect(page.locator('main')).not.toContainText('Rechazado')
})

test('MAP-06 selecting a card or marker preserves viewport and map instance', async ({ page }) => {
  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  const map = page.locator('.leaflet-map-canvas')
  await expect(map).toHaveAttribute('data-map-center', /,/)
  const before = await map.evaluate((element) => ({ instance: element.getAttribute('data-map-instance'), center: element.getAttribute('data-map-center'), zoom: element.getAttribute('data-map-zoom') }))
  await page.locator('.map-results-cards .property-card').first().getByRole('link').first().focus()
  await page.locator('.price-marker.is-selected').click()
  await expect(page.locator('.map-selected-card')).toBeVisible()
  const after = await map.evaluate((element) => ({ instance: element.getAttribute('data-map-instance'), center: element.getAttribute('data-map-center'), zoom: element.getAttribute('data-map-zoom') }))
  expect(after).toEqual(before)
})

test('RESP-06 short mobile dialogs and critical map/uploader targets remain reachable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 680 })
  await page.goto(`/#/habitacion/${encodeURIComponent(firstListingId)}`)
  await page.getByRole('button', { name: 'Enviar mensaje' }).first().click()
  const dialogBox = await page.getByRole('dialog', { name: 'Enviar un mensaje local' }).boundingBox()
  expect(dialogBox && dialogBox.y >= 0 && dialogBox.y + dialogBox.height <= 680).toBeTruthy()
  await page.keyboard.press('Escape')

  await openAsHost(page, '/#/publicar')
  await advanceWizard(page, 6)
  const deletePhoto = await page.getByRole('button', { name: 'Eliminar foto 1' }).boundingBox()
  expect(deletePhoto && deletePhoto.width >= 44 && deletePhoto.height >= 44).toBeTruthy()

  await page.goto('/#/buscar?q=Tenerife&alquiler=long&vista=mapa')
  const searchArea = await page.getByRole('button', { name: 'Buscar en esta zona' }).boundingBox()
  expect(searchArea && searchArea.height >= 44).toBeTruthy()
})

test('I18N-01 Russian and English versions switch and persist without changing routes', async ({ page }) => {
  await page.goto('/#/')

  await page.getByRole('button', { name: 'Seleccionar idioma' }).first().click()
  await page.getByRole('menuitemradio', { name: 'RU Русский' }).click()
  await expect(page.locator('html')).toHaveAttribute('lang', 'ru')
  await expect(page.getByRole('heading', { level: 1, name: 'Ваша следующая комната ближе, чем кажется' })).toBeVisible()

  await page.getByRole('button', { name: 'Выбрать язык' }).first().click()
  await page.getByRole('menuitemradio', { name: 'EN English' }).click()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect(page.getByRole('heading', { level: 1, name: 'Your next room is closer than you think' })).toBeVisible()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('112233:language:v1'))).toBe('en')

  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect(page.getByRole('heading', { level: 1, name: 'Your next room is closer than you think' })).toBeVisible()
})
