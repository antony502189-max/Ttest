import { useMemo, useState, type FormEvent } from 'react'
import { CalendarClock, Edit3, Eye, EyeOff, LogOut, MoreHorizontal, Plus, RotateCcw, Save, Trash2, UserRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { ConfirmDialog, FormField, StatusBadge } from '@/components/forms'
import { EmptyState, PropertyCard } from '@/components/marketplace'
import { useApp } from '@/contexts/app-context'
import { listings } from '@/data/listings'
import type { Listing, ListingStatus } from '@/types'

function AccountHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <header className="account-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</header>
}

export function FavoritesPage() {
  const { favorites } = useApp()
  const saved = listings.filter((listing) => favorites.has(listing.id))
  return <div className="container account-page"><AccountHeader eyebrow="Tu selección" title="Favoritos" description={`${saved.length} habitaciones guardadas`} action={<Button asChild variant="outline"><Link to="/buscar">Seguir buscando</Link></Button>} />{saved.length ? <div className="property-grid">{saved.map((listing) => <PropertyCard key={listing.id} listing={listing} compact />)}</div> : <EmptyState favorites />}</div>
}

export function ProfilePage() {
  const [editing, setEditing] = useState(false)
  const [saved, setSaved] = useState(false)
  const submit = (event: FormEvent) => { event.preventDefault(); setEditing(false); setSaved(true); toast.success('Perfil actualizado') }
  return <div className="container account-page"><AccountHeader eyebrow="Tu cuenta" title="Perfil" description="Controla cómo te ven anunciantes y futuros inquilinos." action={<Button variant={editing ? 'outline' : 'default'} onClick={() => setEditing((value) => !value)}><Edit3 data-icon="inline-start" />{editing ? 'Cancelar' : 'Editar perfil'}</Button>} /><div className="profile-layout"><aside className="profile-card"><Avatar className="profile-avatar"><AvatarFallback>LM</AvatarFallback></Avatar><h2>Lucía Martín</h2><p>Busco habitación</p><span className="profile-verified">Identidad básica verificada</span><Button variant="outline" size="sm">Cambiar foto</Button></aside><form className="profile-form" onSubmit={submit}><div className="form-grid"><FormField label="Nombre" htmlFor="profile-name"><Input id="profile-name" defaultValue="Lucía Martín" disabled={!editing} /></FormField><FormField label="Email" htmlFor="profile-email"><Input id="profile-email" defaultValue="lucia@example.es" type="email" disabled={!editing} /></FormField><FormField label="Teléfono" htmlFor="profile-phone"><Input id="profile-phone" defaultValue="+34 600 000 112" type="tel" disabled={!editing} /></FormField><FormField label="WhatsApp" htmlFor="profile-whatsapp"><Input id="profile-whatsapp" defaultValue="+34 600 000 112" type="tel" disabled={!editing} /></FormField></div><FormField label="Sobre mí" htmlFor="profile-about" description="Una breve presentación ayuda a iniciar la conversación."><Textarea id="profile-about" defaultValue="Trabajo en remoto y busco una habitación tranquila en el sur de Tenerife. Soy ordenada, no fumo y valoro una convivencia respetuosa." disabled={!editing} rows={4} /></FormField><fieldset className="privacy-settings"><legend>Privacidad de contacto</legend><label><div><strong>Mostrar teléfono a anunciantes</strong><span>Solo después de iniciar contacto</span></div><Switch defaultChecked disabled={!editing} /></label><label><div><strong>Permitir contacto por WhatsApp</strong><span>Los anunciantes verán tu número</span></div><Switch defaultChecked disabled={!editing} /></label></fieldset>{saved ? <p className="save-confirm" role="status">Cambios guardados correctamente.</p> : null}{editing ? <Button type="submit"><Save data-icon="inline-start" />Guardar cambios</Button> : null}<div className="danger-zone"><h2>Cuenta</h2><Button asChild variant="outline"><Link to="/acceso"><LogOut data-icon="inline-start" />Cerrar sesión</Link></Button><ConfirmDialog trigger={<Button variant="destructive"><Trash2 data-icon="inline-start" />Eliminar cuenta</Button>} title="¿Eliminar tu cuenta?" description="Se borrarán favoritos, mensajes y anuncios. Esta acción no se puede deshacer." confirmLabel="Eliminar definitivamente" destructive onConfirm={() => toast.error('Cuenta marcada para eliminación (demo)')} /></div></form></div></div>
}

const demoStatuses: ListingStatus[] = ['Publicado', 'Pendiente', 'Borrador', 'Oculto', 'Finalizado', 'Rechazado']

export function MyListingsPage() {
  const seed = useMemo(() => listings.slice(0, 6).map((listing, index) => ({ ...listing, status: demoStatuses[index] })), [])
  const [items, setItems] = useState<Listing[]>(seed)
  const remove = (id: string) => { setItems((current) => current.filter((item) => item.id !== id)); toast.success('Anuncio eliminado') }
  return <div className="container account-page"><AccountHeader eyebrow="Área del anunciante" title="Mis anuncios" description="Gestiona el estado, la vigencia y el rendimiento de tus habitaciones." action={<Button asChild><Link to="/publicar"><Plus data-icon="inline-start" />Nuevo anuncio</Link></Button>} />{items.length ? <div className="my-listings"><div className="listing-summary"><span><strong>{items.filter((item) => item.status === 'Publicado').length}</strong> publicados</span><span><strong>{items.reduce((sum, item) => sum + item.views, 0).toLocaleString('es-ES')}</strong> visualizaciones</span><span><strong>4</strong> contactos esta semana</span></div>{items.map((listing) => <article className="manage-card" key={listing.id}><img src={listing.images[0]} alt={`Habitación en ${listing.area}`} /><div className="manage-card__main"><div><StatusBadge status={listing.status} /><span>Ref. {listing.id.slice(-5).toUpperCase()}</span></div><h2>{listing.title}</h2><p>{listing.area} · {listing.price} €/{listing.cadence}</p><div className="manage-metrics"><span><Eye />{listing.views} vistas</span><span><CalendarClock />Finaliza {listing.expiresAt}</span></div></div><div className="manage-actions"><Button asChild variant="outline" size="sm"><Link to={`/mis-anuncios/${listing.id}/editar`}><Edit3 data-icon="inline-start" />Editar</Link></Button><DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon" aria-label={`Más acciones para ${listing.title}`}><MoreHorizontal /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuGroup><DropdownMenuItem onClick={() => { setItems((current) => current.map((item) => item.id === listing.id ? { ...item, status: item.status === 'Oculto' ? 'Publicado' : 'Oculto' } : item)); toast.success(listing.status === 'Oculto' ? 'Anuncio publicado' : 'Anuncio ocultado') }}>{listing.status === 'Oculto' ? <Eye /> : <EyeOff />}{listing.status === 'Oculto' ? 'Mostrar' : 'Ocultar'}</DropdownMenuItem><DropdownMenuItem onClick={() => toast.success('Anuncio renovado 30 días')}><RotateCcw />Renovar</DropdownMenuItem><DropdownMenuItem variant="destructive" onClick={() => remove(listing.id)}><Trash2 />Eliminar</DropdownMenuItem></DropdownMenuGroup></DropdownMenuContent></DropdownMenu></div></article>)}</div> : <div className="account-empty"><UserRound /><h2>Aún no tienes anuncios</h2><p>Crea tu primer anuncio y guárdalo como borrador cuando quieras.</p><Button asChild><Link to="/publicar">Crear anuncio</Link></Button></div>}</div>
}
