import { Component, lazy, Suspense, useEffect, useState, type ErrorInfo, type ReactNode } from 'react'
import { HashRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router'
import { checkAdminAccess } from '@/api/admin'
import { AUTH_READY_EVENT, hasSessionHint } from '@/api/auth'
import { ApiError } from '@/api/client'
import { AppLayout } from '@/components/layout'
import { CustomerFeedbackFixes } from '@/components/customer-feedback-fixes'
import { CustomerVideoCriticalFixes } from '@/components/customer-video-critical-fixes'
import { MobileSiteFeedbackFixes } from '@/components/mobile-site-feedback-fixes'
import { ModerationGate } from '@/components/moderation-gate'
import { OwnedListingsHydrationGate } from '@/components/owned-listings-hydration-gate'
import { PublishOccupancySync } from '@/components/publish-occupancy-sync'
import { AppProvider, useApp } from '@/contexts/app-context'
import { I18nProvider, useI18n } from '@/contexts/i18n-context'

const HomePage = lazy(() => import('@/pages/HomePage').then((module) => ({ default: module.HomePage })))
const SearchPage = lazy(() => import('@/pages/SearchPage').then((module) => ({ default: module.SearchPage })))
const ListingPage = lazy(() => import('@/pages/ListingPage').then((module) => ({ default: module.ListingPage })))
const RegisterPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.RegisterPage })))
const LoginPage = lazy(() => import('@/pages/UnifiedAuthPage').then((module) => ({ default: module.UnifiedAuthPage })))
const RecoverPasswordPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.RecoverPasswordPage })))
const ResetPasswordPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.ResetPasswordPage })))
const VerifyEmailPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.VerifyEmailCodePage })))
const FavoritesPage = lazy(() => import('@/pages/FavoritesPage').then((module) => ({ default: module.FavoritesPage })))
const NotificationsPage = lazy(() => import('@/pages/NotificationsPage').then((module) => ({ default: module.NotificationsPage })))
const SavedSearchesPage = lazy(() => import('@/pages/AccountPages').then((module) => ({ default: module.SavedSearchesPage })))
const ProfilePage = lazy(() => import('@/pages/ProfilePage').then((module) => ({ default: module.ProfilePage })))
const MyListingsPage = lazy(() => import('@/pages/AccountPages').then((module) => ({ default: module.MyListingsPage })))
const PublishPage = lazy(() => import('@/pages/PublishPage').then((module) => ({ default: module.PublishPage })))
const InfoPage = lazy(() => import('@/pages/InfoPages').then((module) => ({ default: module.InfoPage })))
const AdminPage = lazy(() => import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
  ? import('@/pages/LegacyMockAdminPage').then((module) => ({ default: module.LegacyMockAdminPage }))
  : import('@/pages/AdminPage').then((module) => ({ default: module.AdminPage })))
const MenuPage = lazy(() => import('@/pages/MobilePages').then((module) => ({ default: module.MenuPage })))

const infoRoutes = ['/sobre-nosotros', '/como-funciona', '/ayuda', '/terminos', '/privacidad', '/cookies', '/normas-de-publicacion']
const MOBILE_ONBOARDING_KEY = '112233:mobile-onboarding:v1'
const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'

type AdminRouteAccess = boolean | 'error' | null

function RouteLoading() {
  return <div className="route-loading" role="status" aria-live="polite"><span /><strong>Cargando 112233.es…</strong></div>
}

function ScrollToTop() {
  const { pathname, search, hash } = useLocation()
  useEffect(() => {
    const previousRestoration = window.history.scrollRestoration
    window.history.scrollRestoration = 'manual'
    let firstFrame = 0
    let secondFrame = 0
    let delayedReset = 0
    let anchorFrame = 0

    if (hash) {
      let attempts = 0
      const anchorId = decodeURIComponent(hash.slice(1))
      const revealAnchor = () => {
        const candidates = Array.from(document.querySelectorAll<HTMLElement>('[id]')).filter((element) => element.id === anchorId)
        const target = candidates.find((candidate) => {
          const style = window.getComputedStyle(candidate)
          return style.display !== 'none' && style.visibility !== 'hidden' && candidate.getClientRects().length > 0
        }) ?? candidates[0]
        if (!target) {
          if (attempts < 120) {
            attempts += 1
            anchorFrame = window.requestAnimationFrame(revealAnchor)
          }
          return
        }
        for (const candidate of candidates) {
          if (candidate !== target) candidate.removeAttribute('id')
        }
        target.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'auto' })
        if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1')
        target.focus({ preventScroll: true })
      }
      anchorFrame = window.requestAnimationFrame(revealAnchor)
    } else {
      const reset = () => window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
      reset()
      firstFrame = window.requestAnimationFrame(() => {
        reset()
        secondFrame = window.requestAnimationFrame(reset)
      })
      delayedReset = window.setTimeout(reset, 100)
    }

    return () => {
      if (firstFrame) window.cancelAnimationFrame(firstFrame)
      if (secondFrame) window.cancelAnimationFrame(secondFrame)
      if (anchorFrame) window.cancelAnimationFrame(anchorFrame)
      if (delayedReset) window.clearTimeout(delayedReset)
      window.history.scrollRestoration = previousRestoration
    }
  }, [pathname, search, hash])
  return null
}

function MobileOnboardingAuthBridge() {
  const location = useLocation()
  const navigate = useNavigate()
  useEffect(() => {
    if (location.pathname === '/acceso') return
    const openRealAuth = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      const button = target.closest('.m2-onboarding--auth .m2-auth-panel > button')
      if (!button) return
      event.preventDefault()
      event.stopPropagation()
      try { localStorage.setItem(MOBILE_ONBOARDING_KEY, 'done:refreshable') } catch { /* Navigation still works when storage is unavailable. */ }
      navigate('/acceso')
    }
    document.addEventListener('click', openRealAuth, true)
    return () => document.removeEventListener('click', openRealAuth, true)
  }, [location.pathname, navigate])
  return null
}

function ProtectedRoute({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const { currentUser } = useApp()
  const { language } = useI18n()
  const location = useLocation()
  const currentUserId = currentUser?.id ?? null
  const currentUserRole = currentUser?.role ?? null
  const [authReady, setAuthReady] = useState(() => Boolean(currentUser) || !hasSessionHint())
  const [adminAllowed, setAdminAllowed] = useState<AdminRouteAccess>(() => admin ? null : true)
  const [adminCheckAttempt, setAdminCheckAttempt] = useState(0)

  useEffect(() => {
    if (currentUserId || !hasSessionHint()) {
      setAuthReady(true)
      return
    }
    const markReady = () => setAuthReady(true)
    const checkHint = window.setInterval(() => { if (!hasSessionHint()) markReady() }, 100)
    const timeout = window.setTimeout(markReady, 16_000)
    window.addEventListener(AUTH_READY_EVENT, markReady)
    return () => {
      window.removeEventListener(AUTH_READY_EVENT, markReady)
      window.clearInterval(checkHint)
      window.clearTimeout(timeout)
    }
  }, [currentUserId])

  useEffect(() => {
    if (!admin) {
      setAdminAllowed(true)
      return
    }
    if (!currentUserId) {
      setAdminAllowed(null)
      return
    }
    if (mockMode) {
      setAdminAllowed(currentUserRole === 'admin')
      return
    }

    let cancelled = false
    let retryTimer = 0
    setAdminAllowed(null)

    const verifyAdmin = async (retryTransient = true) => {
      try {
        await checkAdminAccess()
        if (!cancelled) setAdminAllowed(true)
      } catch (error) {
        if (cancelled) return
        const explicitDenial = error instanceof ApiError && (error.status === 401 || error.status === 403)
        if (explicitDenial) {
          setAdminAllowed(false)
          return
        }
        if (retryTransient) {
          retryTimer = window.setTimeout(() => { void verifyAdmin(false) }, 450)
          return
        }
        setAdminAllowed('error')
      }
    }

    void verifyAdmin(true)
    return () => {
      cancelled = true
      if (retryTimer) window.clearTimeout(retryTimer)
    }
  }, [admin, adminCheckAttempt, currentUserId, currentUserRole])

  if (!authReady) return <RouteLoading />
  if (!currentUser) return <Navigate to="/acceso" state={{ returnTo: `${location.pathname}${location.search}` }} replace />
  if (admin && adminAllowed === null) return <RouteLoading />
  if (admin && adminAllowed === 'error') {
    const title = language === 'ru' ? 'Не удалось проверить доступ к админ-панели' : language === 'en' ? 'We could not verify admin access' : 'No pudimos comprobar el acceso de administración'
    const text = language === 'ru' ? 'Сессия остаётся активной. Повторите проверку.' : language === 'en' ? 'Your session is still active. Try the access check again.' : 'Tu sesión sigue activa. Vuelve a comprobar el acceso.'
    const retry = language === 'ru' ? 'Повторить' : language === 'en' ? 'Retry' : 'Reintentar'
    return <div className="route-error customer-admin-access-error" role="alert"><h1>{title}</h1><p>{text}</p><button type="button" onClick={() => setAdminCheckAttempt((value) => value + 1)}>{retry}</button></div>
  }
  if (admin && adminAllowed === false) return <Navigate to="/" replace />
  return children
}

class RouteErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('Route error', error, info) }
  render() { return this.state.failed ? <div className="route-error" role="alert"><h1>No pudimos abrir esta página</h1><p>Recarga la aplicación. Tus datos locales permanecen guardados.</p><button type="button" onClick={() => location.reload()}>Recargar</button></div> : this.props.children }
}

export default function App() {
  return <HashRouter><ScrollToTop /><I18nProvider><AppProvider><MobileOnboardingAuthBridge /><CustomerFeedbackFixes /><CustomerVideoCriticalFixes /><MobileSiteFeedbackFixes /><PublishOccupancySync /><ModerationGate><RouteErrorBoundary><Suspense fallback={<RouteLoading />}><Routes><Route element={<AppLayout />}><Route index element={<HomePage />} /><Route path="buscar" element={<SearchPage />} /><Route path="habitacion/:id" element={<ListingPage />} /><Route path="registro" element={<RegisterPage />} /><Route path="acceso" element={<LoginPage />} /><Route path="recuperar-contrasena" element={<RecoverPasswordPage />} /><Route path="restablecer-contrasena" element={<ResetPasswordPage />} /><Route path="verificar-email" element={<VerifyEmailPage />} /><Route path="favoritos" element={<FavoritesPage />} /><Route path="notificaciones" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} /><Route path="busquedas-guardadas" element={<ProtectedRoute><SavedSearchesPage /></ProtectedRoute>} /><Route path="menu" element={<MenuPage />} /><Route path="perfil" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} /><Route path="mis-anuncios" element={<ProtectedRoute><OwnedListingsHydrationGate><MyListingsPage /></OwnedListingsHydrationGate></ProtectedRoute>} /><Route path="publicar" element={<ProtectedRoute><PublishPage key="publish-create" /></ProtectedRoute>} /><Route path="mis-anuncios/:id/editar" element={<ProtectedRoute><OwnedListingsHydrationGate><PublishPage key="publish-edit" editing /></OwnedListingsHydrationGate></ProtectedRoute>} />{infoRoutes.map((path) => <Route key={path} path={path.slice(1)} element={<InfoPage />} />)}<Route path="admin" element={<ProtectedRoute admin><AdminPage /></ProtectedRoute>} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes></Suspense></RouteErrorBoundary></ModerationGate></AppProvider></I18nProvider></HashRouter>
}
