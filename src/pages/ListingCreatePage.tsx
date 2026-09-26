import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, RotateCcw, Save } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { ConfirmDialog, FormField, ImageUploader, VideoUploader } from '@/components/forms'
import { ApproximateLocationMap } from '@/components/map-view'
import { useApp } from '@/contexts/app-context'
import { amenityOptions, createDefaultDraft } from '@/data/listings'
import { getCriticalRestrictions } from '@/lib/listings'
import { approximatePublicCoordinates } from '@/lib/location-privacy'
import type { ResolvedGoogleAddress } from '@/lib/google-maps/address'
import { isMediaReference, MAX_LISTING_PHOTOS, removeUnusedMediaReferences } from '@/lib/media-storage'
import {
  normalizeEquipmentAmenities,
  readEquipmentAmenities,
  withEquipmentDefaults,
  writeEquipmentAmenity,
  type EquipmentField,
  type EquipmentSelections,
} from '@/lib/listing-equipment'
import { validatePublicationContact } from '@/lib/publication-contact'
import { containsBlockedListingLink, listingLinkBlockedMessage } from '@/lib/listing-content-safety'
import { bedTypeOptionLabel } from '@/lib/bed-type-label'
import { municipalityAreaError, municipalities, municipalitySet } from '@/lib/tenerife-address'
import { getEmailVerificationStatus, requestEmailVerification, verifyEmail } from '@/api/auth'
import { useI18n } from '@/contexts/i18n-context'
import type { AcceptedTenantType, DemoUser, Listing, ListingDraft, TenantRequirement } from '@/types'
import '@/listing-edit-long-form.css'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
const draftKey = '112233:listing-draft:v3'
const legacyDraftKey = '112233:listing-draft:v2'
const editDraftPrefix = '112233:listing-edit-draft:v1:'
const editDraftKey = (listingId: string) => `${editDraftPrefix}${listingId}`
function acceptedForRequirement(requirement: TenantRequirement): AcceptedTenantType[] {
  if (requirement === 'single-man') return ['man']
  if (requirement === 'single-woman') return ['woman']
  if (requirement === 'couple') return ['couple']
  if (requirement === 'single-person') return ['man', 'woman']
  return ['man', 'woman', 'couple', 'family']
}


const withProfileDefaults = (user: DemoUser | null) => {
  const initial = createDefaultDraft();
  // Mock-mode drafts still need concrete images so the wizard can exercise
  // publication without making flaky third-party image requests. Production
  // starts empty and requires real uploaded/server media references.
  const mockPlaceholder = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
  const base = { ...initial, images: mockMode ? initial.images.map(() => mockPlaceholder) : [], amenities: withEquipmentDefaults(initial.amenities) };
  if (!user) return base;
  return { ...base, contactName: user.name, contactPhone: user.phone, contactWhatsapp: user.whatsapp, contactEmail: user.email, showPhone: user.showPhone, showWhatsApp: user.showWhatsApp };
};


const toListing = (draft: ListingDraft, previous?: Listing, ownerUserId?: string): Listing => {
  const id = previous?.id ?? draft.publicationKey;
  const primaryPrice = draft.rentalMode === "holiday" ? draft.nightlyPrice : draft.monthlyPrice;
  const availableSpots = Math.max(0, draft.roomCapacity - draft.currentRoomResidents);
  const exactCoordinates = draft.coordinates;
  const publicCoordinates = approximatePublicCoordinates(exactCoordinates);
  const listing: Listing = {
    id,
    title: draft.title,
    city: draft.city,
    area: draft.area,
    street: draft.street.trim(),
    postcode: draft.postcode.trim(),
    approximateAddress: `${draft.area} · ubicación en el mapa`,
    price: primaryPrice,
    cadence: draft.rentalMode === "holiday" ? "noche" : "mes",
    monthlyPrice: draft.monthlyPrice,
    nightlyPrice: draft.rentalMode === "holiday" ? draft.nightlyPrice : undefined,
    weeklyPrice: draft.rentalMode === "holiday" ? draft.weeklyPrice : undefined,
    rentalMode: draft.rentalMode,
    roomType: draft.roomType,
    available: `Disponible desde ${new Intl.DateTimeFormat("es-ES", { dateStyle: "medium" }).format(new Date(`${draft.availableFrom}T12:00:00`))}`,
    availableFrom: draft.availableFrom,
    availableUntil: draft.availableUntil || undefined,
    minimumStay: draft.rentalMode === "holiday" ? `Mínimo ${draft.minimumNights} ${draft.minimumNights === 1 ? "noche" : "noches"}` : `Mínimo ${draft.minimumStayMonths} ${draft.minimumStayMonths === 1 ? "mes" : "meses"}`,
    minimumStayMonths: draft.minimumStayMonths,
    minimumNights: draft.rentalMode === "holiday" ? draft.minimumNights : undefined,
    deposit: draft.depositAmount ? `${draft.depositAmount} €` : "Sin fianza",
    depositAmount: draft.depositAmount,
    bills: draft.billsIncluded ? "Gastos incluidos en el precio" : draft.billsNote ? `Gastos aparte: aprox. ${draft.billsNote} €/mes` : "Gastos aparte",
    billsIncluded: draft.billsIncluded,
    bathroom: draft.bathroom,
    kitchen: draft.kitchen,
    furnished: draft.furnished,
    roomSizeM2: draft.roomSizeM2,
    homeSizeM2: draft.homeSizeM2,
    bedroomCount: Math.min(99, Math.max(1, Math.round(draft.bedroomCount))),
    bathroomCount: draft.bathroomCount,
    currentResidents: draft.currentResidents,
    roomCapacity: draft.roomCapacity,
    rentalUnit: draft.rentalUnit,
    bedType: draft.bedType,
    bedCount: draft.bedCount,
    currentRoomResidents: draft.currentRoomResidents,
    availableSpots,
    toilet: draft.toilet,
    shower: draft.shower,
    householdGender: draft.householdGender,
    householdHasChildren: draft.householdHasChildren,
    heatingType: draft.heatingType,
    accessible: draft.accessible,
    floor: draft.floor,
    couplesAllowed: draft.couplesAllowed,
    acceptedTenantTypes: draft.acceptedTenantTypes,
    coordinates: publicCoordinates,
    exactCoordinates,
    tenantRequirement: draft.tenantRequirement,
    smokingAllowed: draft.smokingAllowed,
    petsAllowed: draft.petsAllowed,
    childrenAllowed: draft.childrenAllowed,
    empadronamientoAllowed: draft.empadronamientoAllowed,
    restrictions: [],
    amenities: normalizeEquipmentAmenities(draft.amenities),
    description: draft.description,
    homeDescription: draft.rules,
    images: draft.images,
    ...(draft.video ? { video: draft.video } : {}),
    owner: previous?.owner ?? {
      name: draft.contactName,
      initials: draft.contactName.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toLocaleUpperCase(),
      since: "Publica desde 2026",
      response: "Suele responder en el mismo día",
      verified: false,
    },
    advertiserType: "Particular",
    source: "Creado en esta demo",
    status: "Publicado",
    publishedAt: previous?.publishedAt ?? new Date().toISOString(),
    views: previous?.views ?? 0,
    expiresAt: draft.expiresAt,
    userCreated: true,
    ownerUserId: previous?.ownerUserId ?? ownerUserId,
    contactPhone: draft.contactPhone,
    contactWhatsapp: draft.contactWhatsapp,
    contactEmail: draft.contactEmail,
    showPhone: draft.showPhone,
    showWhatsApp: draft.showWhatsApp,
  };
  listing.restrictions = getCriticalRestrictions(listing);
  return listing;
};


function Section({ id, title, hint, disabled = false, children }: { id: string; title: string; hint?: string; disabled?: boolean; children: React.ReactNode }) {
  return <section id={id} className="listing-edit-section"><header><h2>{title}</h2>{hint ? <p>{hint}</p> : null}</header><fieldset className="listing-edit-section__fields" disabled={disabled}>{children}</fieldset></section>
}

export function ListingCreatePage() {
  const { language } = useI18n()
  const navigate = useNavigate()
  const { allListings, ownedListings, createListing, currentUser, partialPublication } = useApp()
  const [draft, setDraft] = useState<ListingDraft>(() => {
    const defaults = withProfileDefaults(currentUser as DemoUser | null)
    try {
      const raw = localStorage.getItem(draftKey)
      const stored = JSON.parse(raw ?? 'null') as { version?: number; ownerUserId?: string; listingId?: string; data?: Partial<ListingDraft> } | null
      if (raw && stored?.listingId) {
        const scopedKey = editDraftKey(stored.listingId)
        if (!localStorage.getItem(scopedKey)) localStorage.setItem(scopedKey, raw)
        localStorage.removeItem(draftKey)
      } else if (stored?.version === 3 && !stored.listingId && (!stored.ownerUserId || stored.ownerUserId === currentUser?.id) && stored.data) {
        return { ...defaults, ...stored.data }
      }
      const legacy = localStorage.getItem(legacyDraftKey)
      return legacy ? { ...defaults, ...(JSON.parse(legacy) as Partial<ListingDraft>) } : defaults
    } catch { return defaults }
  })
  const [baseline, setBaseline] = useState(() => JSON.stringify(draft))
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [processingImages, setProcessingImages] = useState(false)
  const [processingVideo, setProcessingVideo] = useState(false)
  const savingRef = useRef(false)
  const [verificationOpen, setVerificationOpen] = useState(false)
  const [verificationEmail, setVerificationEmail] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [verificationError, setVerificationError] = useState('')
  const [verificationBusy, setVerificationBusy] = useState(false)
  const [verificationCooldown, setVerificationCooldown] = useState(0)
  const [pendingRoute, setPendingRoute] = useState<string | null>(null)

  const equipment = readEquipmentAmenities(draft.amenities)
  const isDirty = JSON.stringify(draft) !== baseline
  const recoveringImages = Boolean(partialPublication && partialPublication.publicationKey === draft.publicationKey)
  const nonDraftMedia = useMemo(() => {
    const refs = new Set([...allListings, ...ownedListings].flatMap((listing) => [
      ...listing.images,
      ...(listing.video ? [listing.video] : []),
    ]))
    if (currentUser?.avatarRef) refs.add(currentUser.avatarRef)
    return refs
  }, [allListings, currentUser?.avatarRef, ownedListings])

  useEffect(() => {
    try { localStorage.setItem(draftKey, JSON.stringify({ version: 3, ownerUserId: currentUser?.id, data: draft })) } catch { /* autosave is best-effort */ }
  }, [currentUser?.id, draft])

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (isDirty) event.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [isDirty])

  useEffect(() => {
    if (!isDirty) return
    const intercept = (event: MouseEvent) => {
      const anchor = (event.target as HTMLElement).closest<HTMLAnchorElement>('a[href]')
      if (!anchor || anchor.target === '_blank') return
      const url = new URL(anchor.href, location.href)
      if (url.origin !== location.origin || url.hash === location.hash) return
      event.preventDefault()
      setPendingRoute(url.hash.replace(/^#/, '') || '/')
    }
    document.addEventListener('click', intercept, true)
    return () => document.removeEventListener('click', intercept, true)
  }, [isDirty])

  useEffect(() => {
    if (verificationCooldown <= 0) return
    const timer = window.setTimeout(() => setVerificationCooldown((seconds) => seconds - 1), 1000)
    return () => window.clearTimeout(timer)
  }, [verificationCooldown])

  const set = <K extends keyof ListingDraft>(key: K, value: ListingDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }))
    setErrors((current) => {
      const next = { ...current }
      delete next[String(key)]
      if (key === 'city' || key === 'area') delete next.area
      if (key === 'city' || key === 'area' || key === 'street' || key === 'postcode') delete next.location
      return next
    })
  }
  const setEquipment = (field: EquipmentField, value: EquipmentSelections[EquipmentField]) => set('amenities', writeEquipmentAmenity(draft.amenities, field, value))
  const toggleAmenity = (item: string) => set('amenities', draft.amenities.includes(item) ? draft.amenities.filter((value) => value !== item) : [...draft.amenities, item])
  const toggleAccepted = (item: AcceptedTenantType) => set('acceptedTenantTypes', draft.acceptedTenantTypes.includes(item) ? draft.acceptedTenantTypes.filter((value) => value !== item) : [...draft.acceptedTenantTypes, item])
  const applyResolvedAddress = (address: ResolvedGoogleAddress) => {
    setDraft((current) => {
      const next = {
        ...current,
        coordinates: address.coordinates,
        locationManuallyMoved: true,
        ...(address.street ? { street: address.street } : {}),
        ...(address.postcode ? { postcode: address.postcode } : {}),
        ...(address.city && municipalitySet.has(address.city) ? { city: address.city } : {}),
        ...(address.area ? { area: address.area } : {}),
      }
      return next
    })
    setErrors((current) => {
      const next = { ...current }
      delete next.location
      delete next.city
      delete next.area
      delete next.street
      delete next.postcode
      return next
    })
  }

  const validate = () => {
    const next: Record<string, string> = {}
    if (!municipalitySet.has(draft.city)) next.city = 'Selecciona un municipio válido.'
    if (!draft.area.trim()) next.area = 'Indica la zona o barrio.'
    else if (draft.area.trim().length > 120) next.area = 'La zona no puede superar 120 caracteres.'
    else if (containsBlockedListingLink(draft.area)) next.area = listingLinkBlockedMessage
    else {
      const mismatch = municipalityAreaError(draft.city, draft.area)
      if (mismatch) next.area = mismatch
    }
    if (draft.street.trim().length > 160) next.street = 'La calle no puede superar 160 caracteres.'
    if (draft.postcode.trim() && !/^\d{5}$/.test(draft.postcode.trim())) next.postcode = 'El código postal debe tener exactamente 5 dígitos.'
    if (!Number.isInteger(draft.roomSizeM2) || draft.roomSizeM2 < 1 || draft.roomSizeM2 > 200) next.roomSizeM2 = 'Indica entre 1 y 200 m².'
    if (!Number.isInteger(draft.homeSizeM2) || draft.homeSizeM2 < draft.roomSizeM2 || draft.homeSizeM2 > 10_000) next.homeSizeM2 = 'Debe ser igual o mayor que la habitación.'
    if (!Number.isInteger(draft.bedroomCount) || draft.bedroomCount < 1 || draft.bedroomCount > 99) next.bedroomCount = 'Indica al menos una habitación.'
    if (!Number.isInteger(draft.bathroomCount) || draft.bathroomCount < 0 || draft.bathroomCount > 20) next.bathroomCount = 'Indica un número válido.'
    if (!Number.isInteger(draft.currentResidents) || draft.currentResidents < 0) next.currentResidents = 'Indica un número válido.'
    if (draft.roomCapacity < 1 || draft.roomCapacity > 10) next.roomCapacity = 'La capacidad debe estar entre 1 y 10.'
    if (!Number.isInteger(draft.bedCount) || draft.bedCount < 1 || draft.bedCount > 10) next.bedCount = 'Indica entre 1 y 10 camas.'
    if (!Number.isInteger(draft.currentRoomResidents) || draft.currentRoomResidents < 0 || draft.currentRoomResidents >= draft.roomCapacity) next.currentRoomResidents = 'Debe quedar al menos una plaza libre.'
    if (draft.rentalUnit === 'bed' && draft.roomType !== 'Habitación compartida') next.rentalUnit = 'Las plazas individuales solo se pueden alquilar en una habitación compartida.'
    if (draft.rentalUnit === 'bed' && draft.bedType === 'double') next.bedType = 'Las plazas independientes no usan cama doble.'
    const sleepingPlaces = draft.bedCount * (draft.bedType === 'double' || draft.bedType === 'bunk' ? 2 : 1)
    if (sleepingPlaces < draft.roomCapacity) next.bedCount = 'Las camas indicadas no cubren la capacidad.'
    if (!equipment.bedding) next.bedding = 'Selecciona una opción.'
    if (!equipment.refrigerator) next.refrigerator = 'Selecciona una opción.'
    if (!equipment.balcony) next.balcony = 'Selecciona una opción.'
    if (!equipment.washingMachine) next.washingMachine = 'Selecciona una opción.'
    const price = draft.rentalMode === 'holiday' ? draft.nightlyPrice : draft.monthlyPrice
    if (!Number.isInteger(price) || price < 1) next.price = 'Indica un precio válido.'
    if (draft.weeklyPrice !== undefined && (!Number.isInteger(draft.weeklyPrice) || draft.weeklyPrice < 0)) next.weeklyPrice = 'El precio semanal debe ser válido.'
    if (!Number.isInteger(draft.depositAmount) || draft.depositAmount < 0) next.depositAmount = 'La fianza no puede ser negativa.'
    if (!draft.billsIncluded) { const billsAmount = Number(draft.billsNote); if (!draft.billsNote.trim() || !Number.isFinite(billsAmount) || billsAmount <= 0) next.billsAmount = 'Indica el gasto aproximado al mes.' }
    if (!draft.availableFrom) next.availableFrom = 'Selecciona una fecha.'
    if (draft.availableUntil && draft.availableUntil < draft.availableFrom) next.availableUntil = 'La fecha final debe ser posterior.'
    if (draft.rentalMode === 'long' && (!Number.isInteger(draft.minimumStayMonths) || draft.minimumStayMonths < 1)) next.minimumStay = 'Indica al menos 1 mes.'
    if (draft.rentalMode === 'holiday' && (!Number.isInteger(draft.minimumNights) || draft.minimumNights < 1)) next.minimumStay = 'Indica al menos 1 noche.'
    if (!draft.images.length) next.images = 'Añade al menos una fotografía.'
    else if (draft.images.length > MAX_LISTING_PHOTOS) next.images = `Puedes añadir como máximo ${MAX_LISTING_PHOTOS} fotografías.`
    else if (!mockMode && draft.images.some((image) => !isMediaReference(image) && !/\/media\/[0-9a-f-]{36}(?:$|[?#])/i.test(image))) next.images = 'Vuelve a añadir las fotografías no disponibles.'
    if (!mockMode && draft.video && !isMediaReference(draft.video) && !/\/media\/[0-9a-f-]{36}(?:$|[?#])/i.test(draft.video)) next.video = 'Vuelve a añadir el vídeo no disponible.'
    if (draft.title.trim().length < 15) next.title = 'Escribe un título de al menos 15 caracteres.'
    else if (containsBlockedListingLink(draft.title)) next.title = listingLinkBlockedMessage
    if (draft.description.trim().length < 40 || draft.description.length > 10_000) next.description = 'La descripción debe tener entre 40 y 10.000 caracteres.'
    else if (containsBlockedListingLink(draft.description)) next.description = listingLinkBlockedMessage
    if (draft.rules.length > 10_000) next.rules = 'Las normas no pueden superar 10.000 caracteres.'
    else if (containsBlockedListingLink(draft.rules)) next.rules = listingLinkBlockedMessage
    Object.assign(next, validatePublicationContact(draft))
    setErrors(next)
    if (Object.keys(next).length) requestAnimationFrame(() => document.querySelector<HTMLElement>('[aria-invalid="true"], .field-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
    return Object.keys(next).length === 0
  }

  const save = async () => {
    if (savingRef.current || processingImages || processingVideo || !validate()) return
    savingRef.current = true
    setSaving(true)
    try {
      if (!mockMode) {
        const verification = await getEmailVerificationStatus()
        if (!verification.verified) {
          setVerificationEmail(verification.email)
          setVerificationOpen(true)
          return
        }
      }
      const authoritative = currentUser ? { ...draft, contactEmail: currentUser.email } : draft
      const listing = toListing(authoritative, undefined, currentUser?.id)
      if (!await createListing(listing)) return
      localStorage.removeItem(draftKey)
      setBaseline(JSON.stringify(authoritative))
      navigate('/mis-anuncios')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudo publicar el anuncio.')
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  const saveDraft = () => {
    try {
      localStorage.setItem(draftKey, JSON.stringify({ version: 3, ownerUserId: currentUser?.id, data: draft }))
      setBaseline(JSON.stringify(draft))
      toast.success('Borrador guardado')
    } catch {
      toast.error('No se pudo guardar el borrador. Revisa el espacio disponible.')
    }
  }

  const resetDraft = () => {
    const fresh = withProfileDefaults(currentUser as DemoUser | null)
    const retained = new Set([
      ...fresh.images,
      ...(fresh.video ? [fresh.video] : []),
    ])
    const transientMedia = [
      ...draft.images,
      ...(draft.video ? [draft.video] : []),
    ].filter((reference) => !retained.has(reference))
    void removeUnusedMediaReferences(transientMedia, nonDraftMedia).catch((error) => {
      toast.error(error instanceof Error ? error.message : 'No se pudieron limpiar las imágenes locales.')
    })
    setDraft(fresh)
    setErrors({})
    setBaseline(JSON.stringify(fresh))
    try {
      localStorage.setItem(draftKey, JSON.stringify({ version: 3, ownerUserId: currentUser?.id, data: fresh }))
    } catch {
      toast.error('No se pudo guardar el borrador restablecido.')
    }
    toast.success('Borrador restablecido')
  }

  const choice = <T extends string>(name: string, value: T, options: { value: T; title: string; text?: string }[], onChange: (value: T) => void) => <div className="listing-edit-choice-grid">{options.map((option) => <label key={option.value}><input type="radio" name={name} checked={value === option.value} onChange={() => onChange(option.value)} /><span><strong>{option.title}</strong>{option.text ? <small>{option.text}</small> : null}</span></label>)}</div>

  return <>
    <main className="listing-edit-page listing-create-page">
      <div className="listing-edit-topbar"><div className="listing-edit-topbar__inner"><Link to="/mis-anuncios" className="listing-edit-back"><ArrowLeft /> Tus anuncios</Link><strong>Publicar anuncio</strong><Button onClick={save} disabled={saving || processingImages || processingVideo}><Save data-icon="inline-start" />{saving ? 'Publicando…' : processingImages ? 'Procesando foto…' : recoveringImages ? 'Reintentar fotos' : 'Publicar'}</Button></div></div>
      <div className="listing-edit-shell">
        <header className="listing-edit-heading"><p>Nuevo anuncio</p><h1>Publicar habitación</h1><span>Todo el anuncio está en una sola página. Baja, completa los datos y publica al final.</span></header>
        <div className="listing-create-draft-actions">
          <span className="dirty-state" aria-live="polite">{isDirty ? 'Cambios sin guardar' : 'Borrador guardado'}</span>
          <div>
            <ConfirmDialog trigger={<Button variant="outline" disabled={recoveringImages || processingImages}><RotateCcw data-icon="inline-start" />Restablecer</Button>} title="¿Restablecer el borrador?" description="Se eliminarán los cambios del anuncio y las fotos temporales que no usa ningún anuncio guardado." confirmLabel="Restablecer" destructive onConfirm={resetDraft} />
            <Button variant="outline" disabled={recoveringImages || processingImages || !isDirty} onClick={saveDraft}><Save data-icon="inline-start" />Guardar borrador</Button>
          </div>
        </div>
        {recoveringImages ? <div className="listing-edit-recovery" role="status"><strong>El anuncio ya está creado.</strong><span>Solo faltan las fotografías. Los demás campos quedan bloqueados hasta terminar la sincronización para evitar perder cambios.</span></div> : null}

      <Section disabled={recoveringImages} id="publish-basic" title="Tipo de alquiler">
        {choice('publish-rental-mode', draft.rentalMode, [
          { value: 'long', title: 'Larga estancia', text: 'Precio mensual' },
          { value: 'holiday', title: 'Alquiler vacacional', text: 'Precio por noche' },
        ], (value) => set('rentalMode', value))}
      </Section>

      <Section disabled={recoveringImages} id="publish-location" title="Ubicación" hint="La dirección exacta no se muestra públicamente.">
        <div className="listing-edit-grid">
          <FormField label="Municipio" htmlFor="publish-city" error={errors.city}><select id="publish-city" value={draft.city} aria-invalid={Boolean(errors.city)} onChange={(e) => set('city', e.target.value)}>{municipalities.map((city) => <option key={city}>{city}</option>)}</select></FormField>
          <FormField label="Zona o barrio" htmlFor="publish-area" error={errors.area}><Input id="publish-area" value={draft.area} aria-invalid={Boolean(errors.area)} onChange={(e) => set('area', e.target.value)} /></FormField>
          <FormField label="Calle" htmlFor="publish-street"><Input id="publish-street" value={draft.street} onChange={(e) => set('street', e.target.value)} /></FormField>
          <FormField label="Código postal" htmlFor="publish-postcode" error={errors.postcode}><Input id="publish-postcode" inputMode="numeric" value={draft.postcode} aria-invalid={Boolean(errors.postcode)} onChange={(e) => set('postcode', e.target.value)} /></FormField>
        </div>
        <ApproximateLocationMap coordinates={draft.coordinates} onChange={(coordinates) => setDraft((current) => current ? { ...current, coordinates, locationManuallyMoved: true } : current)} onAddressResolved={applyResolvedAddress} onLocationError={(message) => setErrors((current) => ({ ...current, location: message }))} />
        {errors.location ? <p className="field-error" role="alert">{errors.location}</p> : null}
        <output className="listing-edit-coordinates" aria-live="polite">Coordenadas exactas: {draft.coordinates.lat.toFixed(4)}, {draft.coordinates.lng.toFixed(4)}</output>
      </Section>

      <Section disabled={recoveringImages} id="publish-room" title="Habitación y vivienda">
        {choice('publish-room-type', draft.roomType, [
          { value: 'Habitación individual', title: 'Habitación privada' },
          { value: 'Habitación compartida', title: 'Habitación compartida' },
          { value: 'Estudio', title: 'Estudio' },
        ], (value) => setDraft((current) => current ? { ...current, roomType: value, rentalUnit: value === 'Habitación compartida' ? current.rentalUnit : 'room', currentRoomResidents: value === 'Habitación compartida' ? current.currentRoomResidents : 0 } : current))}
        {draft.roomType === 'Habitación compartida' ? choice('publish-rental-unit', draft.rentalUnit, [
          { value: 'room', title: 'Habitación completa' },
          { value: 'bed', title: 'Plazas / camas' },
        ], (value) => setDraft((current) => ({ ...current, rentalUnit: value, bedType: value === 'bed' ? 'single' : current.bedType, bedCount: value === 'bed' ? Math.max(current.bedCount, current.roomCapacity) : current.bedCount }))) : null}
        <div className="listing-edit-grid listing-edit-grid--3">
          <FormField label="Superficie habitación (m²)" htmlFor="publish-room-size" error={errors.roomSizeM2}><Input id="publish-room-size" type="number" min="1" max="200" value={draft.roomSizeM2} aria-invalid={Boolean(errors.roomSizeM2)} onChange={(e) => set('roomSizeM2', Number(e.target.value))} /></FormField>
          <FormField label="Superficie vivienda (m²)" htmlFor="publish-home-size" error={errors.homeSizeM2}><Input id="publish-home-size" type="number" min="1" value={draft.homeSizeM2} aria-invalid={Boolean(errors.homeSizeM2)} onChange={(e) => set('homeSizeM2', Number(e.target.value))} /></FormField>
          <FormField label="Habitaciones" htmlFor="publish-bedrooms" error={errors.bedroomCount}><Input id="publish-bedrooms" type="number" min="1" value={draft.bedroomCount} aria-invalid={Boolean(errors.bedroomCount)} onChange={(e) => set('bedroomCount', Number(e.target.value))} /></FormField>
          <FormField label="Baños" htmlFor="publish-bathrooms" error={errors.bathroomCount}><Input id="publish-bathrooms" type="number" min="0" value={draft.bathroomCount} aria-invalid={Boolean(errors.bathroomCount)} onChange={(e) => set('bathroomCount', Number(e.target.value))} /></FormField>
          <FormField label="Personas en la vivienda" htmlFor="publish-residents"><Input id="publish-residents" type="number" min="0" value={draft.currentResidents} onChange={(e) => set('currentResidents', Number(e.target.value))} /></FormField>
          <FormField label="Capacidad habitación" htmlFor="publish-capacity" error={errors.roomCapacity}><select id="publish-capacity" value={draft.roomCapacity} aria-invalid={Boolean(errors.roomCapacity)} onChange={(e) => { const roomCapacity = Number(e.target.value); setDraft((current) => { const placesPerBed = current.bedType === 'double' || current.bedType === 'bunk' ? 2 : 1; return { ...current, roomCapacity, bedCount: Math.max(current.bedCount, Math.ceil(roomCapacity / placesPerBed)), currentRoomResidents: Math.min(current.currentRoomResidents, roomCapacity - 1) } }) }}>{Array.from({ length: 10 }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}</select></FormField>
          <FormField label="Personas ya en la habitación" htmlFor="publish-room-residents" error={errors.currentRoomResidents}><Input id="publish-room-residents" type="number" min="0" value={draft.currentRoomResidents} aria-invalid={Boolean(errors.currentRoomResidents)} onChange={(e) => set('currentRoomResidents', Number(e.target.value))} /></FormField>
          <FormField label="Tipo de cama" htmlFor="publish-bed-type"><select id="publish-bed-type" value={draft.bedType} onChange={(e) => { const bedType = e.target.value as ListingDraft['bedType']; setDraft((current) => { const placesPerBed = bedType === 'double' || bedType === 'bunk' ? 2 : 1; return { ...current, bedType, bedCount: Math.max(current.bedCount, Math.ceil(current.roomCapacity / placesPerBed)) } }) }}><option value="single">{bedTypeOptionLabel(language, 'single')}</option><option value="double" disabled={draft.rentalUnit === 'bed'}>{bedTypeOptionLabel(language, 'double')}</option><option value="bunk">{bedTypeOptionLabel(language, 'bunk')}</option></select></FormField>
          <FormField label="Número de camas" htmlFor="publish-bed-count"><Input id="publish-bed-count" type="number" min="1" max="10" value={draft.bedCount} onChange={(e) => set('bedCount', Number(e.target.value))} /></FormField>
          <FormField label="Baño" htmlFor="publish-bathroom"><select id="publish-bathroom" value={draft.bathroom} onChange={(e) => set('bathroom', e.target.value as ListingDraft['bathroom'])}><option>Baño compartido</option><option>Baño privado</option></select></FormField>
          <FormField label="Aseo / WC" htmlFor="publish-toilet"><select id="publish-toilet" value={draft.toilet} onChange={(e) => set('toilet', e.target.value as ListingDraft['toilet'])}><option>Aseo compartido</option><option>Aseo privado</option></select></FormField>
          <FormField label="Ducha" htmlFor="publish-shower"><select id="publish-shower" value={draft.shower} onChange={(e) => set('shower', e.target.value as ListingDraft['shower'])}><option>Ducha compartida</option><option>Ducha privada</option></select></FormField>
          <FormField label="Cocina" htmlFor="publish-kitchen"><select id="publish-kitchen" value={draft.kitchen} onChange={(e) => set('kitchen', e.target.value as ListingDraft['kitchen'])}><option>Cocina compartida</option><option>Cocina privada</option></select></FormField>
          <FormField label="Planta" htmlFor="publish-floor"><select id="publish-floor" value={draft.floor} onChange={(e) => set('floor', e.target.value as ListingDraft['floor'])}><option value="basement">Sótano</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4+">4+</option><option value="top">Última planta</option></select></FormField>
          <FormField label="Calefacción" htmlFor="publish-heating"><select id="publish-heating" value={draft.heatingType} onChange={(e) => set('heatingType', e.target.value as ListingDraft['heatingType'])}><option value="none">Sin calefacción</option><option value="individual">Individual</option><option value="central">Central</option><option value="unknown">No especificado</option></select></FormField>
          <FormField label="Ropa de cama" htmlFor="publish-bedding" error={errors.bedding}><select id="publish-bedding" value={equipment.bedding} aria-invalid={Boolean(errors.bedding)} onChange={(e) => setEquipment('bedding', e.target.value as EquipmentSelections['bedding'])}><option value="">Selecciona</option><option value="included">Incluida</option><option value="not_included">No incluida</option></select></FormField>
          <FormField label="Frigorífico" htmlFor="publish-refrigerator" error={errors.refrigerator}><select id="publish-refrigerator" value={equipment.refrigerator} aria-invalid={Boolean(errors.refrigerator)} onChange={(e) => setEquipment('refrigerator', e.target.value as EquipmentSelections['refrigerator'])}><option value="">Selecciona</option><option value="individual">Individual</option><option value="shared">Compartido</option><option value="none">No disponible</option></select></FormField>
          <FormField label="Balcón" htmlFor="publish-balcony" error={errors.balcony}><select id="publish-balcony" value={equipment.balcony} aria-invalid={Boolean(errors.balcony)} onChange={(e) => setEquipment('balcony', e.target.value as EquipmentSelections['balcony'])}><option value="">Selecciona</option><option value="yes">Sí</option><option value="no">No</option></select></FormField>
          <FormField label="Lavadora" htmlFor="publish-washing-machine" error={errors.washingMachine}><select id="publish-washing-machine" value={equipment.washingMachine} aria-invalid={Boolean(errors.washingMachine)} onChange={(e) => setEquipment('washingMachine', e.target.value as EquipmentSelections['washingMachine'])}><option value="">Selecciona</option><option value="individual">Individual</option><option value="shared">Compartida</option><option value="none">No disponible</option></select></FormField>
        </div>
        <div className="listing-edit-checks"><label><Checkbox checked={draft.furnished} onCheckedChange={(value) => set('furnished', value === true)} />Amueblada</label><label><Checkbox checked={draft.accessible} onCheckedChange={(value) => set('accessible', value === true)} />Accesible</label></div>
        <div className="listing-edit-amenities"><strong>Equipamiento y servicios</strong><div>{amenityOptions.map((item) => <label key={item}><Checkbox checked={draft.amenities.includes(item)} onCheckedChange={() => toggleAmenity(item)} />{item}</label>)}</div></div>
      </Section>

      <Section disabled={recoveringImages} id="publish-price" title="Precio, gastos y fianza">
        <div className="listing-edit-grid listing-edit-grid--3">
          {draft.rentalMode === 'long' ? <FormField label="Alquiler mensual (€)" htmlFor="publish-monthly-price" error={errors.price}><Input id="publish-monthly-price" type="number" min="1" value={draft.monthlyPrice} aria-invalid={Boolean(errors.price)} onChange={(e) => set('monthlyPrice', Number(e.target.value))} /></FormField> : <FormField label="Precio por noche (€)" htmlFor="publish-nightly-price" error={errors.price}><Input id="publish-nightly-price" type="number" min="1" value={draft.nightlyPrice} aria-invalid={Boolean(errors.price)} onChange={(e) => set('nightlyPrice', Number(e.target.value))} /></FormField>}
          {draft.rentalMode === 'holiday' ? <FormField label="Precio semanal (€)" htmlFor="publish-weekly-price"><Input id="publish-weekly-price" type="number" min="0" value={draft.weeklyPrice ?? ''} onChange={(e) => set('weeklyPrice', e.target.value ? Number(e.target.value) : undefined)} /></FormField> : null}
          <FormField label="Fianza (€)" htmlFor="publish-deposit" error={errors.depositAmount}><Input id="publish-deposit" type="number" min="0" value={draft.depositAmount} aria-invalid={Boolean(errors.depositAmount)} onChange={(e) => set('depositAmount', Number(e.target.value))} /></FormField>
        </div>
        <label className="listing-edit-inline-check"><Checkbox checked={draft.billsIncluded} onCheckedChange={(value) => set('billsIncluded', value === true)} />Gastos incluidos en el precio</label>
        {!draft.billsIncluded ? <FormField label="Gastos aproximados al mes (€)" htmlFor="publish-bills" error={errors.billsAmount}><Input id="publish-bills" inputMode="decimal" value={draft.billsNote} aria-invalid={Boolean(errors.billsAmount)} onChange={(e) => set('billsNote', e.target.value)} /></FormField> : null}
      </Section>

      <Section disabled={recoveringImages} id="publish-availability" title="Disponibilidad">
        <div className="listing-edit-grid listing-edit-grid--3">
          <FormField label="Disponible desde" htmlFor="publish-from" error={errors.availableFrom}><Input id="publish-from" type="date" value={draft.availableFrom} aria-invalid={Boolean(errors.availableFrom)} onChange={(e) => set('availableFrom', e.target.value)} /></FormField>
          <FormField label="Disponible hasta" htmlFor="publish-until" error={errors.availableUntil}><Input id="publish-until" type="date" value={draft.availableUntil} aria-invalid={Boolean(errors.availableUntil)} onChange={(e) => set('availableUntil', e.target.value)} /></FormField>
          {draft.rentalMode === 'long' ? <FormField label="Estancia mínima (meses)" htmlFor="publish-min-months" error={errors.minimumStay}><Input id="publish-min-months" type="number" min="1" value={draft.minimumStayMonths} aria-invalid={Boolean(errors.minimumStay)} onChange={(e) => set('minimumStayMonths', Number(e.target.value))} /></FormField> : <FormField label="Estancia mínima (noches)" htmlFor="publish-min-nights" error={errors.minimumStay}><Input id="publish-min-nights" type="number" min="1" value={draft.minimumNights} aria-invalid={Boolean(errors.minimumStay)} onChange={(e) => set('minimumNights', Number(e.target.value))} /></FormField>}
        </div>
      </Section>

      <Section disabled={recoveringImages} id="publish-household" title="Convivencia y requisitos">
        <FormField label="A quién buscas" htmlFor="publish-requirement"><select id="publish-requirement" value={draft.tenantRequirement} onChange={(e) => { const value = e.target.value as TenantRequirement; setDraft((current) => current ? { ...current, tenantRequirement: value, acceptedTenantTypes: acceptedForRequirement(value), couplesAllowed: value === 'couple' || value === 'any' } : current) }}><option value="any">Sin preferencia</option><option value="single-person">Una persona</option><option value="single-man">Solo hombre</option><option value="single-woman">Solo mujer</option><option value="couple">Pareja</option></select></FormField>
        <div className="listing-edit-tenant-types"><strong>Perfiles aceptados</strong>{(['man','woman','couple','family'] as AcceptedTenantType[]).map((item) => <label key={item}><Checkbox checked={draft.acceptedTenantTypes.includes(item)} onCheckedChange={() => toggleAccepted(item)} />{{ man: 'Hombre', woman: 'Mujer', couple: 'Pareja', family: 'Familia' }[item]}</label>)}</div>
        <div className="listing-edit-grid">
          <FormField label="Composición actual" htmlFor="publish-gender"><select id="publish-gender" value={draft.householdGender} onChange={(e) => set('householdGender', e.target.value as ListingDraft['householdGender'])}><option value="unknown">No especificado</option><option value="men">Hombres</option><option value="women">Mujeres</option><option value="mixed">Mixto</option></select></FormField>
        </div>
        <div className="listing-edit-checks listing-edit-checks--wrap"><label><Checkbox checked={draft.couplesAllowed} onCheckedChange={(value) => set('couplesAllowed', value === true)} />Se aceptan parejas</label><label><Checkbox checked={draft.smokingAllowed} onCheckedChange={(value) => set('smokingAllowed', value === true)} />Se permite fumar</label><label><Checkbox checked={draft.petsAllowed} onCheckedChange={(value) => set('petsAllowed', value === true)} />Se aceptan mascotas</label><label><Checkbox checked={draft.childrenAllowed} onCheckedChange={(value) => set('childrenAllowed', value === true)} />Se aceptan menores</label><label><Checkbox checked={draft.householdHasChildren} onCheckedChange={(value) => set('householdHasChildren', value === true)} />Ya viven menores</label><label><Checkbox checked={draft.empadronamientoAllowed} onCheckedChange={(value) => set('empadronamientoAllowed', value === true)} />Empadronamiento posible</label></div>
        <FormField label="Normas de la vivienda" htmlFor="publish-rules" description="No se permiten enlaces ni dominios externos." error={errors.rules}><Textarea id="publish-rules" rows={5} value={draft.rules} aria-invalid={Boolean(errors.rules)} onChange={(e) => set('rules', e.target.value)} /></FormField>
      </Section>

      <Section id="publish-photos" title="Fotografías" hint="Hasta 15 fotos y, opcionalmente, un vídeo de hasta 30 segundos. La primera foto será la portada.">
        <ImageUploader images={draft.images} onChange={(images) => set('images', images)} onRemove={(image) => { void removeUnusedMediaReferences([image], nonDraftMedia).catch(() => undefined) }} onProcessingChange={setProcessingImages} error={errors.images} />
        <VideoUploader video={draft.video} onChange={(video) => set('video', video)} onProcessingChange={setProcessingVideo} onRemove={(video) => { void removeUnusedMediaReferences([video], nonDraftMedia).catch(() => undefined) }} error={errors.video} />
      </Section>

      <Section disabled={recoveringImages} id="publish-description" title="Título y descripción">
        <FormField label="Título del anuncio" htmlFor="publish-title" description="Máximo 80 caracteres." error={errors.title}><Input id="publish-title" maxLength={80} value={draft.title} aria-invalid={Boolean(errors.title)} onChange={(e) => set('title', e.target.value)} /></FormField>
        <FormField label="Descripción" htmlFor="publish-description-text" description="No se permiten enlaces ni dominios externos." error={errors.description}><Textarea id="publish-description-text" rows={9} value={draft.description} aria-invalid={Boolean(errors.description)} onChange={(e) => set('description', e.target.value)} /></FormField>
      </Section>

      <Section disabled={recoveringImages} id="publish-contact" title="Contacto">
        <div className="listing-edit-grid">
          <FormField label="Nombre" htmlFor="publish-contact-name" error={errors.contactName}><Input id="publish-contact-name" value={draft.contactName} aria-invalid={Boolean(errors.contactName)} onChange={(e) => set('contactName', e.target.value)} /></FormField>
          <FormField label="Email" htmlFor="publish-contact-email"><Input id="publish-contact-email" type="email" value={currentUser?.email ?? draft.contactEmail} disabled /></FormField>
          <FormField label="Teléfono" htmlFor="publish-contact-phone" error={errors.contactPhone}><Input id="publish-contact-phone" value={draft.contactPhone} aria-invalid={Boolean(errors.contactPhone)} onChange={(e) => set('contactPhone', e.target.value)} /></FormField>
          <FormField label="WhatsApp" htmlFor="publish-contact-whatsapp" error={errors.contactWhatsapp}><Input id="publish-contact-whatsapp" value={draft.contactWhatsapp} aria-invalid={Boolean(errors.contactWhatsapp)} onChange={(e) => set('contactWhatsapp', e.target.value)} /></FormField>
        </div>
        <div className="listing-edit-checks"><label><Checkbox checked={draft.showPhone} onCheckedChange={(value) => set('showPhone', value === true)} />Mostrar teléfono</label><label><Checkbox checked={draft.showWhatsApp} onCheckedChange={(value) => set('showWhatsApp', value === true)} />Mostrar WhatsApp</label></div>
        {errors.contactMethods ? <p className="field-error" role="alert">{errors.contactMethods}</p> : null}
      </Section>

      <div className="listing-edit-final"><div><strong>{processingImages ? 'Procesando la foto…' : recoveringImages ? 'Falta terminar las fotografías' : isDirty ? 'El borrador tiene cambios' : 'Borrador guardado automáticamente'}</strong><span>{processingImages ? 'El giro ya se muestra; terminamos de guardar la imagen.' : 'Revisamos todos los campos antes de publicar.'}</span></div><Button size="lg" onClick={save} disabled={saving || processingImages || processingVideo}><Save data-icon="inline-start" />{saving ? 'Publicando…' : processingImages ? 'Procesando foto…' : recoveringImages ? 'Reintentar fotografías' : 'Publicar anuncio'}</Button></div>
    </div>
    </main>
    <Dialog open={verificationOpen} onOpenChange={setVerificationOpen}><DialogContent aria-describedby="create-email-verification-description"><DialogHeader><DialogTitle>Confirma tu email para publicar</DialogTitle><DialogDescription id="create-email-verification-description">Enviaremos un código de seis dígitos a {verificationEmail || 'tu email'}. Tu borrador y tus fotos seguirán guardados.</DialogDescription></DialogHeader><div className="space-y-3"><Input value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" placeholder="000000" aria-label="Código de seis dígitos" aria-invalid={Boolean(verificationError)} />{verificationError ? <p className="field-error" role="alert">{verificationError}</p> : null}<Button type="button" variant="outline" disabled={verificationBusy || verificationCooldown > 0} onClick={async () => { setVerificationBusy(true); try { const result = await requestEmailVerification(); setVerificationEmail(result.email); setVerificationCooldown(result.cooldownSeconds); setVerificationError(''); toast.success('Código enviado'); } catch (error) { setVerificationError(error instanceof Error ? error.message : 'No se pudo enviar el código.'); } finally { setVerificationBusy(false); } }}>{verificationCooldown > 0 ? `Reenviar en ${verificationCooldown}s` : 'Enviar código'}</Button><Button type="button" disabled={verificationBusy || verificationCode.length !== 6} onClick={async () => { setVerificationBusy(true); try { await verifyEmail(verificationCode); setVerificationOpen(false); setVerificationCode(''); setVerificationError(''); await save(); } catch (error) { setVerificationError(error instanceof Error ? error.message : 'Código no válido.'); } finally { setVerificationBusy(false); } }}>Confirmar y publicar</Button></div></DialogContent></Dialog>
    <AlertDialog open={Boolean(pendingRoute)} onOpenChange={(open) => { if (!open) setPendingRoute(null) }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>¿Salir del editor?</AlertDialogTitle><AlertDialogDescription>Hay cambios sin guardar. El borrador automático se conserva, pero puedes guardarlo manualmente antes de salir.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Seguir editando</AlertDialogCancel><AlertDialogAction onClick={() => { const route = pendingRoute; setPendingRoute(null); if (route) navigate(route) }}>Salir y conservar borrador</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </>
}
