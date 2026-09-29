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
  preloadPublicationEnhancers()
}

export function preloadOwnerListingRoutes() {
  preloadAccountPages()
  preloadListingCreatePage()
}

function preloadPublicationEnhancers() {
  void import('@/components/publish-location-enhancer').catch(() => undefined)
  void import('@/components/publish-address-lifecycle').catch(() => undefined)
}

/** Start fetching only the route the user is about to visit. The imports never block navigation. */
export function preloadRoute(pathname: string, mobile: boolean) {
  if (mobile) {
    void import('@/components/mobile-publication-gate').catch(() => undefined)
    if (['/', '/buscar', '/favoritos', '/busquedas-guardadas', '/menu'].includes(pathname)) {
      void import('@/components/mobile-app-v2').catch(() => undefined)
      if (pathname === '/buscar') void import('@/components/mobile-search-results-v2').catch(() => undefined)
      return
    }
  }

  if (pathname === '/') void import('@/pages/HomePage').catch(() => undefined)
  else if (pathname === '/buscar') void import('@/pages/SearchPage').catch(() => undefined)
  else if (pathname === '/favoritos') void import('@/pages/FavoritesPage').catch(() => undefined)
  else if (pathname === '/menu') void import('@/pages/MobilePages').catch(() => undefined)
  else if (pathname === '/perfil') void import('@/pages/ProfilePage').catch(() => undefined)
  else if (pathname === '/notificaciones') void import('@/pages/NotificationsPage').catch(() => undefined)
  else if (pathname === '/busquedas-guardadas' || pathname === '/mis-anuncios') preloadAccountPages()
  else if (pathname === '/publicar') preloadListingCreatePage()
  else if (/^\/mis-anuncios\/[^/]+\/editar$/.test(pathname)) {
    void import('@/pages/ListingEditPage').catch(() => undefined)
    preloadPublicationEnhancers()
  }
  else if (pathname.startsWith('/habitacion/')) void import('@/pages/ListingPage').catch(() => undefined)
  else if (pathname === '/acceso') void import('@/pages/UnifiedAuthPage').catch(() => undefined)
  else if (['/registro', '/recuperar-contrasena', '/restablecer-contrasena', '/verificar-email'].includes(pathname)) void import('@/pages/AuthPages').catch(() => undefined)
  else if (pathname === '/admin') {
    if (import.meta.env.VITE_ENABLE_MOCK_MODE === '1') void import('@/pages/LegacyMockAdminPage').catch(() => undefined)
    else void import('@/pages/AdminPage').catch(() => undefined)
  }
  else if (pathname === '/admin/publicidad') void import('@/components/admin-commercial-advertisements').catch(() => undefined)
  else if (pathname === '/mis-campanas' || pathname.startsWith('/publicidad/')) void import('@/pages/CommercialAdvertisementPages').catch(() => undefined)
  else if (['/sobre-nosotros', '/como-funciona', '/ayuda', '/terminos', '/privacidad', '/cookies', '/normas-de-publicacion'].includes(pathname)) void import('@/pages/InfoPages').catch(() => undefined)
}
