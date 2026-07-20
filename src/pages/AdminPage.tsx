import { useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Check,
  Eye,
  FileSearch,
  Filter,
  Gauge,
  MoreHorizontal,
  Search,
  ShieldBan,
  ShieldCheck,
  Trash2,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AdminTable, ConfirmDialog, StatusBadge } from "@/components/forms";
import { listings } from "@/data/listings";

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: Gauge },
  { id: "listings", label: "Anuncios", icon: FileSearch },
  { id: "users", label: "Usuarios", icon: Users },
  { id: "reports", label: "Denuncias", icon: AlertTriangle },
  { id: "moderation", label: "Moderación", icon: ShieldCheck },
];

function ModerationActions({ title }: { title: string }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Acciones para ${title}`}
        >
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuGroup>
          <DropdownMenuItem onClick={() => toast.success("Anuncio aprobado")}>
            <Check />
            Aprobar
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => toast("Anuncio ocultado")}>
            <Eye />
            Ocultar
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => toast.error("Anuncio rechazado")}>
            <X />
            Rechazar
          </DropdownMenuItem>
          <DropdownMenuItem
            variant="destructive"
            onClick={() => toast.error("Elemento eliminado (demo)")}
          >
            <Trash2 />
            Eliminar
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function AdminPage() {
  const [section, setSection] = useState("dashboard");
  const listingRows = useMemo(
    () =>
      listings.slice(0, 6).map((listing, index) => [
        <div key="listing" className="admin-listing-cell">
          <img src={listing.images[0]} alt="" />
          <div>
            <strong>{listing.title}</strong>
            <span>
              {listing.area} · REF {listing.id.slice(-5).toUpperCase()}
            </span>
          </div>
        </div>,
        <StatusBadge
          key="status"
          status={index % 3 === 0 ? "Pendiente" : listing.status}
        />,
        listing.owner.name,
        `${listing.price} €`,
        listing.publishedAt,
        <ModerationActions key="actions" title={listing.title} />,
      ]),
    [],
  );
  const userRows = [
    [
      "Lucía Martín",
      "lucia@example.es",
      "Inquilina",
      "19 jul 2026",
      <Badge key="status" variant="outline">
        Activa
      </Badge>,
    ],
    [
      "Equipo Casa Norte",
      "casa@example.es",
      "Anunciante",
      "16 jul 2026",
      <Badge key="status" variant="outline">
        Verificada
      </Badge>,
    ],
    [
      "Atlántico Estancias",
      "atlantico@example.es",
      "Profesional",
      "10 jul 2026",
      <Badge key="status" variant="outline">
        Revisión
      </Badge>,
    ],
  ].map((row) => [
    ...row,
    <ConfirmDialog
      key="actions"
      trigger={
        <Button variant="ghost" size="icon" aria-label={`Bloquear ${row[0]}`}>
          <ShieldBan />
        </Button>
      }
      title="¿Bloquear esta cuenta?"
      description="La cuenta no podrá acceder ni publicar hasta que se revise el caso."
      confirmLabel="Bloquear"
      destructive
      onConfirm={() => toast.error("Cuenta bloqueada (demo)")}
    />,
  ]);
  const reportRows = [
    [
      "REP-418",
      "Posible fraude",
      "Habitación en Costa Adeje",
      "Alta",
      "Hace 12 min",
    ],
    [
      "REP-417",
      "Datos incorrectos",
      "Habitación en Armeñime",
      "Media",
      "Hace 1 h",
    ],
    [
      "REP-416",
      "Contenido discriminatorio",
      "Estudio en Las Américas",
      "Alta",
      "Hace 3 h",
    ],
  ].map((row) => [...row, <ModerationActions key="actions" title={row[2]} />]);
  return (
    <div className="admin-page">
      <aside className="admin-sidebar">
        <Link to="/" className="admin-brand">
          11·22·33 <span>admin</span>
        </Link>
        <nav aria-label="Administración">
          {navItems.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setSection(id)}
              aria-current={section === id ? "page" : undefined}
            >
              <Icon />
              {label}
              {id === "reports" ? <span>3</span> : null}
            </button>
          ))}
        </nav>
        <div className="admin-user">
          <div>AM</div>
          <span>
            <strong>Ana Mod.</strong>
            <small>Administración</small>
          </span>
        </div>
      </aside>
      <div className="admin-main">
        <header className="admin-header">
          <div>
            <span className="eyebrow">Panel interno</span>
            <h1>{navItems.find((item) => item.id === section)?.label}</h1>
          </div>
          <div className="admin-search">
            <Search />
            <Input
              aria-label="Buscar en administración"
              placeholder="Buscar usuarios o referencias"
            />
          </div>
          <Button variant="outline">
            <UserRound data-icon="inline-start" />
            Ana
          </Button>
        </header>
        {section === "dashboard" ? (
          <>
            <section className="stats-grid">
              <div>
                <span>Anuncios activos</span>
                <strong>148</strong>
                <small>+12 esta semana</small>
                <BarChart3 />
              </div>
              <div>
                <span>Pendientes</span>
                <strong>16</strong>
                <small>5 con más de 24 h</small>
                <FileSearch />
              </div>
              <div>
                <span>Usuarios</span>
                <strong>1.284</strong>
                <small>+4,8% este mes</small>
                <Users />
              </div>
              <div>
                <span>Denuncias abiertas</span>
                <strong>3</strong>
                <small>2 prioridad alta</small>
                <AlertTriangle />
              </div>
            </section>
            <section className="admin-panel">
              <div className="admin-panel__head">
                <div>
                  <h2>Pendientes de moderación</h2>
                  <p>Anuncios ordenados por tiempo de espera y riesgo.</p>
                </div>
                <Button
                  variant="outline"
                  onClick={() => setSection("moderation")}
                >
                  Ver cola completa
                </Button>
              </div>
              <AdminTable
                headers={[
                  "Anuncio",
                  "Estado",
                  "Anunciante",
                  "Precio",
                  "Publicado",
                  "",
                ]}
                rows={listingRows.slice(0, 4)}
              />
            </section>
            <div className="admin-dashboard-grid">
              <section className="admin-panel">
                <div className="admin-panel__head">
                  <div>
                    <h2>Denuncias recientes</h2>
                    <p>Casos que requieren revisión.</p>
                  </div>
                </div>
                <AdminTable
                  headers={[
                    "Ref.",
                    "Motivo",
                    "Anuncio",
                    "Prioridad",
                    "Fecha",
                    "",
                  ]}
                  rows={reportRows}
                />
              </section>
              <section className="admin-panel admin-health">
                <h2>Estado del marketplace</h2>
                <dl>
                  <div>
                    <dt>Anuncios completos</dt>
                    <dd>84%</dd>
                  </div>
                  <div>
                    <dt>Respuesta &lt;24 h</dt>
                    <dd>71%</dd>
                  </div>
                  <div>
                    <dt>Tasa de denuncia</dt>
                    <dd>0,8%</dd>
                  </div>
                </dl>
              </section>
            </div>
          </>
        ) : (
          <section className="admin-panel">
            <div className="admin-panel__head">
              <div>
                <h2>
                  {section === "users"
                    ? "Usuarios registrados"
                    : section === "reports"
                      ? "Denuncias abiertas"
                      : "Anuncios y moderación"}
                </h2>
                <p>
                  Datos de demostración listos para conectar a la API de
                  administración.
                </p>
              </div>
              <div>
                <Button variant="outline">
                  <Filter data-icon="inline-start" />
                  Filtros
                </Button>
                <Button>Exportar CSV</Button>
              </div>
            </div>
            {section === "users" ? (
              <AdminTable
                headers={["Usuario", "Email", "Tipo", "Registro", "Estado", ""]}
                rows={userRows}
              />
            ) : section === "reports" ? (
              <AdminTable
                headers={[
                  "Ref.",
                  "Motivo",
                  "Anuncio",
                  "Prioridad",
                  "Fecha",
                  "",
                ]}
                rows={reportRows}
              />
            ) : (
              <AdminTable
                headers={[
                  "Anuncio",
                  "Estado",
                  "Anunciante",
                  "Precio",
                  "Publicado",
                  "",
                ]}
                rows={listingRows}
              />
            )}
          </section>
        )}
      </div>
    </div>
  );
}
