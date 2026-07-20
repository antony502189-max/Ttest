import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  Bell,
  BellOff,
  CalendarClock,
  Clock3,
  Edit3,
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
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
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
import { filtersToParams } from "@/lib/search";
import { getCriticalRestrictions, getPrimaryCadence, getPrimaryPrice } from "@/lib/listings";
import { MediaImage, useMediaUrl } from "@/components/media-image";
import { MediaStorageError, saveMediaFile } from "@/lib/media-storage";
import type { DemoUser } from "@/types";

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
  const { favorites, allListings } = useApp();
  const saved = allListings.filter((listing) => favorites.has(listing.id));
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
            <PropertyCard key={listing.id} listing={listing} compact />
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
  const avatarUrl = useMediaUrl(draft?.avatarRef);
  useEffect(() => { if (!editing) setDraft(currentUser); }, [currentUser, editing]);
  if (!currentUser) return null;
  const profileDraft = draft ?? currentUser;
  const updateDraft = <K extends keyof DemoUser>(key: K, value: DemoUser[K]) => setDraft((current) => ({ ...(current ?? currentUser), [key]: value }));
  const cancelEditing = () => { setDraft(currentUser); setEditing(false); };
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
      allowContactForm: profileDraft.allowContactForm,
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
              void saveMediaFile(file).then((avatarRef) => updateDraft("avatarRef", avatarRef)).catch((error) => toast.error(error instanceof MediaStorageError ? error.message : "No se pudo guardar el avatar."));
            }} />
            {profileDraft.avatarRef ? <Button type="button" variant="ghost" size="sm" onClick={() => updateDraft("avatarRef", undefined)}>Eliminar foto</Button> : null}
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
            <label>
              <div>
                <strong>Permitir formulario local</strong>
                <span>Registra mensajes solo en la demo</span>
              </div>
              <Switch
                checked={profileDraft.allowContactForm}
                onCheckedChange={(value) => updateDraft("allowContactForm", value)}
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
              description="La cuenta local se borrará. Esta acción no se puede deshacer."
              confirmLabel="Eliminar definitivamente"
              destructive
              onConfirm={() => {
                deleteAccount();
                navigate("/acceso");
              }}
            />
          </div>
        </form>
      </div>
    </div>
  );
}

export function MyListingsPage() {
  const { allListings, deleteListing, setListingStatus, renewListing, closeListing, refreshListingLifecycle, currentUser } =
    useApp();
  const [status, setStatus] = useState("Todos");
  useEffect(() => refreshListingLifecycle(), [refreshListingLifecycle]);
  const mine = allListings.filter((listing) => listing.ownerUserId === currentUser?.id);
  const items =
    status === "Todos"
      ? mine
      : mine.filter((listing) => listing.status === status);
  return (
    <div className="container account-page">
      <AccountHeader
        eyebrow="Área del anunciante"
        title="Mis anuncios"
        description="Gestiona estado, vigencia y rendimiento."
        action={
          <Button asChild>
            <Link to="/publicar">
              <Plus data-icon="inline-start" />
              Nuevo anuncio
            </Link>
          </Button>
        }
      />
      <div className="account-toolbar">
        <label htmlFor="my-listings-status">Estado</label>
        <select
          id="my-listings-status"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option>Todos</option>
          <option>Pendiente</option>
          <option>Publicado</option>
          <option>Oculto</option>
          <option>Borrador</option>
          <option>Finalizado</option>
          <option>Rechazado</option>
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
                  .toLocaleString("es-ES")}
              </strong>{" "}
              visualizaciones
            </span>
            <span>
              <strong>{mine.length}</strong> anuncios locales
            </span>
          </div>
          {items.map((listing) => (
            <article className="manage-card" key={listing.id}>
              <MediaImage
                src={listing.images[0]}
                alt={`Habitación en ${listing.area}`}
              />
              <div className="manage-card__main">
                <div>
                  <StatusBadge status={listing.status} />
                  <span>Ref. {listing.id.slice(-5).toUpperCase()}</span>
                </div>
                <h2>{listing.title}</h2>
                <p>
                  {listing.area} · {getPrimaryPrice(listing)} €/{getPrimaryCadence(listing)}
                </p>
                <p className="manage-restrictions">{getCriticalRestrictions(listing).slice(0, 2).join(" · ")}</p>
                {listing.status === "Finalizado" ? <p className="listing-ended-reason">{listing.closedReason === "expired" ? "Finalizado automáticamente por vencimiento." : "Cerrado por el anunciante."}</p> : null}
                <div className="manage-metrics">
                  <span>
                    <Eye />
                    {listing.views} vistas
                  </span>
                  <span>
                    <CalendarClock />
                    Finaliza {listing.expiresAt}
                  </span>
                </div>
              </div>
              <div className="manage-actions">
                <Button asChild variant="outline" size="sm">
                  <Link to={`/mis-anuncios/${listing.id}/editar`}>
                    <Edit3 data-icon="inline-start" />
                    Editar
                  </Link>
                </Button>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Más acciones para ${listing.title}`}
                    >
                      <MoreHorizontal />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuGroup>
                      {listing.status === "Finalizado" ? <DropdownMenuItem
                        onClick={() => { renewListing(listing.id); toast.success("Anuncio publicado de nuevo durante 30 días"); }}
                      ><RotateCcw />Volver a publicar</DropdownMenuItem> : <DropdownMenuItem
                        onClick={() => {
                          setListingStatus(
                            listing.id,
                            listing.status === "Oculto"
                              ? "Publicado"
                              : "Oculto",
                          );
                          toast.success(
                            listing.status === "Oculto"
                              ? "Anuncio publicado"
                              : "Anuncio ocultado",
                          );
                        }}
                      >
                        {listing.status === "Oculto" ? <Eye /> : <EyeOff />}
                        {listing.status === "Oculto" ? "Mostrar" : "Ocultar"}
                      </DropdownMenuItem>}
                      <DropdownMenuItem
                        onClick={() => {
                          renewListing(listing.id);
                          toast.success("Anuncio renovado 30 días");
                        }}
                      >
                        <RotateCcw />
                        Renovar
                      </DropdownMenuItem>
                      {listing.status !== "Finalizado" ? <DropdownMenuItem onClick={() => { closeListing(listing.id); toast.success("Anuncio cerrado"); }}><CalendarClock />Cerrar anuncio</DropdownMenuItem> : null}
                      <ConfirmDialog
                        trigger={
                          <DropdownMenuItem
                            onSelect={(event) => event.preventDefault()}
                            variant="destructive"
                          >
                            <Trash2 />
                            Eliminar
                          </DropdownMenuItem>
                        }
                        title="¿Eliminar este anuncio?"
                        description="Se quitará de la búsqueda y de Mis anuncios."
                        confirmLabel="Eliminar"
                        destructive
                        onConfirm={() => deleteListing(listing.id)}
                      />
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
  );
}
