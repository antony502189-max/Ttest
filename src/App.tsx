import { Component, lazy, Suspense, useEffect, useState, type ErrorInfo, type ReactNode } from 'react'
import { HashRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { AppProvider, useApp } from '@/contexts/app-context'
import { I18nProvider } from '@/contexts/i18n-context'
import { AppLayout } from '@/components/layout'
import { CustomerFeedbackFixes } from '@/components/customer-feedback-fixes'
import { ObsoletePhoneSearchRemoval } from '@/components/obsolete-phone-search-removal'
import { PublishOccupancySync } from '@/components/publish-occupancy-sync'
import { AUTH_READY_EVENT, hasSessionHint } from '@/api/auth'

const HomePage = lazy(() => import('@/pages/HomePage').then((module) => ({ default: module.HomePage })))
const SearchPage = lazy(() => import('@/pages/SearchPage').then((module) => ({ default: module.SearchPage })))
const ListingPage = lazy(() => import('@/pages/ListingPage').then((module) => ({ default: module.ListingPage })))
const RegisterPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.RegisterPage })))
const LoginPage = lazy(() => import('@/pages/UnifiedAuthPage').then((module) => ({ default: module.UnifiedAuthPage })))
const RecoverPasswordPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.RecoverPasswordPage })))
const ResetPasswordPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.ResetPasswordPage })))
const VerifyEmailPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.VerifyEmailPage })))
const FavoritesPage = lazy(() => import('@/pages/AccountPages').then((module) => ({ default: module.FavoritesPage })))
const SavedSearchesPage = lazy(() => import('@/pages/AccountPages').then((module) => ({ default: module.SavedSearchesPage })))
const ProfilePage = lazy(() => import('@/pages/ProfilePage').then((module) => ({ default: module.ProfilePage })))
const MyListingsPage = lazy(() => import('@/pages/AccountPages').then((module) => ({ default: module.MyListingsPage })))
const PublishPage = lazy(() => import('@/pages/PublishPage').then((module) => ({ default: module.PublishPage })))
const InfoPage = lazy(() => import('@/pages/InfoPages').then((module) => ({ default: module.InfoPage })))
const AdminPage = lazy(() => import('@/pages/AdminPage').then((module) => ({ default: module.AdminPage })))
const MenuPage = lazy(() => import('@/pages/MobilePages').then((module) => ({ default: module.MenuPage })))
const MessagesPage = lazy(() => import('@/pages/MobilePages').then((module) => ({ default: module.MessagesPage })))

const infoRoutes = ['/sobre-nosotros', '/como-funciona', '/ayuda', '/terminos', '/privacidad', '/cookies', '/normas-de-publicacion']
const MOBILE_ONBOARDING_KEY = '112233:mobile-onboarding:v1'

function RouteLoading() {
  return <div className="route-loading" role="status" aria-live="polite"><span /><strong>Cargando 112233.es…</strong></div>
}

function ScrollToTop() {
  const { pathname, search } = useLocation()
  useEffect(() => {
    const previousRestoration = window.history.scrollRestoration
    window.history.scrollRestoration = 'manual'
    const reset = () => window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    reset()
    let secondFrame = 0
    const firstFrame = window.requestAnimationFrame(() => {
      reset()
      secondFrame = window.requestAnimationFrame(reset)
    })
    const delayedReset = window.setTimeout(reset, 100)
    return () => {
      window.cancelAnimationFrame(firstFrame)
      if (secondFrame) window.cancelAnimationFrame(secondFrame)
      window.clearTimeout(delayedReset)
      window.history.scrollRestoration = previousRestoration
    }
  }, [pathname, search])
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
      try { localStorage.setItem(MOBILE_ONBOARDING_KEY, 'done') } catch { /* Navigation still works when storage is unavailable. */ }
      navigate('/acceso')
    }
    document.addEventListener('click', openRealAuth, true)
    return () => document.removeEventListener('click', openRealAuth, true)
  }, [location.pathname, navigate])
  return null
}

function ProtectedRoute({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const { currentUser } = useApp()
  const location = useLocation()
  const [authReady, setAuthReady] = useState(() => Boolean(currentUser) || !hasSessionHint())

  useEffect(() => {
    if (currentUser || !hasSessionHint()) {
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
  }, [currentUser])

  if (!authReady) return <RouteLoading />
  if (!currentUser) return <Navigate to="/acceso" state={{ returnTo: `${location.pathname}${location.search}` }} replace />
  if (admin && currentUser.role !== 'admin') return <Navigate to="/" replace />
  return children
}

class RouteErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('Route error', error, info) }
  render() { return this.state.failed ? <div className="route-error" role="alert"><h1>No pudimos abrir esta página</h1><p>Recarga la aplicación. Tus datos locales permanecen guardados.</p><button type="button" onClick={() => location.reload()}>Recargar</button></div> : this.props.children }
}

export default function App() {
  return <HashRouter><ScrollToTop /><I18nProvider><AppProvider><MobileOnboardingAuthBridge /><CustomerFeedbackFixes /><ObsoletePhoneSearchRemoval /><PublishOccupancySync /><RouteErrorBoundary><Suspense fallback={<RouteLoading />}><Routes><Route element={<AppLayout />}><Route index element={<HomePage />} /><Route path="buscar" element={<SearchPage />} /><Route path="habitacion/:id" element={<ListingPage />} /><Route path="registro" element={<RegisterPage />} /><Route path="acceso" element={<LoginPage />} /><Route path="recuperar-contrasena" element={<RecoverPasswordPage />} /><Route path="restablecer-contrasena" element={<ResetPasswordPage />} /><Route path="verificar-email" element={<VerifyEmailPage />} /><Route path="favoritos" element={<FavoritesPage />} /><Route path="busquedas-guardadas" element={<ProtectedRoute><SavedSearchesPage /></ProtectedRoute>} /><Route path="mensajes" element={<MessagesPage />} /><Route path="menu" element={<MenuPage />} /><Route path="perfil" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} /><Route path="mis-anuncios" element={<ProtectedRoute><MyListingsPage /></ProtectedRoute>} /><Route path="publicar" element={<ProtectedRoute><PublishPage key="publish-create" /></ProtectedRoute>} /><Route path="mis-anuncios/:id/editar" element={<ProtectedRoute><PublishPage key="publish-edit" editing /></ProtectedRoute>} />{infoRoutes.map((path) => <Route key={path} path={path.slice(1)} element={<InfoPage />} />)}<Route path="admin" element={<ProtectedRoute admin><AdminPage /></ProtectedRoute>} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes></Suspense></RouteErrorBoundary></AppProvider></I18nProvider></HashRouter>
}
