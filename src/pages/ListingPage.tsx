import { useEffect, useState } from 'react'
import { ArrowLeft, Bath, BedDouble, Check, CircleAlert, CookingPot, Heart, Home, MapPin, MessageSquareText, MoreHorizontal, Pencil, Ruler, Share2, ShieldCheck, Trash2, UsersRound } from 'lucide-react'
import { Link, Navigate, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Separator } from '@/components/ui/separator'
import { DropdownMenu, DropdownMenuContent, DropdownMenuGroup, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { ContactPanel, MapView, PriceBlock, PropertyBadge, PropertyCard, PropertyGallery, ReportDialog } from '@/components/marketplace'
import { UserReportDialog } from '@/components/user-report-dialog'
import { useApp } from '@/contexts/app-context'
import { getPublicListing } from '@/api/listings'
import { formatPublishedAt } from '@/lib/search'
import { getCriticalRestrictions, getPrimaryCadence, getPrimaryPrice, isPublicListing, unknownListingFact } from '@/lib/listings'
import type { Listing } from '@/types'

const preferenceTitle = (value?: string) => value === 'Solo hombre' ? 'Este anuncio busca a un hombre' : value === 'Solo mujer' ? 'Este anuncio busca a una mujer' : value
const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
const householdLabels: Record<string, string> = { men: 'Hombres', women: 'Mujeres', mixed: 'Convivencia mixta', unknown: 'No especificado' }
const heatingLabels: Record<string, string> = { individual: 'Calefacción individual', central: 'Calefacción central', none: 'Sin calefacción', unknown: 'Calefacción no especificada' }
const tenantTypeLabels: Record<string, string> = { man: 'Hombres', woman: 'Mujeres', couple: 'Parejas', family: 'Familias' }

function ExternalListingRedirect({ sourceUrl }: { sourceUrl: string }) {
  useEffect(() => { window.location.replace(sourceUrl) }, [sourceUrl])
  return null
}

export function ListingPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { allListings, favorites, toggleFavorite, discardListing, localComments, addLocalComment, updateLocalComment, deleteLocalComment } = useApp()
  const [reportOpen, setReportOpen] = useState(false)
  const [userReportOpen, setUserReportOpen] = useState(false)
  const [commentEditorOpen, setCommentEditorOpen] = useState(false)
  const [commentText, setCommentText] = useState('')
  const [editingCommentId, setEditingCommentId] = useState<string | null>(null)
  const [serverListing, setServerListing] = useState<Listing | null>(null)
  const [detailLoading, setDetailLoading] = useState(true)

  useEffect(() => {
    if (!id || mockMode) { setDetailLoading(false); return }
    let cancelled = false
    setDetailLoading(true)
    setServerListing(null)
    void getPublicListing(id).then((listing) => { if (!cancelled) setServerListing(listing) }).catch(() => { if (!cancelled) setServerListing(null) }).finally(() => { if (!cancelled) setDetailLoading(false) })
    return () => { cancelled = true }
  }, [id])

  const listing = serverListing ?? allListings.find((item) => item.id === id && isPublicListing(item))
  if (!listing && detailLoading) return null
  if (!listing) return <Navigate to="/buscar" replace />
  if (listing.isExternal && listing.sourceUrl) return <ExternalListingRedirect sourceUrl={listing.sourceUrl} />

  const criticalRestrictions = getCriticalRestrictions(listing)
  const primaryRestriction = criticalRestrictions[0]
  const similar = allListings.filter((item) => item.id !== listing.id && item.status === 'Publicado' && item.rentalMode === listing.rentalMode).sort((a, b) => Number(b.area === listing.area) - Number(a.area === listing.area) || Math.abs(getPrimaryPrice(a) - getPrimaryPrice(listing)) - Math.abs(getPrimaryPrice(b) - getPrimaryPrice(listing))).slice(0, 3)
  const saved = favorites.has(listing.id)
  const listingComments = localComments.filter((comment) => comment.listingId === listing.id)
  const availableSpots = listing.availableSpots ?? (listing.roomCapacity != null && listing.currentRoomResidents != null ? Math.max(0, listing.roomCapacity - listing.currentRoomResidents) : null)
  const bedLabel = listing.bedCount == null || listing.bedType == null ? unknownListingFact : `${listing.bedCount} ${listing.bedCount === 1 ? 'cama' : 'camas'} ${listing.bedType === 'double' ? 'doble' : 'individual'}`
  const rentalUnitLabel = listing.rentalUnit === 'bed' ? 'Se alquilan plazas individuales' : listing.rentalUnit === 'room' ? 'Se alquila la habitación completa' : unknownListingFact

  const share = async () => {
    const data = { title: listing.title, text: `Habitación en ${listing.area} por ${getPrimaryPrice(listing)} €`, url: window.location.href }
    try { if (navigator.share) await navigator.share(data); else { await navigator.clipboard.writeText(window.location.href); toast.success('Enlace copiado') } }
    catch (error) { if ((error as DOMException).name !== 'AbortError') toast.error('No se pudo compartir el anuncio') }
  }
  const discard = () => { discardListing(listing.id); toast.success('Anuncio descartado'); navigate('/buscar') }
  const closeCommentEditor = () => { setCommentEditorOpen(false); setEditingCommentId(null); setCommentText('') }
  const saveComment = () => { const value = commentText.trim(); if (!value) return; if (editingCommentId) updateLocalComment(editingCommentId, value); else addLocalComment(listing.id, value); closeCommentEditor() }

  return (
    <article className="listing-page idealista-listing-page">
      <div className="container listing-actionbar">
        <Button asChild variant="ghost" size="icon"><Link to="/buscar" aria-label="Volver al listado"><ArrowLeft /></Link></Button>
        <div><Button variant="ghost" size="icon" onClick={() => toggleFavorite(listing.id)} aria-label={saved ? 'Guardado' : 'Guardar'} aria-pressed={saved}><Heart fill={saved ? 'currentColor' : 'none'} /></Button><Button variant="ghost" size="icon" onClick={share} aria-label="Compartir"><Share2 /></Button><DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon" aria-label="Más acciones del anuncio"><MoreHorizontal /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuGroup><DropdownMenuItem onSelect={discard}><Trash2 />Descartar</DropdownMenuItem><DropdownMenuItem onSelect={() => setReportOpen(true)}><CircleAlert />Denunciar anuncio</DropdownMenuItem><DropdownMenuItem onSelect={() => setUserReportOpen(true)}><CircleAlert />Denunciar anunciante</DropdownMenuItem></DropdownMenuGroup></DropdownMenuContent></DropdownMenu></div>
      </div>

      <ReportDialog listing={listing} open={reportOpen} onOpenChange={setReportOpen} trigger={false} />
      <UserReportDialog listing={listing} open={userReportOpen} onOpenChange={setUserReportOpen} />
      <div className="container listing-gallery-container"><PropertyGallery listing={listing} /></div>
      <div className="container listing-layout">
        <div className="listing-main">
          <header className="listing-title"><div><h1>Habitación en {listing.area}, {listing.city}</h1><p>{listing.title}</p><span className="listing-address"><MapPin aria-hidden="true" />{listing.approximateAddress}</span></div><PriceBlock listing={listing} large /></header>
          <div className="listing-keyfacts" tabIndex={0} role="region" aria-label="Resumen de la habitación"><span>{listing.roomType}</span><span>{rentalUnitLabel}</span><span>{listing.roomSizeM2 == null ? unknownListingFact : `${listing.roomSizeM2} m²`}</span><span>{availableSpots == null ? unknownListingFact : `${availableSpots} ${availableSpots === 1 ? 'plaza libre' : 'plazas libres'}`}</span></div>
          <div className="listing-inline-actions" aria-label="Acciones del anuncio"><Button variant="ghost" onClick={() => toggleFavorite(listing.id)} aria-label={saved ? 'Quitar de favoritos' : 'Añadir a favoritos'} aria-pressed={saved}><Heart fill={saved ? 'currentColor' : 'none'} />{saved ? 'Guardado' : 'Guardar'}</Button><Button variant="ghost" onClick={discard} aria-label="Ocultar anuncio"><Trash2 />Descartar</Button><Button variant="ghost" onClick={share} aria-label="Enviar enlace del anuncio"><Share2 />Compartir</Button></div>
          {primaryRestriction ? <section className="listing-restriction-notice" aria-labelledby="restriction-title"><UsersRound aria-hidden="true" /><div><span>Condición principal</span><h2 id="restriction-title">{preferenceTitle(primaryRestriction)}</h2><p>Comprueba esta preferencia visible del anunciante antes de contactar. Puedes seguir consultando el anuncio sin interrupciones.</p></div></section> : null}

          <section className="listing-comments" aria-labelledby="listing-comments-title">
            <Button variant="ghost" className="listing-comment-add" onClick={() => { setEditingCommentId(null); setCommentText(''); setCommentEditorOpen(true) }}><MessageSquareText data-icon="inline-start" />Añadir comentario</Button>
            {listing.homeDescription ? <div className="advertiser-comment"><h2 id="listing-comments-title">Comentario del anunciante</h2><p>{listing.homeDescription}</p></div> : <h2 id="listing-comments-title" className="sr-only">Comentarios</h2>}
            {commentEditorOpen ? <div className="listing-comment-editor"><label htmlFor="local-listing-comment">{editingCommentId ? 'Editar comentario' : 'Comentario personal'}</label><Textarea id="local-listing-comment" rows={4} maxLength={600} value={commentText} autoFocus onChange={(event) => setCommentText(event.target.value)} placeholder="Escribe una nota sobre este anuncio" /><p>Se guarda solo en este dispositivo y no se envía al anunciante.</p><div><Button variant="ghost" onClick={closeCommentEditor}>Cancelar</Button><Button onClick={saveComment} disabled={!commentText.trim()}>Guardar comentario</Button></div></div> : null}
            {listingComments.length ? <div className="local-listing-comments" aria-label="Tus comentarios locales">{listingComments.map((comment) => <article key={comment.id}><p>{comment.text}</p><footer><span><span>Guardado en este dispositivo</span> · <time dateTime={comment.updatedAt ?? comment.createdAt}>{new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(comment.updatedAt ?? comment.createdAt))}</time>{comment.updatedAt ? <span> · editado</span> : null}</span><div><Button variant="ghost" size="sm" onClick={() => { setEditingCommentId(comment.id); setCommentText(comment.text); setCommentEditorOpen(true) }}><Pencil data-icon="inline-start" />Editar</Button><Button variant="ghost" size="sm" onClick={() => deleteLocalComment(comment.id)}><Trash2 data-icon="inline-start" />Eliminar</Button></div></footer></article>)}</div> : null}
          </section>

          <Separator />
          <section className="listing-section"><h2>Descripción</h2><p className="prose">{listing.description}</p></section>
          <Separator />
          <section className="listing-section"><h2>Habitación y plazas</h2><ul className="idealista-feature-list">
            <li><BedDouble />{rentalUnitLabel}</li>
            <li><UsersRound />Capacidad: {listing.roomCapacity == null ? unknownListingFact : `${listing.roomCapacity} ${listing.roomCapacity === 1 ? 'persona' : 'personas'}`}</li>
            <li><UsersRound />Ya viven en esta habitación: {listing.currentRoomResidents ?? unknownListingFact}</li>
            <li><UsersRound />Plazas libres: {availableSpots ?? unknownListingFact}</li>
            <li><BedDouble />{bedLabel}</li>
            <li><Ruler />Superficie de la habitación: {listing.roomSizeM2 == null ? unknownListingFact : `${listing.roomSizeM2} m²`}</li>
          </ul></section>
          <Separator />
          <section className="listing-section"><h2>Vivienda y espacios</h2><ul className="idealista-feature-list">
            <li><Home />Superficie total: {listing.homeSizeM2 == null ? unknownListingFact : `${listing.homeSizeM2} m²`}</li>
            <li><Home />{listing.bedroomCount == null ? unknownListingFact : `${listing.bedroomCount} habitaciones en la vivienda`}</li>
            <li><Bath />{listing.bathroomCount == null ? unknownListingFact : `${listing.bathroomCount} ${listing.bathroomCount === 1 ? 'baño' : 'baños'} en la vivienda`}</li>
            <li><UsersRound />{listing.currentResidents} residentes actuales en la vivienda</li>
            <li><Bath />{listing.bathroom ?? unknownListingFact} · {listing.toilet ?? unknownListingFact} · {listing.shower}</li>
            <li><CookingPot />{listing.kitchen ?? unknownListingFact}</li>
            <li><Home />{listing.heatingType ? heatingLabels[listing.heatingType] : unknownListingFact}</li>
            <li><Home />{listing.accessible == null ? unknownListingFact : listing.accessible ? 'Adaptada para movilidad reducida' : 'No indicada como adaptada'}</li>
          </ul></section>
          <Separator />
          <section className="listing-section"><h2>Convivencia</h2><dl className="detail-list">
            <div><dt>Composición actual</dt><dd>{listing.householdGender ? householdLabels[listing.householdGender] : unknownListingFact}</dd></div>
            <div><dt>Niños viviendo actualmente</dt><dd>{listing.householdHasChildren == null ? unknownListingFact : listing.householdHasChildren ? 'Sí' : 'No'}</dd></div>
            <div><dt>Perfiles admitidos</dt><dd>{listing.acceptedTenantTypes?.length ? listing.acceptedTenantTypes.map((value) => tenantTypeLabels[value] ?? value).join(', ') : unknownListingFact}</dd></div>
            <div><dt>Parejas</dt><dd>{listing.couplesAllowed == null ? unknownListingFact : listing.couplesAllowed ? 'Permitidas' : 'No permitidas'}</dd></div>
          </dl></section>
          <Separator />
          <section className="listing-section"><h2>Equipamiento</h2><div className="amenities-grid">{listing.amenities.map((amenity) => <span key={amenity}><Check />{amenity}</span>)}</div></section>
          <Separator />
          <section className="listing-section conditions-block"><h2>Normas y convivencia</h2><p>Todas las condiciones están visibles antes del contacto.</p><div className="badge-row badge-row--large">{criticalRestrictions.map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}</div></section>
          <Separator />
          <section className="listing-section"><h2>Precio y disponibilidad</h2><dl className="detail-list"><div><dt>Renta</dt><dd>{getPrimaryPrice(listing)} €/{getPrimaryCadence(listing)}</dd></div>{listing.rentalMode === 'holiday' && listing.weeklyPrice ? <div><dt>Semana</dt><dd>{listing.weeklyPrice} €</dd></div> : null}{listing.rentalMode === 'holiday' && listing.monthlyPrice ? <div><dt>Mes</dt><dd>{listing.monthlyPrice} €</dd></div> : null}<div><dt>Gastos</dt><dd>{listing.bills}</dd></div><div><dt>Fianza</dt><dd>{listing.deposit}</dd></div><div><dt>Disponible desde</dt><dd>{listing.availableFrom}</dd></div><div><dt>Disponible hasta</dt><dd>{listing.availableUntil ?? unknownListingFact}</dd></div><div><dt>Estancia mínima</dt><dd>{listing.minimumStay}</dd></div></dl></section>
          <Separator />
          <section className="listing-section"><h2>Ubicación aproximada</h2><p className="map-intro">El marcador protege la dirección exacta.</p><div className="detail-map"><MapView items={[listing]} selectedId={listing.id} onSelect={() => undefined} showPreview={false} /></div></section>
          <Separator />
          <section className="listing-section owner-detail"><div className="owner-monogram">{listing.owner.initials}</div><div><span>Anunciante</span><h2>{listing.owner.name}</h2><p>{listing.owner.since} · {listing.owner.response}</p><p>{listing.owner.verified ? 'Identidad y teléfono verificados por 112233.es.' : 'Identidad pendiente de verificación.'}</p><Button variant="ghost" size="sm" onClick={() => setUserReportOpen(true)}><CircleAlert />Denunciar anunciante</Button></div>{listing.owner.verified ? <Badge variant="outline"><ShieldCheck />Anunciante verificado</Badge> : null}</section>
          <div className="listing-meta"><span>{formatPublishedAt(listing.publishedAt)}</span><span>Referencia {listing.id.slice(-5).toUpperCase()}</span><span>{listing.source ?? 'Anuncio directo'}</span></div>
        </div>
        <div className="listing-aside"><ContactPanel listing={listing} /></div>
      </div>
      <section className="section section--surface listing-similar"><div className="container"><div className="section-heading idealista-section-heading"><div><h2>También te puede interesar</h2><p>Primero mostramos zona y precio parecidos.</p></div><Button asChild variant="outline"><Link to="/buscar">Ver más</Link></Button></div><div className="property-grid">{similar.map((item) => <PropertyCard key={item.id} listing={item} compact />)}</div></div></section>
      <div className="mobile-contact-bar"><ContactPanel listing={listing} mobile /></div>
    </article>
  )
}
