import { readFileSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

async function signInAsHost(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.setItem('112233:session:v1', JSON.stringify('host-demo')))
  await page.reload()
}

async function advanceWizard(page: Page, targetStep: number) {
  for (let index = 0; index < targetStep; index += 1) {
    await page.getByRole('button', { name: /continuar/i }).click()
  }
}

test('customer video fix keeps the owned-listing route behind authoritative hydration', () => {
  const app = readFileSync('src/App.tsx', 'utf8')
  const gate = readFileSync('src/components/owned-listings-hydration-gate.tsx', 'utf8')
  const critical = readFileSync('src/components/customer-video-critical-fixes.tsx', 'utf8')

  expect(app).toContain('<OwnedListingsHydrationGate><MyListingsPage /></OwnedListingsHydrationGate>')
  expect(gate).toContain("getOwnedListings(controller.signal)")
  expect(gate).toContain("type Phase = 'checking' | 'syncing' | 'ready' | 'error'")
  expect(gate).toContain("window.dispatchEvent(new Event('catalog:updated'))")
  expect(gate).toContain('PROVIDER_SYNC_TIMEOUT_MS')
  expect(gate).not.toContain('<AppContext.Provider')
  expect(gate).toContain('Tus anuncios no se han borrado')
  expect(gate).toContain('Объявления не удалены')
  expect(critical).toContain("const PENDING_EDIT_KEY = '112233:pending-edit-route:v1'")
  expect(critical).toContain("if (editId && !existingEditListing) window.dispatchEvent(new Event('catalog:updated'))")
  expect(critical).toContain("navigate(`/mis-anuncios/${encodeURIComponent(pending)}/editar`, { replace: true })")
})

test('customer video fix keeps fresh location unresolved safely and validates it at the wizard model boundary', () => {
  const source = readFileSync('src/components/customer-video-critical-fixes.tsx', 'utf8')
  const publish = readFileSync('src/pages/PublishPage.tsx', 'utf8')

  expect(source).toContain("const LEGACY_DRAFT_KEY = '112233:listing-draft:v2'")
  expect(source).toContain("const AUTO_CITY_VALUE = '__112233_auto_municipality__'")
  expect(source).toContain("draft.city === 'Adeje'")
  expect(source).toContain("draft.area === 'Armeñime'")
  expect(source).toContain("draft.postcode === '38678'")
  expect(source).toContain('const hasLegacyDraft = localStorage.getItem(LEGACY_DRAFT_KEY) !== null')
  expect(source).toContain("const domStillUntouchedLegacyDefault = city.value === 'Adeje'")
  expect(source).toContain("&& area.value === 'Armeñime'")
  expect(source).toContain("&& postcode.value === '38678'")
  expect(source).toContain('const brandNewUnpersistedDefault = raw === null')
  expect(source).toContain('&& !hasLegacyDraft')
  expect(source).toContain('&& domStillUntouchedLegacyDefault')
  expect(source).toContain('const shouldMigrateLegacyDefault = (isUntouchedLegacyLocationDefault(raw) || brandNewUnpersistedDefault)')
  expect(source).toContain("setNativeSelectValue(city, AUTO_CITY_VALUE, true)")
  expect(source).toContain("setNativeInputValue(area, '')")
  expect(source).toContain("setNativeInputValue(postcode, '')")
  expect(source).toContain("!/^\\d{5}$/.test(postcode.value.trim())")
  expect(source).toContain('selector.hidden = true')
  expect(publish).toContain('if (!publicationMunicipalities.has(draft.city)) next.city = "Selecciona un municipio válido."')
  expect(publish).toContain('error={errors.city}')
  expect(publish).toContain('aria-invalid={Boolean(errors.city)}')
  expect(publish).toContain('if (draft.postcode.trim() && !/^\\d{5}$/.test(draft.postcode.trim()))')
  expect(publish).toContain('El código postal debe tener exactamente 5 dígitos.')
  expect(publish).toContain('for (let targetStep = 0; targetStep < steps.length - 1; targetStep += 1)')
  expect(publish).toContain('if (!validate(targetStep))')
})

test('customer video fix retries transient admin authorization without weakening the server route guard', () => {
  const app = readFileSync('src/App.tsx', 'utf8')

  expect(app).toContain('<ProtectedRoute admin><AdminPage /></ProtectedRoute>')
  expect(app).toContain("error.status === 401 || error.status === 403")
  expect(app).toContain('window.setTimeout(() => { void verifyAdmin(false) }, 450)')
  expect(app).toContain("setAdminAllowed('error')")
  expect(app).toContain('Сессия остаётся активной')
})

test('listing editing scopes autosaved drafts and never leaks them into a new publication', () => {
  const source = readFileSync('src/components/customer-video-critical-fixes.tsx', 'utf8')

  expect(source).toContain("const EDIT_DRAFT_PREFIX = '112233:listing-edit-draft:v1:'")
  expect(source).toContain("if (!mockMode && pathname === '/publicar')")
  expect(source).toContain('localStorage.setItem(editDraftKey(globalDraft.listingId), JSON.stringify(globalDraft))')
  expect(source).toContain('localStorage.removeItem(DRAFT_KEY)')
  expect(source).toContain('overlayDraftOnListing(existingEditListing, scopedDraft.data)')
  expect(source).toContain('temporaryListingRestore.current = { target: existingEditListing, snapshot: cloneListing(existingEditListing) }')
  expect(source).toContain('Object.assign(target, snapshot)')
  expect(source).toContain('const draftMirror = editId ? window.setInterval(mirrorEditDraft, 250) : 0')
})

test('listing editing keeps an honest failure state when image synchronization fails', () => {
  const source = readFileSync('src/components/customer-video-critical-fixes.tsx', 'utf8')

  expect(source).toContain("const EDIT_RETRY_PREFIX = '112233:listing-edit-retry:v1:'")
  expect(source).toContain("details.method === 'PUT' && /\\/listings\\/[^/?#]+\\/images")
  expect(source).toContain('if (imageRequest && !response.ok) editImageSyncFailed.current = true')
  expect(source).toContain('if (success && editImageSyncFailed.current && !reloadingAfterImageFailure)')
  expect(source).toContain('localStorage.setItem(DRAFT_KEY, retryDraft)')
  expect(source).toContain("toast.error(copy.imageRetry, { id: 'listing-edit-image-retry' })")
  expect(source).toContain('window.setTimeout(() => window.location.reload(), 0)')
})

test('leaving a new publication does not make existing host listings disappear', async ({ page }) => {
  await signInAsHost(page)
  await page.goto('/#/mis-anuncios')

  await expect(page.locator('.manage-card').first()).toBeVisible()
  const before = await page.locator('.manage-card').count()
  expect(before).toBeGreaterThan(0)

  await page.getByRole('link', { name: /nuevo anuncio/i }).click()
  await page.getByRole('button', { name: /continuar/i }).click()
  await expect(page.locator('#publish-city')).toBeVisible()

  await page.goBack()
  await expect(page).toHaveURL(/#\/mis-anuncios$/)
  await expect(page.locator('.manage-card')).toHaveCount(before)
  await expect(page.getByText('No hay anuncios en este estado')).toHaveCount(0)
})

test('unfinished edit draft survives a create detour and edit CTA says save changes', async ({ page }) => {
  await signInAsHost(page)
  await page.goto('/#/mis-anuncios')
  const editLink = page.locator('.manage-card').first().getByRole('link', { name: /editar/i })
  const href = await editLink.getAttribute('href')
  expect(href).toMatch(/\/mis-anuncios\/.+\/editar$/)
  await editLink.click()
  await expect(page.getByRole('heading', { name: /editar habitación/i })).toBeVisible()

  await advanceWizard(page, 7)
  const uniqueTitle = `Cambio sin guardar ${Date.now()}`
  await page.locator('#publish-title').fill(uniqueTitle)
  await expect.poll(() => page.evaluate(() => {
    const draft = JSON.parse(localStorage.getItem('112233:listing-draft:v3') ?? 'null') as { listingId?: string; data?: { title?: string } } | null
    return draft?.listingId && draft.data?.title
  })).toBe(uniqueTitle)

  await page.goto('/#/publicar')
  await advanceWizard(page, 7)
  await expect(page.locator('#publish-title')).not.toHaveValue(uniqueTitle)

  await page.goto(href!)
  await expect(page.getByRole('heading', { name: /editar habitación/i })).toBeVisible()
  await advanceWizard(page, 7)
  await expect(page.locator('#publish-title')).toHaveValue(uniqueTitle)
  await page.getByRole('button', { name: /continuar/i }).click()
  await page.getByRole('button', { name: /continuar/i }).click()
  await expect(page.getByRole('button', { name: /guardar cambios/i })).toBeVisible()
})

test('owned-listing empty state follows the selected UI language', async ({ page }) => {
  await signInAsHost(page)
  await page.goto('/#/mis-anuncios')

  await page.getByLabel('Estado').selectOption('Borrador')
  await expect(page.locator('.account-empty')).toBeVisible()

  await page.getByRole('button', { name: 'Seleccionar idioma' }).click()
  await page.getByRole('menuitemradio', { name: /Русский/ }).click()

  await expect(page.locator('.account-empty h2')).toHaveText('Нет объявлений с таким статусом')
  await expect(page.locator('.account-empty p')).toHaveText('Выберите другой статус или создайте новое объявление.')
  await expect(page.locator('.account-empty')).not.toContainText('No hay anuncios en este estado')
})
