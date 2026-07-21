import { Bell, ChevronRight, CircleHelp, FileText, Heart, Home, Languages, LogOut, MessageCircle, Plus, Search, UserRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { LanguageSwitcher, Logo } from '@/components/layout'
import { useApp } from '@/contexts/app-context'

const MenuRow = ({ to, icon: Icon, children }: { to: string; icon: typeof Home; children: string }) => <Link className="app-menu-row" to={to}><Icon aria-hidden="true" /><span>{children}</span><ChevronRight aria-hidden="true" /></Link>

export function MenuPage() {
  const { currentUser, logout } = useApp()
  return <section className="mobile-app-page menu-page" aria-labelledby="menu-title">
    <header className="mobile-app-page__header"><div><Logo /><h1 id="menu-title">Menú</h1></div></header>
    <div className="menu-account-block">
      <Avatar><AvatarFallback>{currentUser?.initials ?? <UserRound aria-hidden="true" />}</AvatarFallback></Avatar>
      <div>{currentUser ? <><strong>{currentUser.name}</strong><span>{currentUser.email}</span><Link to="/perfil">Ir a mi perfil</Link></> : <><strong>Tu cuenta</strong><span>Guarda búsquedas y publica habitaciones.</span><Link to="/acceso">Inicia sesión o regístrate</Link></>}</div>
    </div>
    <nav className="app-menu-list" aria-label="Cuenta y anuncios">
      {currentUser ? <MenuRow to="/mis-anuncios" icon={Home}>Mis anuncios</MenuRow> : null}
      <MenuRow to="/publicar" icon={Plus}>Publicar anuncio</MenuRow>
      <MenuRow to="/favoritos" icon={Heart}>Favoritos</MenuRow>
      <MenuRow to="/busquedas-guardadas" icon={Search}>Búsquedas guardadas</MenuRow>
      <MenuRow to="/mensajes" icon={MessageCircle}>Mensajes</MenuRow>
    </nav>
    <Separator />
    <div className="menu-language-row"><Languages aria-hidden="true" /><span>Idioma</span><LanguageSwitcher /></div>
    <nav className="app-menu-list" aria-label="Ayuda y legal">
      <MenuRow to="/ayuda" icon={CircleHelp}>Ayuda</MenuRow>
      <MenuRow to="/como-funciona" icon={FileText}>Cómo funciona</MenuRow>
      <MenuRow to="/privacidad" icon={FileText}>Privacidad y legal</MenuRow>
    </nav>
    {currentUser ? <Button variant="ghost" className="menu-signout" onClick={logout}><LogOut data-icon="inline-start" />Cerrar sesión</Button> : null}
  </section>
}

export function MessagesPage() {
  return <section className="mobile-app-page messages-page" aria-labelledby="messages-title">
    <header className="mobile-app-page__header"><div><span className="eyebrow">Tu actividad</span><h1 id="messages-title">Mensajes</h1></div></header>
    <div className="messages-empty"><div><Bell aria-hidden="true" /></div><h2>Todavía no hay mensajes</h2><p>Cuando registres un contacto local, podrás volver al anuncio desde aquí. Esta demo no envía mensajes por internet.</p><Button asChild><Link to="/buscar">Explorar habitaciones</Link></Button></div>
  </section>
}
