import { OwnerAddressForm } from '@/components/owner-address';
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  ArrowLeft,
  Bell,
  BellOff,
  CalendarClock,
  Clock3,
  Edit3,
  Frown,
  Home,
  Rocket,
  Smile,
  Eye,
  EyeOff,
  LogOut,
  MapPin,
  MoreHorizontal,
  Plus,
  RotateCcw,
  Save,
  Search,
  Trash2,
  UserRound,
} from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { currentLocale } from "@/lib/i18n-locale";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmDialog, FormField, StatusBadge } from "@/components/forms";
import { EmptyState, PropertyCard } from "@/components/marketplace";
import { useApp } from "@/contexts/app-context";
import { useAppBack } from "@/hooks/use-app-back";
import { useFavoriteListings } from "@/hooks/use-favorite-listings";
import { useI18n } from "@/contexts/i18n-context";
import { filtersToParams } from "@/lib/search";
import { getCriticalRestrictions, getPrimaryCadence, getPrimaryPrice } from "@/lib/listings";
import { MediaImage, useMediaUrl } from "@/components/media-image";
import { MediaStorageError, removeMedia, saveMediaFile } from "@/lib/media-storage";
import { api } from "@/api/client";
import type { DemoUser } from "@/types";
import { OwnerHomepagePurchase } from "@/components/owner-homepage-purchase";
import { PromotionPeriod, promotionDate, addPromotionDays, promotionDays } from "@/components/promotion-period";
import { ProvinceTopAvailability, useProvinceTopAvailability } from "@/components/province-top-availability";

type TopPaymentStatus = { orderStatus: string | null; fulfillmentStatus: string | null; endsAt: string | null };

function AccountHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="account-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}

export function FavoritesPage() {
  const { toggleFavorite } = useApp();
  const { listings: saved } = useFavoriteListings();
  return (
    <div className="container account-page">
      <AccountHeader
        eyebrow="Tu selección"
        title="Favoritos"
        description={`${saved.length} habitaciones guardadas`}
        action={
          <Button asChild variant="outline">
            <Link to="/buscar">Seguir buscando</Link>
          </Button>
        }
      />
      {saved.length ? (
        <div className="property-grid">
          {saved.map((listing) => (
            <div className="favorite-card" key={listing.id}>
              <PropertyCard listing={listing} compact />
              <Button className="favorite-card__remove" variant="outline" onClick={() => toggleFavorite(listing.id)} aria-label={`Eliminar ${listing.title} de favoritos`}>
                <Trash2 data-icon="inline-start" />
                Eliminar de favoritos
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState favorites />
      )}
    </div>
  );
}

export function SavedSearchesPage() {
  const {
    savedSearches,
    removeSavedSearch,
    toggleSearchAlerts,
    restoreSavedSearch,
    searchHistory,
    clearSearchHistory,
    setQuery,
  } = useApp();
  return (
    <div className="container account-page saved-searches-page">
      <AccountHeader
        eyebrow="Tu búsqueda"
        title="Búsquedas guardadas"
        description="Recibe avisos sin repetir los mismos filtros."
        action={
          <Button asChild>
            <Link to="/buscar">
              <Search data-icon="inline-start" />
              Nueva búsqueda
            </Link>
          </Button>
        }
      />
      <div className="saved-searches-layout">
        <section aria-labelledby="saved-searches-title">
          <div className="account-section-head">
            <h2 id="saved-searches-title">Alertas</h2>
            <span>{savedSearches.length} guardadas</span>
          </div>
          {savedSearches.length ? (
            <div className="saved-search-list">
              {savedSearches.map((item) => {
                const params = filtersToParams(
                  item.filters,
                  new URLSearchParams({
                    q: item.query,
                    alquiler: item.rentalMode,
                    ...(item.provinceCode ? { provincia: item.provinceCode } : { ubicacion: "ciudad" }),
                  }),
                );
                return (
                  <article key={item.id} className="saved-search-card">
                    <div className="saved-search-card__icon">
                      <MapPin />
                    </div>
                    <div>
                      <h3>Habitaciones en {item.query}</h3>
                      <p>
                        {item.rentalMode === "long"
                          ? "Larga estancia"
                          : "Vacacional"}{" "}
                        · {item.filters.minPrice}–{item.filters.maxPrice} €
                      </p>
                      <span>
                        {item.filters.conditions.join(" · ") ||
                          "Sin condiciones adicionales"}
                      </span>
                    </div>
                    <div className="saved-search-card__actions">
                      <Button asChild size="sm">
                        <Link
                          to={`/buscar?${params.toString()}`}
                          onClick={() => restoreSavedSearch(item.id)}
                        >
                          Ver resultados
                        </Link>
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => toggleSearchAlerts(item.id)}
                        aria-label={`${item.alerts ? "Desactivar" : "Activar"} avisos para ${item.query}`}
                      >
                        {item.alerts ? <Bell /> : <BellOff />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeSavedSearch(item.id)}
                        aria-label={`Eliminar búsqueda en ${item.query}`}
                      >
                        <Trash2 />
                      </Button>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <div className="account-empty">
              <Bell />
              <h2>Aún no tienes alertas</h2>
              <p>Guarda una búsqueda desde los resultados.</p>
              <Button asChild>
                <Link to="/buscar">Buscar habitaciones</Link>
              </Button>
            </div>
          )}
        </section>
        <aside
          className="recent-searches"
          aria-labelledby="recent-searches-title"
        >
          <div className="account-section-head">
            <h2 id="recent-searches-title">Búsquedas recientes</h2>
            {searchHistory.length ? (
              <button type="button" onClick={clearSearchHistory}>
                Borrar
              </button>
            ) : null}
          </div>
          {searchHistory.length ? (
            <nav>
              {searchHistory.map((item) => (
                <Link
                  key={item}
                  to={`/buscar?q=${encodeURIComponent(item)}`}
                  onClick={() => setQuery(item)}
                >
                  <Clock3 />
                  <span>{item}</span>
                </Link>
              ))}
            </nav>
          ) : (
            <p>Tus últimas zonas aparecerán aquí.</p>
          )}
        </aside>
      </div>
    </div>
  );
}

export function ProfilePage() {
  const { currentUser, updateProfile, logout, deleteAccount } = useApp();
  const navigate = useNavigate();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<DemoUser | null>(currentUser);
  const avatarUrl = useMediaUrl(draft?.avatarRef, 'thumb');
  useEffect(() => { if (!editing) setDraft(currentUser); }, [currentUser, editing]);
  if (!currentUser) return null;
  const profileDraft = draft ?? currentUser;
  const updateDraft = <K extends keyof DemoUser>(key: K, value: DemoUser[K]) => setDraft((current) => ({ ...(current ?? currentUser), [key]: value }));
  const cancelEditing = () => {
    if (draft?.avatarRef && draft.avatarRef !== currentUser.avatarRef) {
      void removeMedia(draft.avatarRef).catch(() => toast.error("No se pudo limpiar el avatar temporal."));
    }
    setDraft(currentUser);
    setEditing(false);
  };
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const name = profileDraft.name.trim();
    const phone = profileDraft.phone.trim();
    const focusField = (field: string) => {
      const control = form.elements.namedItem(field);
      if (control instanceof HTMLElement) control.focus();
    };
    if (name.length < 2) {
      toast.error("El nombre debe tener al menos 2 caracteres.");
      focusField("name");
      return;
    }
    if (phone && !/^\+?[\d\s-]{7,}$/.test(phone)) {
      toast.error("Introduce un teléfono válido.");
      focusField("phone");
      return;
    }
    updateProfile({
      name,
      phone,
      whatsapp: profileDraft.whatsapp,
      telegram: profileDraft.telegram,
      about: profileDraft.about,
      showPhone: profileDraft.showPhone,
      showWhatsApp: profileDraft.showWhatsApp,
      avatarRef: profileDraft.avatarRef,
    });
    setEditing(false);
  };
  return (
    <div className="container account-page">
      <AccountHeader
        eyebrow="Tu cuenta"
        title="Perfil"
        description="Controla tus datos públicos y preferencias."
        action={
          <Button
            variant={editing ? "outline" : "default"}
            onClick={() => {
              if (editing) cancelEditing();
              else { setDraft(currentUser); setEditing(true); }
            }}
          >
            <Edit3 data-icon="inline-start" />
            {editing ? "Cancelar" : "Editar perfil"}
          </Button>
        }
      />
      {currentUser.role === "host" || currentUser.role === "admin" ? <OwnerAddressForm /> : null}
      <div className="profile-layout">
        <aside className="profile-card">
          <Avatar className="profile-avatar">
            {avatarUrl ? <AvatarImage src={avatarUrl} alt={`Foto de ${profileDraft.name}`} /> : null}
            <AvatarFallback>{currentUser.initials}</AvatarFallback>
          </Avatar>
          <h2>{profileDraft.name}</h2>
          <p>
            {currentUser.role === "host"
              ? "Anunciante"
              : currentUser.role === "admin"
                ? "Administración"
                : "Busca habitación"}
          </p>
          <span className="profile-verified">Cuenta demo verificada</span>
          {editing ? <div className="avatar-actions">
            <label className="button-like" htmlFor="profile-avatar-upload">Cambiar foto</label>
            <input id="profile-avatar-upload" className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              void saveMediaFile(file).then((avatarRef) => {
                const transientAvatar = profileDraft.avatarRef;
                if (transientAvatar && transientAvatar !== currentUser.avatarRef) {
                  void removeMedia(transientAvatar).catch(() => toast.error("No se pudo limpiar el avatar temporal."));
                }
                updateDraft("avatarRef", avatarRef);
              }).catch((error) => toast.error(error instanceof MediaStorageError ? error.message : "No se pudo guardar el avatar."));
            }} />
            {profileDraft.avatarRef ? <Button type="button" variant="ghost" size="sm" onClick={() => {
              const avatarReference = profileDraft.avatarRef;
              if (avatarReference && avatarReference !== currentUser.avatarRef) {
                void removeMedia(avatarReference).catch(() => toast.error("No se pudo limpiar el avatar temporal."));
              }
              updateDraft("avatarRef", undefined);
            }}>Eliminar foto</Button> : null}
          </div> : null}
        </aside>
        <form className="profile-form" onSubmit={submit}>
          <div className="form-grid">
            <FormField label="Nombre" htmlFor="profile-name">
              <Input
                id="profile-name"
                name="name"
                value={profileDraft.name}
                onChange={(event) => updateDraft("name", event.target.value)}
                disabled={!editing}
              />
            </FormField>
            <FormField label="Email" htmlFor="profile-email">
              <Input id="profile-email" value={currentUser.email} disabled />
            </FormField>
            <FormField label="Teléfono" htmlFor="profile-phone">
              <Input
                id="profile-phone"
                name="phone"
                value={profileDraft.phone}
                onChange={(event) => updateDraft("phone", event.target.value)}
                disabled={!editing}
              />
            </FormField>
            <FormField label="WhatsApp" htmlFor="profile-whatsapp">
              <Input
                id="profile-whatsapp"
                name="whatsapp"
                value={profileDraft.whatsapp}
                onChange={(event) => updateDraft("whatsapp", event.target.value)}
                disabled={!editing}
              />
            </FormField>
            <FormField label="Telegram" htmlFor="profile-telegram">
              <Input
                id="profile-telegram"
                name="telegram"
                value={profileDraft.telegram}
                onChange={(event) => updateDraft("telegram", event.target.value)}
                disabled={!editing}
              />
            </FormField>
          </div>
          <FormField label="Sobre mí" htmlFor="profile-about">
            <Textarea
              id="profile-about"
              name="about"
              value={profileDraft.about}
              onChange={(event) => updateDraft("about", event.target.value)}
              disabled={!editing}
              rows={4}
            />
          </FormField>
          <fieldset className="privacy-settings">
            <legend>Privacidad de contacto</legend>
            <label>
              <div>
                <strong>Mostrar teléfono a anunciantes</strong>
                <span>Solo después de iniciar contacto</span>
              </div>
              <Switch
                checked={profileDraft.showPhone}
                onCheckedChange={(value) => updateDraft("showPhone", value)}
                disabled={!editing}
              />
            </label>
            <label>
              <div>
                <strong>Permitir WhatsApp</strong>
                <span>Se muestra solo tras confirmar las condiciones</span>
              </div>
              <Switch
                checked={profileDraft.showWhatsApp}
                onCheckedChange={(value) => updateDraft("showWhatsApp", value)}
                disabled={!editing}
              />
            </label>
          </fieldset>
          {editing ? (
            <Button type="submit">
              <Save data-icon="inline-start" />
              Guardar cambios
            </Button>
          ) : null}
          <div className="danger-zone">
            <h2>Cuenta</h2>
            <Button
              variant="outline"
              onClick={() => {
                logout();
                navigate("/acceso");
              }}
            >
              <LogOut data-icon="inline-start" />
              Cerrar sesión
            </Button>
            <ConfirmDialog
              trigger={
                <Button variant="destructive">
                  <Trash2 data-icon="inline-start" />
                  Eliminar cuenta
                </Button>
              }
              title="¿Eliminar tu cuenta?"
              description="Se eliminarán esta cuenta local, su sesión, anuncios, borrador, búsquedas, favoritos, historial, comentarios y archivos multimedia sin uso. Esta acción no se puede deshacer."
              confirmLabel="Eliminar definitivamente"
              destructive
              onConfirm={async () => {
                const deleted = await deleteAccount();
                if (deleted) navigate("/acceso");
              }}
            />
          </div>
        </form>
      </div>
    </div>
  );
}

/** Fixed vector asset for both TOP states; no platform-dependent emoji artwork. */
function OwnerTopRocket({ active }: { active: boolean }) {
  return (
    <svg
      className={`owner-top-rocket ${active ? "is-launched" : "is-grounded"}`}
      data-top-rocket-active={active ? "true" : "false"}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M15 31 9 39l1-8-5 1 9-13 8 2" fill={active ? "#b8efd0" : "#ffe9ed"} stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M27 29 31 40l-7-4-5 8-2-13" fill={active ? "#88d8a6" : "#ffe9ed"} stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M17 31c-1-7 2-15 10-22 5-4 10-6 16-6 1 8-2 15-7 21-6 7-13 10-19 7Z" fill={active ? "#e8fff3" : "#fff3f5"} stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M30 7 40 17" stroke="currentColor" strokeWidth="2.3" />
      <circle cx="30" cy="18" r="4" fill={active ? "#68c7e4" : "#ffced8"} stroke="currentColor" strokeWidth="2.2" />
      <path d="m17 31-7 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
      {active ? (
        <>
          <path d="M11 34c-5 1-7 6-8 11 5-1 10-3 12-8l-4-3Z" fill="#ffbf39" stroke="#ce7223" strokeWidth="1.5" strokeLinejoin="round" />
          <path d="m12 38-4 4" stroke="#ff6a21" strokeWidth="2" strokeLinecap="round" />
        </>
      ) : null}
    </svg>
  );
}

function formatOwnerPromotionEnd(value: string, locale: string, language: string) {
  const inclusiveEnd = new Date(value);
  if (Number.isNaN(inclusiveEnd.getTime())) return "";
  if (inclusiveEnd.getHours() === 0 && inclusiveEnd.getMinutes() === 0 && inclusiveEnd.getSeconds() === 0) {
    inclusiveEnd.setDate(inclusiveEnd.getDate() - 1);
  }
  const formatted = new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(inclusiveEnd);
  return language === "ru" ? `${formatted} г.` : formatted;
}

export function MyListingsPage() {
  const goBack = useAppBack('/menu');
  const [searchParams] = useSearchParams();
  const { t, language, locale } = useI18n();
  const { ownedListings, deleteListing, setListingStatus, renewListing, closeListing, currentUser, refreshOwnedListings } = useApp();
  const [status, setStatus] = useState("Todos");
  const [topDialogOpen, setTopDialogOpen] = useState(false);
  const [promotionStep, setPromotionStep] = useState<"choose" | "duration" | "payment">("choose");
  const [homepageCandidateId, setHomepageCandidateId] = useState("");
  const [topCandidateId, setTopCandidateId] = useState("");
  const [topStartDate, setTopStartDate] = useState(() => promotionDate());
  const [topEndDate, setTopEndDate] = useState(() => addPromotionDays(promotionDate(), 10));
  const topDays = promotionDays(topStartDate, topEndDate);
  const validTopDays = Number.isInteger(topDays) && topDays >= 10 && topDays <= 365;
  const provinceTop = useProvinceTopAvailability(topCandidateId, topDays, topDialogOpen && promotionStep !== "choose");
  const [topPaymentStatus, setTopPaymentStatus] = useState<TopPaymentStatus | null>(null);
  const [topPaymentBusy, setTopPaymentBusy] = useState(false);
  const [topPaymentError, setTopPaymentError] = useState("");
  const returnedTopId = searchParams.get("top");
  const returnedPayment = searchParams.get("payment");
  useEffect(() => {
    if (!returnedTopId) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let attempts = 0;
    const poll = async () => {
      try {
        const result = await api<TopPaymentStatus>(`/payments/listings/${returnedTopId}/top/status`);
        if (!active) return;
        setTopPaymentStatus(result);
        if (result.fulfillmentStatus === "fulfilled") {
          await refreshOwnedListings();
          window.dispatchEvent(new Event("catalog:refresh"));
        } else if (result.orderStatus === "pending" && ++attempts < 60) {
          timer = setTimeout(() => void poll(), 3000);
        }
      } catch (error) {
        if (active) {
          setTopPaymentError((error as Error).message);
          if (++attempts < 60) timer = setTimeout(() => void poll(), 3000);
        }
      }
    };
    const initialize = async () => {
      if (returnedPayment === "cancelled") {
        try { await api(`/payments/listings/${returnedTopId}/top/checkout/cancel`, { method: "POST" }); }
        catch (error) { if (active) setTopPaymentError((error as Error).message); }
      }
      await poll();
    };
    void initialize();
    return () => { active = false; clearTimeout(timer); };
  }, [returnedTopId, returnedPayment, refreshOwnedListings]);
  const mine = ownedListings.filter((listing) => listing.ownerUserId === currentUser?.id);
  const promotable = mine.filter((listing) => listing.status === "Publicado" && !listing.isExternal);
  const items =
    status === "Todos"
      ? mine
      : mine.filter((listing) => listing.status === status);
  const openTopFlow = (listingId?: string) => {
    const candidate = listingId
      ? promotable.find((listing) => listing.id === listingId)
      : undefined;
    if (!promotable.length) return;
    setTopCandidateId(candidate?.id ?? "");
    const currentEnd = candidate?.promotionEndsAt ? new Date(candidate.promotionEndsAt) : null;
    const startDate = promotionDate(currentEnd && currentEnd.getTime() > Date.now() ? currentEnd : new Date());
    setTopStartDate(startDate);
    setTopEndDate(addPromotionDays(startDate, 10));
    setPromotionStep("choose");
    setTopPaymentError("");
    setTopDialogOpen(true);
  };
  const payForTop = async () => {
    if (!topCandidateId || !validTopDays || !provinceTop.canBuy) return;
    setTopPaymentBusy(true);
    setTopPaymentError("");
    try {
      const checkout = await api<{ url: string }>(`/payments/listings/${topCandidateId}/top/checkout`, {
        method: "POST", body: JSON.stringify({ days: Number(topDays) }),
      });
      window.location.assign(checkout.url);
    } catch (error) {
      setTopPaymentError((error as Error).message);
      provinceTop.refresh();
      setTopPaymentBusy(false);
    }
  };
  const cancelTopPayment = async () => {
    if (!topCandidateId) return;
    setTopPaymentBusy(true); setTopPaymentError("");
    try {
      await api(`/payments/listings/${topCandidateId}/top/checkout/cancel`, { method: "POST" });
      await refreshOwnedListings();
      setTopDialogOpen(false);
    } catch (error) { setTopPaymentError((error as Error).message); }
    finally { setTopPaymentBusy(false); }
  };
  return (
    <div className="owner-listings-page">
      <header className="owner-mobile-appbar"><Button type="button" variant="ghost" size="icon" onClick={goBack} aria-label="Volver"><ArrowLeft /></Button><strong>Tus anuncios</strong></header>
      <div className="container account-page">
      <AccountHeader
        eyebrow="Área del anunciante"
        title="Mis anuncios"
        description="Gestiona el estado y rendimiento de tus anuncios."
        action={
          <Button asChild>
            <Link to="/publicar">
              <Plus data-icon="inline-start" />
              Nuevo anuncio
            </Link>
          </Button>
        }
      />
      {searchParams.get("payment") === "return" && !returnedTopId && !searchParams.get("homepage") ? (
        <p role="status">{t("Estamos confirmando el pago. El estado de TOP se actualizará en unos segundos.")}</p>
      ) : null}
      {returnedTopId ? <p role={topPaymentStatus?.fulfillmentStatus === "review_required" ? "alert" : "status"}>{t(topPaymentStatus?.fulfillmentStatus === "review_required" ? "El pago se ha recibido, pero necesita revisión. Contacta con soporte; no vuelvas a pagar." : topPaymentStatus?.fulfillmentStatus === "revoked" ? "Pago devuelto · servicio finalizado" : topPaymentStatus?.fulfillmentStatus === "fulfilled" ? "Pago confirmado · tu anuncio está en TOP" : topPaymentStatus?.orderStatus === "failed" ? "Pago fallido. Puedes volver a intentarlo." : topPaymentStatus?.orderStatus === "expired" ? "Pago cancelado. Puedes volver a comprar TOP." : "Estamos confirmando el pago. El estado de TOP se actualizará en unos segundos.")}</p> : null}
      {topPaymentError && !topDialogOpen ? <p role="alert">{t(topPaymentError)}</p> : null}
      <OwnerHomepagePurchase listingId={homepageCandidateId} onClose={() => setHomepageCandidateId("")} onBack={() => { setHomepageCandidateId(""); setPromotionStep("choose"); setTopDialogOpen(true); }} />
      <div className="account-toolbar">
        <label htmlFor="my-listings-status">Estado</label>
        <select
          id="my-listings-status"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option>Todos</option>
          <option>Publicado</option>
          <option>Oculto</option>
          <option>Borrador</option>
          <option>Pendiente</option>
          <option>Rechazado</option>
          <option>Finalizado</option>
        </select>
      </div>
      {items.length ? (
        <div className="my-listings">
          <div className="listing-summary">
            <span>
              <strong>
                {mine.filter((item) => item.status === "Publicado").length}
              </strong>{" "}
              publicados
            </span>
            <span>
              <strong>
                {mine
                  .reduce((sum, item) => sum + item.views, 0)
                  .toLocaleString(currentLocale())}
              </strong>{" "}
              visualizaciones
            </span>
            <span>
              <strong>{mine.length}</strong> anuncios locales
            </span>
          </div>
          {items.map((listing) => (
            <article className="manage-card" key={listing.id} data-listing-id={listing.id}>
              <MediaImage
                src={listing.images[0]}
                variant="thumb"
                alt={`Habitación en ${listing.area}`}
                loading="lazy"
              />
              <div className="manage-card__main">
                <div>
                  <StatusBadge status={listing.status} />
                  <span>Ref. {listing.id.slice(-5).toUpperCase()}</span>
                </div>
                <h2 data-i18n-exempt>{listing.title}</h2>
                <p>
                  {listing.area} · {getPrimaryPrice(listing)} €/{getPrimaryCadence(listing)}
                </p>
                <span
                  data-testid="owner-rental-type"
                  className={`owner-rental-type owner-rental-type--${listing.rentalMode === "long" ? "long" : "holiday"}`}
                >
                  {t(listing.rentalMode === "long" ? "Larga estancia" : "Alquiler vacacional")}
                </span>
                {listing.promoted ? (
                  <>
                    <div className="owner-top-state owner-top-state--active" data-testid="owner-top-status" data-top-active="true">
                      <span className="owner-top-state__copy">
                        <strong>{t("Estás en TOP")}</strong>
                        {listing.promotionEndsAt ? (
                          <small>{t("Estás en TOP hasta")} {formatOwnerPromotionEnd(listing.promotionEndsAt, locale, language)}</small>
                        ) : (
                          <small>{t("Más visibilidad para tu anuncio")}</small>
                        )}
                      </span>
                    </div>
                    {listing.status === "Publicado" && !listing.isExternal ? (
                      <Button type="button" variant="outline"
                        className="owner-top-action owner-top-action--active"
                        data-testid="owner-top-manage-button"
                        onClick={() => openTopFlow(listing.id)}
                        aria-label={`${t("Gestionar TOP")}: ${listing.title}`}
                      >
                        <Smile className="owner-top-action__face" aria-hidden="true" />
                        <OwnerTopRocket active />
                        <span className="owner-top-action__label">{t("Gestionar TOP")}</span>
                      </Button>
                    ) : null}
                  </>
                ) : listing.status === "Publicado" && !listing.isExternal ? (
                  <>
                    <div className="owner-top-state owner-top-state--inactive" data-testid="owner-top-status" data-top-active="false">
                      <span className="owner-top-state__copy">
                        <strong>{t("No estás en TOP")}</strong>
                        <small>{t("Más visibilidad para tu anuncio")}</small>
                      </span>
                    </div>
                    <Button type="button" variant="outline"
                      className="owner-top-promote-button owner-top-action owner-top-action--inactive"
                      data-testid="owner-top-promote-button"
                      onClick={() => openTopFlow(listing.id)}
                      aria-label={`${t("Llevar a TOP")}: ${listing.title}`}
                    >
                      <Frown className="owner-top-action__face" aria-hidden="true" />
                      <OwnerTopRocket active={false} />
                      <span className="owner-top-action__label">{t("Llevar a TOP")}</span>
                    </Button>
                  </>
                ) : null}
                <p className="manage-restrictions">{getCriticalRestrictions(listing).slice(0, 2).join(" · ")}</p>
                {listing.status === "Finalizado" ? <p className="listing-ended-reason">Cerrado por el anunciante.</p> : null}
                <div className="manage-metrics">
                  <span>
                    <Eye />
                    {listing.views} vistas
                  </span>
                </div>
              </div>
              <div className="manage-actions">
                <Button asChild variant="outline" size="sm" className="owner-manage-action owner-manage-action--edit">
                  <Link to={`/mis-anuncios/${listing.id}/editar`}>
                    <Edit3 aria-hidden="true" />
                    <span className="owner-manage-action__label">{language === "ru" ? t("Modificar") : t("Editar")}</span>
                  </Link>
                </Button>
                {!listing.isExternal ? <ConfirmDialog
                  trigger={
                    <Button
                      variant="outline"
                      size="sm"
                      className="owner-manage-action owner-manage-action--delete"
                      aria-label={`Eliminar ${listing.title}`}
                      title={t("Eliminar")}
                    >
                      <Trash2 aria-hidden="true" />
                      <span>{t("Eliminar")}</span>
                    </Button>
                  }
                  title="¿Eliminar este anuncio?"
                  description="El anuncio y sus datos asociados se eliminarán definitivamente de 112233.es."
                  confirmLabel="Eliminar"
                  destructive
                  onConfirm={async () => {
                    if (await deleteListing(listing.id)) toast.success("Anuncio eliminado");
                  }}
                /> : null}
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="outline"
                      size="sm"
                      className="owner-manage-action owner-manage-action--more"
                      aria-label={`Más acciones para ${listing.title}`}
                    >
                      <MoreHorizontal aria-hidden="true" />
                      <span>{t("Más")}</span>
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuGroup>
                      {listing.status === "Finalizado" ? <DropdownMenuItem
                        onClick={async () => {
                          const next = await renewListing(listing.id);
                          if (next) toast.success(next === "Publicado" ? "Anuncio publicado de nuevo" : "Anuncio enviado a revisión");
                        }}
                      ><RotateCcw />Volver a publicar</DropdownMenuItem> : <DropdownMenuItem
                        onClick={async () => {
                          const showing = listing.status === "Oculto" || listing.status === "Rechazado";
                          const next = await setListingStatus(listing.id, showing ? "Pendiente" : "Oculto");
                          if (next) toast.success(showing ? "Anuncio enviado a revisión" : "Anuncio ocultado");
                        }}
                      >
                        {listing.status === "Oculto" || listing.status === "Rechazado" ? <Eye /> : <EyeOff />}
                        {listing.status === "Oculto" || listing.status === "Rechazado" ? "Enviar a revisión" : "Ocultar"}
                      </DropdownMenuItem>}
                      {listing.status !== "Finalizado" ? <DropdownMenuItem onClick={async () => { if (await closeListing(listing.id)) toast.success("Anuncio cerrado"); }}><CalendarClock />Cerrar anuncio</DropdownMenuItem> : null}
                    </DropdownMenuGroup>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="account-empty">
          <UserRound />
          <h2>No hay anuncios en este estado</h2>
          <p>Crea uno nuevo o cambia el filtro.</p>
          <Button asChild>
            <Link to="/publicar">Crear anuncio</Link>
          </Button>
        </div>
      )}
      </div>
      <Dialog open={topDialogOpen} onOpenChange={setTopDialogOpen}>
        <DialogContent className="owner-top-dialog">
          <DialogHeader>
            <DialogTitle>{t(promotionStep === "choose" ? "Promocionar anuncio" : promotionStep === "duration" ? "Sube tu anuncio a TOP" : "Confirmar promoción")}</DialogTitle>
            <DialogDescription>{t(promotionStep === "choose" ? "Elige cómo quieres promocionar este anuncio." : "TOP sitúa tu anuncio antes que los anuncios sin TOP.")}</DialogDescription>
          </DialogHeader>
          <div className="owner-top-dialog__list" role="list">
            {promotable.filter((listing) => listing.id === topCandidateId).map((listing) => (
              <button
                key={listing.id}
                type="button"
                aria-pressed={topCandidateId === listing.id}
                className={`owner-top-dialog__option ${topCandidateId === listing.id ? "is-selected" : ""}`}
                data-testid="owner-top-option"
                data-listing-id={listing.id}
                onClick={() => setTopCandidateId(listing.id)}
              >
                <MediaImage src={listing.images[0]} variant="thumb" alt="" />
                <span>
                  <strong>{listing.title}</strong>
                  <small>{listing.area} · {getPrimaryPrice(listing)} €/{getPrimaryCadence(listing)}</small>
                  <em>{listing.promoted ? `👍 ${t("Estás en TOP")}` : `😏 ${t("No estás en TOP")}`}</em>
                </span>
              </button>
            ))}
          </div>
          {promotionStep === "choose" ? <div className="owner-top-dialog__list" data-testid="owner-promotion-choices">
            <button type="button" className="owner-top-dialog__option owner-promotion-choice" onClick={() => { setTopDialogOpen(false); setHomepageCandidateId(topCandidateId); }} disabled={!promotable.find((listing) => listing.id === topCandidateId)?.images.length}>
              <span className="owner-promotion-choice__icon"><Home aria-hidden="true" /></span><span><strong>{t("Destacar en portada")}</strong><small>{t("Su foto aparecerá en la portada con un enlace al anuncio.")}</small></span>
            </button>
            <button type="button" className="owner-top-dialog__option owner-promotion-choice" onClick={() => setPromotionStep("duration")}>
              <span className="owner-promotion-choice__icon"><Rocket aria-hidden="true" /></span><span><strong>{t("Sube tu anuncio a TOP")}</strong><small>{t("Haz que tu anuncio destaque y aparezca antes que los demás.")}</small></span>
            </button>
          </div> : <div className={`owner-top-dialog__next ${promotionStep === "duration" ? "owner-top-dialog__next--period" : ""}`} data-testid="owner-top-next-step">
            <ProvinceTopAvailability state={provinceTop} />
            {promotionStep === "duration" ? <>
              <PromotionPeriod start={topStartDate} end={topEndDate} onChange={setTopEndDate} />
              <Button type="button" disabled={!validTopDays || !provinceTop.canBuy} onClick={() => setPromotionStep("payment")}>{t("Continuar")}</Button>
              <Button type="button" variant="outline" onClick={() => setPromotionStep("choose")}>{t("Volver")}</Button>
            </> : <>
              <strong>{t("1 € al día · mínimo 10 días")}{validTopDays ? ` · ${t(`${topDays} días`)} · ${new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR' }).format(Number(topDays))}` : ''}</strong>
              <span>{t("El plazo empieza cuando se confirma el pago. Si ya tienes TOP, se añaden los días al plazo actual.")}</span>
              {topPaymentError ? <span role="alert">{t(topPaymentError)}</span> : null}
              <Button type="button" disabled={topPaymentBusy || !topCandidateId || !validTopDays || !provinceTop.canBuy} onClick={() => { void payForTop() }}>{topPaymentBusy ? t("Cargando…") : t("Pagar con Stripe")}</Button>
              <Button type="button" variant="outline" disabled={topPaymentBusy} onClick={() => setPromotionStep("duration")}>{t("Volver")}</Button>
              <Button type="button" variant="outline" disabled={topPaymentBusy || !topCandidateId} onClick={() => { void cancelTopPayment() }}>{t("Cancelar pago")}</Button>
            </>}
          </div>}

        </DialogContent>
      </Dialog>
    </div>
  );
}
