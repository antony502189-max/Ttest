import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { ArrowLeft, ArrowRight, CheckCircle2, Eye, FileCheck2, Info, MapPin, Save } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { FormField, ImageUploader, Stepper } from '@/components/forms'
import { PropertyBadge, PropertyCard, PropertyGallery } from '@/components/marketplace'
import { useApp } from '@/contexts/app-context'
import { createDefaultDraft } from '@/data/listings'
import type { Listing, ListingDraft } from '@/types'

const steps = ['Tipo de alquiler', 'Ubicación', 'Habitación', 'Precio y gastos', 'Disponibilidad', 'Convivencia', 'Fotografías', 'Descripción', 'Contacto', 'Vista previa']
const draftKey = '112233:listing-draft:v2'

const toDraft = (listing: Listing): ListingDraft => ({
  rentalMode: listing.rentalMode, city: listing.city, area: listing.area, street: '', postcode: '', roomType: listing.roomType, size: 12, occupants: listing.occupants,
  bathroom: listing.bathroom, kitchen: listing.kitchen, furnished: listing.furnished, amenities: listing.amenities, price: listing.price, depositAmount: listing.depositAmount,
  billsIncluded: listing.billsIncluded, billsNote: listing.bills, availableFrom: listing.availableFrom, minimumStayMonths: listing.minimumStayMonths, expiresAt: listing.expiresAt,
  genderPreference: listing.genderPreference, smokingAllowed: listing.smokingAllowed, petsAllowed: listing.petsAllowed, couplesAllowed: listing.couplesAllowed,
  childrenAllowed: listing.childrenAllowed, empadronamientoAllowed: listing.empadronamientoAllowed, rules: listing.homeDescription, images: listing.images,
  title: listing.title, description: listing.description, contactName: listing.owner.name, contactPhone: listing.contactPhone ?? '', contactWhatsapp: listing.contactPhone ?? '', contactEmail: listing.contactEmail ?? '', status: listing.status,
})

const toListing = (draft: ListingDraft, previous?: Listing): Listing => {
  const restrictions = [draft.genderPreference, draft.couplesAllowed ? 'Parejas permitidas' : 'No parejas', draft.petsAllowed ? 'Mascotas permitidas' : 'Sin mascotas', draft.smokingAllowed ? 'Se puede fumar' : 'No fumar', draft.empadronamientoAllowed ? 'Empadronamiento posible' : 'Sin empadronamiento', draft.rentalMode === 'holiday' ? 'Mínimo 3 noches' : `Mínimo ${draft.minimumStayMonths} ${draft.minimumStayMonths === 1 ? 'mes' : 'meses'}`]
  if (draft.billsIncluded) restrictions.push('Gastos incluidos')
  const id = previous?.id ?? `${draft.area.toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-')}-${Date.now().toString().slice(-6)}`
  return {
    id, title: draft.title, city: draft.city, area: draft.area, approximateAddress: `${draft.area} · ubicación aproximada`, price: draft.price,
    cadence: draft.rentalMode === 'holiday' ? 'noche' : 'mes', rentalMode: draft.rentalMode, roomType: draft.roomType,
    available: `Disponible desde ${new Intl.DateTimeFormat('es-ES', { dateStyle: 'medium' }).format(new Date(`${draft.availableFrom}T12:00:00`))}`, availableFrom: draft.availableFrom,
    minimumStay: draft.rentalMode === 'holiday' ? 'Mínimo 3 noches' : `Mínimo ${draft.minimumStayMonths} ${draft.minimumStayMonths === 1 ? 'mes' : 'meses'}`, minimumStayMonths: draft.minimumStayMonths,
    deposit: draft.depositAmount ? `${draft.depositAmount} €` : 'Sin fianza', depositAmount: draft.depositAmount, bills: draft.billsNote || (draft.billsIncluded ? 'Gastos incluidos' : 'Gastos aparte'), billsIncluded: draft.billsIncluded,
    bathroom: draft.bathroom, kitchen: draft.kitchen, furnished: draft.furnished, occupants: draft.occupants, coordinates: previous?.coordinates ?? { lat: 28.1227, lng: -16.7244 },
    genderPreference: draft.genderPreference, smokingAllowed: draft.smokingAllowed, petsAllowed: draft.petsAllowed, couplesAllowed: draft.couplesAllowed, childrenAllowed: draft.childrenAllowed, empadronamientoAllowed: draft.empadronamientoAllowed,
    restrictions, amenities: draft.amenities, description: draft.description, homeDescription: draft.rules, images: draft.images,
    owner: previous?.owner ?? { name: draft.contactName, initials: draft.contactName.split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toLocaleUpperCase(), since: 'Publica desde 2026', response: 'Suele responder en el mismo día', verified: false },
    advertiserType: 'Particular', source: 'Creado en esta demo', status: 'Publicado', publishedAt: previous?.publishedAt ?? new Date().toISOString(), views: previous?.views ?? 0, expiresAt: draft.expiresAt, userCreated: true, contactPhone: draft.contactPhone, contactEmail: draft.contactEmail,
  }
}

function WizardSection({ title, description, children }: { title: string; description: string; children: ReactNode }) { return <section className="wizard-section"><header><h2>{title}</h2><p>{description}</p></header>{children}</section> }

export function PublishPage({ editing = false }: { editing?: boolean }) {
  const { id } = useParams()
  const { allListings, createListing, updateListing, currentUser } = useApp()
  const existing = editing ? allListings.find((listing) => listing.id === id) : undefined
  const [draft, setDraft] = useState<ListingDraft>(() => {
    if (existing) return toDraft(existing)
    try { const saved = localStorage.getItem(draftKey); return saved ? { ...createDefaultDraft(), ...JSON.parse(saved) as ListingDraft } : createDefaultDraft() } catch { return createDefaultDraft() }
  })
  const [step, setStep] = useState(0)
  const [maxVisited, setMaxVisited] = useState(0)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [published, setPublished] = useState(false)
  const set = <K extends keyof ListingDraft>(key: K, value: ListingDraft[K]) => setDraft((current) => ({ ...current, [key]: value }))
  const preview = useMemo(() => toListing(draft, existing), [draft, existing])
  useEffect(() => { localStorage.setItem(draftKey, JSON.stringify(draft)) }, [draft])
  useEffect(() => { const warn = (event: BeforeUnloadEvent) => { if (!published) event.preventDefault() }; window.addEventListener('beforeunload', warn); return () => window.removeEventListener('beforeunload', warn) }, [published])
  if (editing && !existing) return <Navigate to="/mis-anuncios" replace />

  const validate = () => {
    const next: Record<string, string> = {}
    if (step === 1 && !draft.area.trim()) next.area = 'Indica la zona o barrio.'
    if (step === 2 && draft.occupants < 1) next.occupants = 'Indica al menos una persona.'
    if (step === 3 && draft.price < 1) next.price = 'El precio debe ser mayor que cero.'
    if (step === 4 && !draft.availableFrom) next.availableFrom = 'Selecciona una fecha.'
    if (step === 6 && !draft.images.length) next.images = 'Añade al menos una fotografía.'
    if (step === 7 && draft.title.trim().length < 15) next.title = 'Escribe un título de al menos 15 caracteres.'
    if (step === 7 && draft.description.trim().length < 40) next.description = 'La descripción debe tener al menos 40 caracteres.'
    if (step === 8 && !draft.contactName.trim()) next.contactName = 'Indica un nombre público.'
    if (step === 8 && !/^\+?[\d\s-]{7,}$/.test(draft.contactPhone)) next.contactPhone = 'Introduce un teléfono válido.'
    if (step === 8 && !/^\S+@\S+\.\S+$/.test(draft.contactEmail)) next.contactEmail = 'Introduce un email válido.'
    setErrors(next)
    if (Object.keys(next).length) requestAnimationFrame(() => document.querySelector<HTMLElement>('[aria-invalid="true"], .field-error')?.focus())
    return Object.keys(next).length === 0
  }
  const next = () => { if (!validate()) return; const value = Math.min(steps.length - 1, step + 1); setStep(value); setMaxVisited((current) => Math.max(current, value)); window.scrollTo({ top: 0, behavior: 'smooth' }) }
  const finish = () => { const listing = toListing(draft, existing); if (existing) { updateListing(existing.id, listing); toast.success('Cambios publicados') } else createListing(listing); localStorage.removeItem(draftKey); setPublished(true) }

  const choice = <T extends string>(name: string, value: T, options: { value: T; title: string; text: string }[], onChange: (value: T) => void) => <div className="wizard-choice-grid">{options.map((option) => <label key={option.value}><input type="radio" name={name} checked={value === option.value} onChange={() => onChange(option.value)} /><span><strong>{option.title}</strong><small>{option.text}</small></span></label>)}</div>
  const toggleAmenity = (item: string) => set('amenities', draft.amenities.includes(item) ? draft.amenities.filter((value) => value !== item) : [...draft.amenities, item])
  const content = (() => {
    switch (step) {
      case 0: return <WizardSection title="¿Qué tipo de estancia ofreces?" description="El precio, las fechas y la duración se adaptan al tipo de alquiler.">{choice('rental-mode', draft.rentalMode, [{ value: 'long', title: 'Larga estancia', text: 'Precio mensual.' }, { value: 'holiday', title: 'Alquiler vacacional', text: 'Precio por noche.' }], (value) => set('rentalMode', value))}<Alert><Info /><AlertTitle>Información clara</AlertTitle><AlertDescription>Las condiciones se mostrarán antes del contacto.</AlertDescription></Alert></WizardSection>
      case 1: return <WizardSection title="Sitúa la habitación" description="La dirección exacta no se muestra públicamente."><div className="form-grid"><FormField label="Municipio" htmlFor="publish-city"><select id="publish-city" value={draft.city} onChange={(event) => set('city', event.target.value)}><option>Adeje</option><option>Arona</option><option>Granadilla de Abona</option><option>Santa Cruz de Tenerife</option><option>San Cristóbal de La Laguna</option></select></FormField><FormField label="Zona o barrio" htmlFor="publish-area" error={errors.area}><Input id="publish-area" value={draft.area} aria-invalid={Boolean(errors.area)} aria-describedby={errors.area ? 'publish-area-error' : undefined} onChange={(event) => set('area', event.target.value)} /></FormField><FormField label="Calle" htmlFor="publish-street"><Input id="publish-street" value={draft.street} onChange={(event) => set('street', event.target.value)} /></FormField><FormField label="Código postal" htmlFor="publish-postcode"><Input id="publish-postcode" inputMode="numeric" value={draft.postcode} onChange={(event) => set('postcode', event.target.value)} /></FormField></div><div className="location-preview"><MapPin /><div><strong>{draft.area}, {draft.city}</strong><span>Mostraremos un punto aproximado.</span></div></div></WizardSection>
      case 2: return <WizardSection title="Describe la habitación" description="Datos básicos para comparar.">{choice('room-type', draft.roomType, [{ value: 'Habitación individual', title: 'Individual', text: 'Para una persona.' }, { value: 'Habitación compartida', title: 'Compartida', text: 'Dos o más camas.' }, { value: 'Estudio', title: 'Estudio', text: 'Espacio autónomo.' }], (value) => set('roomType', value))}<div className="form-grid"><FormField label="Tamaño aproximado" htmlFor="publish-size"><Input id="publish-size" type="number" min="1" value={draft.size} onChange={(e) => set('size', Number(e.target.value))} /></FormField><FormField label="Personas que viven en casa" htmlFor="publish-occupants" error={errors.occupants}><Input id="publish-occupants" type="number" min="1" value={draft.occupants} aria-invalid={Boolean(errors.occupants)} onChange={(e) => set('occupants', Number(e.target.value))} /></FormField><FormField label="Baño" htmlFor="publish-bathroom"><select id="publish-bathroom" value={draft.bathroom} onChange={(e) => set('bathroom', e.target.value as ListingDraft['bathroom'])}><option>Baño compartido</option><option>Baño privado</option></select></FormField><FormField label="Cocina" htmlFor="publish-kitchen"><select id="publish-kitchen" value={draft.kitchen} onChange={(e) => set('kitchen', e.target.value as ListingDraft['kitchen'])}><option>Cocina compartida</option><option>Cocina privada</option></select></FormField></div><fieldset className="checks-panel"><legend>Equipamiento</legend>{['Fibra', 'Escritorio', 'Armario', 'Balcón', 'Lavadora', 'Aire acondicionado'].map((item) => <label key={item}><Checkbox checked={draft.amenities.includes(item)} onCheckedChange={() => toggleAmenity(item)} />{item}</label>)}</fieldset></WizardSection>
      case 3: return <WizardSection title="Precio, gastos y fianza" description="Separa cada concepto."><div className="form-grid"><FormField label={draft.rentalMode === 'holiday' ? 'Precio por noche' : 'Alquiler mensual'} htmlFor="publish-price" error={errors.price}><Input id="publish-price" type="number" min="1" value={draft.price} aria-invalid={Boolean(errors.price)} onChange={(e) => set('price', Number(e.target.value))} /></FormField><FormField label="Fianza" htmlFor="publish-deposit"><Input id="publish-deposit" type="number" min="0" value={draft.depositAmount} onChange={(e) => set('depositAmount', Number(e.target.value))} /></FormField></div><label className="check-row"><Checkbox checked={draft.billsIncluded} onCheckedChange={(value) => set('billsIncluded', value === true)} />Gastos incluidos</label><FormField label="Aclaración sobre gastos" htmlFor="publish-bills"><Input id="publish-bills" value={draft.billsNote} onChange={(e) => set('billsNote', e.target.value)} /></FormField></WizardSection>
      case 4: return <WizardSection title="Disponibilidad" description="Indica cuándo puede entrar la próxima persona."><div className="form-grid"><FormField label="Disponible desde" htmlFor="publish-available" error={errors.availableFrom}><Input id="publish-available" type="date" value={draft.availableFrom} aria-invalid={Boolean(errors.availableFrom)} onChange={(e) => set('availableFrom', e.target.value)} /></FormField><FormField label="Estancia mínima (meses)" htmlFor="publish-min-stay"><Input id="publish-min-stay" type="number" min="0" value={draft.minimumStayMonths} onChange={(e) => set('minimumStayMonths', Number(e.target.value))} /></FormField><FormField label="Fecha límite" htmlFor="publish-expiry"><Input id="publish-expiry" type="date" value={draft.expiresAt} onChange={(e) => set('expiresAt', e.target.value)} /></FormField></div></WizardSection>
      case 5: return <WizardSection title="Condiciones de convivencia" description="Exprésalas de forma concreta y neutral."><FormField label="Preferencia" htmlFor="publish-gender"><select id="publish-gender" value={draft.genderPreference} onChange={(e) => set('genderPreference', e.target.value as ListingDraft['genderPreference'])}><option>Cualquiera</option><option>Sin preferencia de género</option><option>Solo hombre</option><option>Solo mujer</option></select></FormField><fieldset className="checks-panel checks-panel--columns"><legend>Convivencia</legend>{([['couplesAllowed', 'Parejas permitidas'], ['petsAllowed', 'Mascotas permitidas'], ['smokingAllowed', 'Se puede fumar'], ['childrenAllowed', 'Niños permitidos'], ['empadronamientoAllowed', 'Empadronamiento posible']] as const).map(([key, label]) => <label key={key}><Checkbox checked={draft[key]} onCheckedChange={(value) => set(key, value === true)} />{label}</label>)}</fieldset><FormField label="Normas de la vivienda" htmlFor="publish-rules"><Textarea id="publish-rules" rows={5} value={draft.rules} onChange={(e) => set('rules', e.target.value)} /></FormField></WizardSection>
      case 6: return <WizardSection title="Fotografías" description="La primera será la portada. Puedes reordenarlas."><ImageUploader images={draft.images} onChange={(images) => set('images', images)} error={errors.images} /></WizardSection>
      case 7: return <WizardSection title="Cuenta cómo es vivir aquí" description="Responde las dudas habituales."><FormField label="Título del anuncio" htmlFor="publish-title" description="Máximo 80 caracteres." error={errors.title}><Input id="publish-title" maxLength={80} value={draft.title} aria-invalid={Boolean(errors.title)} onChange={(e) => set('title', e.target.value)} /></FormField><FormField label="Descripción" htmlFor="publish-description" error={errors.description}><Textarea id="publish-description" rows={8} value={draft.description} aria-invalid={Boolean(errors.description)} onChange={(e) => set('description', e.target.value)} /></FormField></WizardSection>
      case 8: return <WizardSection title="Datos de contacto" description="Estos canales se mostrarán tras confirmar la condición principal."><div className="form-grid"><FormField label="Nombre público" htmlFor="publish-contact-name" error={errors.contactName}><Input id="publish-contact-name" value={draft.contactName || currentUser?.name || ''} aria-invalid={Boolean(errors.contactName)} onChange={(e) => set('contactName', e.target.value)} /></FormField><FormField label="Teléfono / WhatsApp" htmlFor="publish-contact-phone" error={errors.contactPhone}><Input id="publish-contact-phone" type="tel" value={draft.contactPhone} aria-invalid={Boolean(errors.contactPhone)} onChange={(e) => { set('contactPhone', e.target.value); set('contactWhatsapp', e.target.value) }} /></FormField><FormField label="Email" htmlFor="publish-contact-email" error={errors.contactEmail}><Input id="publish-contact-email" type="email" value={draft.contactEmail} aria-invalid={Boolean(errors.contactEmail)} onChange={(e) => set('contactEmail', e.target.value)} /></FormField></div></WizardSection>
      default: return <WizardSection title="Revisa antes de publicar" description="Así se verá el anuncio."><Alert><FileCheck2 /><AlertTitle>El anuncio está completo</AlertTitle><AlertDescription>Revisa precio, condiciones y fecha de entrada.</AlertDescription></Alert><div className="preview-card-wrap"><PropertyCard listing={preview} /></div><div className="preview-conditions"><h3>Condiciones visibles</h3><div className="badge-row">{preview.restrictions.map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}</div></div><Dialog><DialogTrigger asChild><Button variant="outline"><Eye data-icon="inline-start" />Vista previa completa</Button></DialogTrigger><DialogContent className="full-preview-dialog"><DialogHeader><DialogTitle>Vista previa del anuncio</DialogTitle><DialogDescription>Versión pública antes de publicar.</DialogDescription></DialogHeader><PropertyGallery listing={preview} /><h2>{preview.title}</h2><p>{preview.description}</p></DialogContent></Dialog></WizardSection>
    }
  })()

  if (published) return <div className="publish-success"><CheckCircle2 /><span className="eyebrow">Anuncio publicado</span><h1>{editing ? 'Cambios guardados' : 'Tu habitación ya está visible'}</h1><p>El anuncio se ha guardado localmente y aparece en la búsqueda y en Mis anuncios.</p><div><Button asChild><Link to="/mis-anuncios">Ver mis anuncios</Link></Button><Button asChild variant="outline"><Link to={`/habitacion/${preview.id}`}>Ver anuncio</Link></Button></div></div>
  return <div className="publish-page"><div className="container publish-header"><Button asChild variant="ghost"><Link to="/mis-anuncios"><ArrowLeft data-icon="inline-start" />Salir</Link></Button><div><span className="eyebrow">{editing ? `Editando ${id?.slice(-5).toUpperCase()}` : 'Nuevo anuncio'}</span><h1>{editing ? 'Editar habitación' : 'Publicar una habitación'}</h1></div><Button variant="outline" onClick={() => { localStorage.setItem(draftKey, JSON.stringify(draft)); toast.success('Borrador guardado') }}><Save data-icon="inline-start" />Guardar borrador</Button></div><div className="container wizard-layout"><aside><Stepper steps={steps} current={step} maxVisited={maxVisited} onStep={setStep} /></aside><section className="wizard-content" aria-label="Formulario del anuncio">{content}<div className="wizard-actions"><Button variant="outline" disabled={step === 0} onClick={() => setStep((value) => value - 1)}><ArrowLeft data-icon="inline-start" />Atrás</Button>{step === steps.length - 1 ? <Button onClick={finish}>Publicar anuncio <CheckCircle2 data-icon="inline-end" /></Button> : <Button onClick={next}>Continuar <ArrowRight data-icon="inline-end" /></Button>}</div></section></div></div>
}
