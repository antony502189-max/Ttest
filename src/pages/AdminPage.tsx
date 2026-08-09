import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react'
import {
  AlertTriangle,
  ArrowLeft,
  Ban,
  CheckCircle2,
  ClipboardList,
  FileSearch,
  Mail,
  MoreHorizontal,
  NotebookPen,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Shield,
  ShieldBan,
  Trash2,
  UserRound,
  Users,
  XCircle,
} from 'lucide-react'
import { Link } from 'react-router'
import { toast } from 'sonner'
import {
  addAdminNote,
  addAdministrator,
  deleteAdminUser,
  getAdminAuditLog,
  getAdminListings,
  getAdminNotes,
  getAdmins,
  getAdminUser,
  getAdminUserRows,
  restrictAdminListing,
  restrictAdminUser,
  revokeAdministrator,
  unrestrictAdminListing,
  unrestrictAdminUser,
  type AdminAccount,
  type AdminAuditLog,
  type AdminListing,
  type AdminNote,
  type AdminUser,
  type AdminUserDetail,
  type RestrictionType,
} from '@/api/admin'
import { getAdminReports, updateAdminReport, type AdminReport } from '@/api/reports'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { useApp } from '@/contexts/app-context'

const SUPPORT_EMAIL = 'tf.shuler@gmail.com'

type Section = 'users' | 'reports' | 'listings' | 'activity' | 'settings'
type UserFilter = '' | 'active' | 'restricted' | 'full' | 'publish' | 'view_listings' | 'deleted'
type RestrictionDuration = 'day' | 'week' | 'month' | 'forever' | 'custom'

const navItems: Array<{ id: Section; label: string; icon: typeof Users }> = [
  { id: 'users', label: 'Usuarios', icon: Users },
  { id: 'reports', label: 'Denuncias', icon: AlertTriangle },
  { id: 'listings', label: 'Anuncios', icon: FileSearch },
  { id: 'activity', label: 'Actividad', icon: ClipboardList },
  { id: 'settings', label: 'Ajustes', icon: Settings },
]

const restrictionLabels: Record<RestrictionType, string> = {
  full: 'Bloqueo completo',
  publish: 'No puede publicar',
  view_listings: 'No puede ver anuncios',
}

const durationLabels: Record<RestrictionDuration, string> = {
  day: '1 día',
  week: '1 semana',
  month: '1 mes',
  forever: 'Para siempre',
  custom: 'Fecha personalizada',
}

const reportLabels: Record<AdminReport['status'], string> = {
  open: 'Nueva',
  in_review: 'En revisión',
  resolved: 'Resuelta',
  rejected: 'Descartada',
}

const listingStatusLabels: Record<string, string> = {
  draft: 'Borrador',
  pending: 'Pendiente',
  published: 'Publicado',
  hidden: 'Oculto',
  closed: 'Finalizado',
  rejected: 'Rechazado',
}

function formatDate(value: string | null | undefined) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

function restrictionEndText(value: string | null | undefined) {
  return value ? `Hasta ${formatDate(value)}` : 'Sin fecha final'
}

function localDateTimeInput(value: Date) {
  const copy = new Date(value)
  copy.setMinutes(copy.getMinutes() - copy.getTimezoneOffset())
  return copy.toISOString().slice(0, 16)
}

function dateInputDefault(days = 7) {
  const value = new Date()
  value.setDate(value.getDate() + days)
  return localDateTimeInput(value)
}

function addCalendarMonth(value: Date) {
  const result = new Date(value)
  const targetDay = result.getDate()
  result.setDate(1)
  result.setMonth(result.getMonth() + 1)
  const lastDay = new Date(result.getFullYear(), result.getMonth() + 1, 0).getDate()
  result.setDate(Math.min(targetDay, lastDay))
  return result
}

function restrictionUntil(duration: RestrictionDuration, customUntil: string): string | null {
  if (duration === 'forever') return null
  if (duration === 'custom') {
    const parsed = new Date(customUntil)
    if (!customUntil || Number.isNaN(parsed.getTime()) || parsed <= new Date()) {
      throw new Error('Selecciona una fecha futura válida.')
    }
    return parsed.toISOString()
  }
  const value = new Date()
  if (duration === 'day') value.setDate(value.getDate() + 1)
  if (duration === 'week') value.setDate(value.getDate() + 7)
  if (duration === 'month') return addCalendarMonth(value).toISOString()
  return value.toISOString()
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'No se pudo completar la operación.'
}

function UserStatus({ user }: { user: AdminUser }) {
  if (user.deletedAt) return <Badge variant="destructive">Eliminada</Badge>
  if (user.activeRestriction) {
    return <Badge variant="destructive">{restrictionLabels[user.activeRestriction.restrictionType]}</Badge>
  }
  if (user.blocked) return <Badge variant="destructive">Bloqueada (legacy)</Badge>
  return <Badge variant="outline">Activa</Badge>
}

function EmptyState({ icon: Icon, title, description }: { icon: typeof Users; title: string; description: string }) {
  return <div className="admin-empty"><Icon /><strong>{title}</strong><p>{description}</p></div>
}

function SectionHeader({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) {
  return <header className="admin-section-head">
    <div><h1>{title}</h1><p>{description}</p></div>
    {actions ? <div className="admin-section-actions">{actions}</div> : null}
  </header>
}

function UserRestrictionDialog({
  user,
  open,
  onOpenChange,
  onSaved,
}: {
  user: AdminUser
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: (user: AdminUserDetail) => void
}) {
  const [type, setType] = useState<RestrictionType>('full')
  const [duration, setDuration] = useState<RestrictionDuration>('week')
  const [customUntil, setCustomUntil] = useState(dateInputDefault())
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const reset = () => {
    setType('full')
    setDuration('week')
    setCustomUntil(dateInputDefault())
    setReason('')
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!reason.trim()) return
    setSubmitting(true)
    try {
      const until = restrictionUntil(duration, customUntil)
      const updated = await restrictAdminUser(user.id, {
        restrictionType: type,
        until,
        reason: reason.trim(),
      })
      toast.success('Restricción aplicada y usuario notificado')
      onSaved(updated)
      onOpenChange(false)
      reset()
    } catch (error) {
      toast.error(errorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  return <Dialog open={open} onOpenChange={(next) => { onOpenChange(next); if (!next) reset() }}>
    <DialogContent className="admin-action-dialog">
      <DialogHeader>
        <DialogTitle>Restringir a {user.name}</DialogTitle>
        <DialogDescription>Elige exactamente qué dejará de poder hacer, durante cuánto tiempo y el motivo visible para el usuario.</DialogDescription>
      </DialogHeader>
      <form id="admin-user-restriction-form" className="admin-dialog-form" onSubmit={submit}>
        <label><span>Tipo de restricción</span><select value={type} onChange={(event) => setType(event.target.value as RestrictionType)}>
          <option value="full">Bloqueo completo</option>
          <option value="publish">No puede publicar anuncios</option>
          <option value="view_listings">No puede acceder a anuncios</option>
        </select></label>
        <label><span>Duración</span><select value={duration} onChange={(event) => setDuration(event.target.value as RestrictionDuration)}>
          <option value="day">1 día</option>
          <option value="week">1 semana</option>
          <option value="month">1 mes</option>
          <option value="forever">Para siempre</option>
          <option value="custom">Fecha personalizada</option>
        </select></label>
        {duration === 'custom' ? <label><span>Hasta</span><Input type="datetime-local" min={localDateTimeInput(new Date())} value={customUntil} onChange={(event) => setCustomUntil(event.target.value)} required /></label> : null}
        <label><span>Motivo que verá el usuario</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={2} maxLength={4000} required placeholder="Explica claramente por qué se aplica la restricción…" /></label>
        <div className="admin-dialog-summary">
          <ShieldBan />
          <p>Duración: <strong>{durationLabels[duration]}</strong>. Sus anuncios se ocultarán mientras exista la restricción. Se enviará un email y un aviso dentro de la cuenta.{duration === 'forever' ? ' Solo otro administrador podrá retirarla manualmente.' : ' Al finalizar, se retirará automáticamente.'}</p>
        </div>
      </form>
      <DialogFooter>
        <Button variant="outline" type="button" onClick={() => onOpenChange(false)}>Cancelar</Button>
        <Button form="admin-user-restriction-form" type="submit" variant="destructive" disabled={submitting || !reason.trim()}>{submitting ? 'Aplicando…' : 'Confirmar restricción'}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
}

function ListingRestrictionDialog({
  listing,
  open,
  onOpenChange,
  onSaved,
}: {
  listing: AdminListing
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: (listing: AdminListing) => void
}) {
  const [until, setUntil] = useState(dateInputDefault())
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitting(true)
    try {
      const updated = await restrictAdminListing(listing.id, {
        until: new Date(until).toISOString(),
        reason: reason.trim(),
      })
      toast.success('Anuncio restringido y propietario notificado')
      onSaved(updated)
      onOpenChange(false)
      setReason('')
      setUntil(dateInputDefault())
    } catch (error) {
      toast.error(errorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="admin-action-dialog">
      <DialogHeader><DialogTitle>Bloquear anuncio</DialogTitle><DialogDescription>{listing.title}</DialogDescription></DialogHeader>
      <form id="admin-listing-restriction-form" className="admin-dialog-form" onSubmit={submit}>
        <label><span>Hasta</span><Input type="datetime-local" min={localDateTimeInput(new Date())} value={until} onChange={(event) => setUntil(event.target.value)} required /></label>
        <label><span>Motivo que verá el propietario</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={2} maxLength={4000} required placeholder="Motivo de la retirada temporal…" /></label>
      </form>
      <DialogFooter>
        <Button variant="outline" type="button" onClick={() => onOpenChange(false)}>Cancelar</Button>
        <Button form="admin-listing-restriction-form" type="submit" variant="destructive" disabled={submitting || !reason.trim()}>{submitting ? 'Aplicando…' : 'Bloquear anuncio'}</Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
}

function DeleteUserDialog({ user, open, onOpenChange, onDeleted }: { user: AdminUser; open: boolean; onOpenChange: (open: boolean) => void; onDeleted: () => void }) {
  const [confirmation, setConfirmation] = useState('')
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (confirmation !== 'DELETE' || !reason.trim()) return
    setSubmitting(true)
    try {
      await deleteAdminUser(user.id, reason.trim())
      toast.success('Cuenta eliminada')
      onDeleted()
      onOpenChange(false)
    } catch (error) {
      toast.error(errorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }
  return <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent className="admin-action-dialog">
      <DialogHeader><DialogTitle>Eliminar cuenta de {user.name}</DialogTitle><DialogDescription>La cuenta se desactivará, dejará de ser accesible y sus anuncios desaparecerán de la parte pública. La auditoría y las denuncias se conservarán.</DialogDescription></DialogHeader>
      <form id="admin-delete-user-form" className="admin-dialog-form" onSubmit={submit}>
        <label><span>Motivo</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={2} required /></label>
        <label><span>Escribe DELETE para confirmar</span><Input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} autoComplete="off" /></label>
      </form>
      <DialogFooter><Button variant="outline" type="button" onClick={() => onOpenChange(false)}>Cancelar</Button><Button form="admin-delete-user-form" type="submit" variant="destructive" disabled={submitting || confirmation !== 'DELETE' || !reason.trim()}><Trash2 /> Eliminar cuenta</Button></DialogFooter>
    </DialogContent>
  </Dialog>
}

function UserDetailView({
  userId,
  listings,
  reports,
  onBack,
  onUserChanged,
}: {
  userId: string
  listings: AdminListing[]
  reports: AdminReport[]
  onBack: () => void
  onUserChanged: (user: AdminUser) => void
}) {
  const [user, setUser] = useState<AdminUserDetail | null>(null)
  const [notes, setNotes] = useState<AdminNote[]>([])
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(true)
  const [restrictOpen, setRestrictOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [detail, loadedNotes] = await Promise.all([getAdminUser(userId), getAdminNotes(userId)])
      setUser(detail)
      setNotes(loadedNotes)
    } catch (error) {
      toast.error(errorMessage(error))
      onBack()
    } finally {
      setLoading(false)
    }
  }, [onBack, userId])

  useEffect(() => { void load() }, [load])

  const ownedListings = useMemo(() => listings.filter((listing) => listing.ownerUserId === userId), [listings, userId])
  const listingIds = useMemo(() => new Set(ownedListings.map((listing) => listing.id)), [ownedListings])
  const relatedReports = useMemo(() => reports.filter((report) => listingIds.has(report.listingId)), [listingIds, reports])

  if (loading || !user) return <div className="admin-detail-loading"><RefreshCw className="spin" /> Cargando usuario…</div>

  const saveRestriction = (updated: AdminUserDetail) => {
    setUser(updated)
    onUserChanged(updated)
  }

  const unrestrict = async () => {
    try {
      const updated = await unrestrictAdminUser(user.id)
      saveRestriction(updated)
      toast.success('Restricción retirada y usuario notificado')
    } catch (error) { toast.error(errorMessage(error)) }
  }

  const saveNote = async (event: FormEvent) => {
    event.preventDefault()
    if (!note.trim()) return
    try {
      const saved = await addAdminNote(user.id, note.trim())
      setNotes((current) => [saved, ...current])
      setNote('')
      toast.success('Nota interna guardada')
    } catch (error) { toast.error(errorMessage(error)) }
  }

  return <div className="admin-user-detail">
    <button type="button" className="admin-back" onClick={onBack}><ArrowLeft /> Volver a usuarios</button>
    <section className="admin-user-hero">
      <div className="admin-avatar">{user.initials || user.name.slice(0, 2).toUpperCase()}</div>
      <div><div className="admin-title-line"><h1>{user.name}</h1><UserStatus user={user} />{user.isAdmin ? <Badge><Shield /> Admin</Badge> : null}</div><p>{user.email}</p><small>ID {user.id}</small></div>
      <div className="admin-user-actions">
        {user.activeRestriction ? <Button variant="outline" onClick={() => { void unrestrict() }}><CheckCircle2 /> Desbloquear ahora</Button> : <Button variant="destructive" disabled={user.isAdmin} onClick={() => setRestrictOpen(true)}><Ban /> Restringir</Button>}
        <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline" size="icon" aria-label="Más acciones"><MoreHorizontal /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem variant="destructive" disabled={user.isAdmin} onSelect={() => setDeleteOpen(true)}><Trash2 /> Eliminar cuenta</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
      </div>
    </section>

    {user.isAdmin ? <div className="admin-callout"><Shield /><p>Esta cuenta es administradora. Para restringirla o eliminarla primero hay que revocar sus permisos en Ajustes → Administradores.</p></div> : null}
    {user.activeRestriction ? <div className="admin-active-restriction"><ShieldBan /><div><strong>{restrictionLabels[user.activeRestriction.restrictionType]}</strong><p>{user.activeRestriction.reason}</p><span>{restrictionEndText(user.activeRestriction.endsAt)}</span></div></div> : null}

    <div className="admin-detail-grid">
      <section className="admin-detail-card"><h2>Cuenta</h2><dl>
        <div><dt>Teléfono</dt><dd>{user.phone || '—'}</dd></div>
        <div><dt>Registro</dt><dd>{formatDate(user.createdAt)}</dd></div>
        <div><dt>Último acceso</dt><dd>{formatDate(user.lastLoginAt)}</dd></div>
        <div><dt>Anuncios</dt><dd>{user.listingCount}</dd></div>
        <div><dt>Rol de producto</dt><dd>{user.role}</dd></div>
      </dl></section>
      <section className="admin-detail-card"><h2>Soporte</h2><p>Los avisos de moderación incluyen el motivo, la fecha final —si existe— y esta dirección.</p><a className="admin-support-link" href={`mailto:${SUPPORT_EMAIL}`}><Mail /> {SUPPORT_EMAIL}</a></section>
    </div>

    <section className="admin-detail-card"><div className="admin-card-head"><div><h2>Anuncios</h2><p>{ownedListings.length} asociados a esta cuenta</p></div></div>
      {ownedListings.length ? <div className="admin-compact-list">{ownedListings.map((listing) => <div key={listing.id}><div><strong>{listing.title}</strong><span>{listing.area} · {listingStatusLabels[listing.status] ?? listing.status}</span></div>{listing.activeRestriction ? <Badge variant="destructive">Restringido</Badge> : <Badge variant="outline">Visible según estado</Badge>}</div>)}</div> : <EmptyState icon={FileSearch} title="Sin anuncios" description="Esta cuenta todavía no tiene anuncios." />}
    </section>

    <section className="admin-detail-card"><div className="admin-card-head"><div><h2>Denuncias relacionadas</h2><p>{relatedReports.length} sobre sus anuncios o su cuenta</p></div></div>
      {relatedReports.length ? <div className="admin-compact-list">{relatedReports.map((report) => <div key={report.id}><div><strong>{report.reason}</strong><span>{report.publicReference} · {formatDate(report.createdAt)}</span></div><Badge variant="outline">{reportLabels[report.status]}</Badge></div>)}</div> : <EmptyState icon={AlertTriangle} title="Sin denuncias" description="No hay denuncias asociadas a esta cuenta." />}
    </section>

    <section className="admin-detail-card"><div className="admin-card-head"><div><h2>Historial de restricciones</h2><p>Registro cronológico no editable.</p></div></div>
      {user.restrictions.length ? <div className="admin-history">{user.restrictions.map((item) => <article key={item.id}><span className={item.active ? 'is-active' : ''} /><div><strong>{restrictionLabels[item.restrictionType]}</strong><p>{item.reason}</p><small>{formatDate(item.startsAt)} → {item.endsAt ? formatDate(item.endsAt) : 'Sin fecha final'}{item.revokedAt ? ` · Retirada: ${formatDate(item.revokedAt)}` : ''}</small></div></article>)}</div> : <EmptyState icon={Shield} title="Sin historial" description="Nunca se aplicaron restricciones a esta cuenta." />}
    </section>

    <section className="admin-detail-card"><div className="admin-card-head"><div><h2>Notas internas</h2><p>Solo las ven los administradores.</p></div></div>
      <form className="admin-note-form" onSubmit={saveNote}><textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={4000} placeholder="Añadir contexto para futuras revisiones…" /><Button type="submit" disabled={!note.trim()}><NotebookPen /> Guardar nota</Button></form>
      {notes.length ? <div className="admin-note-list">{notes.map((item) => <article key={item.id}><p>{item.body}</p><small>{item.createdByName ?? 'Admin'} · {formatDate(item.createdAt)}</small></article>)}</div> : null}
    </section>

    <UserRestrictionDialog user={user} open={restrictOpen} onOpenChange={setRestrictOpen} onSaved={saveRestriction} />
    <DeleteUserDialog user={user} open={deleteOpen} onOpenChange={setDeleteOpen} onDeleted={() => { onUserChanged({ ...user, deletedAt: new Date().toISOString() }); onBack() }} />
  </div>
}

export function AdminPage() {
  const { currentUser } = useApp()
  const [section, setSection] = useState<Section>('users')
  const [users, setUsers] = useState<AdminUser[]>([])
  const [listings, setListings] = useState<AdminListing[]>([])
  const [reports, setReports] = useState<AdminReport[]>([])
  const [auditLog, setAuditLog] = useState<AdminAuditLog[]>([])
  const [admins, setAdmins] = useState<AdminAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [userFilter, setUserFilter] = useState<UserFilter>('')
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const [listingRestriction, setListingRestriction] = useState<AdminListing | null>(null)
  const [newAdminEmail, setNewAdminEmail] = useState('')
  const [addingAdmin, setAddingAdmin] = useState(false)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [loadedUsers, loadedListings, loadedReports, loadedAudit, loadedAdmins] = await Promise.all([
        getAdminUserRows(),
        getAdminListings(),
        getAdminReports(),
        getAdminAuditLog(),
        getAdmins(),
      ])
      setUsers(loadedUsers)
      setListings(loadedListings)
      setReports(loadedReports)
      setAuditLog(loadedAudit)
      setAdmins(loadedAdmins)
    } catch (error) {
      toast.error(errorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void loadAll() }, [loadAll])

  const visibleUsers = useMemo(() => users.filter((user) => {
    const matchesName = !query.trim() || user.name.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())
    if (!matchesName) return false
    if (!userFilter) return !user.deletedAt
    if (userFilter === 'deleted') return Boolean(user.deletedAt)
    if (user.deletedAt) return false
    if (userFilter === 'active') return !user.activeRestriction && !user.blocked
    if (userFilter === 'restricted') return Boolean(user.activeRestriction)
    return user.activeRestriction?.restrictionType === userFilter
  }), [query, userFilter, users])

  const visibleListings = useMemo(() => listings.filter((listing) => {
    if (!query.trim()) return true
    const needle = query.toLocaleLowerCase()
    return `${listing.title} ${listing.ownerName ?? ''} ${listing.area}`.toLocaleLowerCase().includes(needle)
  }), [listings, query])

  const visibleReports = useMemo(() => [...reports].sort((a, b) => b.createdAt.localeCompare(a.createdAt)), [reports])

  const updateUserRow = (changed: AdminUser) => setUsers((current) => current.map((user) => user.id === changed.id ? { ...user, ...changed } : user))
  const updateListingRow = (changed: AdminListing) => setListings((current) => current.map((listing) => listing.id === changed.id ? changed : listing))

  const changeReportStatus = async (report: AdminReport, status: AdminReport['status']) => {
    try {
      const updated = await updateAdminReport(report.id, status)
      setReports((current) => current.map((item) => item.id === updated.id ? updated : item))
      toast.success(`Denuncia: ${reportLabels[status]}`)
    } catch (error) { toast.error(errorMessage(error)) }
  }

  const removeListingRestriction = async (listing: AdminListing) => {
    try {
      const updated = await unrestrictAdminListing(listing.id)
      updateListingRow(updated)
      toast.success('Restricción retirada y propietario notificado')
    } catch (error) { toast.error(errorMessage(error)) }
  }

  const addAdmin = async (event: FormEvent) => {
    event.preventDefault()
    if (!newAdminEmail.trim()) return
    setAddingAdmin(true)
    try {
      const added = await addAdministrator(newAdminEmail.trim())
      setAdmins((current) => [...current.filter((item) => item.email !== added.email), added].sort((a, b) => a.email.localeCompare(b.email)))
      setNewAdminEmail('')
      toast.success('Administrador añadido')
    } catch (error) { toast.error(errorMessage(error)) } finally { setAddingAdmin(false) }
  }

  const revokeAdmin = async (email: string) => {
    if (!confirm(`¿Revocar acceso de administrador a ${email}?`)) return
    try {
      await revokeAdministrator(email)
      setAdmins((current) => current.filter((item) => item.email !== email))
      setUsers((current) => current.map((user) => user.email.toLowerCase() === email.toLowerCase() ? { ...user, isAdmin: false } : user))
      toast.success('Acceso de administrador revocado')
    } catch (error) { toast.error(errorMessage(error)) }
  }

  if (selectedUserId) {
    return <div className="admin-page admin-page--detail"><AdminSidebar section={section} onSection={(next) => { setSelectedUserId(null); setSection(next) }} currentUserName={currentUser?.name} /><main className="admin-main"><UserDetailView userId={selectedUserId} listings={listings} reports={reports} onBack={() => setSelectedUserId(null)} onUserChanged={updateUserRow} /></main></div>
  }

  return <div className="admin-page">
    <AdminSidebar section={section} onSection={(next) => { setSection(next); setQuery('') }} currentUserName={currentUser?.name} reportCount={reports.filter((report) => report.status === 'open').length} />
    <main className="admin-main">
      {section === 'users' ? <>
        <SectionHeader title="Usuarios" description="Busca una cuenta, revisa su contexto y aplica solo la restricción necesaria." actions={<Button variant="outline" onClick={() => { void loadAll() }} disabled={loading}><RefreshCw /> Actualizar</Button>} />
        <div className="admin-toolbar"><div className="admin-search"><Search /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por nombre…" aria-label="Buscar usuarios por nombre" /></div><select value={userFilter} onChange={(event) => setUserFilter(event.target.value as UserFilter)} aria-label="Filtrar usuarios"><option value="">Todos</option><option value="active">Activos</option><option value="restricted">Con restricción</option><option value="full">Bloqueo completo</option><option value="publish">Sin publicación</option><option value="view_listings">Sin acceso a anuncios</option><option value="deleted">Eliminados</option></select></div>
        {loading ? <div className="admin-detail-loading"><RefreshCw className="spin" /> Cargando…</div> : visibleUsers.length ? <div className="admin-user-list">{visibleUsers.map((user) => <button type="button" className="admin-user-row" key={user.id} onClick={() => setSelectedUserId(user.id)}><div className="admin-avatar admin-avatar--small">{user.initials || user.name.slice(0, 2).toUpperCase()}</div><div className="admin-user-primary"><strong>{user.name}</strong><span>{user.email}</span></div><div className="admin-user-meta"><span>{user.listingCount} anuncios</span><span>Último acceso: {formatDate(user.lastLoginAt)}</span></div><UserStatus user={user}/><span className="admin-row-arrow">›</span></button>)}</div> : <EmptyState icon={Users} title="Sin resultados" description="No hay usuarios que coincidan con este filtro." />}
      </> : null}

      {section === 'reports' ? <>
        <SectionHeader title="Denuncias" description="Revisa el contexto y llega al usuario o al anuncio sin tener que buscarlo manualmente." />
        {visibleReports.length ? <div className="admin-report-list">{visibleReports.map((report) => {
          const listing = listings.find((item) => item.id === report.listingId)
          return <article key={report.id} className="admin-report-card"><header><div><strong>{report.reason}</strong><span>{report.publicReference} · {formatDate(report.createdAt)}</span></div><Badge variant={report.status === 'open' ? 'destructive' : 'outline'}>{reportLabels[report.status]}</Badge></header><p>{report.comment || 'Sin comentario adicional.'}</p><div className="admin-report-context"><span>Objetivo: <b>{report.targetType === 'user' ? 'Usuario' : 'Anuncio'}</b></span><span>Anuncio: <b>{listing?.title ?? report.listingId}</b></span><span>Usuario: <b>{listing?.ownerName ?? '—'}</b></span></div><footer>{listing ? <><Button variant="outline" size="sm" onClick={() => setSelectedUserId(listing.ownerUserId)}><UserRound /> Ver usuario</Button><Button variant="outline" size="sm" onClick={() => { setSection('listings'); setQuery(listing.title) }}><FileSearch /> Ver anuncio</Button></> : null}{report.status === 'open' ? <Button size="sm" onClick={() => { void changeReportStatus(report, 'in_review') }}>Tomar revisión</Button> : null}{report.status !== 'resolved' ? <Button size="sm" onClick={() => { void changeReportStatus(report, 'resolved') }}><CheckCircle2 /> Resolver</Button> : null}{report.status !== 'rejected' ? <Button variant="outline" size="sm" onClick={() => { void changeReportStatus(report, 'rejected') }}><XCircle /> Descartar</Button> : null}</footer></article>
        })}</div> : <EmptyState icon={AlertTriangle} title="Sin denuncias" description="No hay reportes pendientes ni históricos disponibles." />}
      </> : null}

      {section === 'listings' ? <>
        <SectionHeader title="Anuncios" description="Consulta el propietario y bloquea temporalmente un anuncio sin alterar permanentemente su estado original." />
        <div className="admin-toolbar"><div className="admin-search"><Search /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Título, usuario o zona…" /></div></div>
        {visibleListings.length ? <div className="admin-listing-list">{visibleListings.map((listing) => <article key={listing.id} className="admin-listing-row"><div><strong>{listing.title}</strong><span>{listing.area} · {listing.ownerName ?? 'Sin propietario'}</span><small>{listingStatusLabels[listing.status] ?? listing.status} · {listing.views} visitas</small></div><div className="admin-listing-state">{listing.activeRestriction ? <><Badge variant="destructive">Bloqueado hasta {formatDate(listing.activeRestriction.endsAt)}</Badge><span>{listing.activeRestriction.reason}</span></> : <Badge variant="outline">Sin bloqueo administrativo</Badge>}</div><div className="admin-listing-actions"><Button variant="outline" size="sm" onClick={() => setSelectedUserId(listing.ownerUserId)}><UserRound /> Usuario</Button>{listing.activeRestriction ? <Button size="sm" onClick={() => { void removeListingRestriction(listing) }}><CheckCircle2 /> Desbloquear</Button> : <Button variant="destructive" size="sm" onClick={() => setListingRestriction(listing)}><Ban /> Bloquear</Button>}</div></article>)}</div> : <EmptyState icon={FileSearch} title="Sin anuncios" description="No hay anuncios que coincidan con la búsqueda." />}
      </> : null}

      {section === 'activity' ? <>
        <SectionHeader title="Actividad" description="Historial de acciones administrativas: quién hizo qué y cuándo." />
        {auditLog.length ? <div className="admin-audit-list">{auditLog.map((item) => <article key={item.id}><span className="admin-audit-icon"><ClipboardList /></span><div><strong>{item.action}</strong><p>{item.actorName ?? 'Sistema'} · {item.targetType}{item.targetId ? ` · ${item.targetId}` : ''}</p><small>{formatDate(item.createdAt)}</small></div><pre>{Object.keys(item.detail).length ? JSON.stringify(item.detail, null, 2) : ''}</pre></article>)}</div> : <EmptyState icon={ClipboardList} title="Sin actividad" description="Las acciones administrativas aparecerán aquí." />}
      </> : null}

      {section === 'settings' ? <>
        <SectionHeader title="Ajustes" description="Gestiona quién puede entrar en esta administración mediante una cuenta Google vinculada." />
        <section className="admin-detail-card admin-admins-card"><div className="admin-card-head"><div><h2>Administradores</h2><p>Todos tienen los mismos permisos. No se puede eliminar el último administrador ni revocar tus propios permisos desde aquí.</p></div></div><form className="admin-add-admin" onSubmit={addAdmin}><Input type="email" value={newAdminEmail} onChange={(event) => setNewAdminEmail(event.target.value)} placeholder="nuevo-admin@gmail.com" required /><Button type="submit" disabled={addingAdmin || !newAdminEmail.trim()}><Plus /> Añadir administrador</Button></form><div className="admin-admin-list">{admins.map((admin) => <div key={admin.email}><div><Shield /><span><strong>{admin.email}</strong><small>Activo desde {formatDate(admin.createdAt)}</small></span></div><Button variant="outline" size="sm" disabled={admin.email.toLowerCase() === currentUser?.email.toLowerCase()} onClick={() => { void revokeAdmin(admin.email) }}>Revocar acceso</Button></div>)}</div></section>
        <section className="admin-detail-card"><h2>Correo de soporte</h2><p>Se muestra al usuario en bloqueos, avisos y correos de moderación.</p><a className="admin-support-link" href={`mailto:${SUPPORT_EMAIL}`}><Mail /> {SUPPORT_EMAIL}</a></section>
      </> : null}
    </main>
    {listingRestriction ? <ListingRestrictionDialog listing={listingRestriction} open onOpenChange={(open) => { if (!open) setListingRestriction(null) }} onSaved={(updated) => { updateListingRow(updated); setListingRestriction(null) }} /> : null}
  </div>
}

function AdminSidebar({ section, onSection, currentUserName, reportCount = 0 }: { section: Section; onSection: (section: Section) => void; currentUserName?: string; reportCount?: number }) {
  return <aside className="admin-sidebar"><Link to="/" className="admin-brand">11·22·33 <span>admin</span></Link><nav aria-label="Administración">{navItems.map(({ id, label, icon: Icon }) => <button key={id} type="button" onClick={() => onSection(id)} aria-current={section === id ? 'page' : undefined}><Icon />{label}{id === 'reports' && reportCount ? <span>{reportCount}</span> : null}</button>)}</nav><div className="admin-user"><div>{(currentUserName || 'A').slice(0, 2).toUpperCase()}</div><span><strong>{currentUserName || 'Admin'}</strong><small>Administración</small></span></div></aside>
}
