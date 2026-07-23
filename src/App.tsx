import { Component, lazy, Suspense, useEffect, type ErrorInfo, type ReactNode } from 'react'
import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppProvider } from '@/contexts/app-context'
import { useApp } from '@/contexts/app-context'
import { I18nProvider } from '@/contexts/i18n-context'
import { AppLayout } from '@/components/layout'
import { SearchExperienceGuards } from '@/components/search-experience-guards'

const HomePage = lazy(() => import('@/pages/HomePage').then((module) => ({ default: module.HomePage })))
const SearchPage = lazy(() => import('@/pages/SearchPage').then((module) => ({ default: module.SearchPage })))
const ListingPage = lazy(() => import('@/pages/ListingPage').then((module) => ({ default: module.ListingPage })))
const RegisterPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.RegisterPage })))
const LoginPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.LoginPage })))
const RecoverPasswordPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.RecoverPasswordPage })))
const ResetPasswordPage = lazy(() => import('@/pages/AuthPages').then((module) => ({ default: module.ResetPasswordPage })))
const FavoritesPage = lazy(() => import('@/pages/AccountPages').then((module) => ({ default: module.FavoritesPage })))
const SavedSearchesPage = lazy(() => import('@/pages/AccountPages').then((module) => ({ default: module.SavedSearchesPage })))
const ProfilePage = lazy(() => import('@/pages/AccountPages').then((module) => ({ default: module.ProfilePage })))
const MyListingsPage = lazy(() => import('@/pages/AccountPages').then((module) => ({ default: module.MyListingsPage })))
const PublishPage = lazy(() => import('@/pages/PublishPage').then((module) => ({ default: module.PublishPage })))
const InfoPage = lazy(() => import('@/pages/InfoPages').then((module) => ({ default: module.InfoPage })))
const AdminPage = lazy(() => import('@/pages/AdminPage').then((module) => ({ default: module.AdminPage })))
const MenuPage = lazy(() => import('@/pages/MobilePages').then((module) => ({ default: module.MenuPage })))
const MessagesPage = lazy(() => import('@/pages/MobilePages').then((module) => ({ default: module.MessagesPage })))

const infoRoutes = ['/sobre-nosotros', '/como-funciona', '/ayuda', '/contacto', '/terminos', '/privacidad', '/cookies', '/normas-de-publicacion']

function RouteLoading() {
  return <div className="route-loading" role="status" aria-live="polite"><span /><strong>Cargando 112233.es…</strong></div>
}

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo({ top: 0, left: 0, behavior: 'auto' }) }, [pathname])
  return null
}

function ProtectedRoute({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const { currentUser } = useApp()
  const location = useLocation()
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
  return <HashRouter><ScrollToTop /><I18nProvider><AppProvider><SearchExperienceGuards /><RouteErrorBoundary><Suspense fallback={<RouteLoading />}><Routes><Route element={<AppLayout />}><Route index element={<HomePage />} /><Route path="buscar" element={<SearchPage />} /><Route path="habitacion/:id" element={<ListingPage />} /><Route path="registro" element={<RegisterPage />} /><Route path="acceso" element={<LoginPage />} /><Route path="recuperar-contrasena" element={<RecoverPasswordPage />} /><Route path="restablecer-contrasena" element={<ResetPasswordPage />} /><Route path="favoritos" element={<FavoritesPage />} /><Route path="busquedas-guardadas" element={<ProtectedRoute><SavedSearchesPage /></ProtectedRoute>} /><Route path="mensajes" element={<MessagesPage />} /><Route path="menu" element={<MenuPage />} /><Route path="perfil" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} /><Route path="mis-anuncios" element={<ProtectedRoute><MyListingsPage /></ProtectedRoute>} /><Route path="publicar" element={<ProtectedRoute><PublishPage key="publish-create" /></ProtectedRoute>} /><Route path="mis-anuncios/:id/editar" element={<ProtectedRoute><PublishPage key="publish-edit" editing /></ProtectedRoute>} />{infoRoutes.map((path) => <Route key={path} path={path.slice(1)} element={<InfoPage />} />)}<Route path="admin" element={<ProtectedRoute admin><AdminPage /></ProtectedRoute>} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes></Suspense></RouteErrorBoundary></AppProvider></I18nProvider></HashRouter>
}
