import { Link, Outlet, useLocation } from 'react-router-dom'
import { Heart, LayoutDashboard, Map, Menu, Plus, Search, UserRound } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Toaster } from '@/components/ui/sonner'
import { cn } from '@/lib/utils'
import { useApp } from '@/contexts/app-context'

export function Logo({ compact = false }: { compact?: boolean }) {
  return <Link to="/" className="brand-logo" aria-label="112233.es — inicio"><span aria-hidden="true">11<span>·</span>22<span>·</span>33</span>{compact ? null : <small>.es</small>}</Link>
}

export function Header() {
  const { currentUser } = useApp()
  return <header className="site-header"><div className="site-header__inner"><Logo /><div className="header-actions"><Button asChild variant="ghost" className="desktop-only"><Link to="/favoritos"><Heart data-icon="inline-start" />Favoritos</Link></Button>{currentUser?.role === 'admin' ? <Button asChild variant="ghost" className="desktop-only"><Link to="/admin"><LayoutDashboard data-icon="inline-start" />Administración</Link></Button> : null}<Button asChild variant="ghost" className="desktop-only"><Link to={currentUser ? '/perfil' : '/acceso'}>{currentUser ? currentUser.name.split(' ')[0] : 'Acceder'}</Link></Button><Button asChild className="publish-header-button"><Link to="/publicar"><Plus data-icon="inline-start" />Publicar anuncio gratis</Link></Button></div></div></header>
}

export function MobileHeader() {
  const { currentUser } = useApp()
  const items = [['/buscar', 'Buscar habitaciones'], ['/publicar', 'Publicar habitación'], ['/favoritos', 'Favoritos'], ['/busquedas-guardadas', 'Búsquedas guardadas'], ['/mis-anuncios', 'Mis anuncios'], ['/perfil', 'Mi perfil'], ['/como-funciona', 'Cómo funciona'], ['/ayuda', 'Ayuda']]
  if (currentUser?.role === 'admin') items.push(['/admin', 'Administración'])
  return <header className="mobile-header"><Sheet><SheetTrigger asChild><Button variant="ghost" size="icon" aria-label="Abrir menú"><Menu /></Button></SheetTrigger><SheetContent side="left" className="w-[88vw] max-w-sm"><SheetHeader><SheetTitle><Logo /></SheetTitle><SheetDescription>Habitaciones en Tenerife, sin rodeos.</SheetDescription></SheetHeader><nav className="mobile-menu" aria-label="Menú principal">{items.map(([to, label]) => <Link key={to} to={to}>{label}</Link>)}</nav></SheetContent></Sheet><Logo compact /><Link to={currentUser ? '/perfil' : '/acceso'} className="mobile-icon-link" aria-label={currentUser ? 'Abrir mi cuenta' : 'Acceder'}><UserRound /></Link></header>
}

const bottomItems = [{ to: '/buscar', label: 'Buscar', icon: Search }, { to: '/buscar?vista=mapa', label: 'Mapa', icon: Map }, { to: '/publicar', label: 'Publicar', icon: Plus }, { to: '/favoritos', label: 'Favoritos', icon: Heart }, { to: '/perfil', label: 'Mi cuenta', icon: UserRound }]
export function BottomNavigation() { const location = useLocation(); return <nav className="bottom-nav" aria-label="Navegación móvil">{bottomItems.map(({ to, label, icon: Icon }) => { const [pathname, search = ''] = to.split('?'); const isMapItem = search.includes('vista=mapa'); const active = location.pathname === pathname && (isMapItem ? location.search.includes('vista=mapa') : pathname !== '/buscar' || !location.search.includes('vista=mapa')); return <Link key={label} to={to} aria-current={active ? 'page' : undefined} className={cn('bottom-nav__item', label === 'Publicar' && 'bottom-nav__item--featured', active && 'is-active')}><Icon /><span>{label}</span></Link> })}</nav> }

export function Footer() { return <footer className="site-footer"><div className="container footer-grid"><div><Logo /><p>El marketplace especializado en habitaciones de Tenerife.</p></div><nav aria-label="Información"><strong>112233.es</strong><Link to="/sobre-nosotros">Sobre nosotros</Link><Link to="/como-funciona">Cómo funciona</Link><Link to="/contacto">Contacto</Link></nav><nav aria-label="Ayuda"><strong>Ayuda</strong><Link to="/ayuda">Centro de ayuda</Link><Link to="/normas-de-publicacion">Normas de publicación</Link><Link to="/publicar">Publicar</Link></nav><nav aria-label="Legal"><strong>Legal</strong><Link to="/terminos">Términos</Link><Link to="/privacidad">Privacidad</Link><Link to="/cookies">Cookies</Link></nav></div><div className="container footer-bottom"><span>© 2026 112233.es</span><span>Frontend demo con datos locales.</span></div></footer> }

export function AppLayout() {
  const { pathname } = useLocation()
  const hideFooter = pathname === '/buscar' || pathname === '/admin' || pathname === '/publicar' || pathname.includes('/editar') || ['/registro', '/acceso', '/recuperar-contrasena', '/restablecer-contrasena'].includes(pathname)
  return <><a className="skip-link" href="#main-content" onClick={(event) => { event.preventDefault(); document.getElementById('main-content')?.focus() }}>Saltar al contenido</a><Header /><MobileHeader /><main id="main-content" tabIndex={-1}><Outlet /></main>{hideFooter ? null : <Footer />}<BottomNavigation /><Toaster position="top-center" richColors closeButton /></>
}
