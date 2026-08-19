import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eye,
  FileCheck2,
  Info,
  MapPin,
  RotateCcw,
  Save,
} from "lucide-react";
import { Link, Navigate, useNavigate, useParams } from "react-router";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmDialog, FormField, ImageUploader, Stepper } from "@/components/forms";
import { PriceBlock, PropertyBadge, PropertyCard, PropertyGallery } from "@/components/marketplace";
import { ApproximateLocationMap } from "@/components/map-view";
import { useApp } from "@/contexts/app-context";
import { amenityOptions, areaCenters, createDefaultDraft } from "@/data/listings";
import { getCriticalRestrictions, getPrimaryPrice } from "@/lib/listings";
import { approximatePublicCoordinates } from "@/lib/location-privacy";
import { removeUnusedMediaReferences } from "@/lib/media-storage";
import { getEmailVerificationStatus, requestEmailVerification, verifyEmail } from "@/api/auth";
import type { AcceptedTenantType, DemoUser, Listing, ListingDraft, TenantRequirement } from "@/types";

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === "1";

const steps = [
  "Tipo de alquiler",
  "Ubicación",
  "Habitación",
  "Precio y gastos",
  "Disponibilidad",
  "Convivencia",
  "Fotografías",
  "Descripción",
  "Contacto",
  "Vista previa",
];
const draftKey = "112233:listing-draft:v3";
const legacyDraftKey = "112233:listing-draft:v2";

function acceptedForRequirement(requirement: TenantRequirement): AcceptedTenantType[] {
  if (requirement === "single-man") return ["man"];
  if (requirement === "single-woman") return ["woman"];
  if (requirement === "couple") return ["couple"];
  if (requirement === "single-person") return ["man", "woman"];
  return ["man", "woman", "couple", "family"];
}

const billsAmountFromText = (value: string) => {
  const match = value.match(/(\d+(?:[.,]\d{1,2})?)/);
  return match ? match[1].replace(",", ".") : "";
};

const toDraft = (listing: Listing): ListingDraft => {
  const roomCapacity = Math.min(10, Math.max(1, Math.round(listing.roomCapacity ?? 1)));
  const roomSize = Math.max(1, listing.roomSizeM2 ?? 12);
  return {
    rentalMode: listing.rentalMode,
    city: listing.city,
    area: listing.area,
    street: listing.street ?? "",
    postcode: listing.postcode ?? "",
    coordinates: listing.exactCoordinates ?? listing.coordinates,
    locationManuallyMoved: true,
    roomType: listing.roomType === "Estudio" ? "Estudio" : listing.roomType === "Habitación compartida" ? "Habitación compartida" : "Habitación individual",
    roomSizeM2: roomSize,
    homeSizeM2: Math.max(roomSize, listing.homeSizeM2 ?? 70),
    bedroomCount: listing.bedroomCount ?? Math.max(1, listing.currentResidents + 1),
    bathroomCount: Math.max(0, listing.bathroomCount ?? 1),
    currentResidents: Math.max(0, listing.currentResidents),
    roomCapacity,
    rentalUnit: listing.rentalUnit ?? (listing.roomType === "Habitación compartida" ? "bed" : "room"),
    bedType: listing.bedType ?? (roomCapacity === 2 && listing.roomType !== "Habitación compartida" ? "double" : "single"),
    bedCount: Math.min(10, Math.max(1, listing.bedCount ?? (listing.roomType === "Habitación compartida" ? roomCapacity : 1))),
    currentRoomResidents: Math.min(roomCapacity - 1, Math.max(0, listing.currentRoomResidents ?? 0)),
    bathroom: listing.bathroom ?? "Baño compartido",
    toilet: listing.toilet ?? (listing.bathroom === "Baño privado" ? "Aseo privado" : "Aseo compartido"),
    shower: listing.shower,
    kitchen: listing.kitchen ?? "Cocina compartida",
    heatingType: listing.heatingType ?? "none",
    accessible: listing.accessible ?? false,
    floor: listing.floor ?? '1',
    furnished: listing.furnished ?? true,
    amenities: listing.amenities.map((item) => item === "Fibra" ? "Wi-Fi" : item),
    monthlyPrice: listing.monthlyPrice ?? (listing.rentalMode === "long" ? listing.price : 0),
    nightlyPrice: listing.nightlyPrice ?? (listing.rentalMode === "holiday" ? listing.price : 0),
    weeklyPrice: listing.weeklyPrice,
    depositAmount: listing.depositAmount ?? 0,
    billsIncluded: listing.billsIncluded ?? false,
    billsNote: listing.billsIncluded ? "" : billsAmountFromText(listing.bills),
    availableFrom: listing.availableFrom,
    availableUntil: listing.availableUntil ?? "",
    minimumStayMonths: listing.minimumStayMonths ?? 0,
    minimumNights: listing.minimumNights ?? 1,
    expiresAt: listing.expiresAt,
    tenantRequirement: listing.tenantRequirement ?? "any",
    acceptedTenantTypes: listing.acceptedTenantTypes?.length ? listing.acceptedTenantTypes : acceptedForRequirement(listing.tenantRequirement ?? "any"),
    householdGender: listing.householdGender ?? "unknown",
    householdHasChildren: listing.householdHasChildren ?? false,
    couplesAllowed: listing.couplesAllowed ?? (listing.tenantRequirement === "couple" || listing.tenantRequirement === "any"),
    smokingAllowed: listing.smokingAllowed ?? false,
    petsAllowed: listing.petsAllowed ?? false,
    childrenAllowed: listing.childrenAllowed ?? false,
    empadronamientoAllowed: listing.empadronamientoAllowed ?? false,
    rules: listing.homeDescription,
    images: listing.images,
    title: listing.title,
    description: listing.description,
    contactName: listing.owner.name,
    contactPhone: listing.contactPhone ?? "",
    contactWhatsapp: listing.contactWhatsapp ?? "",
    contactEmail: listing.contactEmail ?? "",
    showPhone: listing.showPhone,
    showWhatsApp: listing.showWhatsApp,
    allowContactForm: listing.allowContactForm,
    status: listing.status,
  };
};

const withProfileDefaults = (user: DemoUser | null) => {
  const base = createDefaultDraft();
  if (!user) return base;
  return { ...base, contactName: user.name, contactPhone: user.phone, contactWhatsapp: user.whatsapp, contactEmail: user.email, showPhone: user.showPhone, showWhatsApp: user.showWhatsApp, allowContactForm: user.allowContactForm };
};

const toListing = (draft: ListingDraft, previous?: Listing, ownerUserId?: string): Listing => {
  const id = previous?.id ?? `${draft.area.toLocaleLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, "-")}-${Date.now().toString().slice(-6)}`;
  const primaryPrice = draft.rentalMode === "holiday" ? draft.nightlyPrice : draft.monthlyPrice;
  const availableSpots = Math.max(0, draft.roomCapacity - draft.currentRoomResidents);
  const exactCoordinates = draft.coordinates;
  const publicCoordinates = approximatePublicCoordinates(exactCoordinates);
  const listing: Listing = {
    id,
    title: draft.title,
    city: draft.city,
    area: draft.area,
    approximateAddress: `${draft.area} · ubicación aproximada`,
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
    amenities: draft.amenities,
    description: draft.description,
    homeDescription: draft.rules,
    images: draft.images,
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
    allowContactForm: draft.allowContactForm,
  };
  listing.restrictions = getCriticalRestrictions(listing);
  return listing;
};

function WizardSection({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <section className="wizard-section"><header><h2>{title}</h2><p>{description}</p></header>{children}</section>;
}

export function PublishPage({ editing = false }: { editing?: boolean }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const { allListings, createListing, updateListing, currentUser, canManageListing } = useApp();
  const existing = editing ? allListings.find((listing) => listing.id === id) : undefined;
  const [draft, setDraft] = useState<ListingDraft>(() => {
    if (existing) return toDraft(existing);
    const defaults = withProfileDefaults(currentUser);
    try {
      const saved = localStorage.getItem(draftKey);
      if (saved) {
        const parsed = JSON.parse(saved) as { version?: number; ownerUserId?: string; listingId?: string; data?: Partial<ListingDraft> };
        if (parsed.version === 3 && parsed.data && (!parsed.ownerUserId || parsed.ownerUserId === currentUser?.id)) return { ...defaults, ...parsed.data };
      }
      const legacy = localStorage.getItem(legacyDraftKey);
      return legacy ? { ...defaults, ...(JSON.parse(legacy) as Partial<ListingDraft>) } : defaults;
    } catch { return defaults; }
  });
  const [baseline, setBaseline] = useState(() => JSON.stringify(draft));
  const [step, setStep] = useState(0);
  const [maxVisited, setMaxVisited] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [published, setPublished] = useState(false);
  const [verificationOpen, setVerificationOpen] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [verificationError, setVerificationError] = useState("");
  const [verificationBusy, setVerificationBusy] = useState(false);
  const [verificationCooldown, setVerificationCooldown] = useState(0);
  const [pendingRoute, setPendingRoute] = useState<string | null>(null);
  const nonDraftMedia = useMemo(() => {
    const references = new Set(allListings.flatMap((listing) => listing.images));
    if (currentUser?.avatarRef) references.add(currentUser.avatarRef);
    return references;
  }, [allListings, currentUser?.avatarRef]);
  const isDirty = JSON.stringify(draft) !== baseline;
  const set = <K extends keyof ListingDraft>(key: K, value: ListingDraft[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const preview = useMemo(() => toListing(draft, existing, currentUser?.id), [draft, existing, currentUser?.id]);

  useEffect(() => {
    try { localStorage.setItem(draftKey, JSON.stringify({ version: 3, ownerUserId: currentUser?.id, listingId: existing?.id, data: draft })); }
    catch { toast.error("No se pudo guardar el borrador. Revisa el espacio disponible.", { id: "draft-storage-error" }); }
  }, [currentUser?.id, draft, existing?.id]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => { if (isDirty && !published) event.preventDefault(); };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [isDirty, published]);
  useEffect(() => {
    if (!isDirty || published) return;
    const intercept = (event: MouseEvent) => {
      const anchor = (event.target as HTMLElement).closest<HTMLAnchorElement>("a[href]");
      if (!anchor || anchor.target === "_blank") return;
      const url = new URL(anchor.href, location.href);
      if (url.origin !== location.origin || url.hash === location.hash) return;
      event.preventDefault();
      setPendingRoute(url.hash.replace(/^#/, "") || "/");
    };
    document.addEventListener("click", intercept, true);
    return () => document.removeEventListener("click", intercept, true);
  }, [isDirty, published]);
  useEffect(() => {
    if (verificationCooldown <= 0) return;
    const timer = window.setTimeout(() => setVerificationCooldown((seconds) => seconds - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [verificationCooldown]);
  if (editing && (!existing || !canManageListing(existing))) return <Navigate to="/mis-anuncios" replace />;

  const validate = () => {
    const next: Record<string, string> = {};
    if (step === 1 && !draft.area.trim()) next.area = "Indica la zona o barrio.";
    if (step === 2) {
      if (draft.roomSizeM2 < 1) next.roomSizeM2 = "Indica la superficie de la habitación.";
      if (draft.homeSizeM2 < draft.roomSizeM2) next.homeSizeM2 = "La vivienda no puede ser menor que la habitación.";
      if (draft.bedroomCount < 1 || draft.bedroomCount > 99) next.bedroomCount = "Indica entre 1 y 99 habitaciones.";
      if (draft.bathroomCount < 0 || draft.bathroomCount > 20) next.bathroomCount = "Indica entre 0 y 20 baños.";
      if (draft.currentResidents < 0) next.currentResidents = "El número de residentes no puede ser negativo.";
      if (draft.roomCapacity < 1 || draft.roomCapacity > 10) next.roomCapacity = "La capacidad debe estar entre 1 y 10 personas.";
      if (draft.bedCount < 1 || draft.bedCount > 10) next.bedCount = "Indica entre 1 y 10 camas.";
      if (draft.currentRoomResidents < 0 || draft.currentRoomResidents >= draft.roomCapacity) next.currentRoomResidents = "Debe quedar al menos una plaza disponible.";
      if (draft.rentalUnit === "bed" && draft.roomType !== "Habitación compartida") next.rentalUnit = "Las plazas individuales solo se pueden alquilar en una habitación compartida.";
      if (draft.rentalUnit === "bed" && draft.bedType !== "single") next.bedType = "Las plazas independientes se publican como camas individuales.";
      const sleepingPlaces = draft.bedCount * (draft.bedType === "double" ? 2 : 1);
      if (sleepingPlaces < draft.roomCapacity) next.bedCount = "Las camas indicadas no cubren la capacidad de la habitación.";
    }
    if (step === 3) {
      if (getPrimaryPrice(preview) < 1) next.price = "El precio debe ser mayor que cero.";
      if (!draft.billsIncluded) {
        const billsAmount = Number(draft.billsNote);
        if (!draft.billsNote.trim() || !Number.isFinite(billsAmount) || billsAmount <= 0) next.billsAmount = "Indica el gasto adicional aproximado al mes.";
      }
    }
    if (step === 4) {
      if (!draft.availableFrom) next.availableFrom = "Selecciona una fecha de inicio.";
      if (draft.availableFrom && draft.availableUntil && draft.availableUntil < draft.availableFrom) next.availableUntil = "La fecha final debe ser posterior a la inicial.";
      if (draft.rentalMode === "long" && draft.minimumStayMonths < 1) next.minimumStay = "Indica al menos 1 mes.";
      if (draft.rentalMode === "holiday" && draft.minimumNights < 1) next.minimumStay = "Indica al menos 1 noche.";
    }
    if (step === 6 && !draft.images.length) next.images = "Añade al menos una fotografía.";
    if (step === 7 && draft.title.trim().length < 15) next.title = "Escribe un título de al menos 15 caracteres.";
    if (step === 7 && draft.description.trim().length < 40) next.description = "La descripción debe tener al menos 40 caracteres.";
    if (step === 8 && !draft.contactName.trim()) next.contactName = "Indica un nombre público.";
    if (step === 8 && !draft.showPhone && !draft.showWhatsApp && !draft.allowContactForm) next.contactMethods = "Activa al menos una forma de contacto.";
    if (step === 8 && draft.showPhone && !/^\+?[\d\s-]{7,}$/.test(draft.contactPhone)) next.contactPhone = "Introduce un teléfono válido.";
    if (step === 8 && draft.showWhatsApp && !/^\+?[\d\s-]{7,}$/.test(draft.contactWhatsapp)) next.contactWhatsapp = "Introduce un WhatsApp válido.";
    if (step === 8 && draft.allowContactForm && !/^\S+@\S+\.\S+$/.test(currentUser?.email ?? draft.contactEmail)) next.contactEmail = "Introduce un email válido.";
    setErrors(next);
    if (Object.keys(next).length) requestAnimationFrame(() => document.querySelector<HTMLElement>('[aria-invalid="true"], .field-error')?.focus());
    return Object.keys(next).length === 0;
  };
  const next = () => {
    if (!validate()) return;
    const value = Math.min(steps.length - 1, step + 1);
    setStep(value);
    setMaxVisited((current) => Math.max(current, value));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const finish = async () => {
    if (!editing && !mockMode) {
      try {
        const verification = await getEmailVerificationStatus();
        if (!verification.verified) { setVerificationEmail(verification.email); setVerificationOpen(true); return; }
      } catch (error) { toast.error(error instanceof Error ? error.message : "No se pudo comprobar el email."); return; }
    }
    const authoritativeDraft = currentUser ? { ...draft, contactEmail: currentUser.email } : draft;
    const listing = toListing(authoritativeDraft, existing, currentUser?.id);
    const saved = existing ? await updateListing(existing.id, listing) : await createListing(listing);
    if (!saved) return;
    if (existing) {
      const usedAfterUpdate = new Set([...allListings.filter((item) => item.id !== existing.id).flatMap((item) => item.images), ...listing.images, ...(currentUser?.avatarRef ? [currentUser.avatarRef] : [])]);
      await removeUnusedMediaReferences(existing.images, usedAfterUpdate).catch((error) => toast.error(error instanceof Error ? error.message : "No se pudieron limpiar las imágenes reemplazadas."));
      toast.success("Cambios guardados");
    }
    localStorage.removeItem(draftKey);
    setBaseline(JSON.stringify(draft));
    setPublished(true);
  };
  const resetDraft = () => {
    const fresh = existing ? toDraft(existing) : withProfileDefaults(currentUser);
    const retained = new Set(fresh.images);
    const transientMedia = draft.images.filter((reference) => !retained.has(reference) && !existing?.images.includes(reference));
    void removeUnusedMediaReferences(transientMedia, nonDraftMedia).catch((error) => toast.error(error instanceof Error ? error.message : "No se pudieron limpiar las imágenes locales."));
    setDraft(fresh); setStep(0); setMaxVisited(0); setErrors({}); setBaseline(JSON.stringify(fresh));
    localStorage.setItem(draftKey, JSON.stringify({ version: 3, ownerUserId: currentUser?.id, listingId: existing?.id, data: fresh }));
    toast.success("Borrador restablecido");
  };

  const choice = <T extends string>(name: string, value: T, options: { value: T; title: string; text: string }[], onChange: (value: T) => void) => (
    <div className="wizard-choice-grid">{options.map((option) => <label key={option.value}><input type="radio" name={name} checked={value === option.value} onChange={() => onChange(option.value)} /><span><strong>{option.title}</strong><small>{option.text}</small></span></label>)}</div>
  );
  const toggleAmenity = (item: string) => set("amenities", draft.amenities.includes(item) ? draft.amenities.filter((value) => value !== item) : [...draft.amenities, item]);
  const toggleAcceptedTenant = (item: AcceptedTenantType) => set("acceptedTenantTypes", draft.acceptedTenantTypes.includes(item) ? draft.acceptedTenantTypes.filter((value) => value !== item) : [...draft.acceptedTenantTypes, item]);

  const content = (() => {
    switch (step) {
      case 0:
        return <WizardSection title="¿Qué tipo de estancia ofreces?" description="El precio, las fechas y la duración se adaptan al tipo de alquiler.">
          {choice("rental-mode", draft.rentalMode, [
            { value: "long", title: "Larga estancia", text: "Precio mensual en euros." },
            { value: "holiday", title: "Alquiler vacacional", text: "Precio por noche en euros." },
          ], (value) => set("rentalMode", value))}
          <Alert><Info /><AlertTitle>Especializado en habitaciones</AlertTitle><AlertDescription>Publica una habitación completa o, si es compartida, plazas/camas individuales. Las condiciones se muestran antes del contacto.</AlertDescription></Alert>
        </WizardSection>;
      case 1:
        return <WizardSection title="Sitúa la habitación" description="La dirección exacta no se muestra públicamente.">
          <div className="form-grid">
            <FormField label="Municipio" htmlFor="publish-city"><select id="publish-city" value={draft.city} onChange={(event) => set("city", event.target.value)}>{['Adeje','Arafo','Arico','Arona','Buenavista del Norte','Candelaria','El Rosario','El Sauzal','El Tanque','Fasnia','Garachico','Granadilla de Abona','Guía de Isora','Güímar','Icod de los Vinos','La Guancha','La Matanza de Acentejo','La Orotava','La Victoria de Acentejo','Los Realejos','Los Silos','Puerto de la Cruz','San Cristóbal de La Laguna','San Juan de la Rambla','San Miguel de Abona','Santa Cruz de Tenerife','Santa Úrsula','Santiago del Teide','Tacoronte','Tegueste','Vilaflor de Chasna'].map((city) => <option key={city}>{city}</option>)}</select></FormField>
            <FormField label="Zona o barrio" htmlFor="publish-area" error={errors.area}><Input id="publish-area" value={draft.area} aria-invalid={Boolean(errors.area)} aria-describedby={errors.area ? "publish-area-error" : undefined} onChange={(event) => { const area = event.target.value; setDraft((current) => ({ ...current, area, coordinates: current.locationManuallyMoved ? current.coordinates : areaCenters[area] ?? current.coordinates })); }} /></FormField>
            <FormField label="Calle" htmlFor="publish-street"><Input id="publish-street" value={draft.street} onChange={(event) => set("street", event.target.value)} /></FormField>
            <FormField label="Código postal" htmlFor="publish-postcode"><Input id="publish-postcode" inputMode="numeric" value={draft.postcode} onChange={(event) => set("postcode", event.target.value)} /></FormField>
          </div>
          <div className="location-preview"><MapPin /><div><strong>{draft.area}, {draft.city}</strong><span>Mostraremos un punto aproximado.</span></div></div>
          <fieldset className="approximate-location-selector">
            <legend>Selecciona un punto aproximado</legend><p>El marcador se centra en la zona. Muévelo ligeramente sin publicar la calle exacta.</p>
            <ApproximateLocationMap coordinates={draft.coordinates} onChange={(coordinates) => setDraft((current) => ({ ...current, coordinates, locationManuallyMoved: true }))} />
            <Button type="button" variant="outline" disabled={!areaCenters[draft.area]} onClick={() => { const center = areaCenters[draft.area]; if (center) setDraft((current) => ({ ...current, coordinates: center, locationManuallyMoved: false })); }}>Centrar de nuevo en la zona</Button>
            <div className="approximate-location-selector__grid" aria-label={`Punto aproximado: ${draft.coordinates.lat.toFixed(4)}, ${draft.coordinates.lng.toFixed(4)}`}>
              <Button type="button" variant="outline" aria-label="Mover punto al norte" onClick={() => setDraft((current) => ({ ...current, locationManuallyMoved: true, coordinates: { ...current.coordinates, lat: current.coordinates.lat + 0.002 } }))}>Norte</Button>
              <Button type="button" variant="outline" aria-label="Mover punto al oeste" onClick={() => setDraft((current) => ({ ...current, locationManuallyMoved: true, coordinates: { ...current.coordinates, lng: current.coordinates.lng - 0.002 } }))}>Oeste</Button>
              <span className="approximate-location-selector__marker"><MapPin aria-hidden="true" /></span>
              <Button type="button" variant="outline" aria-label="Mover punto al este" onClick={() => setDraft((current) => ({ ...current, locationManuallyMoved: true, coordinates: { ...current.coordinates, lng: current.coordinates.lng + 0.002 } }))}>Este</Button>
              <Button type="button" variant="outline" aria-label="Mover punto al sur" onClick={() => setDraft((current) => ({ ...current, locationManuallyMoved: true, coordinates: { ...current.coordinates, lat: current.coordinates.lat - 0.002 } }))}>Sur</Button>
            </div>
            <output aria-live="polite">Coordenadas aproximadas: {draft.coordinates.lat.toFixed(4)}, {draft.coordinates.lng.toFixed(4)}</output>
          </fieldset>
        </WizardSection>;
      case 2:
        return <WizardSection title="Describe la habitación" description="Datos estructurados de la habitación, las plazas y la vivienda.">
          {choice("room-type", draft.roomType, [
            { value: "Habitación individual", title: "Habitación privada", text: "Se alquila una habitación separada." },
            { value: "Habitación compartida", title: "Habitación compartida", text: "Puede alojar a varias personas y admitir plazas individuales." },
            { value: "Estudio", title: "Estudio", text: "Espacio autónomo que se alquila completo." },
          ], (value) => setDraft((current) => ({ ...current, roomType: value, rentalUnit: value === "Habitación compartida" ? current.rentalUnit : "room", currentRoomResidents: value === "Habitación compartida" ? current.currentRoomResidents : 0 })))}
          {draft.roomType === "Habitación compartida" ? choice("rental-unit", draft.rentalUnit, [
            { value: "room", title: "Habitación completa", text: "Un grupo alquila toda la habitación." },
            { value: "bed", title: "Plazas / camas", text: "Se alquilan plazas individuales dentro de la habitación." },
          ], (value) => setDraft((current) => ({ ...current, rentalUnit: value, bedType: value === "bed" ? "single" : current.bedType, bedCount: value === "bed" ? Math.max(current.bedCount, current.roomCapacity) : current.bedCount })) ) : null}
          <div className="form-grid">
            <FormField label="Superficie de la habitación (m²)" htmlFor="publish-size" error={errors.roomSizeM2}><Input id="publish-size" aria-label="Tamaño aproximado" type="number" min="1" max="200" value={draft.roomSizeM2} aria-invalid={Boolean(errors.roomSizeM2)} onChange={(e) => set("roomSizeM2", Number(e.target.value))} /></FormField>
            <FormField label="Superficie total de la vivienda (m²)" htmlFor="publish-home-size" error={errors.homeSizeM2}><Input id="publish-home-size" type="number" min="1" max="10000" value={draft.homeSizeM2} aria-invalid={Boolean(errors.homeSizeM2)} onChange={(e) => set("homeSizeM2", Number(e.target.value))} /></FormField>
            <FormField label="Número de habitaciones de la vivienda" htmlFor="publish-bedrooms" error={errors.bedroomCount}><Input id="publish-bedrooms" type="number" min="1" max="99" value={draft.bedroomCount} aria-invalid={Boolean(errors.bedroomCount)} onChange={(e) => set("bedroomCount", Math.min(99, Math.max(1, Number(e.target.value) || 1)))} /></FormField>
            <FormField label="Número de baños / cuartos de baño" htmlFor="publish-bathroom-count" error={errors.bathroomCount}><Input id="publish-bathroom-count" type="number" min="0" max="20" value={draft.bathroomCount} aria-invalid={Boolean(errors.bathroomCount)} onChange={(e) => set("bathroomCount", Number(e.target.value))} /></FormField>
            <FormField label="Personas que ya viven en la vivienda" htmlFor="publish-residents" error={errors.currentResidents}><Input id="publish-residents" aria-label="Personas que viven en casa" type="number" min="0" max="50" value={draft.currentResidents} aria-invalid={Boolean(errors.currentResidents)} onChange={(e) => set("currentResidents", Number(e.target.value))} /></FormField>
            <FormField label="Capacidad total de esta habitación" htmlFor="publish-capacity" error={errors.roomCapacity}><select id="publish-capacity" aria-label="Capacidad de la habitación" value={draft.roomCapacity} aria-invalid={Boolean(errors.roomCapacity)} onChange={(e) => { const roomCapacity = Number(e.target.value); setDraft((current) => { const placesPerBed = current.bedType === "double" ? 2 : 1; return { ...current, roomCapacity, bedCount: Math.max(current.bedCount, Math.ceil(roomCapacity / placesPerBed)), currentRoomResidents: Math.min(current.currentRoomResidents, roomCapacity - 1) }; }); }}>{Array.from({ length: 10 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1} {i === 0 ? "persona" : "personas"}</option>)}</select></FormField>
            <FormField label="Personas que ya viven en esta habitación" htmlFor="publish-room-residents" error={errors.currentRoomResidents}><Input id="publish-room-residents" type="number" min="0" max="9" value={draft.currentRoomResidents} aria-invalid={Boolean(errors.currentRoomResidents)} onChange={(e) => set("currentRoomResidents", Number(e.target.value))} /></FormField>
            <FormField label="Tipo de cama" htmlFor="publish-bed-type" error={errors.bedType}><select id="publish-bed-type" value={draft.bedType} disabled={draft.rentalUnit === "bed"} aria-invalid={Boolean(errors.bedType)} onChange={(e) => { const bedType = e.target.value as ListingDraft["bedType"]; setDraft((current) => { const placesPerBed = bedType === "double" ? 2 : 1; return { ...current, bedType, bedCount: Math.max(current.bedCount, Math.ceil(current.roomCapacity / placesPerBed)) }; }); }}><option value="single">1 plaza / individual</option><option value="double">2 plazas / doble</option></select></FormField>
            <FormField label="Número de camas" htmlFor="publish-bed-count" error={errors.bedCount}><Input id="publish-bed-count" type="number" min="1" max="10" value={draft.bedCount} aria-invalid={Boolean(errors.bedCount)} onChange={(e) => set("bedCount", Number(e.target.value))} /></FormField>
            <FormField label="Baño" htmlFor="publish-bathroom"><select id="publish-bathroom" value={draft.bathroom} onChange={(e) => set("bathroom", e.target.value as ListingDraft["bathroom"])}><option>Baño compartido</option><option>Baño privado</option></select></FormField>
            <FormField label="Aseo / WC" htmlFor="publish-toilet"><select id="publish-toilet" value={draft.toilet} onChange={(e) => set("toilet", e.target.value as ListingDraft["toilet"])}><option>Aseo compartido</option><option>Aseo privado</option></select></FormField>
            <FormField label="Ducha" htmlFor="publish-shower"><select id="publish-shower" value={draft.shower} onChange={(e) => set("shower", e.target.value as ListingDraft["shower"])}><option>Ducha compartida</option><option>Ducha privada</option></select></FormField>
            <FormField label="Cocina" htmlFor="publish-kitchen"><select id="publish-kitchen" value={draft.kitchen} onChange={(e) => set("kitchen", e.target.value as ListingDraft["kitchen"])}><option>Cocina compartida</option><option>Cocina privada</option></select></FormField>
            <FormField label="Planta" htmlFor="publish-floor"><select id="publish-floor" value={draft.floor} onChange={(e) => set("floor", e.target.value as ListingDraft["floor"])}><option value="basement">Sótano / semisótano</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4+">4+</option><option value="top">Última planta</option></select></FormField>
            <FormField label="Calefacción" htmlFor="publish-heating"><select id="publish-heating" value={draft.heatingType} onChange={(e) => set("heatingType", e.target.value as ListingDraft["heatingType"])}><option value="none">Sin calefacción</option><option value="individual">Calefacción individual</option><option value="central">Calefacción central</option><option value="unknown">No especificado</option></select></FormField>
          </div>
          <fieldset className="checks-panel"><legend>Equipamiento y accesibilidad</legend>
            <label><Checkbox checked={draft.furnished} onCheckedChange={(value) => set("furnished", value === true)} />Amueblada</label>
            <label><Checkbox checked={draft.accessible} onCheckedChange={(value) => set("accessible", value === true)} />Adaptada para personas con movilidad reducida</label>
            {amenityOptions.map((item) => <label key={item}><Checkbox checked={draft.amenities.includes(item)} onCheckedChange={() => toggleAmenity(item)} />{item}</label>)}
          </fieldset>
        </WizardSection>;
      case 3:
        return <WizardSection title="Precio, gastos y fianza" description="Todos los importes se introducen y se muestran en euros (€).">
          <div className="form-grid">
            {draft.rentalMode === "long" ? <FormField label="Alquiler mensual (€)" htmlFor="publish-price" error={errors.price}><Input id="publish-price" aria-label="Alquiler mensual" type="number" min="1" value={draft.monthlyPrice} aria-invalid={Boolean(errors.price)} onChange={(e) => set("monthlyPrice", Number(e.target.value))} /></FormField> : <>
              <FormField label="Precio por noche (€)" htmlFor="publish-price" error={errors.price}><Input id="publish-price" aria-label="Precio por noche" type="number" min="1" value={draft.nightlyPrice} aria-invalid={Boolean(errors.price)} onChange={(e) => set("nightlyPrice", Number(e.target.value))} /></FormField>
              <FormField label="Precio por semana (€)" htmlFor="publish-weekly-price"><Input id="publish-weekly-price" aria-label="Precio por semana" type="number" min="0" value={draft.weeklyPrice ?? ""} onChange={(e) => set("weeklyPrice", e.target.value ? Number(e.target.value) : undefined)} /></FormField>
              <FormField label="Precio por mes (€)" htmlFor="publish-monthly-price"><Input id="publish-monthly-price" aria-label="Precio por mes" type="number" min="0" value={draft.monthlyPrice} onChange={(e) => set("monthlyPrice", Number(e.target.value))} /></FormField>
            </>}
            <FormField label="Fianza / depósito (€)" htmlFor="publish-deposit"><Input id="publish-deposit" type="number" min="0" value={draft.depositAmount} onChange={(e) => set("depositAmount", Number(e.target.value))} /></FormField>
          </div>
          <div className="form-grid">
            <FormField label="Gastos de suministros" htmlFor="publish-bills-included"><select id="publish-bills-included" value={draft.billsIncluded ? "included" : "extra"} onChange={(e) => setDraft((current) => ({ ...current, billsIncluded: e.target.value === "included", billsNote: e.target.value === "included" ? "" : current.billsNote }))}><option value="included">Incluidos en el precio</option><option value="extra">Se pagan aparte</option></select></FormField>
            {!draft.billsIncluded ? <FormField label="Gastos adicionales aproximados (€/mes)" htmlFor="publish-bills" error={errors.billsAmount}><Input id="publish-bills" type="number" min="1" inputMode="decimal" value={draft.billsNote} aria-invalid={Boolean(errors.billsAmount)} onChange={(e) => set("billsNote", e.target.value)} /></FormField> : null}
          </div>
        </WizardSection>;
      case 4:
        return <WizardSection title="Disponibilidad" description="Indica desde qué día está disponible. La fecha final es opcional; si no la conoces, basta con indicar la estancia mínima.">
          <div className="form-grid">
            <FormField label="Disponible desde" htmlFor="publish-available" error={errors.availableFrom}><Input id="publish-available" type="date" value={draft.availableFrom} aria-invalid={Boolean(errors.availableFrom)} onChange={(e) => set("availableFrom", e.target.value)} /></FormField>
            <FormField label="Disponible hasta (opcional)" htmlFor="publish-available-until" error={errors.availableUntil}><Input id="publish-available-until" type="date" value={draft.availableUntil} aria-invalid={Boolean(errors.availableUntil)} onChange={(e) => set("availableUntil", e.target.value)} /></FormField>
            {draft.rentalMode === "long" ? <FormField label="Estancia mínima (meses)" htmlFor="publish-min-stay" error={errors.minimumStay}><Input id="publish-min-stay" type="number" min="1" value={draft.minimumStayMonths} aria-invalid={Boolean(errors.minimumStay)} onChange={(e) => set("minimumStayMonths", Number(e.target.value))} /></FormField> : <FormField label="Estancia mínima (noches)" htmlFor="publish-min-nights" error={errors.minimumStay}><Input id="publish-min-nights" type="number" min="1" value={draft.minimumNights} aria-invalid={Boolean(errors.minimumStay)} onChange={(e) => set("minimumNights", Number(e.target.value))} /></FormField>}
            <FormField label="Fecha límite del anuncio" htmlFor="publish-expiry"><Input id="publish-expiry" type="date" value={draft.expiresAt} onChange={(e) => set("expiresAt", e.target.value)} /></FormField>
          </div>
        </WizardSection>;
      case 5:
        return <WizardSection title="Condiciones de convivencia" description="Distingue quién vive en la vivienda y qué perfiles acepta el anunciante.">
          <div className="form-grid">
            <FormField label="Requisito para la persona inquilina" htmlFor="publish-tenant-requirement"><select id="publish-tenant-requirement" value={draft.tenantRequirement} onChange={(e) => { const requirement = e.target.value as ListingDraft["tenantRequirement"]; setDraft((current) => ({ ...current, tenantRequirement: requirement, acceptedTenantTypes: acceptedForRequirement(requirement), couplesAllowed: requirement === "couple" || requirement === "any" })); }}><option value="single-man">Solo un hombre</option><option value="single-woman">Solo una mujer</option><option value="single-person">Una persona</option><option value="couple">Solo pareja</option><option value="any">Sin restricción</option></select></FormField>
            <FormField label="Quién vive actualmente en la vivienda" htmlFor="publish-household-gender"><select id="publish-household-gender" value={draft.householdGender} onChange={(e) => set("householdGender", e.target.value as ListingDraft["householdGender"])}><option value="men">Hombres</option><option value="women">Mujeres</option><option value="mixed">Convivencia mixta</option><option value="unknown">No especificado</option></select></FormField>
          </div>
          <fieldset className="checks-panel checks-panel--columns"><legend>Perfiles admitidos</legend>{([
            ["man", "Hombres"], ["woman", "Mujeres"], ["couple", "Parejas"], ["family", "Familias"],
          ] as const).map(([key, label]) => <label key={key}><Checkbox checked={draft.acceptedTenantTypes.includes(key)} onCheckedChange={() => toggleAcceptedTenant(key)} />{label}</label>)}</fieldset>
          <fieldset className="checks-panel checks-panel--columns"><legend>Convivencia y normas</legend>
            <label><Checkbox checked={draft.householdHasChildren} onCheckedChange={(value) => set("householdHasChildren", value === true)} />Actualmente viven niños en la vivienda</label>
            <label><Checkbox checked={draft.couplesAllowed} onCheckedChange={(value) => set("couplesAllowed", value === true)} />Se aceptan parejas</label>
            <label><Checkbox checked={draft.petsAllowed} onCheckedChange={(value) => set("petsAllowed", value === true)} />Mascotas permitidas</label>
            <label><Checkbox checked={draft.smokingAllowed} onCheckedChange={(value) => set("smokingAllowed", value === true)} />Se puede fumar</label>
            <label><Checkbox checked={draft.childrenAllowed} onCheckedChange={(value) => set("childrenAllowed", value === true)} />Se aceptan menores / niños</label>
            <label><Checkbox checked={draft.empadronamientoAllowed} onCheckedChange={(value) => set("empadronamientoAllowed", value === true)} />Empadronamiento posible</label>
          </fieldset>
          <FormField label="Normas de la vivienda" htmlFor="publish-rules"><Textarea id="publish-rules" rows={5} value={draft.rules} onChange={(e) => set("rules", e.target.value)} /></FormField>
        </WizardSection>;
      case 6:
        return <WizardSection title="Fotografías" description="La primera será la portada. Puedes reordenarlas."><ImageUploader images={draft.images} onChange={(images) => set("images", images)} onRemove={(image) => { if (!existing?.images.includes(image)) void removeUnusedMediaReferences([image], nonDraftMedia).catch((error) => toast.error(error instanceof Error ? error.message : "No se pudo limpiar la imagen local.")); }} error={errors.images} /></WizardSection>;
      case 7:
        return <WizardSection title="Cuenta cómo es vivir aquí" description="Responde las dudas habituales.">
          <FormField label="Título del anuncio" htmlFor="publish-title" description="Máximo 80 caracteres." error={errors.title}><Input id="publish-title" maxLength={80} value={draft.title} aria-invalid={Boolean(errors.title)} onChange={(e) => set("title", e.target.value)} /></FormField>
          <FormField label="Descripción" htmlFor="publish-description" error={errors.description}><Textarea id="publish-description" rows={8} value={draft.description} aria-invalid={Boolean(errors.description)} onChange={(e) => set("description", e.target.value)} /></FormField>
        </WizardSection>;
      case 8:
        return <WizardSection title="Datos de contacto" description="Estos canales se mostrarán tras confirmar la condición principal.">
          <div className="form-grid">
            <FormField label="Nombre público" htmlFor="publish-contact-name" error={errors.contactName}><Input id="publish-contact-name" value={draft.contactName || currentUser?.name || ""} aria-invalid={Boolean(errors.contactName)} onChange={(e) => set("contactName", e.target.value)} /></FormField>
            <FormField label="Teléfono" htmlFor="publish-contact-phone" error={errors.contactPhone}><Input id="publish-contact-phone" type="tel" value={draft.contactPhone} aria-invalid={Boolean(errors.contactPhone)} onChange={(e) => set("contactPhone", e.target.value)} /></FormField>
            <FormField label="WhatsApp" htmlFor="publish-contact-whatsapp" error={errors.contactWhatsapp}><Input id="publish-contact-whatsapp" type="tel" value={draft.contactWhatsapp} aria-invalid={Boolean(errors.contactWhatsapp)} onChange={(e) => set("contactWhatsapp", e.target.value)} /></FormField>
            <FormField label="Email" htmlFor="publish-contact-email" error={errors.contactEmail}><Input id="publish-contact-email" type="email" value={currentUser?.email ?? draft.contactEmail} aria-invalid={Boolean(errors.contactEmail)} readOnly aria-readonly="true" title="Se usa el email de tu cuenta" /></FormField>
          </div>
          <fieldset className="checks-panel contact-methods" aria-describedby={errors.contactMethods ? "contact-methods-error" : undefined}><legend>Canales disponibles</legend><label><Checkbox checked={draft.showPhone} onCheckedChange={(value) => set("showPhone", value === true)} />Mostrar teléfono tras confirmar</label><label><Checkbox checked={draft.showWhatsApp} onCheckedChange={(value) => set("showWhatsApp", value === true)} />Permitir WhatsApp tras confirmar</label><label><Checkbox checked={draft.allowContactForm} onCheckedChange={(value) => set("allowContactForm", value === true)} />Permitir mensaje local</label></fieldset>
          {errors.contactMethods ? <p id="contact-methods-error" className="field-error" role="alert">{errors.contactMethods}</p> : null}
        </WizardSection>;
      default:
        return <WizardSection title="Revisa antes de publicar" description="Así se verá el anuncio.">
          <Alert><FileCheck2 /><AlertTitle>El anuncio está completo</AlertTitle><AlertDescription>Revisa habitación, plazas, precio, convivencia y fechas.</AlertDescription></Alert>
          <div className="preview-card-wrap"><PropertyCard listing={preview} /></div>
          <div className="preview-contact-methods" aria-label="Canales de contacto visibles"><h3>Canales tras confirmar condiciones</h3><div className="badge-row">{preview.showPhone ? <PropertyBadge>Teléfono</PropertyBadge> : null}{preview.showWhatsApp ? <PropertyBadge>WhatsApp</PropertyBadge> : null}{preview.allowContactForm ? <PropertyBadge>Mensaje local</PropertyBadge> : null}</div></div>
          <div className="preview-conditions"><h3>Condiciones visibles</h3><div className="badge-row">{preview.restrictions.map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}</div></div>
          <Dialog><DialogTrigger asChild><Button variant="outline"><Eye data-icon="inline-start" />Vista previa completa</Button></DialogTrigger><DialogContent className="full-preview-dialog"><DialogHeader><DialogTitle>Vista previa del anuncio</DialogTitle><DialogDescription>Versión pública antes de publicar.</DialogDescription></DialogHeader><PropertyGallery listing={preview} /><div className="full-preview-summary"><div><span className="eyebrow">{preview.area}, {preview.city}</span><h2>{preview.title}</h2><p>{preview.description}</p></div><PriceBlock listing={preview} large /></div><dl className="detail-list"><div><dt>Disponibilidad</dt><dd>{preview.availableFrom}{preview.availableUntil ? ` — ${preview.availableUntil}` : " · sin fecha final"}</dd></div><div><dt>Estancia mínima</dt><dd>{preview.minimumStay}</dd></div><div><dt>Plazas libres</dt><dd>{preview.availableSpots ?? "Consultar"}</dd></div><div><dt>Gastos</dt><dd>{preview.bills}</dd></div><div><dt>Fianza</dt><dd>{preview.deposit}</dd></div></dl><div className="badge-row">{preview.restrictions.map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}</div></DialogContent></Dialog>
        </WizardSection>;
    }
  })();

  if (published) return <div className="publish-success"><CheckCircle2 /><span className="eyebrow">{editing ? "Anuncio actualizado" : "Anuncio enviado"}</span><h1>{editing ? "Cambios guardados" : "Tu anuncio se ha enviado a revisión"}</h1><p>{editing ? "Los cambios se han guardado. Consulta el estado del anuncio en Mis anuncios." : "Revisaremos el anuncio antes de publicarlo. Puedes consultar su estado en Mis anuncios."}</p><div><Button asChild><Link to="/mis-anuncios">Ver mis anuncios</Link></Button><Button asChild variant="outline"><Link to={`/habitacion/${preview.id}`}>Ver anuncio</Link></Button></div></div>;

  return <>
    <div className={`publish-page${editing ? " publish-page--editing" : ""}`}>
      <div className="container publish-header">
        {isDirty ? <ConfirmDialog trigger={<Button variant="ghost"><ArrowLeft data-icon="inline-start" />Salir</Button>} title="¿Salir del editor?" description="El borrador automático seguirá guardado para que puedas continuar después." confirmLabel="Salir y conservar borrador" onConfirm={() => navigate("/mis-anuncios")} /> : <Button variant="ghost" onClick={() => navigate("/mis-anuncios")}><ArrowLeft data-icon="inline-start" />Salir</Button>}
        <div><span className="eyebrow">{editing ? `Editando ${id?.slice(-5).toUpperCase()}` : "Nuevo anuncio"}</span><h1 aria-label={editing ? "Editar habitación" : undefined}>{editing ? "Editar anuncio" : "Publicar una habitación"}</h1></div>
        <div className="publish-header__actions">
          <ConfirmDialog trigger={<Button variant="ghost"><RotateCcw data-icon="inline-start" />Restablecer</Button>} title="¿Restablecer el borrador?" description="Se eliminarán los cambios de todos los pasos y volverán los valores iniciales." confirmLabel="Restablecer" destructive onConfirm={resetDraft} />
          <Button variant="outline" onClick={() => { try { localStorage.setItem(draftKey, JSON.stringify({ version: 3, ownerUserId: currentUser?.id, listingId: existing?.id, data: draft })); setBaseline(JSON.stringify(draft)); toast.success("Borrador guardado"); } catch { toast.error("No se pudo guardar el borrador. Revisa el espacio disponible."); } }}><Save data-icon="inline-start" />Guardar borrador</Button>
          <span className="dirty-state" aria-live="polite">{isDirty ? "Cambios sin guardar" : "Borrador guardado"}</span>
        </div>
      </div>
      <div className="container wizard-layout"><aside><Stepper steps={steps} current={step} maxVisited={maxVisited} onStep={setStep} /></aside><section className="wizard-content" aria-label="Formulario del anuncio">{content}<div className="wizard-actions"><Button variant="outline" disabled={step === 0} onClick={() => setStep((value) => value - 1)}><ArrowLeft data-icon="inline-start" />Atrás</Button>{step === steps.length - 1 ? <Button onClick={finish}>Publicar anuncio <CheckCircle2 data-icon="inline-end" /></Button> : <Button onClick={next}>Continuar <ArrowRight data-icon="inline-end" /></Button>}</div></section></div>
    </div>
    <Dialog open={verificationOpen} onOpenChange={setVerificationOpen}><DialogContent aria-describedby="email-verification-description"><DialogHeader><DialogTitle>Confirma tu email para publicar</DialogTitle><DialogDescription id="email-verification-description">Enviaremos un código de seis dígitos a {verificationEmail || "tu email"}. Tu borrador y tus fotos seguirán guardados.</DialogDescription></DialogHeader><div className="space-y-3"><Input value={verificationCode} onChange={(event) => setVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" placeholder="000000" aria-label="Código de seis dígitos" aria-invalid={Boolean(verificationError)} />{verificationError ? <p className="field-error" role="alert">{verificationError}</p> : null}<Button type="button" variant="outline" disabled={verificationBusy || verificationCooldown > 0} onClick={async () => { setVerificationBusy(true); try { const result = await requestEmailVerification(); setVerificationEmail(result.email); setVerificationCooldown(result.cooldownSeconds); setVerificationError(""); toast.success("Código enviado"); } catch (error) { setVerificationError(error instanceof Error ? error.message : "No se pudo enviar el código."); } finally { setVerificationBusy(false); } }}>{verificationCooldown > 0 ? `Reenviar en ${verificationCooldown}s` : "Enviar código"}</Button><Button type="button" disabled={verificationBusy || verificationCode.length !== 6} onClick={async () => { setVerificationBusy(true); try { await verifyEmail(verificationCode); setVerificationOpen(false); setVerificationCode(""); setVerificationError(""); await finish(); } catch (error) { setVerificationError(error instanceof Error ? error.message : "Código no válido."); } finally { setVerificationBusy(false); } }}>Confirmar y publicar</Button></div></DialogContent></Dialog>
    <AlertDialog open={Boolean(pendingRoute)} onOpenChange={(open) => { if (!open) setPendingRoute(null); }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>¿Salir del editor?</AlertDialogTitle><AlertDialogDescription>Hay cambios sin guardar. El borrador automático se conserva, pero puedes guardar manualmente antes de salir.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>Seguir editando</AlertDialogCancel><AlertDialogAction onClick={() => { const route = pendingRoute; setPendingRoute(null); if (route) navigate(route); }}>Salir y conservar borrador</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
  </>;
}
