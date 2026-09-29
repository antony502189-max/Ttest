let accountPagesPromise: Promise<typeof import('@/pages/AccountPages')> | null = null
let listingCreatePagePromise: Promise<typeof import('@/pages/ListingCreatePage')> | null = null

export function loadAccountPages() {
  if (!accountPagesPromise) {
    accountPagesPromise = import('@/pages/AccountPages').catch((error) => {
      accountPagesPromise = null
      throw error
    })
  }
  return accountPagesPromise
}

export function loadListingCreatePage() {
  if (!listingCreatePagePromise) {
    listingCreatePagePromise = import('@/pages/ListingCreatePage').catch((error) => {
      listingCreatePagePromise = null
      throw error
    })
  }
  return listingCreatePagePromise
}

export function preloadAccountPages() {
  void loadAccountPages().catch(() => undefined)
}

export function preloadListingCreatePage() {
  void loadListingCreatePage().catch(() => undefined)
}

export function preloadOwnerListingRoutes() {
  preloadAccountPages()
  preloadListingCreatePage()
}
