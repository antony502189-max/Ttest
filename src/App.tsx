import { lazy, Suspense, useEffect } from 'react'
import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { AppProvider } from '@/contexts/app-context'
import { I18nProvider } from '@/contexts/i18n-context'
import { AppLayout } from '@/components/layout'

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

const infoRoutes = ['/sobre-nosotros', '/como-funciona', '/ayuda', '/contacto', '/terminos', '/privacidad', '/cookies', '/normas-de-publicacion']

function RouteLoading() {
  return <div className="route-loading" role="status" aria-live="polite"><span /><strong>Cargando 112233.es…</strong></div>
}

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo({ top: 0, left: 0, behavior: 'auto' }) }, [pathname])
  return null
}

export default function App() {
  return <HashRouter><ScrollToTop /><I18nProvider><AppProvider><Suspense fallback={<RouteLoading />}><Routes><Route element={<AppLayout />}><Route index element={<HomePage />} /><Route path="buscar" element={<SearchPage />} /><Route path="habitacion/:id" element={<ListingPage />} /><Route path="registro" element={<RegisterPage />} /><Route path="acceso" element={<LoginPage />} /><Route path="recuperar-contrasena" element={<RecoverPasswordPage />} /><Route path="restablecer-contrasena" element={<ResetPasswordPage />} /><Route path="favoritos" element={<FavoritesPage />} /><Route path="busquedas-guardadas" element={<SavedSearchesPage />} /><Route path="perfil" element={<ProfilePage />} /><Route path="mis-anuncios" element={<MyListingsPage />} /><Route path="publicar" element={<PublishPage />} /><Route path="mis-anuncios/:id/editar" element={<PublishPage editing />}/>{infoRoutes.map((path) => <Route key={path} path={path.slice(1)} element={<InfoPage />} />)}<Route path="admin" element={<AdminPage />} /><Route path="*" element={<Navigate to="/" replace />} /></Route></Routes></Suspense></AppProvider></I18nProvider></HashRouter>
}
