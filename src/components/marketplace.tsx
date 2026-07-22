import {
  lazy,
  Suspense,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
  type SyntheticEvent,
} from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Bath,
  BedDouble,
  CalendarDays,
  Camera,
  ChevronLeft,
  ChevronRight,
  CigaretteOff,
  CircleAlert,
  Crosshair,
  Euro,
  Expand,
  Heart,
  Home,
  Map as MapIcon,
  MapPin,
  MessageCircle,
  MoreHorizontal,
  PawPrint,
  Phone,
  Pencil,
  Search,
  Share2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Trash2,
  UsersRound,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { cn } from "@/lib/utils";
import { MediaImage } from "@/components/media-image";
import {
  amenityOptions,
  areas,
  defaultFilters,
  initialListings,
} from "@/data/listings";
import {
  filterListings,
  filtersToParams,
  formatPublishedAt,
} from "@/lib/search";
import {
  buildContactConfirmationText,
  getCriticalRestrictions,
  getImageCriticalRestrictions,
  getPrimaryCadence,
  getPrimaryPrice,
} from "@/lib/listings";
import { TENERIFE_LOCATIONS, resolveTenerifeLocation } from "@/lib/tenerife";
import type {
  Filters,
  Listing,
  MapPolygonPoint,
  RentalMode,
  YesNoAny,
} from "@/types";
import { useApp } from "@/contexts/app-context";
import { useI18n } from "@/contexts/i18n-context";

const LazyLeafletMap = lazy(() =>
  import("@/components/map-view").then((module) => ({
    default: module.LeafletMapView,
  })),
);
export type { MapBounds } from "@/components/map-view";

const fallbackImage =
  'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 560"%3E%3Crect width="800" height="560" fill="%23eceeea"/%3E%3Cpath d="M260 360l90-95 62 65 48-44 92 96H260z" fill="%2398a19a"/%3E%3Ccircle cx="505" cy="190" r="34" fill="%23b7beb8"/%3E%3Ctext x="400" y="445" text-anchor="middle" fill="%235b635d" font-family="Arial" font-size="28"%3EFoto no disponible%3C/text%3E%3C/svg%3E';
const imageFallback = (event: SyntheticEvent<HTMLImageElement>) => {
  event.currentTarget.src = fallbackImage;
};

export function RentalTypeSwitch({
  compact = false,
  onChange,
}: {
  compact?: boolean;
  onChange?: (mode: RentalMode) => void;
}) {
  const { rentalMode, setRentalMode } = useApp();
  return (
    <ToggleGroup
      type="single"
      value={rentalMode}
      onValueChange={(value) => {
        if (!value) return;
        const mode = value as RentalMode;
        setRentalMode(mode);
        onChange?.(mode);
      }}
      className={cn("rental-switch", compact && "rental-switch--compact")}
      aria-label="Tipo de alquiler"
    >
      <ToggleGroupItem value="long" aria-label="Larga estancia">Habitaciones Vivienda</ToggleGroupItem>
      <ToggleGroupItem value="holiday" aria-label="Alquiler vacacional">Habitaciones Turísticas</ToggleGroupItem>
    </ToggleGroup>
  );
}

export function SearchLocationInput({
  value,
  onChange,
  error,
}: {
  value: string;
  onChange: (value: string) => void;
  error?: string;
}) {
  const id = useId();
  const listId = useId();
  const { searchHistory, filters, setFilters } = useApp();
  const suggestions = [...new Set([...searchHistory, ...TENERIFE_LOCATIONS.map((location) => location.normalizedValue)])];
  return (
    <div className="search-location">
      <label htmlFor={id}>Ciudad, barrio o zona</label>
      <div className="search-location-row">
        <MapPin className="search-location-row__icon" aria-hidden="true" />
        <Input
          id={id}
          list={listId}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Municipio, barrio o zona de Tenerife"
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
        />
        <datalist id={listId}>
          {suggestions.map((suggestion) => (
            <option key={suggestion} value={suggestion} />
          ))}
        </datalist>
        <LocationSelector
          selected={filters.areas}
          currentQuery={value}
          onLocationSelect={onChange}
          onApply={(selected) => {
            setFilters({ ...filters, areas: selected });
            onChange(selected.length === 1 ? selected[0] : "Tenerife");
          }}
        />
      </div>
      {error ? <span id={`${id}-error`} className="location-validation" role="alert">{error}</span> : null}
    </div>
  );
}

export function SearchBar({ compact = false, home = false }: { compact?: boolean; home?: boolean }) {
  const { query, setQuery, addSearchHistory, filters, setFilters, rentalMode } =
    useApp();
  const { language, t } = useI18n();
  const navigate = useNavigate();
  const [locationError, setLocationError] = useState("");
  const tenantOptions = language === "ru"
    ? [
        ["Cualquiera", "Для кого: любой"], ["single-man", "Для кого: только мужчина"],
        ["single-woman", "Для кого: только женщина"], ["single-person", "Для кого: один человек"],
        ["couple", "Для кого: только пара"], ["any", "Для кого: без ограничений"],
      ]
    : language === "en"
      ? [
          ["Cualquiera", "Who is it for: anyone"], ["single-man", "Who is it for: men only"],
          ["single-woman", "Who is it for: women only"], ["single-person", "Who is it for: one person"],
          ["couple", "Who is it for: couples only"], ["any", "Who is it for: no restriction"],
        ]
      : [
          ["Cualquiera", "Para quién: cualquiera"], ["single-man", "Para quién: solo un hombre"],
          ["single-woman", "Para quién: solo una mujer"], ["single-person", "Para quién: una persona"],
          ["couple", "Para quién: solo pareja"], ["any", "Para quién: sin restricción"],
        ];
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const location = resolveTenerifeLocation(query.trim() || "Tenerife");
    if (!location) {
      setLocationError("En esta versión solo puedes buscar habitaciones en Tenerife.");
      return;
    }
    setLocationError("");
    const normalized = location.normalizedValue;
    const exactArea = location.type === "area" || location.type === "district" ? location.normalizedValue : undefined;
    const nextFilters = {
      ...filters,
      areas: exactArea ? [exactArea] : location.type === "island" && filters.areas.length > 1 ? filters.areas : [],
    };
    setQuery(normalized);
    setFilters(nextFilters);
    addSearchHistory(normalized);
    const params = filtersToParams(
      nextFilters,
      new URLSearchParams({ q: normalized, alquiler: rentalMode }),
    );
    navigate(`/buscar?${params.toString()}`);
  };
  return (
    <form
      className={cn("search-bar", compact && "search-bar--compact", home && "search-bar--home")}
      onSubmit={submit}
      role="search"
    >
      {home ? <FieldGroup className="home-tenant-field"><Field><FieldLabel className="sr-only" htmlFor="home-tenant-requirement">{t("Para quién")}</FieldLabel><select id="home-tenant-requirement" aria-label={t("Para quién")} value={filters.tenantRequirement} onChange={(event) => setFilters({ ...filters, tenantRequirement: event.target.value as Filters["tenantRequirement"] })}>{tenantOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field></FieldGroup> : null}
      <SearchLocationInput value={query} error={locationError} onChange={(value) => { setQuery(value); if (locationError) setLocationError(""); }} />
      {compact ? null : (
        <div className="search-date">
          <label htmlFor="move-date">Entrada</label>
          <div>
            <CalendarDays aria-hidden="true" />
            <Input
              id="move-date"
              type="date"
              value={filters.available}
              onChange={(event) =>
                setFilters({ ...filters, available: event.target.value })
              }
            />
          </div>
        </div>
      )}
      <Button size="lg" type="submit">
        <Search data-icon="inline-start" />
        Buscar
      </Button>
    </form>
  );
}

export function LocationSelector({
  selected,
  onApply,
  currentQuery = "Tenerife",
  onLocationSelect,
}: {
  selected: string[];
  onApply: (selectedAreas: string[]) => void;
  currentQuery?: string;
  onLocationSelect?: (query: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(selected);
  const [term, setTerm] = useState("");
  const [showZoneList, setShowZoneList] = useState(false);
  const filteredAreas = areas.filter((area) =>
    area.toLocaleLowerCase().includes(term.trim().toLocaleLowerCase()),
  );
  const catalogResults = TENERIFE_LOCATIONS.filter((location) => {
    if (!term.trim()) return location.type === "island" || location.type === "municipality" && ['Adeje', 'Arona', 'Granadilla de Abona', 'San Cristóbal de La Laguna', 'Santa Cruz de Tenerife'].includes(location.label)
    const needle = term.trim().normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase()
    return [location.label, ...(location.aliases ?? [])].some((value) => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().includes(needle))
  }).slice(0, 8);
  useEffect(() => {
    if (open) {
      setDraft(selected);
      setTerm("");
      setShowZoneList(false);
    }
  }, [open, selected]);
  const toggle = (area: string) =>
    setDraft((current) =>
      current.includes(area)
        ? current.filter((item) => item !== area)
        : [...current, area],
    );
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="location-selector-trigger"
          aria-label={`Abrir selección de ubicación. ${currentQuery || "Tenerife"}`}
        >
          <MapPin className="location-trigger-mobile-icon" aria-hidden="true" />
          <span className="location-trigger-mobile-copy">{currentQuery || "Municipio, barrio o zona de Tenerife"}</span>
          <SlidersHorizontal className="location-trigger-desktop-icon" data-icon="inline-start" />
          <span className="location-trigger-desktop-copy">Zonas{selected.length ? ` (${selected.length})` : ""}</span>
        </Button>
      </DialogTrigger>
      <DialogContent className="location-selector-dialog" showCloseButton={false}>
        <DialogHeader className="location-selector-dialog__header">
          {showZoneList ? <Button type="button" variant="ghost" size="icon" onClick={() => setShowZoneList(false)} aria-label="Volver a las opciones de ubicación"><ArrowLeft /></Button> : <DialogClose asChild><Button type="button" variant="ghost" size="icon" aria-label="Volver"><ArrowLeft /></Button></DialogClose>}
          <div>
            <DialogTitle>{showZoneList ? "Seleccionar zonas" : "¿Dónde buscas?"}</DialogTitle>
            <DialogDescription>{showZoneList ? "Elige uno o varios municipios o barrios de Tenerife." : "Busca en Tenerife por municipio, barrio o zona."}</DialogDescription>
          </div>
        </DialogHeader>
        <div className={cn("location-dialog-primary", showZoneList && "is-hidden")}>
          <div className="location-market-row"><span>Buscar en</span><strong>Tenerife</strong></div>
          <label className="location-selector-search">
            <span className="sr-only">Buscar zona</span>
            <Search aria-hidden="true" />
            <Input value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Municipio, barrio, zona o dirección" autoComplete="off" autoFocus />
          </label>
          {term.trim() ? <div className="location-catalog-list" aria-label="Lugares de Tenerife">
            {catalogResults.map((location) => <button type="button" key={`${location.type}-${location.label}`} onClick={() => {
              onLocationSelect?.(location.normalizedValue);
              setDraft(location.type === 'area' || location.type === 'district' ? [location.normalizedValue] : []);
              setOpen(false);
            }}><MapPin aria-hidden="true" /><span><strong>{location.label}</strong><small>{location.type === 'island' ? 'Isla' : location.type === 'municipality' ? 'Municipio' : location.type === 'district' ? 'Distrito' : 'Zona'}</small></span></button>)}
          </div> : null}
          <div className="location-action-list" aria-label="También puedes">
            <span>También puedes:</span>
            <Link to="/buscar?vista=mapa"><MapIcon aria-hidden="true" /><strong>Seleccionar zonas en el mapa</strong><ChevronRight aria-hidden="true" /></Link>
            <Link to="/buscar?vista=mapa&dibujar=1"><Pencil aria-hidden="true" /><strong>Dibujar tu zona</strong><ChevronRight aria-hidden="true" /></Link>
            <Link to="/buscar?vista=mapa"><MapPin aria-hidden="true" /><strong>Buscar en el mapa</strong><ChevronRight aria-hidden="true" /></Link>
            <Link to="/buscar?vista=mapa&cerca=1"><Crosshair aria-hidden="true" /><strong>Buscar alrededor de ti</strong><ChevronRight aria-hidden="true" /></Link>
          </div>
          <Button type="button" variant="ghost" className="location-zones-toggle" onClick={() => setShowZoneList(true)}>Seleccionar municipios y barrios <ChevronRight data-icon="inline-end" /></Button>
        </div>
        <div className={cn("location-zones-panel", showZoneList && "is-open")}>
          <div className="location-selector-summary"><strong>Tenerife</strong><button type="button" onClick={() => setDraft([])}>Toda la isla</button></div>
          <div className="location-selector-list" role="group" aria-label="Zonas de Tenerife">
            {filteredAreas.map((area) => (
              <label className="location-selector-option" key={area}>
                <Checkbox checked={draft.includes(area)} onCheckedChange={() => toggle(area)} />
                <span><strong>{area}</strong><small>{initialListings.filter((listing) => listing.area === area).length} habitaciones demo</small></span>
              </label>
            ))}
          </div>
          <DialogFooter className="location-selector-footer">
            <Button variant="ghost" onClick={() => setDraft([])}>Borrar</Button>
            <Button onClick={() => { onApply(draft); setOpen(false); }}>Aplicar{draft.length ? ` ${draft.length} zonas` : ""}</Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}

const restrictionTone = (text: string) =>
  text.includes("incluid") ||
  text.includes("permitid") ||
  text.includes("posible")
    ? "positive"
    : text.includes("Solo") || text.includes("Sin") || text.includes("No ")
      ? "restriction"
      : "neutral";
const restrictionIcon = (text: string) =>
  text.toLocaleLowerCase().includes("mascota")
    ? PawPrint
    : text.toLocaleLowerCase().includes("fumar")
      ? CigaretteOff
      : text.includes("mes") || text.includes("noche")
        ? CalendarDays
        : text.includes("Gastos")
          ? Euro
          : text.includes("Parej") ||
              text.includes("hombre") ||
              text.includes("mujer") ||
              text.includes("género")
            ? UsersRound
            : ShieldCheck;

export function PropertyBadge({ children }: { children: string }) {
  const Icon = restrictionIcon(children);
  return (
    <Badge
      variant="outline"
      className={cn(
        "property-badge",
        `property-badge--${restrictionTone(children)}`,
      )}
    >
      <Icon aria-hidden="true" />
      {children}
    </Badge>
  );
}

export function FavoriteButton({ listing }: { listing: Listing }) {
  const { favorites, toggleFavorite } = useApp();
  const saved = favorites.has(listing.id);
  return (
    <button
      type="button"
      className={cn("favorite-button", saved && "is-saved")}
      aria-label={
        saved
          ? `Quitar ${listing.title} de favoritos`
          : `Guardar ${listing.title} en favoritos`
      }
      aria-pressed={saved}
      onClick={() => toggleFavorite(listing.id)}
    >
      <Heart aria-hidden="true" fill={saved ? "currentColor" : "none"} />
    </button>
  );
}

export function CriticalRestrictionOverlay({ listing, compact = false }: { listing: Listing; compact?: boolean }) {
  const restrictions = getImageCriticalRestrictions(listing);
  if (!restrictions.length) return null;
  return (
    <div className={cn("critical-restriction-overlay", compact && "critical-restriction-overlay--compact")} role="note" aria-label={`Condiciones importantes: ${restrictions.join(", ")}`}>
      {restrictions.map((restriction) => <span key={restriction}>{restriction}</span>)}
    </div>
  );
}

export function PriceBlock({
  listing,
  large = false,
}: {
  listing: Listing;
  large?: boolean;
}) {
  return (
    <div className={cn("price-block", large && "price-block--large")}>
      <strong>
        {new Intl.NumberFormat("es-ES", {
          style: "currency",
          currency: "EUR",
          maximumFractionDigits: 0,
        }).format(getPrimaryPrice(listing))}
      </strong>
      <span>/{getPrimaryCadence(listing)}</span>
    </div>
  );
}

export function PropertyCard({
  listing,
  compact = false,
  selected = false,
  onFocus,
}: {
  listing: Listing;
  compact?: boolean;
  selected?: boolean;
  onFocus?: () => void;
}) {
  const { discardListing } = useApp();
  const [imageIndex, setImageIndex] = useState(0);
  const share = async () => {
    const url = `${location.origin}${location.pathname}#/habitacion/${listing.id}`;
    if (navigator.share)
      await navigator
        .share({ title: listing.title, url })
        .catch(() => undefined);
    else
      await navigator.clipboard
        ?.writeText(url)
        .then(() => toast.success("Enlace copiado"))
        .catch(() => toast.info(url));
  };
  const criticalRestrictions = getCriticalRestrictions(listing);
  const visibleRestrictions = criticalRestrictions.slice(0, compact ? 2 : 3);
  return (
    <article
      className={cn(
        "property-card",
        compact && "property-card--compact",
        selected && "is-selected",
      )}
      onMouseEnter={onFocus}
      onFocus={onFocus}
      data-listing-id={listing.id}
    >
      <div className="property-card__media">
        <Link
          to={`/habitacion/${listing.id}`}
          aria-label={`Ver ${listing.title}`}
        >
          <MediaImage
            src={listing.images[imageIndex] || fallbackImage}
            onError={imageFallback}
            alt={`Habitación en ${listing.area}, foto ${imageIndex + 1} de ${listing.images.length}`}
            width="720"
            height="480"
            loading="lazy"
          />
        </Link>
        <button
          type="button"
          className="card-gallery-arrow card-gallery-arrow--previous"
          onClick={() =>
            setImageIndex(
              (current) =>
                (current - 1 + listing.images.length) % listing.images.length,
            )
          }
          aria-label={`Foto anterior de ${listing.title}`}
        >
          <ChevronLeft />
        </button>
        <button
          type="button"
          className="card-gallery-arrow card-gallery-arrow--next"
          onClick={() =>
            setImageIndex((current) => (current + 1) % listing.images.length)
          }
          aria-label={`Foto siguiente de ${listing.title}`}
        >
          <ChevronRight />
        </button>
        <span className="image-counter">
          <Camera aria-hidden="true" />
          {imageIndex + 1}/{listing.images.length}
        </span>
        <FavoriteButton listing={listing} />
        {imageIndex === 0 ? <CriticalRestrictionOverlay listing={listing} /> : null}
        {listing.advertiserType === "Profesional" ? (
          <span className="listing-status">Profesional</span>
        ) : null}
      </div>
      <div className="property-card__content">
        <Link className="property-card__body-link" to={`/habitacion/${listing.id}`} aria-label={`Abrir ${listing.title}`}>
          <h3>{listing.title}</h3>
          <div className="card-topline">
            <PriceBlock listing={listing} />
            <span>{listing.bills}</span>
          </div>
          <p className="property-location"><MapPin aria-hidden="true" />{listing.area}, {listing.city}</p>
          <div className="property-facts">
            <span><BedDouble aria-hidden="true" />{listing.roomType}</span>
            <span>{listing.currentResidents} residentes · {listing.roomSizeM2} m²</span>
            <span><CalendarDays aria-hidden="true" />{listing.available}</span>
          </div>
          {compact ? null : <p className="property-description">{listing.description}</p>}
          <div className="badge-row">
            {visibleRestrictions.map((item) => <PropertyBadge key={item}>{item}</PropertyBadge>)}
            {criticalRestrictions.length > visibleRestrictions.length ? <Badge variant="secondary">+{criticalRestrictions.length - visibleRestrictions.length} condiciones</Badge> : null}
          </div>
          <div className="property-card__meta"><span>{formatPublishedAt(listing.publishedAt)}</span><span>{listing.advertiserType}</span></div>
        </Link>
        {compact ? null : (
          <div className="property-card__actions">
            <Button asChild>
              <Link to={`/habitacion/${listing.id}`}>
                <MessageCircle data-icon="inline-start" />
                Contactar
              </Link>
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon" aria-label={`Más opciones para ${listing.title}`}>
                  <MoreHorizontal />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuGroup>
                  <DropdownMenuItem onSelect={() => void share()}><Share2 />Compartir</DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => { discardListing(listing.id); toast.success("Anuncio descartado de la búsqueda"); }}><Trash2 />Descartar</DropdownMenuItem>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}
      </div>
    </article>
  );
}

export function LoadingSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div
      className="skeleton-list"
      aria-label="Cargando habitaciones"
      aria-busy="true"
    >
      {Array.from({ length: count }).map((_, index) => (
        <div className="property-skeleton" key={index}>
          <Skeleton className="h-full min-h-52" />
          <div>
            <Skeleton className="h-7 w-28" />
            <Skeleton className="h-5 w-4/5" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-16 w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}
export function EmptyState({
  favorites = false,
  onReset,
}: {
  favorites?: boolean;
  onReset?: () => void;
}) {
  return (
    <Empty className="empty-state">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          {favorites ? <Heart /> : <Search />}
        </EmptyMedia>
        <EmptyTitle>
          {favorites
            ? "Aún no has guardado habitaciones"
            : "No hay habitaciones con estos filtros"}
        </EmptyTitle>
        <EmptyDescription>
          {favorites
            ? "Guarda las que te gusten para compararlas aquí."
            : "Prueba a ampliar el precio, quitar una condición o recuperar anuncios descartados."}
        </EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        {onReset ? (
          <Button onClick={onReset}>Borrar filtros</Button>
        ) : (
          <Button asChild>
            <Link to="/buscar">Explorar habitaciones</Link>
          </Button>
        )}
      </EmptyContent>
    </Empty>
  );
}
export function ErrorState() {
  return (
    <Alert variant="destructive">
      <CircleAlert />
      <AlertTitle>No hemos podido cargar los resultados</AlertTitle>
      <AlertDescription>
        Comprueba tu conexión y vuelve a intentarlo. Tus filtros siguen
        guardados.{" "}
        <Button variant="outline" size="sm" onClick={() => location.reload()}>
          Reintentar
        </Button>
      </AlertDescription>
    </Alert>
  );
}

const filterConditions = [
  "Mascotas permitidas",
  "No fumar",
  "Empadronamiento posible",
  "Gastos incluidos",
];
function CheckOption({
  label,
  checked,
  onCheckedChange,
}: {
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  const id = useId();
  return (
    <label className="check-option" htmlFor={id}>
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(value) => onCheckedChange(value === true)}
      />
      <span>{label}</span>
    </label>
  );
}
function NativeSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<string | { value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  const id = useId();
  return (
    <label className="field-label" htmlFor={id}>
      {label}
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => {
          const item = typeof option === "string" ? { value: option, label: option } : option;
          return <option key={item.value} value={item.value}>{item.label}</option>;
        })}
      </select>
    </label>
  );
}
function YesNoFilter({
  label,
  value,
  onChange,
}: {
  label: string;
  value: YesNoAny;
  onChange: (value: YesNoAny) => void;
}) {
  return (
    <NativeSelect
      label={label}
      value={value}
      options={["Cualquiera", "Sí", "No"]}
      onChange={(next) => onChange(next as YesNoAny)}
    />
  );
}

function FilterPanel({
  value,
  onChange,
  rentalMode,
}: {
  value: Filters;
  onChange: (value: Filters) => void;
  rentalMode: RentalMode;
}) {
  const update = <K extends keyof Filters>(key: K, next: Filters[K]) =>
    onChange({ ...value, [key]: next });
  const max = rentalMode === "holiday" ? 350 : 1200;
  return (
    <div className="filter-panel">
      <label className="field-label filter-room-only">
        Tipo de propiedad
        <select aria-label="Tipo de propiedad" value="Habitaciones" disabled>
          <option>Habitaciones</option>
        </select>
      </label>
      <section className="filter-section">
        <h3>Precio por {rentalMode === "holiday" ? "noche" : "mes"}</h3>
        <div className="filter-price-fields">
          <label>Desde<Input aria-label="Precio mínimo" type="number" min="0" max={max} step={rentalMode === "holiday" ? 5 : 25} value={value.minPrice} onChange={(event) => update("minPrice", Number(event.target.value))} /></label>
          <label>Hasta<Input aria-label="Precio máximo" type="number" min="0" max={max} step={rentalMode === "holiday" ? 5 : 25} value={value.maxPrice} onChange={(event) => update("maxPrice", Number(event.target.value))} /></label>
        </div>
        <div className="range-values">
          <span>{value.minPrice} €</span>
          <span>
            {value.maxPrice >= max ? `${max} €+` : `${value.maxPrice} €`}
          </span>
        </div>
        <Slider
          min={0}
          max={max}
          step={rentalMode === "holiday" ? 5 : 25}
          value={[Math.min(value.minPrice, max), Math.min(value.maxPrice, max)]}
          onValueChange={([min, nextMax]) =>
            onChange({ ...value, minPrice: min, maxPrice: nextMax })
          }
          aria-label="Rango de precio"
        />
      </section>
      <Separator />
      <fieldset className="filter-section">
        <legend>Zona</legend>
        <div className="checks-grid">
          {areas.map((area) => (
            <CheckOption
              key={area}
              label={area}
              checked={value.areas.includes(area)}
              onCheckedChange={(checked) =>
                update(
                  "areas",
                  checked
                    ? [...value.areas, area]
                    : value.areas.filter((item) => item !== area),
                )
              }
            />
          ))}
        </div>
      </fieldset>
      <Separator />
      <section className="filter-section">
        <h3>Habitación</h3>
        <NativeSelect
          label="Tipo"
          value={value.roomType}
          options={[
            "Cualquiera",
            "Habitación individual",
            "Habitación compartida",
            "Estudio",
          ]}
          onChange={(next) => update("roomType", next)}
        />
        <NativeSelect
          label="Requisito para la persona inquilina"
          value={value.tenantRequirement}
          options={[
            "Cualquiera",
            { value: "single-man", label: "Solo un hombre" },
            { value: "single-woman", label: "Solo una mujer" },
            { value: "single-person", label: "Una persona" },
            { value: "couple", label: "Solo pareja" },
            { value: "any", label: "Sin restricción" },
          ]}
          onChange={(next) => update("tenantRequirement", next as Filters["tenantRequirement"])}
        />
        <div className="form-grid form-grid--compact">
          <label className="field-label">
            Tamaño mínimo (m²)
            <Input type="number" min="0" max="50" value={value.roomSizeMin} onChange={(event) => update("roomSizeMin", Number(event.target.value))} />
          </label>
          <label className="field-label">
            Tamaño máximo (m²)
            <Input type="number" min="1" max="50" value={value.roomSizeMax} onChange={(event) => update("roomSizeMax", Number(event.target.value))} />
          </label>
        </div>
        <NativeSelect label="Capacidad de la habitación" value={value.roomCapacity} options={["Cualquiera", { value: "1", label: "1 persona" }, { value: "2", label: "2 personas" }]} onChange={(next) => update("roomCapacity", next)} />
      </section>
      <Separator />
      <section className="filter-section">
        <h3>Disponibilidad</h3>
        <label className="field-label">
          Disponible para esta fecha
          <Input
            type="date"
            value={value.available}
            onChange={(event) => update("available", event.target.value)}
          />
        </label>
        {rentalMode === "long" ? (
          <NativeSelect
            label="Estancia mínima aceptada"
            value={value.minStay}
            options={["Cualquiera", "1", "2", "3", "6"]}
            onChange={(next) => update("minStay", next)}
          />
        ) : (
          <>
            <label className="field-label">
              Estancia mínima: hasta (noches)
              <Input type="number" min="0" value={value.minimumNights} onChange={(event) => update("minimumNights", Number(event.target.value))} />
            </label>
            <label className="field-label">
              Disponible hasta al menos
              <Input type="date" value={value.availableUntil} onChange={(event) => update("availableUntil", event.target.value)} />
            </label>
          </>
        )}
        <NativeSelect
          label="Publicado"
          value={value.publicationDate}
          options={["Cualquiera", "24h", "7d", "30d"]}
          onChange={(next) => update("publicationDate", next)}
        />
      </section>
      <Separator />
      <fieldset className="filter-section">
        <legend>Condiciones destacadas</legend>
        <div className="checks-grid">
          {filterConditions.map((condition) => (
            <CheckOption
              key={condition}
              label={condition}
              checked={value.conditions.includes(condition)}
              onCheckedChange={(checked) =>
                update(
                  "conditions",
                  checked
                    ? [...value.conditions, condition]
                    : value.conditions.filter((item) => item !== condition),
                )
              }
            />
          ))}
        </div>
      </fieldset>
      <Separator />
      <section className="filter-section">
        <h3>Convivencia</h3>
        <YesNoFilter
          label="Se puede fumar"
          value={value.smoking}
          onChange={(next) => update("smoking", next)}
        />
        <YesNoFilter
          label="Mascotas"
          value={value.pets}
          onChange={(next) => update("pets", next)}
        />
        <YesNoFilter
          label="Niños"
          value={value.children}
          onChange={(next) => update("children", next)}
        />
        <YesNoFilter
          label="Empadronamiento"
          value={value.empadronamiento}
          onChange={(next) => update("empadronamiento", next)}
        />
      </section>
      <Separator />
      <section className="filter-section">
        <h3>Espacios y equipamiento</h3>
        <NativeSelect
          label="Baño"
          value={value.bathroom}
          options={["Cualquiera", "Baño privado", "Baño compartido"]}
          onChange={(next) => update("bathroom", next)}
        />
        <NativeSelect
          label="Ducha"
          value={value.shower}
          options={["Cualquiera", "Ducha privada", "Ducha compartida"]}
          onChange={(next) => update("shower", next)}
        />
        <NativeSelect
          label="Cocina"
          value={value.kitchen}
          options={["Cualquiera", "Cocina privada", "Cocina compartida"]}
          onChange={(next) => update("kitchen", next)}
        />
        <CheckOption
          label="Amueblada"
          checked={value.furnished}
          onCheckedChange={(checked) => update("furnished", checked)}
        />
        <CheckOption
          label="Gastos incluidos"
          checked={value.billsIncluded}
          onCheckedChange={(checked) => update("billsIncluded", checked)}
        />
        <div className="checks-grid">
          {amenityOptions.map((amenity) => (
            <CheckOption
              key={amenity}
              label={amenity}
              checked={value.amenities.includes(amenity)}
              onCheckedChange={(checked) =>
                update(
                  "amenities",
                  checked
                    ? [...value.amenities, amenity]
                    : value.amenities.filter((item) => item !== amenity),
                )
              }
            />
          ))}
        </div>
      </section>
      <Separator />
      <section className="filter-section">
        <h3>Fianza y vivienda</h3>
        <NativeSelect
          label="Depósito"
          value={value.deposit}
          options={["Cualquiera", "Sin fianza", "Hasta 1 mes", "Más de 1 mes"]}
          onChange={(next) => update("deposit", next)}
        />
        <NativeSelect
          label="Residentes actuales"
          value={value.currentResidents}
          options={["Cualquiera", "1", "2", "3", "4", { value: "5+", label: "5 o más" }]}
          onChange={(next) => update("currentResidents", next)}
        />
        <NativeSelect
          label="Tipo de anunciante"
          value={value.advertiserType}
          options={["Cualquiera", "Particular", "Profesional"]}
          onChange={(next) => update("advertiserType", next)}
        />
      </section>
    </div>
  );
}

export function FilterButton({
  resultCount,
  onFiltersChange,
  onRentalModeChange,
}: {
  resultCount: number;
  onFiltersChange?: (filters: Filters) => void;
  onRentalModeChange?: (mode: RentalMode) => void;
}) {
  const {
    filters,
    setFilters,
    activeFilterCount,
    rentalMode,
    allListings,
    discarded,
  } = useApp();
  const [draft, setDraft] = useState(filters);
  const [open, setOpen] = useState(false);
  const draftResultCount = useMemo(
    () =>
      filterListings(
        allListings.filter((item) => !discarded.has(item.id)),
        rentalMode,
        draft,
      ).length,
    [allListings, discarded, draft, rentalMode],
  );
  useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);
  const commit = onFiltersChange ?? setFilters;
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="outline"
          aria-label={`Todos los filtros. ${resultCount} habitaciones actuales`}
        >
          <SlidersHorizontal data-icon="inline-start" />
          Filtros
          {activeFilterCount ? (
            <span className="filter-count">{activeFilterCount}</span>
          ) : null}
        </Button>
      </SheetTrigger>
      <SheetContent className="filter-drawer" showCloseButton={false}>
        <SheetHeader>
          <SheetClose asChild><Button type="button" variant="ghost" size="icon" className="filter-drawer__back" aria-label="Cerrar filtros"><X /></Button></SheetClose>
          <SheetTitle>Filtros</SheetTitle>
          <SheetDescription>
            Ajusta las condiciones y revisa cuántas habitaciones coinciden.
          </SheetDescription>
        </SheetHeader>
        {onRentalModeChange ? <div className="filter-mode-switch"><span>Tipo de estancia</span><RentalTypeSwitch compact onChange={onRentalModeChange} /></div> : null}
        <FilterPanel
          value={draft}
          onChange={setDraft}
          rentalMode={rentalMode}
        />
        <SheetFooter className="filter-footer">
          <Button
            variant="ghost"
            onClick={() => {
              const cleared = { ...defaultFilters };
              setDraft(cleared);
            }}
          >
            Limpiar
          </Button>
          <Button
            onClick={() => {
              commit(draft);
              setOpen(false);
            }}
          >
            Mostrar {draftResultCount} habitaciones
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export function FilterSidebar({
  resultCount,
  onFiltersChange,
}: {
  resultCount: number;
  onFiltersChange?: (filters: Filters) => void;
}) {
  const {
    filters,
    setFilters,
    activeFilterCount,
    saveCurrentSearch,
    rentalMode,
  } = useApp();
  const commit = onFiltersChange ?? setFilters;
  return (
    <aside className="filter-sidebar" aria-label="Filtros de búsqueda">
      <div className="filter-sidebar__save">
        <Button className="w-full" onClick={saveCurrentSearch}>
          <Heart data-icon="inline-start" />
          Guardar búsqueda
        </Button>
        <p>Recibe avisos cuando haya habitaciones nuevas.</p>
      </div>
      <div className="filter-sidebar__head">
        <h2>Filtrar resultados</h2>
        {activeFilterCount ? (
          <button type="button" onClick={() => commit({ ...defaultFilters })}>
            Borrar ({activeFilterCount})
          </button>
        ) : null}
      </div>
      <FilterPanel value={filters} onChange={commit} rentalMode={rentalMode} />
      <div className="filter-sidebar__result" aria-live="polite">
        <strong>{resultCount}</strong> habitaciones
      </div>
    </aside>
  );
}

export function MapView(props: {
  items: Listing[];
  selectedId?: string;
  onSelect: (id: string) => void;
  fullScreen?: boolean;
  showPreview?: boolean;
  onBoundsSearch?: (bounds: import("@/components/map-view").MapBounds) => void;
  onPolygonSearch?: (polygon: MapPolygonPoint[]) => void;
  fitResultsKey?: number;
  initialAction?: 'draw' | 'near' | null;
}) {
  return (
    <Suspense
      fallback={
        <div className="map-loading map-loading--standalone" role="status">
          <span aria-hidden="true" />
          <strong>Cargando mapa OpenStreetMap</strong>
        </div>
      }
    >
      <LazyLeafletMap {...props} />
    </Suspense>
  );
}

export function PropertyGallery({ listing }: { listing: Listing }) {
  const [index, setIndex] = useState(0);
  const [open, setOpen] = useState(false);
  const next = () => setIndex((value) => (value + 1) % listing.images.length);
  const previous = () =>
    setIndex(
      (value) => (value - 1 + listing.images.length) % listing.images.length,
    );
  return (
    <>
      <section
        className="property-gallery"
        aria-label={`Galería de ${listing.title}`}
        onKeyDown={(event) => {
          if (event.key === "ArrowRight") next();
          if (event.key === "ArrowLeft") previous();
        }}
        tabIndex={0}
      >
        <div className="gallery-main">
          <MediaImage
            src={listing.images[index] || fallbackImage}
            onError={imageFallback}
            alt={`Habitación en ${listing.area}, foto ${index + 1} de ${listing.images.length}`}
            width="1200"
            height="800"
          />
          {index === 0 ? <CriticalRestrictionOverlay listing={listing} /> : null}
          <button
            type="button"
            className="gallery-prev"
            onClick={previous}
            aria-label="Foto anterior"
          >
            <ChevronLeft />
          </button>
          <button
            type="button"
            className="gallery-next"
            onClick={next}
            aria-label="Foto siguiente"
          >
            <ChevronRight />
          </button>
          <span>
            {index + 1}/{listing.images.length}
          </span>
        </div>
        <div className="gallery-thumbs">
          {listing.images.slice(1, 5).map((image, thumbIndex) => (
            <button
              key={`${image}-${thumbIndex}`}
              type="button"
              onClick={() =>
                thumbIndex === 3 ? setOpen(true) : setIndex(thumbIndex + 1)
              }
              aria-label={
                thumbIndex === 3
                  ? "Ver todas las fotos"
                  : `Ver foto ${thumbIndex + 2}`
              }
            >
              <MediaImage
                src={image}
                onError={imageFallback}
                alt=""
                width="400"
                height="280"
              />
              {thumbIndex === 3 ? (
                <span>
                  <Expand />
                  Ver todas
                </span>
              ) : null}
            </button>
          ))}
        </div>
        <Button
          className="gallery-all-button"
          variant="outline"
          onClick={() => setOpen(true)}
        >
          <Expand data-icon="inline-start" />
          Ver todas las fotos ({listing.images.length})
        </Button>
      </section>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="gallery-dialog">
          <DialogHeader>
            <DialogTitle>Todas las fotos</DialogTitle>
            <DialogDescription>
              {listing.title} · {listing.images.length} imágenes
            </DialogDescription>
          </DialogHeader>
          <div className="gallery-dialog__grid">
            {listing.images.map((image, imageIndex) => (
              <button
                type="button"
                key={`${image}-${imageIndex}`}
                onClick={() => {
                  setIndex(imageIndex);
                  setOpen(false);
                }}
                aria-label={`Abrir foto ${imageIndex + 1}`}
              >
                <MediaImage
                  src={image}
                  onError={imageFallback}
                  alt={`Habitación en ${listing.area}, foto ${imageIndex + 1}`}
                  width="720"
                  height="480"
                  loading="lazy"
                />
              </button>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

const contactSubmissions = new Map<string, { time: number; signature: string }>();

export function ContactPanel({
  listing,
  mobile = false,
}: {
  listing: Listing;
  mobile?: boolean;
}) {
  const { addLocalMessage } = useApp();
  const [confirmed, setConfirmed] = useState(false);
  const [phone, setPhone] = useState(false);
  const [messageOpen, setMessageOpen] = useState(false);
  const [messageSending, setMessageSending] = useState(false);
  const [messageStatus, setMessageStatus] = useState("");
  const [messageErrors, setMessageErrors] = useState<Record<string, string>>({});
  const [messageForm, setMessageForm] = useState({ name: "", contact: "", message: "", website: "", confirmed: false });
  const messageStartedAt = useRef(Date.now());
  const messageFormRef = useRef<HTMLFormElement>(null);
  const messageTimerRef = useRef<number | null>(null);
  const checkboxId = useId();
  const confirmationText = buildContactConfirmationText(listing);
  useEffect(() => {
    setConfirmed(false);
    setPhone(false);
    setMessageOpen(false);
    setMessageStatus("");
  }, [listing.id]);
  useEffect(() => () => {
    if (messageTimerRef.current !== null) window.clearTimeout(messageTimerRef.current);
  }, []);
  const contactText = encodeURIComponent(
    `Hola, me interesa la habitación de ${listing.area}. ¿Sigue disponible?`,
  );
  const updateMessage = (key: keyof typeof messageForm, value: string | boolean) => setMessageForm((current) => ({ ...current, [key]: value }));
  const submitMessage = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const next: Record<string, string> = {};
    if (messageForm.website) next.form = "No se pudo enviar este formulario.";
    if (Date.now() - messageStartedAt.current < 700) next.form = "Revisa los datos antes de enviar.";
    if (messageForm.name.trim().length < 2) next.name = "Escribe al menos 2 caracteres.";
    if (!messageForm.contact.trim()) next.contact = "Indica un email o teléfono.";
    if (messageForm.message.trim().length < 10) next.message = "Escribe al menos 10 caracteres.";
    if (messageForm.message.length > 1000) next.message = "El mensaje no puede superar 1000 caracteres.";
    if (!messageForm.confirmed) next.confirmed = "Confirma las condiciones del anuncio.";
    const contactIdentity = messageForm.contact.trim().toLocaleLowerCase();
    const signature = messageForm.message.trim().toLocaleLowerCase();
    const contactKey = `${listing.id}:${contactIdentity}`;
    const previous = contactSubmissions.get(contactKey);
    if (previous && Date.now() - previous.time < 30_000) next.form = previous.signature === signature ? "Este mismo mensaje ya se ha registrado. Espera 30 segundos." : "Espera 30 segundos antes de enviar otro mensaje.";
    setMessageErrors(next);
    if (Object.keys(next).length) {
      setMessageStatus("Corrige los campos indicados.");
      requestAnimationFrame(() => (messageFormRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]') ?? messageFormRef.current?.querySelector<HTMLElement>('input:not([name="website"])'))?.focus());
      return;
    }
    contactSubmissions.set(contactKey, { time: Date.now(), signature });
    addLocalMessage({
      listingId: listing.id,
      listingTitle: listing.title,
      imageRef: listing.images[0] ?? '',
      contactName: messageForm.name.trim(),
      messagePreview: messageForm.message.trim().slice(0, 160),
    });
    setMessageSending(true);
    setMessageStatus("Registrando el mensaje local…");
    messageTimerRef.current = window.setTimeout(() => {
      setMessageSending(false);
      setMessageStatus("Mensaje guardado solo en esta demo local. No se ha enviado por internet.");
      setMessageForm((current) => ({ ...current, message: "", website: "", confirmed: false }));
      messageTimerRef.current = null;
    }, 250);
  };
  return (
    <aside
      id="contacto"
      className={cn("contact-panel", mobile && "contact-panel--mobile")}
      aria-label="Contactar con el anunciante"
    >
      {mobile ? null : (
        <>
          <PriceBlock listing={listing} large />
          <p>
            {listing.bills} · {listing.deposit}
          </p>
          <Separator />
          <div className="owner-row">
            <Avatar>
              <AvatarFallback>{listing.owner.initials}</AvatarFallback>
            </Avatar>
            <div>
              <strong>{listing.owner.name}</strong>
              <span>{listing.owner.response}</span>
            </div>
            {listing.owner.verified ? (
              <ShieldCheck aria-label="Identidad verificada" />
            ) : null}
          </div>
        </>
      )}
      <label className="condition-confirm" htmlFor={checkboxId}>
        <Checkbox
          id={checkboxId}
          checked={confirmed}
          onCheckedChange={(value) => setConfirmed(value === true)}
        />
        <span>{confirmationText}</span>
      </label>
      <div className="contact-actions">
        {listing.showWhatsApp ? <Button asChild={confirmed} disabled={!confirmed}>
          {confirmed ? (
            <a
              href={`https://wa.me/${(listing.contactWhatsapp || "34600112233").replace(/\D/g, "")}?text=${contactText}`}
              target="_blank"
              rel="noreferrer"
            >
              <MessageCircle data-icon="inline-start" />
              WhatsApp
            </a>
          ) : (
            <>
              <MessageCircle data-icon="inline-start" />
              WhatsApp
            </>
          )}
        </Button> : null}
        {listing.showPhone ? (
          <Button
            variant="outline"
            disabled={!confirmed && !mobile}
            onClick={() => setPhone(true)}
          >
            <Phone data-icon="inline-start" />
            {phone
              ? listing.contactPhone || "+34 600 112 233"
              : mobile ? "Llamar" : "Mostrar teléfono"}
          </Button>
        ) : null}
        {listing.allowContactForm ? <Dialog open={messageOpen} onOpenChange={(open) => {
          setMessageOpen(open);
          if (open) messageStartedAt.current = Date.now();
          else {
            if (messageTimerRef.current !== null) window.clearTimeout(messageTimerRef.current);
            messageTimerRef.current = null;
            setMessageSending(false);
            setMessageErrors({});
            setMessageStatus("");
            setMessageForm({ name: "", contact: "", message: "", website: "", confirmed: false });
          }
        }}>
          <DialogTrigger asChild><Button variant="outline" aria-label="Enviar mensaje"><MessageCircle data-icon="inline-start" />{mobile ? "Chat" : "Enviar mensaje"}</Button></DialogTrigger>
          <DialogContent className="contact-message-dialog">
            <DialogHeader>
              <DialogTitle>Enviar un mensaje local</DialogTitle>
              <DialogDescription>La demo valida y guarda el envío en esta sesión, pero no lo entrega por internet.</DialogDescription>
            </DialogHeader>
            <form ref={messageFormRef} className="contact-message-form" onSubmit={submitMessage} noValidate>
              <label className="field-label">Nombre
                <Input name="name" autoComplete="name" value={messageForm.name} aria-invalid={Boolean(messageErrors.name)} aria-describedby={messageErrors.name ? "contact-name-error" : undefined} onChange={(event) => updateMessage("name", event.target.value)} />
                {messageErrors.name ? <span id="contact-name-error" className="field-error">{messageErrors.name}</span> : null}
              </label>
              <label className="field-label">Email o teléfono
                <Input name="contact" autoComplete="email" value={messageForm.contact} aria-invalid={Boolean(messageErrors.contact)} aria-describedby={messageErrors.contact ? "contact-detail-error" : undefined} onChange={(event) => updateMessage("contact", event.target.value)} />
                {messageErrors.contact ? <span id="contact-detail-error" className="field-error">{messageErrors.contact}</span> : null}
              </label>
              <label className="field-label">Mensaje
                <Textarea minLength={10} maxLength={1000} rows={5} value={messageForm.message} aria-invalid={Boolean(messageErrors.message)} aria-describedby={messageErrors.message ? "contact-message-error" : undefined} onChange={(event) => updateMessage("message", event.target.value)} />
                {messageErrors.message ? <span id="contact-message-error" className="field-error">{messageErrors.message}</span> : <span className="field-hint">{messageForm.message.length}/1000</span>}
              </label>
              <label className="honeypot-field">Sitio web<Input name="website" tabIndex={-1} autoComplete="url" value={messageForm.website} onChange={(event) => updateMessage("website", event.target.value)} /></label>
              <label className="condition-confirm">
                <Checkbox checked={messageForm.confirmed} aria-invalid={Boolean(messageErrors.confirmed)} aria-describedby={messageErrors.confirmed ? "contact-confirm-error" : undefined} onCheckedChange={(value) => updateMessage("confirmed", value === true)} />
                <span>{confirmationText}</span>
              </label>
              {messageErrors.confirmed ? <span id="contact-confirm-error" className="field-error">{messageErrors.confirmed}</span> : null}
              {(messageErrors.form || messageStatus) ? <div className="contact-message-status" role={messageErrors.form || Object.keys(messageErrors).length ? "alert" : "status"} aria-live="polite">{messageErrors.form || messageStatus}</div> : null}
              <DialogFooter><Button type="submit" disabled={messageSending}>{messageSending ? "Registrando…" : "Registrar mensaje"}</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog> : null}
      </div>
    </aside>
  );
}

export function ReportDialog({ listing, open: controlledOpen, onOpenChange, trigger }: { listing: Listing; open?: boolean; onOpenChange?: (open: boolean) => void; trigger?: ReactNode | false }) {
  const { addReport } = useApp();
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlledOpen ?? internalOpen;
  const setOpen = (next: boolean) => { setInternalOpen(next); onOpenChange?.(next); };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger === false ? null : <DialogTrigger asChild>
        {trigger ?? <Button variant="ghost" className="report-trigger">
          <CircleAlert data-icon="inline-start" />
          Denunciar anuncio
        </Button>}
      </DialogTrigger>}
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Denunciar este anuncio</DialogTitle>
          <DialogDescription>
            Revisaremos «{listing.title}». No compartiremos tu identidad con el
            anunciante.
          </DialogDescription>
        </DialogHeader>
        <fieldset className="report-options">
          <legend>Motivo</legend>
          {[
            "El anuncio ya no está disponible",
            "Datos incorrectos",
            "Posible fraude",
            "Contenido prohibido",
            "Contenido discriminatorio",
            "Otro motivo",
          ].map((item) => (
            <label key={item}>
              <input
                type="radio"
                name="report"
                value={item}
                checked={reason === item}
                onChange={(event) => setReason(event.target.value)}
              />
              {item}
            </label>
          ))}
        </fieldset>
        <label className="field-label">
          Comentario opcional
          <Textarea
            rows={3}
            value={comment}
            onChange={(event) => setComment(event.target.value)}
          />
        </label>
        <DialogFooter>
          <Button
            disabled={!reason}
            onClick={() => {
              addReport(listing.id, reason, comment);
              setOpen(false);
              toast.success("Denuncia enviada");
            }}
          >
            Enviar denuncia
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function Pagination({
  page,
  totalPages,
  onPage,
}: {
  page: number;
  totalPages: number;
  onPage: (page: number) => void;
}) {
  const pages = Array.from({ length: totalPages }, (_, index) => index + 1);
  return (
    <nav className="pagination" aria-label="Paginación">
      <Button
        variant="outline"
        size="icon"
        disabled={page === 1}
        onClick={() => onPage(page - 1)}
        aria-label="Página anterior"
      >
        <ChevronLeft />
      </Button>
      {pages.map((item) => (
        <Button
          key={item}
          variant={page === item ? "default" : "outline"}
          size="icon"
          onClick={() => onPage(item)}
          aria-current={page === item ? "page" : undefined}
        >
          {item}
        </Button>
      ))}
      <Button
        variant="outline"
        size="icon"
        disabled={page === totalPages}
        onClick={() => onPage(page + 1)}
        aria-label="Página siguiente"
      >
        <ChevronRight />
      </Button>
    </nav>
  );
}

export function getFilteredListings(mode: RentalMode, filters: Filters) {
  return filterListings(initialListings, mode, filters);
}
export function QuickFilters({
  resultCount,
  onFiltersChange,
}: {
  resultCount: number;
  onFiltersChange?: (filters: Filters) => void;
}) {
  const { filters, setFilters, activeFilterCount } = useApp();
  const commit = onFiltersChange ?? setFilters;
  const chips = [
    {
      label: "Hasta 500 €",
      active: filters.maxPrice === 500,
      apply: () =>
        commit({
          ...filters,
          maxPrice: filters.maxPrice === 500 ? defaultFilters.maxPrice : 500,
        }),
    },
    {
      label: "Gastos incluidos",
      active: filters.billsIncluded,
      apply: () =>
        commit({ ...filters, billsIncluded: !filters.billsIncluded }),
    },
    {
      label: "Baño privado",
      active: filters.bathroom === "Baño privado",
      apply: () =>
        commit({
          ...filters,
          bathroom:
            filters.bathroom === "Baño privado" ? "Cualquiera" : "Baño privado",
        }),
    },
    {
      label: "Empadronamiento",
      active: filters.empadronamiento === "Sí",
      apply: () =>
        commit({
          ...filters,
          empadronamiento:
            filters.empadronamiento === "Sí" ? "Cualquiera" : "Sí",
        }),
    },
  ];
  return (
    <div className="quick-filters" aria-label="Filtros rápidos">
      {chips.map((chip) => (
        <Button
          key={chip.label}
          variant={chip.active ? "default" : "outline"}
          aria-pressed={chip.active}
          onClick={chip.apply}
        >
          {chip.label}
        </Button>
      ))}
      <FilterButton resultCount={resultCount} onFiltersChange={commit} />
      {activeFilterCount ? (
        <span className="active-filter-note" aria-live="polite">
          {activeFilterCount} activos
        </span>
      ) : null}
    </div>
  );
}
export function FeatureIcon({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof Home;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="feature-icon">
      <div>
        <Icon aria-hidden="true" />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
export const featureIcons = { Home, ShieldCheck, Sparkles, Bath, UsersRound };
