import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowLeft, Save } from 'lucide-react'
import { Link, Navigate, useNavigate, useParams } from 'react-router'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { FormField, ImageUploader, VideoUploader } from '@/components/forms'
import { ApproximateLocationMap } from '@/components/map-view'
import { useApp } from '@/contexts/app-context'
import { amenityOptions } from '@/data/listings'
import { getCriticalRestrictions } from '@/lib/listings'
import { approximatePublicCoordinates } from '@/lib/location-privacy'
import type { ResolvedGoogleAddress } from '@/lib/google-maps/address'
import { isMediaReference, removeUnusedMediaReferences } from '@/lib/media-storage'
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
import { useI18n } from '@/contexts/i18n-context'
import type { AcceptedTenantType, Listing, ListingDraft, TenantRequirement } from '@/types'
import '@/listing-edit-long-form.css'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
const editDraftPrefix = '112233:listing-edit-draft:v1:'
const editDraftKey = (id: string) => `${editDraftPrefix}${id}`

function acceptedForRequirement(requirement: TenantRequirement): AcceptedTenantType[] {
  if (requirement === 'single-man') return ['man']
  if (requirement === 'single-woman') return ['woman']
  if (requirement === 'couple') return ['couple']
  if (requirement === 'single-person') return ['man', 'woman']
  return ['man', 'woman', 'couple', 'family']
}

function billsAmountFromText(value: string) {
  const match = value.match(/(\d+(?:[.,]\d{1,2})?)/)
  return match ? match[1].replace(',', '.') : ''
}

function ownerInitials(name: string) {
  return name.trim().split(/\s+/).filter(Boolean).map((part) => part[0]).join('').slice(0, 2).toLocaleUpperCase()
}

function toDraft(listing: Listing): ListingDraft {
  const roomCapacity = Math.min(10, Math.max(1, Math.round(listing.roomCapacity ?? 1)))
  const roomSize = Math.max(1, listing.roomSizeM2 ?? 12)
  const amenities = withEquipmentDefaults(listing.amenities.map((item) => item === 'Fibra' ? 'Wi-Fi' : item))
  return {
    publicationKey: crypto.randomUUID(),
    rentalMode: listing.rentalMode,
    city: listing.city,
    area: listing.area,
    street: listing.street ?? '',
    postcode: listing.postcode ?? '',
    coordinates: (listing.exactCoordinates ?? listing.coordinates)!,
    locationManuallyMoved: true,
    roomType: listing.roomType,
    roomSizeM2: roomSize,
    homeSizeM2: Math.max(roomSize, listing.homeSizeM2 ?? 70),
    bedroomCount: listing.bedroomCount ?? Math.max(1, listing.currentResidents + 1),
    bathroomCount: Math.max(0, listing.bathroomCount ?? 1),
    currentResidents: Math.max(0, listing.currentResidents),
    roomCapacity,
    rentalUnit: listing.rentalUnit ?? (listing.roomType === 'Habitación compartida' ? 'bed' : 'room'),
    bedType: listing.bedType ?? (roomCapacity === 2 && listing.roomType !== 'Habitación compartida' ? 'double' : 'single'),
    bedCount: Math.min(10, Math.max(1, listing.bedCount ?? (listing.roomType === 'Habitación compartida' ? roomCapacity : 1))),
    currentRoomResidents: Math.min(roomCapacity - 1, Math.max(0, listing.currentRoomResidents ?? 0)),
    bathroom: listing.bathroom ?? 'Baño compartido',
    toilet: listing.toilet ?? (listing.bathroom === 'Baño privado' ? 'Aseo privado' : 'Aseo compartido'),
    shower: listing.shower,
    kitchen: listing.kitchen ?? 'Cocina compartida',
    heatingType: listing.heatingType ?? 'none',
    accessible: listing.accessible ?? false,
    floor: listing.floor ?? '1',
    furnished: listing.furnished ?? true,
    amenities,
    monthlyPrice: listing.monthlyPrice ?? (listing.rentalMode === 'long' ? listing.price : 0),
    nightlyPrice: listing.nightlyPrice ?? (listing.rentalMode === 'holiday' ? listing.price : 0),
    weeklyPrice: listing.weeklyPrice,
    depositAmount: listing.depositAmount ?? 0,
    billsIncluded: listing.billsIncluded ?? false,
    billsNote: listing.billsIncluded ? '' : billsAmountFromText(listing.bills),
    availableFrom: listing.availableFrom,
    availableUntil: listing.availableUntil ?? '',
    minimumStayMonths: listing.minimumStayMonths ?? 1,
    minimumNights: listing.minimumNights ?? 1,
    expiresAt: listing.expiresAt,
    tenantRequirement: listing.tenantRequirement ?? 'any',
    acceptedTenantTypes: listing.acceptedTenantTypes?.length ? listing.acceptedTenantTypes : acceptedForRequirement(listing.tenantRequirement ?? 'any'),
    householdGender: listing.householdGender ?? 'unknown',
    householdHasChildren: listing.householdHasChildren ?? false,
    couplesAllowed: listing.couplesAllowed ?? (listing.tenantRequirement === 'couple' || listing.tenantRequirement === 'any'),
    smokingAllowed: listing.smokingAllowed ?? false,
    petsAllowed: listing.petsAllowed ?? false,
    childrenAllowed: listing.childrenAllowed ?? false,
    empadronamientoAllowed: listing.empadronamientoAllowed ?? false,
    rules: listing.homeDescription,
    images: listing.images,
    video: listing.video,
    title: listing.title,
    description: listing.description,
    contactName: listing.owner.name,
    contactPhone: listing.contactPhone ?? '',
    contactWhatsapp: listing.contactWhatsapp ?? '',
    contactEmail: listing.contactEmail ?? '',
    showPhone: listing.showPhone,
    showWhatsApp: listing.showWhatsApp,
    status: listing.status,
  }
}

function readEditDraft(listing: Listing, storageKey: string, currentUserId?: string) {
  const defaults = toDraft(listing)
  try {
    const stored = storageKey
      ? JSON.parse(localStorage.getItem(storageKey) ?? 'null') as { version?: number; ownerUserId?: string; listingId?: string; data?: Partial<ListingDraft> } | null
      : null
    if (
      stored?.version === 3
      && stored.listingId === listing.id
      && (!stored.ownerUserId || stored.ownerUserId === currentUserId)
      && stored.data
    ) {
      return { ...defaults, ...stored.data }
    }
  } catch { /* use server values */ }
  return defaults
}

function toListing(draft: ListingDraft, previous: Listing, ownerUserId?: string): Listing {
  const price = draft.rentalMode === 'holiday' ? draft.nightlyPrice : draft.monthlyPrice
  const availableSpots = Math.max(0, draft.roomCapacity - draft.currentRoomResidents)
  const exactCoordinates = draft.coordinates
  const contactName = draft.contactName.trim()
  const listing: Listing = {
    ...previous,
    title: draft.title.trim(),
    city: draft.city,
    area: draft.area.trim(),
    street: draft.street.trim(),
    postcode: draft.postcode.trim(),
    approximateAddress: `${draft.area.trim()} · ubicación en el mapa`,
    coordinates: approximatePublicCoordinates(exactCoordinates),
    exactCoordinates,
    price,
    cadence: draft.rentalMode === 'holiday' ? 'noche' : 'mes',
    monthlyPrice: draft.monthlyPrice,
    nightlyPrice: draft.rentalMode === 'holiday' ? draft.nightlyPrice : undefined,
    weeklyPrice: draft.rentalMode === 'holiday' ? draft.weeklyPrice : undefined,
    rentalMode: draft.rentalMode,
    roomType: draft.roomType,
    roomSizeM2: draft.roomSizeM2,
    homeSizeM2: draft.homeSizeM2,
    bedroomCount: draft.bedroomCount,
    bathroomCount: draft.bathroomCount,
    currentResidents: draft.currentResidents,
    roomCapacity: draft.roomCapacity,
    rentalUnit: draft.rentalUnit,
    bedType: draft.bedType,
    bedCount: draft.bedCount,
    currentRoomResidents: draft.currentRoomResidents,
    availableSpots,
    bathroom: draft.bathroom,
    toilet: draft.toilet,
    shower: draft.shower,
    kitchen: draft.kitchen,
    heatingType: draft.heatingType,
    accessible: draft.accessible,
    floor: draft.floor,
    furnished: draft.furnished,
    amenities: normalizeEquipmentAmenities(draft.amenities),
    depositAmount: draft.depositAmount,
    deposit: draft.depositAmount ? `${draft.depositAmount} €` : 'Sin fianza',
    billsIncluded: draft.billsIncluded,
    bills: draft.billsIncluded ? 'Gastos incluidos en el precio' : draft.billsNote ? `Gastos aparte: aprox. ${draft.billsNote} €/mes` : 'Gastos aparte',
    availableFrom: draft.availableFrom,
    availableUntil: draft.availableUntil || undefined,
    available: `Disponible desde ${new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium' }).format(new Date(`${draft.availableFrom}T12:00:00`))}`,
    minimumStayMonths: draft.rentalMode === 'long' ? draft.minimumStayMonths : previous.minimumStayMonths,
    minimumNights: draft.rentalMode === 'holiday' ? draft.minimumNights : undefined,
    minimumStay: draft.rentalMode === 'holiday' ? `Mínimo ${draft.minimumNights} ${draft.minimumNights === 1 ? 'noche' : 'noches'}` : `Mínimo ${draft.minimumStayMonths} ${draft.minimumStayMonths === 1 ? 'mes' : 'meses'}`,
    tenantRequirement: draft.tenantRequirement,
    acceptedTenantTypes: draft.acceptedTenantTypes,
    householdGender: draft.householdGender,
    householdHasChildren: draft.householdHasChildren,
    couplesAllowed: draft.couplesAllowed,
    smokingAllowed: draft.smokingAllowed,
    petsAllowed: draft.petsAllowed,
    childrenAllowed: draft.childrenAllowed,
    empadronamientoAllowed: draft.empadronamientoAllowed,
    description: draft.description.trim(),
    homeDescription: draft.rules,
    images: draft.images,
    video: draft.video,
    expiresAt: draft.expiresAt,
    owner: { ...previous.owner, name: contactName, initials: ownerInitials(contactName) },
    ownerUserId: previous.ownerUserId ?? ownerUserId,
    contactPhone: draft.contactPhone,
    contactWhatsapp: draft.contactWhatsapp,
    contactEmail: draft.contactEmail,
    showPhone: draft.showPhone,
    showWhatsApp: draft.showWhatsApp,
  }
  listing.restrictions = getCriticalRestrictions(listing)
  return listing
}

function Section({ id, title, hint, children }: { id: string; title: string; hint?: string; children: React.ReactNode }) {
  return <section id={id} className="listing-edit-section"><header><h2>{title}</h2>{hint ? <p>{hint}</p> : null}</header>{children}</section>
}

export function ListingEditPage() {
  const { language } = useI18n()
  const { id } = useParams()
  const navigate = useNavigate()
  const { allListings, ownedListings, updateListing, currentUser, canManageListing } = useApp()
  const existing = ownedListings.find((listing) => listing.id === id)
  const storageKey = id ? editDraftKey(id) : ''
  const [draft, setDraft] = useState<ListingDraft | null>(() =>
    existing ? readEditDraft(existing, storageKey, currentUser?.id) : null,
  )
  const [baseline, setBaseline] = useState(() => {
    if (!existing || !draft) return ''
    const serverDraft = toDraft(existing)
    return JSON.stringify({ ...serverDraft, publicationKey: draft.publicationKey })
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [processingImages, setProcessingImages] = useState(false)
  const savingRef = useRef(false)
  const draftListingIdRef = useRef(existing?.id ?? null)

  const equipment = readEquipmentAmenities(draft?.amenities ?? [])
  const isDirty = Boolean(draft && JSON.stringify(draft) !== baseline)
  const nonDraftMedia = useMemo(() => {
    const refs = new Set([...allListings, ...ownedListings].flatMap((listing) => [
      ...listing.images,
      ...(listing.video ? [listing.video] : []),
    ]))
    if (currentUser?.avatarRef) refs.add(currentUser.avatarRef)
    return refs
  }, [allListings, currentUser?.avatarRef, ownedListings])

  useEffect(() => {
    if (!existing || !storageKey || draftListingIdRef.current === existing.id) return
    const nextDraft = readEditDraft(existing, storageKey, currentUser?.id)
    draftListingIdRef.current = existing.id
    savingRef.current = false
    setSaving(false)
    setProcessingImages(false)
    setErrors({})
    setDraft(nextDraft)
    setBaseline(JSON.stringify({ ...toDraft(existing), publicationKey: nextDraft.publicationKey }))
  }, [currentUser?.id, existing, storageKey])

  useEffect(() => {
    if (!draft || !existing || !storageKey) return
    try { localStorage.setItem(storageKey, JSON.stringify({ version: 3, ownerUserId: currentUser?.id, listingId: existing.id, data: draft })) } catch { /* autosave is best-effort */ }
  }, [currentUser?.id, draft, existing, storageKey])

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (isDirty) event.preventDefault() }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [isDirty])

  if (!existing || !canManageListing(existing)) return <Navigate to="/mis-anuncios" replace />
  if (!draft) return null

  const set = <K extends keyof ListingDraft>(key: K, value: ListingDraft[K]) => {
    setDraft((current) => current ? { ...current, [key]: value } : current)
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
      if (!current) return current
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
    else if (containsBlockedListingLink(draft.area)) next.area = listingLinkBlockedMessage
    else {
      const mismatch = municipalityAreaError(draft.city, draft.area)
      if (mismatch) next.area = mismatch
    }
    if (draft.postcode.trim() && !/^\d{5}$/.test(draft.postcode.trim())) next.postcode = 'El código postal debe tener 5 dígitos.'
    if (!Number.isInteger(draft.roomSizeM2) || draft.roomSizeM2 < 1 || draft.roomSizeM2 > 200) next.roomSizeM2 = 'Indica entre 1 y 200 m².'
    if (!Number.isInteger(draft.homeSizeM2) || draft.homeSizeM2 < draft.roomSizeM2) next.homeSizeM2 = 'Debe ser igual o mayor que la habitación.'
    if (!Number.isInteger(draft.bedroomCount) || draft.bedroomCount < 1) next.bedroomCount = 'Indica al menos una habitación.'
    if (!Number.isInteger(draft.bathroomCount) || draft.bathroomCount < 0) next.bathroomCount = 'Indica un número válido.'
    if (draft.roomCapacity < 1 || draft.roomCapacity > 10) next.roomCapacity = 'La capacidad debe estar entre 1 y 10.'
    if (draft.currentRoomResidents < 0 || draft.currentRoomResidents >= draft.roomCapacity) next.currentRoomResidents = 'Debe quedar al menos una plaza libre.'
    if (!equipment.bedding) next.bedding = 'Selecciona una opción.'
    if (!equipment.refrigerator) next.refrigerator = 'Selecciona una opción.'
    if (!equipment.balcony) next.balcony = 'Selecciona una opción.'
    if (!equipment.washingMachine) next.washingMachine = 'Selecciona una opción.'
    const price = draft.rentalMode === 'holiday' ? draft.nightlyPrice : draft.monthlyPrice
    if (!Number.isInteger(price) || price < 1) next.price = 'Indica un precio válido.'
    if (!Number.isInteger(draft.depositAmount) || draft.depositAmount < 0) next.depositAmount = 'La fianza no puede ser negativa.'
    if (!draft.billsIncluded && (!draft.billsNote.trim() || Number(draft.billsNote) <= 0)) next.billsAmount = 'Indica el gasto aproximado al mes.'
    if (!draft.availableFrom) next.availableFrom = 'Selecciona una fecha.'
    if (draft.availableUntil && draft.availableUntil < draft.availableFrom) next.availableUntil = 'La fecha final debe ser posterior.'
    if (draft.rentalMode === 'long' && draft.minimumStayMonths < 1) next.minimumStay = 'Indica al menos 1 mes.'
    if (draft.rentalMode === 'holiday' && draft.minimumNights < 1) next.minimumStay = 'Indica al menos 1 noche.'
    if (!draft.images.length) next.images = 'Añade al menos una fotografía.'
    else if (!mockMode && draft.images.some((image) => !isMediaReference(image) && !/\/media\/[0-9a-f-]{36}(?:$|[?#])/i.test(image))) next.images = 'Vuelve a añadir las fotografías no disponibles.'
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
    if (savingRef.current || processingImages || !validate()) return
    savingRef.current = true
    setSaving(true)
    try {
      const authoritative = currentUser ? { ...draft, contactEmail: currentUser.email } : draft
      const listing = toListing(authoritative, existing, currentUser?.id)
      if (!await updateListing(existing.id, listing)) return
      const usedAfterUpdate = new Set([
        ...[...allListings, ...ownedListings]
          .filter((item) => item.id !== existing.id)
          .flatMap((item) => [...item.images, ...(item.video ? [item.video] : [])]),
        ...listing.images,
        ...(listing.video ? [listing.video] : []),
        ...(currentUser?.avatarRef ? [currentUser.avatarRef] : []),
      ])
      await removeUnusedMediaReferences(
        [...existing.images, ...(existing.video ? [existing.video] : [])],
        usedAfterUpdate,
      ).catch(() => undefined)
      if (storageKey) localStorage.removeItem(storageKey)
      setBaseline(JSON.stringify(authoritative))
      toast.success('Cambios guardados')
      navigate('/mis-anuncios')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'No se pudieron guardar los cambios.')
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  const choice = <T extends string>(name: string, value: T, options: { value: T; title: string; text?: string }[], onChange: (value: T) => void) => <div className="listing-edit-choice-grid">{options.map((option) => <label key={option.value}><input type="radio" name={name} checked={value === option.value} onChange={() => onChange(option.value)} /><span><strong>{option.title}</strong>{option.text ? <small>{option.text}</small> : null}</span></label>)}</div>

  return <main className="listing-edit-page">
    <div className="listing-edit-topbar"><div className="listing-edit-topbar__inner"><Link to="/mis-anuncios" className="listing-edit-back"><ArrowLeft /> Tus anuncios</Link><strong>Editar anuncio</strong><Button onClick={save} disabled={saving || processingImages || !isDirty}><Save data-icon="inline-start" />{saving ? 'Guardando…' : processingImages ? 'Procesando foto…' : 'Guardar'}</Button></div></div>
    <div className="listing-edit-shell">
      <header className="listing-edit-heading"><p>Ref. {existing.id.slice(-6).toUpperCase()}</p><h1>Editar habitación</h1><span>Todo el anuncio está en una sola página. Baja, cambia lo que necesites y guarda al final.</span></header>

      <Section id="edit-basic" title="Tipo de alquiler">
        {choice('edit-rental-mode', draft.rentalMode, [
          { value: 'long', title: 'Larga estancia', text: 'Precio mensual' },
          { value: 'holiday', title: 'Alquiler vacacional', text: 'Precio por noche' },
        ], (value) => set('rentalMode', value))}
      </Section>

      <Section id="edit-location" title="Ubicación" hint="La dirección exacta no se muestra públicamente.">
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

      <Section id="edit-room" title="Habitación y vivienda">
        {choice('edit-room-type', draft.roomType, [
          { value: 'Habitación individual', title: 'Habitación privada' },
          { value: 'Habitación compartida', title: 'Habitación compartida' },
          { value: 'Estudio', title: 'Estudio' },
        ], (value) => setDraft((current) => current ? { ...current, roomType: value, rentalUnit: value === 'Habitación compartida' ? current.rentalUnit : 'room', currentRoomResidents: value === 'Habitación compartida' ? current.currentRoomResidents : 0 } : current))}
        {draft.roomType === 'Habitación compartida' ? choice('edit-rental-unit', draft.rentalUnit, [
          { value: 'room', title: 'Habitación completa' },
          { value: 'bed', title: 'Plazas / camas' },
        ], (value) => set('rentalUnit', value)) : null}
        <div className="listing-edit-grid listing-edit-grid--3">
          <FormField label="Superficie habitación (m²)" htmlFor="edit-room-size" error={errors.roomSizeM2}><Input id="edit-room-size" type="number" min="1" max="200" value={draft.roomSizeM2} aria-invalid={Boolean(errors.roomSizeM2)} onChange={(e) => set('roomSizeM2', Number(e.target.value))} /></FormField>
          <FormField label="Superficie vivienda (m²)" htmlFor="edit-home-size" error={errors.homeSizeM2}><Input id="edit-home-size" type="number" min="1" value={draft.homeSizeM2} aria-invalid={Boolean(errors.homeSizeM2)} onChange={(e) => set('homeSizeM2', Number(e.target.value))} /></FormField>
          <FormField label="Habitaciones" htmlFor="edit-bedrooms" error={errors.bedroomCount}><Input id="edit-bedrooms" type="number" min="1" value={draft.bedroomCount} aria-invalid={Boolean(errors.bedroomCount)} onChange={(e) => set('bedroomCount', Number(e.target.value))} /></FormField>
          <FormField label="Baños" htmlFor="edit-bathrooms" error={errors.bathroomCount}><Input id="edit-bathrooms" type="number" min="0" value={draft.bathroomCount} aria-invalid={Boolean(errors.bathroomCount)} onChange={(e) => set('bathroomCount', Number(e.target.value))} /></FormField>
          <FormField label="Personas en la vivienda" htmlFor="edit-residents"><Input id="edit-residents" type="number" min="0" value={draft.currentResidents} onChange={(e) => set('currentResidents', Number(e.target.value))} /></FormField>
          <FormField label="Capacidad habitación" htmlFor="edit-capacity" error={errors.roomCapacity}><select id="edit-capacity" value={draft.roomCapacity} aria-invalid={Boolean(errors.roomCapacity)} onChange={(e) => set('roomCapacity', Number(e.target.value))}>{Array.from({ length: 10 }, (_, index) => <option key={index + 1} value={index + 1}>{index + 1}</option>)}</select></FormField>
          <FormField label="Personas ya en la habitación" htmlFor="edit-room-residents" error={errors.currentRoomResidents}><Input id="edit-room-residents" type="number" min="0" value={draft.currentRoomResidents} aria-invalid={Boolean(errors.currentRoomResidents)} onChange={(e) => set('currentRoomResidents', Number(e.target.value))} /></FormField>
          <FormField label="Tipo de cama" htmlFor="edit-bed-type"><select id="edit-bed-type" value={draft.bedType} onChange={(e) => set('bedType', e.target.value as ListingDraft['bedType'])}><option value="single">{bedTypeOptionLabel(language, 'single')}</option><option value="double" disabled={draft.rentalUnit === 'bed'}>{bedTypeOptionLabel(language, 'double')}</option><option value="bunk">{bedTypeOptionLabel(language, 'bunk')}</option></select></FormField>
          <FormField label="Número de camas" htmlFor="edit-bed-count"><Input id="edit-bed-count" type="number" min="1" max="10" value={draft.bedCount} onChange={(e) => set('bedCount', Number(e.target.value))} /></FormField>
          <FormField label="Baño" htmlFor="edit-bathroom"><select id="edit-bathroom" value={draft.bathroom} onChange={(e) => set('bathroom', e.target.value as ListingDraft['bathroom'])}><option>Baño compartido</option><option>Baño privado</option></select></FormField>
          <FormField label="Aseo / WC" htmlFor="edit-toilet"><select id="edit-toilet" value={draft.toilet} onChange={(e) => set('toilet', e.target.value as ListingDraft['toilet'])}><option>Aseo compartido</option><option>Aseo privado</option></select></FormField>
          <FormField label="Ducha" htmlFor="edit-shower"><select id="edit-shower" value={draft.shower} onChange={(e) => set('shower', e.target.value as ListingDraft['shower'])}><option>Ducha compartida</option><option>Ducha privada</option></select></FormField>
          <FormField label="Cocina" htmlFor="edit-kitchen"><select id="edit-kitchen" value={draft.kitchen} onChange={(e) => set('kitchen', e.target.value as ListingDraft['kitchen'])}><option>Cocina compartida</option><option>Cocina privada</option></select></FormField>
          <FormField label="Planta" htmlFor="edit-floor"><select id="edit-floor" value={draft.floor} onChange={(e) => set('floor', e.target.value as ListingDraft['floor'])}><option value="basement">Sótano</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4+">4+</option><option value="top">Última planta</option></select></FormField>
          <FormField label="Calefacción" htmlFor="edit-heating"><select id="edit-heating" value={draft.heatingType} onChange={(e) => set('heatingType', e.target.value as ListingDraft['heatingType'])}><option value="none">Sin calefacción</option><option value="individual">Individual</option><option value="central">Central</option><option value="unknown">No especificado</option></select></FormField>
          <FormField label="Ropa de cama" htmlFor="edit-bedding" error={errors.bedding}><select id="edit-bedding" value={equipment.bedding} aria-invalid={Boolean(errors.bedding)} onChange={(e) => setEquipment('bedding', e.target.value as EquipmentSelections['bedding'])}><option value="">Selecciona</option><option value="included">Incluida</option><option value="not_included">No incluida</option></select></FormField>
          <FormField label="Frigorífico" htmlFor="edit-refrigerator" error={errors.refrigerator}><select id="edit-refrigerator" value={equipment.refrigerator} aria-invalid={Boolean(errors.refrigerator)} onChange={(e) => setEquipment('refrigerator', e.target.value as EquipmentSelections['refrigerator'])}><option value="">Selecciona</option><option value="individual">Individual</option><option value="shared">Compartido</option><option value="none">No disponible</option></select></FormField>
          <FormField label="Balcón" htmlFor="edit-balcony" error={errors.balcony}><select id="edit-balcony" value={equipment.balcony} aria-invalid={Boolean(errors.balcony)} onChange={(e) => setEquipment('balcony', e.target.value as EquipmentSelections['balcony'])}><option value="">Selecciona</option><option value="yes">Sí</option><option value="no">No</option></select></FormField>
          <FormField label="Lavadora" htmlFor="edit-washing" error={errors.washingMachine}><select id="edit-washing" value={equipment.washingMachine} aria-invalid={Boolean(errors.washingMachine)} onChange={(e) => setEquipment('washingMachine', e.target.value as EquipmentSelections['washingMachine'])}><option value="">Selecciona</option><option value="individual">Individual</option><option value="shared">Compartida</option><option value="none">No disponible</option></select></FormField>
        </div>
        <div className="listing-edit-checks"><label><Checkbox checked={draft.furnished} onCheckedChange={(value) => set('furnished', value === true)} />Amueblada</label><label><Checkbox checked={draft.accessible} onCheckedChange={(value) => set('accessible', value === true)} />Accesible</label></div>
        <div className="listing-edit-amenities"><strong>Equipamiento y servicios</strong><div>{amenityOptions.map((item) => <label key={item}><Checkbox checked={draft.amenities.includes(item)} onCheckedChange={() => toggleAmenity(item)} />{item}</label>)}</div></div>
      </Section>

      <Section id="edit-price" title="Precio, gastos y fianza">
        <div className="listing-edit-grid listing-edit-grid--3">
          {draft.rentalMode === 'long' ? <FormField label="Alquiler mensual (€)" htmlFor="edit-monthly-price" error={errors.price}><Input id="edit-monthly-price" type="number" min="1" value={draft.monthlyPrice} aria-invalid={Boolean(errors.price)} onChange={(e) => set('monthlyPrice', Number(e.target.value))} /></FormField> : <FormField label="Precio por noche (€)" htmlFor="edit-nightly-price" error={errors.price}><Input id="edit-nightly-price" type="number" min="1" value={draft.nightlyPrice} aria-invalid={Boolean(errors.price)} onChange={(e) => set('nightlyPrice', Number(e.target.value))} /></FormField>}
          {draft.rentalMode === 'holiday' ? <FormField label="Precio semanal (€)" htmlFor="edit-weekly-price"><Input id="edit-weekly-price" type="number" min="0" value={draft.weeklyPrice ?? ''} onChange={(e) => set('weeklyPrice', e.target.value ? Number(e.target.value) : undefined)} /></FormField> : null}
          <FormField label="Fianza (€)" htmlFor="edit-deposit" error={errors.depositAmount}><Input id="edit-deposit" type="number" min="0" value={draft.depositAmount} aria-invalid={Boolean(errors.depositAmount)} onChange={(e) => set('depositAmount', Number(e.target.value))} /></FormField>
        </div>
        <label className="listing-edit-inline-check"><Checkbox checked={draft.billsIncluded} onCheckedChange={(value) => set('billsIncluded', value === true)} />Gastos incluidos en el precio</label>
        {!draft.billsIncluded ? <FormField label="Gastos aproximados al mes (€)" htmlFor="edit-bills" error={errors.billsAmount}><Input id="edit-bills" inputMode="decimal" value={draft.billsNote} aria-invalid={Boolean(errors.billsAmount)} onChange={(e) => set('billsNote', e.target.value)} /></FormField> : null}
      </Section>

      <Section id="edit-availability" title="Disponibilidad">
        <div className="listing-edit-grid listing-edit-grid--3">
          <FormField label="Disponible desde" htmlFor="edit-from" error={errors.availableFrom}><Input id="edit-from" type="date" value={draft.availableFrom} aria-invalid={Boolean(errors.availableFrom)} onChange={(e) => set('availableFrom', e.target.value)} /></FormField>
          <FormField label="Disponible hasta" htmlFor="edit-until" error={errors.availableUntil}><Input id="edit-until" type="date" value={draft.availableUntil} aria-invalid={Boolean(errors.availableUntil)} onChange={(e) => set('availableUntil', e.target.value)} /></FormField>
          {draft.rentalMode === 'long' ? <FormField label="Estancia mínima (meses)" htmlFor="edit-min-months" error={errors.minimumStay}><Input id="edit-min-months" type="number" min="1" value={draft.minimumStayMonths} aria-invalid={Boolean(errors.minimumStay)} onChange={(e) => set('minimumStayMonths', Number(e.target.value))} /></FormField> : <FormField label="Estancia mínima (noches)" htmlFor="edit-min-nights" error={errors.minimumStay}><Input id="edit-min-nights" type="number" min="1" value={draft.minimumNights} aria-invalid={Boolean(errors.minimumStay)} onChange={(e) => set('minimumNights', Number(e.target.value))} /></FormField>}
        </div>
      </Section>

      <Section id="edit-household" title="Convivencia y requisitos">
        <FormField label="A quién buscas" htmlFor="edit-requirement"><select id="edit-requirement" value={draft.tenantRequirement} onChange={(e) => { const value = e.target.value as TenantRequirement; setDraft((current) => current ? { ...current, tenantRequirement: value, acceptedTenantTypes: acceptedForRequirement(value) } : current) }}><option value="any">Sin preferencia</option><option value="single-person">Una persona</option><option value="single-man">Solo hombre</option><option value="single-woman">Solo mujer</option><option value="couple">Pareja</option></select></FormField>
        <div className="listing-edit-tenant-types"><strong>Perfiles aceptados</strong>{(['man','woman','couple','family'] as AcceptedTenantType[]).map((item) => <label key={item}><Checkbox checked={draft.acceptedTenantTypes.includes(item)} onCheckedChange={() => toggleAccepted(item)} />{{ man: 'Hombre', woman: 'Mujer', couple: 'Pareja', family: 'Familia' }[item]}</label>)}</div>
        <div className="listing-edit-grid">
          <FormField label="Composición actual" htmlFor="edit-gender"><select id="edit-gender" value={draft.householdGender} onChange={(e) => set('householdGender', e.target.value as ListingDraft['householdGender'])}><option value="unknown">No especificado</option><option value="men">Hombres</option><option value="women">Mujeres</option><option value="mixed">Mixto</option></select></FormField>
        </div>
        <div className="listing-edit-checks listing-edit-checks--wrap"><label><Checkbox checked={draft.couplesAllowed} onCheckedChange={(value) => set('couplesAllowed', value === true)} />Se aceptan parejas</label><label><Checkbox checked={draft.smokingAllowed} onCheckedChange={(value) => set('smokingAllowed', value === true)} />Se permite fumar</label><label><Checkbox checked={draft.petsAllowed} onCheckedChange={(value) => set('petsAllowed', value === true)} />Se aceptan mascotas</label><label><Checkbox checked={draft.childrenAllowed} onCheckedChange={(value) => set('childrenAllowed', value === true)} />Se aceptan menores</label><label><Checkbox checked={draft.householdHasChildren} onCheckedChange={(value) => set('householdHasChildren', value === true)} />Ya viven menores</label><label><Checkbox checked={draft.empadronamientoAllowed} onCheckedChange={(value) => set('empadronamientoAllowed', value === true)} />Empadronamiento posible</label></div>
        <FormField label="Normas de la vivienda" htmlFor="edit-rules" description="No se permiten enlaces ni dominios externos." error={errors.rules}><Textarea id="edit-rules" rows={5} value={draft.rules} aria-invalid={Boolean(errors.rules)} onChange={(e) => set('rules', e.target.value)} /></FormField>
      </Section>

      <Section id="edit-photos" title="Fotografías" hint="Hasta 15 fotos y, opcionalmente, un vídeo de hasta 30 segundos. La primera foto será la portada.">
        <ImageUploader images={draft.images} onChange={(images) => set('images', images)} onRemove={(image) => { if (!existing.images.includes(image)) void removeUnusedMediaReferences([image], nonDraftMedia).catch(() => undefined) }} onProcessingChange={setProcessingImages} error={errors.images} />
        <VideoUploader video={draft.video} onChange={(video) => set('video', video)} onRemove={(video) => { if (video !== existing.video) void removeUnusedMediaReferences([video], nonDraftMedia).catch(() => undefined) }} error={errors.video} />
      </Section>

      <Section id="edit-description" title="Título y descripción">
        <FormField label="Título del anuncio" htmlFor="edit-title" description="Máximo 80 caracteres." error={errors.title}><Input id="edit-title" maxLength={80} value={draft.title} aria-invalid={Boolean(errors.title)} onChange={(e) => set('title', e.target.value)} /></FormField>
        <FormField label="Descripción" htmlFor="edit-description-text" description="No se permiten enlaces ni dominios externos." error={errors.description}><Textarea id="edit-description-text" rows={9} value={draft.description} aria-invalid={Boolean(errors.description)} onChange={(e) => set('description', e.target.value)} /></FormField>
      </Section>

      <Section id="edit-contact" title="Contacto">
        <div className="listing-edit-grid">
          <FormField label="Nombre" htmlFor="edit-contact-name" error={errors.contactName}><Input id="edit-contact-name" value={draft.contactName} aria-invalid={Boolean(errors.contactName)} onChange={(e) => set('contactName', e.target.value)} /></FormField>
          <FormField label="Email" htmlFor="edit-contact-email"><Input id="edit-contact-email" type="email" value={currentUser?.email ?? draft.contactEmail} disabled /></FormField>
          <FormField label="Teléfono" htmlFor="edit-contact-phone" error={errors.contactPhone}><Input id="edit-contact-phone" value={draft.contactPhone} aria-invalid={Boolean(errors.contactPhone)} onChange={(e) => set('contactPhone', e.target.value)} /></FormField>
          <FormField label="WhatsApp" htmlFor="edit-contact-whatsapp" error={errors.contactWhatsapp}><Input id="edit-contact-whatsapp" value={draft.contactWhatsapp} aria-invalid={Boolean(errors.contactWhatsapp)} onChange={(e) => set('contactWhatsapp', e.target.value)} /></FormField>
        </div>
        <div className="listing-edit-checks"><label><Checkbox checked={draft.showPhone} onCheckedChange={(value) => set('showPhone', value === true)} />Mostrar teléfono</label><label><Checkbox checked={draft.showWhatsApp} onCheckedChange={(value) => set('showWhatsApp', value === true)} />Mostrar WhatsApp</label></div>
        {errors.contactMethods ? <p className="field-error" role="alert">{errors.contactMethods}</p> : null}
      </Section>

      <div className="listing-edit-final"><div><strong>{processingImages ? 'Procesando la foto…' : isDirty ? 'Tienes cambios sin guardar' : 'Todo guardado'}</strong><span>{processingImages ? 'El giro ya se muestra; terminamos de guardar la imagen.' : 'Revisamos todos los campos al guardar.'}</span></div><Button size="lg" onClick={save} disabled={saving || processingImages || !isDirty}><Save data-icon="inline-start" />{saving ? 'Guardando…' : processingImages ? 'Procesando foto…' : 'Guardar cambios'}</Button></div>
    </div>
  </main>
}
