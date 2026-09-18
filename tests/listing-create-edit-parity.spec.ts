import { readFileSync } from 'node:fs'
import { expect, test, type Page } from '@playwright/test'

async function signInAsHost(page: Page) {
  await page.goto('/#/')
  await page.evaluate(() => {
    localStorage.setItem('112233:session:v1', JSON.stringify('host-demo'))
    localStorage.setItem('112233:mobile-onboarding:v1', 'done')
  })
  await page.reload()
}

test('creation and editing use the same nine-section long-form shell', async ({ page }) => {
  await signInAsHost(page)

  await page.goto('/#/publicar')
  await expect(page.locator('.listing-create-page')).toBeVisible()
  await expect(page.locator('.stepper')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /continuar/i })).toHaveCount(0)
  const createSections = await page.locator('.listing-create-page .listing-edit-section h2').allTextContents()
  expect(createSections).toEqual([
    'Tipo de alquiler',
    'Ubicación',
    'Habitación y vivienda',
    'Precio, gastos y fianza',
    'Disponibilidad',
    'Convivencia y requisitos',
    'Fotografías',
    'Título y descripción',
    'Contacto',
  ])

  await page.goto('/#/mis-anuncios')
  const edit = page.locator('.manage-card').first().getByRole('link', { name: /editar/i })
  await expect(edit).toBeVisible()
  await edit.click()

  await expect(page.locator('.listing-edit-page')).toBeVisible()
  await expect(page.locator('.listing-create-page')).toHaveCount(0)
  await expect(page.locator('.stepper')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /continuar/i })).toHaveCount(0)
  const editSections = await page.locator('.listing-edit-section h2').allTextContents()
  expect(editSections).toEqual(createSections)
})

test('create and edit keep separate persistence and mutation paths', () => {
  const app = readFileSync('src/App.tsx', 'utf8')
  const create = readFileSync('src/pages/ListingCreatePage.tsx', 'utf8')
  const edit = readFileSync('src/pages/ListingEditPage.tsx', 'utf8')
  const context = readFileSync('src/contexts/app-context.tsx', 'utf8')

  expect(app).toContain('<Route path="publicar" element={<ProtectedRoute><ListingCreatePage /></ProtectedRoute>}')
  expect(app).toContain('<OwnedListingsHydrationGate><ListingEditPage /></OwnedListingsHydrationGate>')

  expect(create).toContain("const draftKey = '112233:listing-draft:v3'")
  expect(create).toContain("const legacyDraftKey = '112233:listing-draft:v2'")
  expect(create).toContain("const editDraftPrefix = '112233:listing-edit-draft:v1:'")
  expect(create).toContain('createListing')
  expect(create).not.toContain('updateListing(')
  expect(create).toContain('getEmailVerificationStatus')
  expect(create).toContain('requestEmailVerification')
  expect(create).toContain('verifyEmail')
  expect(create).toContain('partialPublication')
  expect(create).toContain('partialPublication.publicationKey === draft.publicationKey')
  expect(create).toContain("bedType: value === 'bed' ? 'single' : current.bedType")
  expect(create).toContain('bedCount: Math.max(current.bedCount, Math.ceil(roomCapacity / placesPerBed))')
  expect(create).toContain("couplesAllowed: value === 'couple' || value === 'any'")
  expect(create).toContain('localStorage.removeItem(draftKey)')

  expect(edit).toContain("const editDraftPrefix = '112233:listing-edit-draft:v1:'")
  expect(edit).toContain('updateListing(existing.id, listing)')
  expect(edit).not.toContain('createListing(')
  expect(edit).toContain('stored.listingId === existing.id')
  expect(edit).toContain('localStorage.removeItem(storageKey)')

  const createStart = context.indexOf('const createListing = useCallback(async')
  const updateStart = context.indexOf('const updateListing = useCallback(async')
  const deleteStart = context.indexOf('const deleteListing', updateStart)
  expect(createStart).toBeGreaterThanOrEqual(0)
  expect(updateStart).toBeGreaterThan(createStart)
  const createFlow = context.slice(createStart, updateStart)
  const updateFlow = context.slice(updateStart, deleteStart)

  expect(createFlow).toContain('if (partialPublication)')
  expect(createFlow).toContain('syncListingImages(partialPublication.listingId, listing.images)')
  expect(createFlow).toContain('return false')
  expect(updateFlow).toContain('updateRemoteListing(id, next)')
  expect(updateFlow).toContain('syncListingImages(id, next.images)')
  expect(updateFlow).toContain('return false')
})

test('legacy or global edit drafts are migrated without leaking into a new listing', () => {
  const create = readFileSync('src/pages/ListingCreatePage.tsx', 'utf8')
  const edit = readFileSync('src/pages/ListingEditPage.tsx', 'utf8')

  expect(create).toContain('if (raw && stored?.listingId)')
  expect(create).toContain('const scopedKey = editDraftKey(stored.listingId)')
  expect(create).toContain('if (!localStorage.getItem(scopedKey)) localStorage.setItem(scopedKey, raw)')
  expect(create).toContain('localStorage.removeItem(draftKey)')
  expect(create).toContain('const legacy = localStorage.getItem(legacyDraftKey)')
  expect(create).toContain('!stored.listingId')
  expect(create).toContain('stored.ownerUserId === currentUser?.id')
  expect(edit).toContain('stored.listingId === existing.id')
  expect(edit).toContain('const editDraftKey = (id: string)')
  expect(edit).toContain('editDraftPrefix')
})
