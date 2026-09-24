import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

const read = (path: string) => readFileSync(path, 'utf8')

test('listing deletion uses ownership or server-side admin access instead of an email allowlist', () => {
  const service = read('backend/app/services/listings.py')
  const ownerPage = read('src/pages/AccountPages.tsx')
  const obsoleteUiGateExists = read('src/pages/AccountPages.tsx').includes('canUseHardDelete')

  expect(service).not.toContain('HARD_DELETE_EMAILS')
  expect(service).not.toContain('require_hard_delete_authorization')
  expect(service).toContain('admin = await ensure_owner_or_admin(listing, user, session)')
  expect(ownerPage).toContain('title="¿Eliminar este anuncio?"')
  expect(ownerPage).toContain('confirmLabel="Eliminar anuncio"')
  expect(obsoleteUiGateExists).toBe(false)
})

test('confirmed remote deletion happens before local state and edit-draft cleanup', () => {
  const context = read('src/contexts/app-context.tsx')
  const start = context.indexOf('const deleteListing = useCallback(async')
  const end = context.indexOf('const setListingStatus', start)
  const flow = context.slice(start, end)

  expect(start).toBeGreaterThanOrEqual(0)
  expect(flow).toContain('await deleteRemoteListing(id)')
  expect(flow).toContain('localStorage.removeItem(editDraftKey)')
  expect(flow).toContain('setOwnedListings(remaining)')
  expect(flow.indexOf('await deleteRemoteListing(id)')).toBeLessThan(flow.indexOf('localStorage.removeItem(editDraftKey)'))
  expect(flow.indexOf('await deleteRemoteListing(id)')).toBeLessThan(flow.indexOf('setOwnedListings(remaining)'))
})

test('admin listing deletion has a dedicated protected API and destructive UI', () => {
  const routes = read('backend/app/api/v1/admin.py')
  const api = read('src/api/admin.ts')
  const page = read('src/pages/AdminPage.tsx')

  expect(routes).toContain('@router.delete("/listings/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)')
  expect(routes).toContain('user: User = Depends(require_admin)')
  expect(api).toContain("api<void>(\`/admin/listings/\${id}\`, { method: 'DELETE' })")
  expect(page).toContain('function ListingDeleteDialog')
  expect(page).toContain("await deleteAdminListing(listing.id)")
  expect(page).toContain("setListings((current) => current.filter((listing) => listing.id !== removed.id))")
  expect(page).toContain("<Trash2 /> Eliminar")
})

test('soft deletion preserves tombstone audit while removing active listing relations', () => {
  const service = read('backend/app/services/listings.py')

  expect(service).toContain('listing.deleted_at = datetime.now(UTC)')
  expect(service).toContain('listing.closed_reason = "deleted"')
  expect(service).toContain('action="listing.deleted"')
  expect(service).toContain('delete(ListingImage)')
  expect(service).toContain('delete(Favorite)')
  expect(service).toContain('delete(DiscardedListing)')
  expect(service).toContain('delete(ListingPromotion)')
  expect(service).toContain('delete(HomepageHeroPromotion)')
  expect(service).toContain('await mark_orphaned_media(session, attached_ids)')
  expect(service.indexOf('await notify_favorited_listing_unavailable')).toBeLessThan(service.indexOf('delete(Favorite)'))
})
