import { Link, Outlet, useLocation } from 'react-router-dom'
import { Bell, ChevronDown, Globe2, Heart, Menu, Plus, Search, UserRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Toaster } from '@/components/ui/sonner'
import { cn } from '@/lib/utils'
import { useI18n, type Language } from '@/contexts/i18n-context'

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <Link to="/" className="brand-logo" aria-label="112233.es — inicio">
      <span aria-hidden="true">11<span>·</span>22<span>·</span>33</span>{compact ? null : <small>.es</small>}
    </Link>
  )
}

const languageOptions: { value: Language; code: string; label: string }[] = [
  { value: 'es', code: 'ES', label: 'Español' },
  { value: 'en', code: 'EN', label: 'English' },
  { value: 'ru', code: 'RU', label: 'Русский' },
]

export function LanguageSwitcher() {
  const { language, setLanguage } = useI18n()
  const current = languageOptions.find((option) => option.value === language) ?? languageOptions[0]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="language-switcher" aria-label="Seleccionar idioma">
          <Globe2 data-icon="inline-start" /><span>{current.code}</span><ChevronDown aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="language-menu">
        <DropdownMenuLabel>Idioma</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={language} onValueChange={(value) => setLanguage(value as Language)}>
          {languageOptions.map((option) => <DropdownMenuRadioItem key={option.value} value={option.value}><span className="language-code">{option.code}</span>{option.label}</DropdownMenuRadioItem>)}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function Header() {
  return (
    <header className="site-header">
      <div className="site-header__inner">
        <Logo />
        <LanguageSwitcher />
        <div className="header-actions">
          <Button asChild variant="ghost" className="desktop-only"><Link to="/favoritos"><Heart data-icon="inline-start" />Favoritos</Link></Button>
          <Button asChild variant="ghost" className="desktop-only"><Link to="/acceso">Acceder</Link></Button>
          <Button asChild className="publish-header-button"><Link to="/publicar"><Plus data-icon="inline-start" />Publicar anuncio gratis</Link></Button>
        </div>
      </div>
    </header>
  )
}

export function MobileHeader() {
  return (
    <header className="mobile-header">
      <Sheet>
        <SheetTrigger asChild><Button variant="ghost" size="icon" aria-label="Abrir menú"><Menu /></Button></SheetTrigger>
        <SheetContent side="left" className="w-[88vw] max-w-sm">
          <SheetHeader><SheetTitle><Logo /></SheetTitle><SheetDescription>Habitaciones en Tenerife, sin rodeos.</SheetDescription></SheetHeader>
          <nav className="mobile-menu" aria-label="Menú principal">
            {[
              ['/buscar', 'Buscar habitaciones'], ['/publicar', 'Publicar habitación'], ['/favoritos', 'Favoritos'], ['/busquedas-guardadas', 'Búsquedas guardadas'], ['/mis-anuncios', 'Mis anuncios'], ['/perfil', 'Mi perfil'], ['/como-funciona', 'Cómo funciona'], ['/ayuda', 'Ayuda'], ['/admin', 'Administración'],
            ].map(([to, label]) => <Link key={to} to={to}>{label}</Link>)}
          </nav>
        </SheetContent>
      </Sheet>
      <div className="mobile-brand-group"><Logo compact /><LanguageSwitcher /></div>
      <Link to="/perfil" className="mobile-icon-link" aria-label="Abrir mi cuenta"><UserRound /></Link>
    </header>
  )
}

const bottomItems = [
  { to: '/buscar', label: 'Buscar', icon: Search },
  { to: '/favoritos', label: 'Favoritos', icon: Heart },
  { to: '/busquedas-guardadas', label: 'Alertas', icon: Bell },
  { to: '/publicar', label: 'Publicar', icon: Plus },
  { to: '/perfil', label: 'Mi cuenta', icon: UserRound },
]

export function BottomNavigation() {
  const location = useLocation()
  return (
    <nav className="bottom-nav" aria-label="Navegación móvil">
      {bottomItems.map(({ to, label, icon: Icon }) => {
        const active = location.pathname === to
        return <Link key={label} to={to} aria-current={active ? 'page' : undefined} className={cn('bottom-nav__item', active && 'is-active')}><Icon /><span>{label}</span></Link>
      })}
    </nav>
  )
}

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div><Logo /><p>El marketplace especializado en habitaciones de Tenerife.</p></div>
        <nav aria-label="Información"><strong>112233.es</strong><Link to="/sobre-nosotros">Sobre nosotros</Link><Link to="/como-funciona">Cómo funciona</Link><Link to="/contacto">Contacto</Link></nav>
        <nav aria-label="Ayuda"><strong>Ayuda</strong><Link to="/ayuda">Centro de ayuda</Link><Link to="/normas-de-publicacion">Normas de publicación</Link><Link to="/publicar">Publicar</Link></nav>
        <nav aria-label="Legal"><strong>Legal</strong><Link to="/terminos">Términos</Link><Link to="/privacidad">Privacidad</Link><Link to="/cookies">Cookies</Link></nav>
      </div>
      <div className="container footer-bottom"><span>© 2026 112233.es</span><span>Hecho para encontrar habitación, no para perder tiempo.</span></div>
    </footer>
  )
}

export function AppLayout() {
  const { pathname } = useLocation()
  const hideFooter = pathname === '/buscar' || pathname === '/admin' || pathname === '/publicar' || pathname.includes('/editar') || ['/registro', '/acceso', '/recuperar-contrasena', '/restablecer-contrasena'].includes(pathname)
  return (
    <>
      <a className="skip-link" href="#main-content">Saltar al contenido</a>
      <Header /><MobileHeader />
      <main id="main-content" tabIndex={-1}><Outlet /></main>
      {hideFooter ? null : <Footer />}
      <BottomNavigation />
      <Toaster position="top-center" richColors closeButton />
    </>
  )
}
