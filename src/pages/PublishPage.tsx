import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
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
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
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
import {
  ConfirmDialog,
  FormField,
  ImageUploader,
  Stepper,
} from "@/components/forms";
import {
  PriceBlock,
  PropertyBadge,
  PropertyCard,
  PropertyGallery,
} from "@/components/marketplace";
import { useApp } from "@/contexts/app-context";
import { areaCenters, createDefaultDraft } from "@/data/listings";
import { getCriticalRestrictions, getPrimaryPrice } from "@/lib/listings";
import { removeMedia, removeMediaReferences } from "@/lib/media-storage";
import type { DemoUser, Listing, ListingDraft } from "@/types";

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

const toDraft = (listing: Listing): ListingDraft => ({
  rentalMode: listing.rentalMode,
  city: listing.city,
  area: listing.area,
  street: "",
  postcode: "",
  coordinates: listing.coordinates,
  roomType: listing.roomType,
  roomSizeM2: listing.roomSizeM2,
  currentResidents: listing.currentResidents,
  roomCapacity: listing.roomCapacity,
  bathroom: listing.bathroom,
  shower: listing.shower,
  kitchen: listing.kitchen,
  furnished: listing.furnished,
  amenities: listing.amenities,
  monthlyPrice: listing.monthlyPrice ?? (listing.rentalMode === "long" ? listing.price : 0),
  nightlyPrice: listing.nightlyPrice ?? (listing.rentalMode === "holiday" ? listing.price : 0),
  weeklyPrice: listing.weeklyPrice,
  depositAmount: listing.depositAmount,
  billsIncluded: listing.billsIncluded,
  billsNote: listing.bills,
  availableFrom: listing.availableFrom,
  availableUntil: listing.availableUntil,
  minimumStayMonths: listing.minimumStayMonths,
  minimumNights: listing.minimumNights ?? 1,
  expiresAt: listing.expiresAt,
  genderPreference: listing.genderPreference,
  tenantRequirement: listing.tenantRequirement,
  smokingAllowed: listing.smokingAllowed,
  petsAllowed: listing.petsAllowed,
  couplesAllowed: listing.couplesAllowed,
  childrenAllowed: listing.childrenAllowed,
  empadronamientoAllowed: listing.empadronamientoAllowed,
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
});

const withProfileDefaults = (user: DemoUser | null) => {
  const base = createDefaultDraft();
  if (!user) return base;
  return { ...base, contactName: user.name, contactPhone: user.phone, contactWhatsapp: user.whatsapp, contactEmail: user.email, showPhone: user.showPhone, showWhatsApp: user.showWhatsApp, allowContactForm: user.allowContactForm };
};

const toListing = (draft: ListingDraft, previous?: Listing, ownerUserId?: string): Listing => {
  const id =
    previous?.id ??
    `${draft.area
      .toLocaleLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-z0-9]+/g, "-")}-${Date.now().toString().slice(-6)}`;
  const primaryPrice = draft.rentalMode === "holiday" ? draft.nightlyPrice : draft.monthlyPrice;
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
    availableUntil: draft.rentalMode === "holiday" ? draft.availableUntil : undefined,
    minimumStay:
      draft.rentalMode === "holiday"
        ? `Mínimo ${draft.minimumNights} ${draft.minimumNights === 1 ? "noche" : "noches"}`
        : `Mínimo ${draft.minimumStayMonths} ${draft.minimumStayMonths === 1 ? "mes" : "meses"}`,
    minimumStayMonths: draft.minimumStayMonths,
    minimumNights: draft.rentalMode === "holiday" ? draft.minimumNights : undefined,
    deposit: draft.depositAmount ? `${draft.depositAmount} €` : "Sin fianza",
    depositAmount: draft.depositAmount,
    bills:
      draft.billsNote ||
      (draft.billsIncluded ? "Gastos incluidos" : "Gastos aparte"),
    billsIncluded: draft.billsIncluded,
    bathroom: draft.bathroom,
    kitchen: draft.kitchen,
    furnished: draft.furnished,
    occupants: draft.currentResidents,
    roomSizeM2: draft.roomSizeM2,
    currentResidents: draft.currentResidents,
    roomCapacity: draft.roomCapacity,
    shower: draft.shower,
    coordinates: draft.coordinates,
    genderPreference: draft.genderPreference,
    tenantRequirement: draft.tenantRequirement,
    smokingAllowed: draft.smokingAllowed,
    petsAllowed: draft.petsAllowed,
    couplesAllowed: draft.couplesAllowed,
    childrenAllowed: draft.childrenAllowed,
    empadronamientoAllowed: draft.empadronamientoAllowed,
    restrictions: [],
    amenities: draft.amenities,
    description: draft.description,
    homeDescription: draft.rules,
    images: draft.images,
    owner: previous?.owner ?? {
      name: draft.contactName,
      initials: draft.contactName
        .split(/\s+/)
        .map((part) => part[0])
        .join("")
        .slice(0, 2)
        .toLocaleUpperCase(),
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

function WizardSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="wizard-section">
      <header>
        <h2>{title}</h2>
        <p>{description}</p>
      </header>
      {children}
    </section>
  );
}

export function PublishPage({ editing = false }: { editing?: boolean }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const { allListings, createListing, updateListing, currentUser, canManageListing } = useApp();
  const existing = editing
    ? allListings.find((listing) => listing.id === id)
    : undefined;
  const [draft, setDraft] = useState<ListingDraft>(() => {
    if (existing) return toDraft(existing);
    const defaults = withProfileDefaults(currentUser);
    try {
      const saved = localStorage.getItem(draftKey);
      if (saved) {
        const parsed = JSON.parse(saved) as { version?: number; data?: Partial<ListingDraft> };
        if (parsed.version === 3 && parsed.data) return { ...defaults, ...parsed.data };
      }
      const legacy = localStorage.getItem(legacyDraftKey);
      return legacy ? { ...defaults, ...(JSON.parse(legacy) as Partial<ListingDraft>) } : defaults;
    } catch {
      return defaults;
    }
  });
  const [baseline, setBaseline] = useState(() => JSON.stringify(draft));
  const [step, setStep] = useState(0);
  const [maxVisited, setMaxVisited] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [published, setPublished] = useState(false);
  const [pendingRoute, setPendingRoute] = useState<string | null>(null);
  const pendingMediaRemovals = useRef(new Set<string>());
  const isDirty = JSON.stringify(draft) !== baseline;
  const set = <K extends keyof ListingDraft>(key: K, value: ListingDraft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));
  const preview = useMemo(() => toListing(draft, existing, currentUser?.id), [draft, existing, currentUser?.id]);
  useEffect(() => {
    try { localStorage.setItem(draftKey, JSON.stringify({ version: 3, data: draft })); }
    catch { toast.error("No se pudo guardar el borrador. Revisa el espacio disponible.", { id: "draft-storage-error" }); }
  }, [draft]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (isDirty && !published) event.preventDefault();
    };
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
  if (editing && (!existing || !canManageListing(existing))) return <Navigate to="/mis-anuncios" replace />;

  const validate = () => {
    const next: Record<string, string> = {};
    if (step === 1 && !draft.area.trim())
      next.area = "Indica la zona o barrio.";
    if (step === 2 && draft.currentResidents < 0)
      next.occupants = "El número de residentes no puede ser negativo.";
    if (step === 3 && getPrimaryPrice(preview) < 1)
      next.price = "El precio debe ser mayor que cero.";
    if (step === 4 && !draft.availableFrom)
      next.availableFrom = "Selecciona una fecha.";
    if (step === 6 && !draft.images.length)
      next.images = "Añade al menos una fotografía.";
    if (step === 7 && draft.title.trim().length < 15)
      next.title = "Escribe un título de al menos 15 caracteres.";
    if (step === 7 && draft.description.trim().length < 40)
      next.description = "La descripción debe tener al menos 40 caracteres.";
    if (step === 8 && !draft.contactName.trim())
      next.contactName = "Indica un nombre público.";
    if (step === 8 && !draft.showPhone && !draft.showWhatsApp && !draft.allowContactForm)
      next.contactMethods = "Activa al menos una forma de contacto.";
    if (step === 8 && draft.showPhone && !/^\+?[\d\s-]{7,}$/.test(draft.contactPhone))
      next.contactPhone = "Introduce un teléfono válido.";
    if (step === 8 && draft.showWhatsApp && !/^\+?[\d\s-]{7,}$/.test(draft.contactWhatsapp))
      next.contactWhatsapp = "Introduce un WhatsApp válido.";
    if (step === 8 && draft.allowContactForm && !/^\S+@\S+\.\S+$/.test(draft.contactEmail))
      next.contactEmail = "Introduce un email válido.";
    setErrors(next);
    if (Object.keys(next).length)
      requestAnimationFrame(() =>
        document
          .querySelector<HTMLElement>('[aria-invalid="true"], .field-error')
          ?.focus(),
      );
    return Object.keys(next).length === 0;
  };
  const next = () => {
    if (!validate()) return;
    const value = Math.min(steps.length - 1, step + 1);
    setStep(value);
    setMaxVisited((current) => Math.max(current, value));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const finish = () => {
    const listing = toListing(draft, existing, currentUser?.id);
    if (existing) {
      updateListing(existing.id, listing);
      toast.success("Cambios publicados");
    } else createListing(listing);
    const obsoleteMedia = [...pendingMediaRemovals.current].filter(
      (reference) => !draft.images.includes(reference),
    );
    pendingMediaRemovals.current.clear();
    void removeMediaReferences(obsoleteMedia).catch((error) =>
      toast.error(error instanceof Error ? error.message : "No se pudieron limpiar las imágenes locales."),
    );
    localStorage.removeItem(draftKey);
    setBaseline(JSON.stringify(draft));
    setPublished(true);
  };
  const resetDraft = () => {
    const fresh = existing ? toDraft(existing) : withProfileDefaults(currentUser);
    const retained = new Set(fresh.images);
    const transientMedia = draft.images.filter(
      (reference) => !retained.has(reference) && !existing?.images.includes(reference),
    );
    pendingMediaRemovals.current.clear();
    void removeMediaReferences(transientMedia).catch((error) =>
      toast.error(error instanceof Error ? error.message : "No se pudieron limpiar las imágenes locales."),
    );
    setDraft(fresh);
    setStep(0);
    setMaxVisited(0);
    setErrors({});
    setBaseline(JSON.stringify(fresh));
    localStorage.setItem(draftKey, JSON.stringify({ version: 3, data: fresh }));
    toast.success("Borrador restablecido");
  };

  const choice = <T extends string>(
    name: string,
    value: T,
    options: { value: T; title: string; text: string }[],
    onChange: (value: T) => void,
  ) => (
    <div className="wizard-choice-grid">
      {options.map((option) => (
        <label key={option.value}>
          <input
            type="radio"
            name={name}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
          <span>
            <strong>{option.title}</strong>
            <small>{option.text}</small>
          </span>
        </label>
      ))}
    </div>
  );
  const toggleAmenity = (item: string) =>
    set(
      "amenities",
      draft.amenities.includes(item)
        ? draft.amenities.filter((value) => value !== item)
        : [...draft.amenities, item],
    );
  const content = (() => {
    switch (step) {
      case 0:
        return (
          <WizardSection
            title="¿Qué tipo de estancia ofreces?"
            description="El precio, las fechas y la duración se adaptan al tipo de alquiler."
          >
            {choice(
              "rental-mode",
              draft.rentalMode,
              [
                {
                  value: "long",
                  title: "Larga estancia",
                  text: "Precio mensual.",
                },
                {
                  value: "holiday",
                  title: "Alquiler vacacional",
                  text: "Precio por noche.",
                },
              ],
              (value) => set("rentalMode", value),
            )}
            <Alert>
              <Info />
              <AlertTitle>Información clara</AlertTitle>
              <AlertDescription>
                Las condiciones se mostrarán antes del contacto.
              </AlertDescription>
            </Alert>
          </WizardSection>
        );
      case 1:
        return (
          <WizardSection
            title="Sitúa la habitación"
            description="La dirección exacta no se muestra públicamente."
          >
            <div className="form-grid">
              <FormField label="Municipio" htmlFor="publish-city">
                <select
                  id="publish-city"
                  value={draft.city}
                  onChange={(event) => set("city", event.target.value)}
                >
                  <option>Adeje</option>
                  <option>Arona</option>
                  <option>Granadilla de Abona</option>
                  <option>Santa Cruz de Tenerife</option>
                  <option>San Cristóbal de La Laguna</option>
                </select>
              </FormField>
              <FormField
                label="Zona o barrio"
                htmlFor="publish-area"
                error={errors.area}
              >
                <Input
                  id="publish-area"
                  value={draft.area}
                  aria-invalid={Boolean(errors.area)}
                  aria-describedby={
                    errors.area ? "publish-area-error" : undefined
                  }
                  onChange={(event) => {
                    const area = event.target.value;
                    setDraft((current) => ({ ...current, area, coordinates: areaCenters[area] ?? current.coordinates }));
                  }}
                />
              </FormField>
              <FormField label="Calle" htmlFor="publish-street">
                <Input
                  id="publish-street"
                  value={draft.street}
                  onChange={(event) => set("street", event.target.value)}
                />
              </FormField>
              <FormField label="Código postal" htmlFor="publish-postcode">
                <Input
                  id="publish-postcode"
                  inputMode="numeric"
                  value={draft.postcode}
                  onChange={(event) => set("postcode", event.target.value)}
                />
              </FormField>
            </div>
            <div className="location-preview">
              <MapPin />
              <div>
                <strong>
                  {draft.area}, {draft.city}
                </strong>
                <span>Mostraremos un punto aproximado.</span>
              </div>
            </div>
            <fieldset className="approximate-location-selector">
              <legend>Selecciona un punto aproximado</legend>
              <p>El marcador se centra en la zona. Muévelo ligeramente sin publicar la calle exacta.</p>
              <div className="approximate-location-selector__grid" aria-label={`Punto aproximado: ${draft.coordinates.lat.toFixed(4)}, ${draft.coordinates.lng.toFixed(4)}`}>
                <Button type="button" variant="outline" aria-label="Mover punto al norte" onClick={() => set("coordinates", { ...draft.coordinates, lat: draft.coordinates.lat + 0.002 })}>Norte</Button>
                <Button type="button" variant="outline" aria-label="Mover punto al oeste" onClick={() => set("coordinates", { ...draft.coordinates, lng: draft.coordinates.lng - 0.002 })}>Oeste</Button>
                <span className="approximate-location-selector__marker"><MapPin aria-hidden="true" /></span>
                <Button type="button" variant="outline" aria-label="Mover punto al este" onClick={() => set("coordinates", { ...draft.coordinates, lng: draft.coordinates.lng + 0.002 })}>Este</Button>
                <Button type="button" variant="outline" aria-label="Mover punto al sur" onClick={() => set("coordinates", { ...draft.coordinates, lat: draft.coordinates.lat - 0.002 })}>Sur</Button>
              </div>
              <output aria-live="polite">Coordenadas aproximadas: {draft.coordinates.lat.toFixed(4)}, {draft.coordinates.lng.toFixed(4)}</output>
            </fieldset>
          </WizardSection>
        );
      case 2:
        return (
          <WizardSection
            title="Describe la habitación"
            description="Datos básicos para comparar."
          >
            {choice(
              "room-type",
              draft.roomType,
              [
                {
                  value: "Habitación individual",
                  title: "Individual",
                  text: "Para una persona.",
                },
                {
                  value: "Habitación compartida",
                  title: "Compartida",
                  text: "Dos o más camas.",
                },
                {
                  value: "Estudio",
                  title: "Estudio",
                  text: "Espacio autónomo.",
                },
              ],
              (value) => set("roomType", value),
            )}
            <div className="form-grid">
              <FormField label="Tamaño aproximado" htmlFor="publish-size">
                <Input
                  id="publish-size"
                  type="number"
                  min="1"
                  value={draft.roomSizeM2}
                  onChange={(e) => set("roomSizeM2", Number(e.target.value))}
                />
              </FormField>
              <FormField
                label="Personas que viven en casa"
                htmlFor="publish-occupants"
                error={errors.occupants}
              >
                <Input
                  id="publish-occupants"
                  type="number"
                  min="0"
                  value={draft.currentResidents}
                  aria-invalid={Boolean(errors.occupants)}
                  onChange={(e) => set("currentResidents", Number(e.target.value))}
                />
              </FormField>
              <FormField label="Capacidad de la habitación" htmlFor="publish-capacity">
                <select id="publish-capacity" value={draft.roomCapacity} disabled={draft.tenantRequirement !== "any"} onChange={(e) => set("roomCapacity", Number(e.target.value) as 1 | 2)}>
                  <option value="1">1 persona</option><option value="2">2 personas</option>
                </select>
              </FormField>
              <FormField label="Baño" htmlFor="publish-bathroom">
                <select
                  id="publish-bathroom"
                  value={draft.bathroom}
                  onChange={(e) =>
                    set("bathroom", e.target.value as ListingDraft["bathroom"])
                  }
                >
                  <option>Baño compartido</option>
                  <option>Baño privado</option>
                </select>
              </FormField>
              <FormField label="Cocina" htmlFor="publish-kitchen">
                <select
                  id="publish-kitchen"
                  value={draft.kitchen}
                  onChange={(e) =>
                    set("kitchen", e.target.value as ListingDraft["kitchen"])
                  }
                >
                  <option>Cocina compartida</option>
                  <option>Cocina privada</option>
                </select>
              </FormField>
              <FormField label="Ducha" htmlFor="publish-shower">
                <select id="publish-shower" value={draft.shower} onChange={(e) => set("shower", e.target.value as ListingDraft["shower"])}>
                  <option>Ducha compartida</option><option>Ducha privada</option>
                </select>
              </FormField>
            </div>
            <fieldset className="checks-panel">
              <legend>Equipamiento</legend>
              {[
                "Fibra",
                "Escritorio",
                "Armario",
                "Balcón",
                "Lavadora",
                "Aire acondicionado",
              ].map((item) => (
                <label key={item}>
                  <Checkbox
                    checked={draft.amenities.includes(item)}
                    onCheckedChange={() => toggleAmenity(item)}
                  />
                  {item}
                </label>
              ))}
            </fieldset>
          </WizardSection>
        );
      case 3:
        return (
          <WizardSection
            title="Precio, gastos y fianza"
            description="Separa cada concepto."
          >
            <div className="form-grid">
              {draft.rentalMode === "long" ? <FormField label="Alquiler mensual" htmlFor="publish-price" error={errors.price}>
                <Input
                  id="publish-price"
                  type="number"
                  min="1"
                  value={draft.monthlyPrice}
                  aria-invalid={Boolean(errors.price)}
                  onChange={(e) => set("monthlyPrice", Number(e.target.value))}
                />
              </FormField> : <>
                <FormField label="Precio por noche" htmlFor="publish-price" error={errors.price}><Input id="publish-price" type="number" min="1" value={draft.nightlyPrice} aria-invalid={Boolean(errors.price)} onChange={(e) => set("nightlyPrice", Number(e.target.value))} /></FormField>
                <FormField label="Precio por semana" htmlFor="publish-weekly-price"><Input id="publish-weekly-price" type="number" min="0" value={draft.weeklyPrice ?? ""} onChange={(e) => set("weeklyPrice", e.target.value ? Number(e.target.value) : undefined)} /></FormField>
                <FormField label="Precio por mes" htmlFor="publish-monthly-price"><Input id="publish-monthly-price" type="number" min="0" value={draft.monthlyPrice} onChange={(e) => set("monthlyPrice", Number(e.target.value))} /></FormField>
              </>}
              <FormField label="Fianza" htmlFor="publish-deposit">
                <Input
                  id="publish-deposit"
                  type="number"
                  min="0"
                  value={draft.depositAmount}
                  onChange={(e) => set("depositAmount", Number(e.target.value))}
                />
              </FormField>
            </div>
            <label className="check-row">
              <Checkbox
                checked={draft.billsIncluded}
                onCheckedChange={(value) =>
                  set("billsIncluded", value === true)
                }
              />
              Gastos incluidos
            </label>
            <FormField label="Aclaración sobre gastos" htmlFor="publish-bills">
              <Input
                id="publish-bills"
                value={draft.billsNote}
                onChange={(e) => set("billsNote", e.target.value)}
              />
            </FormField>
          </WizardSection>
        );
      case 4:
        return (
          <WizardSection
            title="Disponibilidad"
            description="Indica cuándo puede entrar la próxima persona."
          >
            <div className="form-grid">
              <FormField
                label="Disponible desde"
                htmlFor="publish-available"
                error={errors.availableFrom}
              >
                <Input
                  id="publish-available"
                  type="date"
                  value={draft.availableFrom}
                  aria-invalid={Boolean(errors.availableFrom)}
                  onChange={(e) => set("availableFrom", e.target.value)}
                />
              </FormField>
              {draft.rentalMode === "long" ? <FormField label="Estancia mínima (meses)" htmlFor="publish-min-stay">
                <Input
                  id="publish-min-stay"
                  type="number"
                  min="0"
                  value={draft.minimumStayMonths}
                  onChange={(e) =>
                    set("minimumStayMonths", Number(e.target.value))
                  }
                />
              </FormField> : <>
                <FormField label="Estancia mínima (noches)" htmlFor="publish-min-nights"><Input id="publish-min-nights" type="number" min="1" value={draft.minimumNights} onChange={(e) => set("minimumNights", Number(e.target.value))} /></FormField>
                <FormField label="Disponible hasta" htmlFor="publish-available-until"><Input id="publish-available-until" type="date" value={draft.availableUntil ?? ""} onChange={(e) => set("availableUntil", e.target.value)} /></FormField>
              </>}
              <FormField label="Fecha límite" htmlFor="publish-expiry">
                <Input
                  id="publish-expiry"
                  type="date"
                  value={draft.expiresAt}
                  onChange={(e) => set("expiresAt", e.target.value)}
                />
              </FormField>
            </div>
          </WizardSection>
        );
      case 5:
        return (
          <WizardSection
            title="Condiciones de convivencia"
            description="Exprésalas de forma concreta y neutral."
          >
            <FormField label="Requisito para la persona inquilina" htmlFor="publish-tenant-requirement">
              <select
                id="publish-tenant-requirement"
                value={draft.tenantRequirement}
                onChange={(e) => {
                  const requirement = e.target.value as ListingDraft["tenantRequirement"];
                  const roomCapacity = requirement === "couple" ? 2 : requirement === "any" ? draft.roomCapacity : 1;
                  const genderPreference = requirement === "single-man" ? "Solo hombre" : requirement === "single-woman" ? "Solo mujer" : "Sin preferencia de género";
                  setDraft((current) => ({ ...current, tenantRequirement: requirement, roomCapacity, couplesAllowed: requirement === "couple", genderPreference }));
                }}
              >
                <option value="single-man">Solo un hombre</option>
                <option value="single-woman">Solo una mujer</option>
                <option value="single-person">Una persona</option>
                <option value="couple">Solo pareja</option>
                <option value="any">Sin restricción</option>
              </select>
            </FormField>
            <fieldset className="checks-panel checks-panel--columns">
              <legend>Convivencia</legend>
              {(
                [
                  ["petsAllowed", "Mascotas permitidas"],
                  ["smokingAllowed", "Se puede fumar"],
                  ["childrenAllowed", "Niños permitidos"],
                  ["empadronamientoAllowed", "Empadronamiento posible"],
                ] as const
              ).map(([key, label]) => (
                <label key={key}>
                  <Checkbox
                    checked={draft[key]}
                    onCheckedChange={(value) => set(key, value === true)}
                  />
                  {label}
                </label>
              ))}
            </fieldset>
            <FormField label="Normas de la vivienda" htmlFor="publish-rules">
              <Textarea
                id="publish-rules"
                rows={5}
                value={draft.rules}
                onChange={(e) => set("rules", e.target.value)}
              />
            </FormField>
          </WizardSection>
        );
      case 6:
        return (
          <WizardSection
            title="Fotografías"
            description="La primera será la portada. Puedes reordenarlas."
          >
            <ImageUploader
              images={draft.images}
              onChange={(images) => set("images", images)}
              onRemove={(image) => {
                if (existing?.images.includes(image)) pendingMediaRemovals.current.add(image);
                else void removeMedia(image).catch((error) =>
                  toast.error(error instanceof Error ? error.message : "No se pudo limpiar la imagen local."),
                );
              }}
              error={errors.images}
            />
          </WizardSection>
        );
      case 7:
        return (
          <WizardSection
            title="Cuenta cómo es vivir aquí"
            description="Responde las dudas habituales."
          >
            <FormField
              label="Título del anuncio"
              htmlFor="publish-title"
              description="Máximo 80 caracteres."
              error={errors.title}
            >
              <Input
                id="publish-title"
                maxLength={80}
                value={draft.title}
                aria-invalid={Boolean(errors.title)}
                onChange={(e) => set("title", e.target.value)}
              />
            </FormField>
            <FormField
              label="Descripción"
              htmlFor="publish-description"
              error={errors.description}
            >
              <Textarea
                id="publish-description"
                rows={8}
                value={draft.description}
                aria-invalid={Boolean(errors.description)}
                onChange={(e) => set("description", e.target.value)}
              />
            </FormField>
          </WizardSection>
        );
      case 8:
        return (
          <WizardSection
            title="Datos de contacto"
            description="Estos canales se mostrarán tras confirmar la condición principal."
          >
            <div className="form-grid">
              <FormField
                label="Nombre público"
                htmlFor="publish-contact-name"
                error={errors.contactName}
              >
                <Input
                  id="publish-contact-name"
                  value={draft.contactName || currentUser?.name || ""}
                  aria-invalid={Boolean(errors.contactName)}
                  onChange={(e) => set("contactName", e.target.value)}
                />
              </FormField>
              <FormField
                label="Teléfono"
                htmlFor="publish-contact-phone"
                error={errors.contactPhone}
              >
                <Input
                  id="publish-contact-phone"
                  type="tel"
                  value={draft.contactPhone}
                  aria-invalid={Boolean(errors.contactPhone)}
                  onChange={(e) => {
                    set("contactPhone", e.target.value);
                  }}
                />
              </FormField>
              <FormField label="WhatsApp" htmlFor="publish-contact-whatsapp" error={errors.contactWhatsapp}>
                <Input id="publish-contact-whatsapp" type="tel" value={draft.contactWhatsapp} aria-invalid={Boolean(errors.contactWhatsapp)} onChange={(e) => set("contactWhatsapp", e.target.value)} />
              </FormField>
              <FormField
                label="Email"
                htmlFor="publish-contact-email"
                error={errors.contactEmail}
              >
                <Input
                  id="publish-contact-email"
                  type="email"
                  value={draft.contactEmail}
                  aria-invalid={Boolean(errors.contactEmail)}
                  onChange={(e) => set("contactEmail", e.target.value)}
                />
              </FormField>
            </div>
            <fieldset className="checks-panel contact-methods" aria-describedby={errors.contactMethods ? "contact-methods-error" : undefined}>
              <legend>Canales disponibles</legend>
              <label><Checkbox checked={draft.showPhone} onCheckedChange={(value) => set("showPhone", value === true)} />Mostrar teléfono tras confirmar</label>
              <label><Checkbox checked={draft.showWhatsApp} onCheckedChange={(value) => set("showWhatsApp", value === true)} />Permitir WhatsApp tras confirmar</label>
              <label><Checkbox checked={draft.allowContactForm} onCheckedChange={(value) => set("allowContactForm", value === true)} />Permitir mensaje local</label>
            </fieldset>
            {errors.contactMethods ? <p id="contact-methods-error" className="field-error" role="alert">{errors.contactMethods}</p> : null}
          </WizardSection>
        );
      default:
        return (
          <WizardSection
            title="Revisa antes de publicar"
            description="Así se verá el anuncio."
          >
            <Alert>
              <FileCheck2 />
              <AlertTitle>El anuncio está completo</AlertTitle>
              <AlertDescription>
                Revisa precio, condiciones y fecha de entrada.
              </AlertDescription>
            </Alert>
            <div className="preview-card-wrap">
              <PropertyCard listing={preview} />
            </div>
            <div className="preview-contact-methods" aria-label="Canales de contacto visibles">
              <h3>Canales tras confirmar condiciones</h3>
              <div className="badge-row">
                {preview.showPhone ? <PropertyBadge>Teléfono</PropertyBadge> : null}
                {preview.showWhatsApp ? <PropertyBadge>WhatsApp</PropertyBadge> : null}
                {preview.allowContactForm ? <PropertyBadge>Mensaje local</PropertyBadge> : null}
              </div>
            </div>
            <div className="preview-conditions">
              <h3>Condiciones visibles</h3>
              <div className="badge-row">
                {preview.restrictions.map((item) => (
                  <PropertyBadge key={item}>{item}</PropertyBadge>
                ))}
              </div>
            </div>
            <Dialog>
              <DialogTrigger asChild>
                <Button variant="outline">
                  <Eye data-icon="inline-start" />
                  Vista previa completa
                </Button>
              </DialogTrigger>
              <DialogContent className="full-preview-dialog">
                <DialogHeader>
                  <DialogTitle>Vista previa del anuncio</DialogTitle>
                  <DialogDescription>
                    Versión pública antes de publicar.
                  </DialogDescription>
                </DialogHeader>
                <PropertyGallery listing={preview} />
                <div className="full-preview-summary">
                  <div>
                    <span className="eyebrow">
                      {preview.area}, {preview.city}
                    </span>
                    <h2>{preview.title}</h2>
                    <p>{preview.description}</p>
                  </div>
                  <PriceBlock listing={preview} large />
                </div>
                <dl className="detail-list">
                  <div>
                    <dt>Disponibilidad</dt>
                    <dd>{preview.available}</dd>
                  </div>
                  <div>
                    <dt>Estancia mínima</dt>
                    <dd>{preview.minimumStay}</dd>
                  </div>
                  <div>
                    <dt>Gastos</dt>
                    <dd>{preview.bills}</dd>
                  </div>
                  <div>
                    <dt>Fianza</dt>
                    <dd>{preview.deposit}</dd>
                  </div>
                </dl>
                <div className="badge-row">
                  {preview.restrictions.map((item) => (
                    <PropertyBadge key={item}>{item}</PropertyBadge>
                  ))}
                </div>
                <div className="preview-contact-methods" aria-label="Canales de contacto visibles">
                  <h3>Canales tras confirmar condiciones</h3>
                  <div className="badge-row">
                    {preview.showPhone ? <PropertyBadge>Teléfono</PropertyBadge> : null}
                    {preview.showWhatsApp ? <PropertyBadge>WhatsApp</PropertyBadge> : null}
                    {preview.allowContactForm ? <PropertyBadge>Mensaje local</PropertyBadge> : null}
                  </div>
                </div>
              </DialogContent>
            </Dialog>
          </WizardSection>
        );
    }
  })();

  if (published)
    return (
      <div className="publish-success">
        <CheckCircle2 />
        <span className="eyebrow">Anuncio publicado</span>
        <h1>
          {editing ? "Cambios guardados" : "Tu habitación ya está visible"}
        </h1>
        <p>
          El anuncio se ha guardado localmente y aparece en la búsqueda y en Mis
          anuncios.
        </p>
        <div>
          <Button asChild>
            <Link to="/mis-anuncios">Ver mis anuncios</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to={`/habitacion/${preview.id}`}>Ver anuncio</Link>
          </Button>
        </div>
      </div>
    );
  return (
    <>
    <div className="publish-page">
      <div className="container publish-header">
        {isDirty ? <ConfirmDialog
          trigger={
            <Button variant="ghost">
              <ArrowLeft data-icon="inline-start" />
              Salir
            </Button>
          }
          title="¿Salir del editor?"
          description="El borrador automático seguirá guardado para que puedas continuar después."
          confirmLabel="Salir y conservar borrador"
          onConfirm={() => navigate("/mis-anuncios")}
        /> : <Button variant="ghost" onClick={() => navigate("/mis-anuncios")}><ArrowLeft data-icon="inline-start" />Salir</Button>}
        <div>
          <span className="eyebrow">
            {editing
              ? `Editando ${id?.slice(-5).toUpperCase()}`
              : "Nuevo anuncio"}
          </span>
          <h1>{editing ? "Editar habitación" : "Publicar una habitación"}</h1>
        </div>
        <div className="publish-header__actions">
          <ConfirmDialog
            trigger={
              <Button variant="ghost">
                <RotateCcw data-icon="inline-start" />
                Restablecer
              </Button>
            }
            title="¿Restablecer el borrador?"
            description="Se eliminarán los cambios de todos los pasos y volverán los valores iniciales."
            confirmLabel="Restablecer"
            destructive
            onConfirm={resetDraft}
          />
          <Button
            variant="outline"
            onClick={() => {
              try {
                localStorage.setItem(draftKey, JSON.stringify({ version: 3, data: draft }));
                setBaseline(JSON.stringify(draft));
                toast.success("Borrador guardado");
              } catch {
                toast.error("No se pudo guardar el borrador. Revisa el espacio disponible.");
              }
            }}
          >
            <Save data-icon="inline-start" />
            Guardar borrador
          </Button>
          <span className="dirty-state" aria-live="polite">{isDirty ? "Cambios sin guardar" : "Borrador guardado"}</span>
        </div>
      </div>
      <div className="container wizard-layout">
        <aside>
          <Stepper
            steps={steps}
            current={step}
            maxVisited={maxVisited}
            onStep={setStep}
          />
        </aside>
        <section className="wizard-content" aria-label="Formulario del anuncio">
          {content}
          <div className="wizard-actions">
            <Button
              variant="outline"
              disabled={step === 0}
              onClick={() => setStep((value) => value - 1)}
            >
              <ArrowLeft data-icon="inline-start" />
              Atrás
            </Button>
            {step === steps.length - 1 ? (
              <Button onClick={finish}>
                Publicar anuncio <CheckCircle2 data-icon="inline-end" />
              </Button>
            ) : (
              <Button onClick={next}>
                Continuar <ArrowRight data-icon="inline-end" />
              </Button>
            )}
          </div>
        </section>
      </div>
    </div>
    <AlertDialog open={Boolean(pendingRoute)} onOpenChange={(open) => { if (!open) setPendingRoute(null); }}>
      <AlertDialogContent>
        <AlertDialogHeader><AlertDialogTitle>¿Salir del editor?</AlertDialogTitle><AlertDialogDescription>Hay cambios sin guardar. El borrador automático se conserva, pero puedes guardar manualmente antes de salir.</AlertDialogDescription></AlertDialogHeader>
        <AlertDialogFooter><AlertDialogCancel>Seguir editando</AlertDialogCancel><AlertDialogAction onClick={() => { const route = pendingRoute; setPendingRoute(null); if (route) navigate(route); }}>Salir y conservar borrador</AlertDialogAction></AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
    </>
  );
}
