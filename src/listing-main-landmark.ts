function ensureListingMainLandmark() {
  if (document.getElementById('main-content')) return
  const listing = document.querySelector<HTMLElement>('.listing-page.idealista-listing-page')
  if (!listing) return
  listing.id = 'main-content'
  listing.setAttribute('role', 'main')
}

ensureListingMainLandmark()

const observer = new MutationObserver(() => ensureListingMainLandmark())
observer.observe(document.documentElement, { childList: true, subtree: true })

window.addEventListener('hashchange', ensureListingMainLandmark)
