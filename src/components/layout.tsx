import { lazy, Suspense, useEffect, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router'
import { ChevronDown, Globe2, Heart, Home, Menu, MessageCircle, Plus, Search, UserRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Toaster } from '@/components/ui/sonner'
import { MobileAppV2 } from '@/components/mobile-app-v2'
import { cn } from '@/lib/utils'
import { useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'

const MOBILE_VIEWPORT = '(max-width: 767px), (max-height: 480px) and (max-width: 900px)'
const MOBILE_SHELL_ROUTES = ['/', '/buscar', '/favoritos', '/busquedas-guardadas', '/mensajes', '/menu']
const MobilePublicationGate = lazy(() => import('@/components/mobile-publication-gate').then((module) => ({ default: module.MobilePublicationGate })))
const MobileSearchResults = lazy(() => import('@/components/mobile-search-results-v2').then((module) => ({ default: module.MobileSearchResults })))

export function Logo({ compact = false }: { compact?: boolean }) {
  return <Link to="/" className="brand-logo" aria-label="112233.es — inicio"><span aria-hidden="true">11<span>·</span>22<span>·</span>33</span>{compact ? null : <small>.es</small>}</Link>
}

const languageOptions: { value: Language; code: string; label: string }[] = [
  { value: 'es', code: 'ES', label: 'Español' },
  { value: 'en', code: 'EN', label: 'English' },
  { value: 'ru', code: 'RU', label: 'Русский' },
]

export function LanguageSwitcher() {
  const { language, setLanguage } = useI18n()
  const current = languageOptions.find((option) => option.value === language) ?? languageOptions[0]
  return <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" className="language-switcher" aria-label="Seleccionar idioma"><Globe2 data-icon="inline-start" /><span>{current.code}</span><ChevronDown aria-hidden="true" /></Button></DropdownMenuTrigger><DropdownMenuContent align="start" className="language-menu"><DropdownMenuLabel>Idioma</DropdownMenuLabel><DropdownMenuRadioGroup value={language} onValueChange={(value) => setLanguage(value as Language)}>{languageOptions.map((option) => <DropdownMenuRadioItem key={option.value} value={option.value}><span className="language-code">{option.code}</span>{option.label}</DropdownMenuRadioItem>)}</DropdownMenuRadioGroup></DropdownMenuContent></DropdownMenu>
}

export function Header() {
  const { currentUser } = useApp()
  return <header className="site-header"><div className="site-header__inner"><Logo /><LanguageSwitcher /><div className="header-actions"><Button asChild variant="ghost" className="desktop-only"><Link to="/favoritos"><Heart data-icon="inline-start" />Favoritos</Link></Button><Button asChild variant="ghost" className="desktop-only"><Link to={currentUser ? '/perfil' : '/acceso'}>{currentUser ? currentUser.name.split(' ')[0] : 'Acceder'}</Link></Button><Button asChild className="publish-header-button"><Link to="/publicar"><Plus data-icon="inline-start" />Publicar anuncio gratis</Link></Button></div></div></header>
}

export function MobileHeader() {
  const { currentUser } = useApp()
  return <header className="mobile-header"><Logo compact /><div className="mobile-header__actions"><LanguageSwitcher /><Link to={currentUser ? '/perfil' : '/acceso'} className="mobile-icon-link" aria-label={currentUser ? 'Abrir mi cuenta' : 'Acceder'}><UserRound /></Link><Link to="/menu" className="mobile-icon-link" aria-label="Abrir menú"><Menu /></Link></div></header>
}

const bottomItems = [{ to: '/', label: 'Inicio', icon: Home }, { to: '/favoritos', label: 'Favoritos', icon: Heart }, { to: '/buscar', label: 'Buscar', icon: Search }, { to: '/mensajes', label: 'Mensajes', icon: MessageCircle }, { to: '/perfil', label: 'Perfil', icon: UserRound }]
export function BottomNavigation() { const location = useLocation(); return <nav className="bottom-nav" aria-label="Navegación móvil">{bottomItems.map(({ to, label, icon: Icon }) => { const active = location.pathname === to; return <Link key={label} to={to} aria-current={active ? 'page' : undefined} className={cn('bottom-nav__item', active && 'is-active')}><Icon /><span>{label}</span></Link> })}</nav> }

export function Footer() {
  const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
  return <footer className="site-footer"><div className="container footer-grid"><div><Logo /><p>El marketplace especializado en habitaciones de Tenerife.</p></div><nav aria-label="Información"><strong>112233.es</strong><Link to="/sobre-nosotros">Sobre nosotros</Link><Link to="/como-funciona">Cómo funciona</Link><Link to="/contacto">Contacto</Link></nav><nav aria-label="Ayuda"><strong>Ayuda</strong><Link to="/ayuda">Centro de ayuda</Link><Link to="/normas-de-publicacion">Normas de publicación</Link><Link to="/publicar">Publicar</Link></nav><nav aria-label="Legal"><strong>Legal</strong><Link to="/terminos">Términos</Link><Link to="/privacidad">Privacidad</Link><Link to="/cookies">Cookies</Link></nav></div><div className="container footer-bottom"><span>© 2026 112233.es</span><span>{mockMode ? 'Entorno de demostración con datos locales.' : 'Catálogo conectado al servicio de anuncios.'}</span></div></footer>
}

export function AppLayout() {
  const location = useLocation()
  const { pathname } = location
  const { storageError, clearStorageError } = useApp()
  const [mobileViewport, setMobileViewport] = useState(() => window.matchMedia(MOBILE_VIEWPORT).matches)
  const mobileShellActive = mobileViewport && MOBILE_SHELL_ROUTES.includes(pathname)
  const mobilePublicationGateActive = mobileViewport && new URLSearchParams(location.search).get('gate') === 'publicar'
  const mobileSearchResultsActive = mobileViewport && pathname === '/buscar'
  const hideFooter = pathname === '/buscar' || pathname === '/admin' || pathname === '/publicar' || pathname === '/menu' || pathname === '/mensajes' || pathname.includes('/editar') || ['/registro', '/acceso', '/recuperar-contrasena', '/restablecer-contrasena'].includes(pathname)
  useEffect(() => {
    const media = window.matchMedia(MOBILE_VIEWPORT)
    const update = () => setMobileViewport(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return <><a className="skip-link" href="#main-content" onClick={(event) => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>Saltar al contenido</a><Header /><MobileHeader />{storageError ? <div className="storage-error-banner" role="alert"><span>{storageError}</span><Button variant="ghost" size="sm" onClick={clearStorageError}>Cerrar</Button></div> : null}<main id="main-content" tabIndex={-1}>{mobileShellActive ? <MobileAppV2 /> : <Outlet />}{mobilePublicationGateActive ? <Suspense fallback={null}><MobilePublicationGate /></Suspense> : null}{mobileSearchResultsActive ? <Suspense fallback={null}><MobileSearchResults /></Suspense> : null}</main>{hideFooter ? null : <Footer />}<BottomNavigation /><Toaster position="top-center" richColors closeButton /></>
}
