import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  Bell,
  CalendarDays,
  ChevronRight,
  Heart,
  List,
  Map,
  ArrowUpDown,
  X,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerClose, DrawerContent, DrawerDescription, DrawerFooter, DrawerHeader, DrawerTitle, DrawerTrigger } from "@/components/ui/drawer";
import { Field, FieldLabel } from "@/components/ui/field";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useApp } from "@/contexts/app-context";
import { defaultFilters } from "@/data/listings";
import { tenantRequirementLabels } from "@/lib/listings";
import { listingMatchesTenerifeLocation, resolveTenerifeLocation } from "@/lib/tenerife";
import {
  filterListings,
  filtersFromParams,
  filtersToParams,
  pointInPolygon,
  sortListings,
} from "@/lib/search";
import {
  EmptyState,
  ErrorState,
  FilterButton,
  FilterSidebar,
  LoadingSkeleton,
  LocationSelector,
  MapView,
  Pagination,
  PropertyCard,
  QuickFilters,
  RentalTypeSwitch,
  SearchBar,
  type MapBounds,
} from "@/components/marketplace";
import type { Filters, MapPolygonPoint, RentalMode } from "@/types";

const PAGE_SIZE = 9;
const sortOptions = ["Relevancia", "Más recientes", "Más antiguos", "Precio más bajo", "Precio más alto"];

function SortControl({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <Drawer><DrawerTrigger asChild><Button variant="outline" className="mobile-sort-control"><ArrowUpDown data-icon="inline-start" />Ordenar</Button></DrawerTrigger><DrawerContent className="sort-drawer"><DrawerHeader><DrawerTitle>Ordenar resultados</DrawerTitle><DrawerDescription>Elige cómo quieres ver las habitaciones.</DrawerDescription></DrawerHeader><RadioGroup value={value} onValueChange={onChange} className="sort-options">{sortOptions.map((option) => { const id = `sort-${option.replace(/\s+/g, '-').toLocaleLowerCase()}`; return <Field key={option} orientation="horizontal"><RadioGroupItem id={id} value={option} /><FieldLabel htmlFor={id}>{option}</FieldLabel></Field> })}</RadioGroup><DrawerFooter><DrawerClose asChild><Button>Aplicar orden</Button></DrawerClose></DrawerFooter></DrawerContent></Drawer>
}

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const paramString = params.toString();
  const {
    rentalMode: storedRentalMode,
    setRentalMode,
    filters: storedFilters,
    setFilters,
    resetFilters,
    query: storedQuery,
    setQuery,
    saveCurrentSearch,
    activeFilterCount,
    allListings,
    discarded,
    restoreDiscarded,
    mapPolygon,
    setMapPolygon,
  } = useApp();
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(false);
  const [mapBounds, setMapBounds] = useState<MapBounds | null>(null);
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 767px)').matches);
  const [initialMapAction] = useState<'draw' | 'near' | null>(() => params.get('dibujar') === '1' ? 'draw' : params.get('cerca') === '1' ? 'near' : null);
  const actionConsumedRef = useRef(false);
  const view = params.get("vista") === "mapa" ? "map" : "list";
  const page = Math.max(1, Number(params.get("pagina") || 1));
  const requestedQuery = params.get("q")?.trim() || "Tenerife";
  const location = resolveTenerifeLocation(requestedQuery);
  const invalidLocation = !location;
  const query = location?.normalizedValue ?? "Tenerife";
  const rentalMode: RentalMode =
    params.get("alquiler") === "holiday" ? "holiday" : "long";
  const filters = useMemo(() => {
    const parsed = filtersFromParams(params);
    if (rentalMode === "holiday") {
      parsed.minPrice = Math.min(parsed.minPrice, 350);
      parsed.maxPrice = Math.min(parsed.maxPrice, 350);
    }
    return parsed;
    // paramString captures the complete serialized filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramString]);

  useLayoutEffect(() => {
    if (["genero", "parejas", "ocupantes"].some((name) => params.has(name))) {
      setParams(filtersToParams(filters, new URLSearchParams(params)), { replace: true });
      return;
    }
    if (query !== storedQuery) setQuery(query);
    if (rentalMode !== storedRentalMode) setRentalMode(rentalMode);
    if (JSON.stringify(filters) !== JSON.stringify(storedFilters))
      setFilters(filters);
    const polygonParam = params.get("poligono");
    if (polygonParam) {
      const points = polygonParam
        .split(";")
        .map((pair) => pair.split(",").map(Number))
        .filter((pair) => pair.length === 2 && pair.every(Number.isFinite))
        .map(([lat, lng]) => ({ lat, lng }));
      if (JSON.stringify(points) !== JSON.stringify(mapPolygon))
        setMapPolygon(points);
    } else if (mapPolygon.length) setMapPolygon([]);
    // Search params are the source of truth for direct URLs and browser navigation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramString]);

  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px)');
    const update = () => setIsMobile(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!initialMapAction || actionConsumedRef.current) return;
    actionConsumedRef.current = true;
    const next = new URLSearchParams(params);
    next.delete('dibujar');
    next.delete('cerca');
    setParams(next, { replace: true });
  }, [initialMapAction, params, setParams]);

  const filteredItems = useMemo(
    () =>
      filterListings(
        allListings.filter((listing) => !discarded.has(listing.id)),
        rentalMode,
        filters,
      ).filter((listing) => !invalidLocation && listingMatchesTenerifeLocation(listing, location)),
    [allListings, discarded, filters, invalidLocation, location, rentalMode],
  );
  const spatialItems = useMemo(
    () =>
      filteredItems.filter((listing) => {
        if (
          mapBounds &&
          (listing.coordinates.lat > mapBounds.north ||
            listing.coordinates.lat < mapBounds.south ||
            listing.coordinates.lng > mapBounds.east ||
            listing.coordinates.lng < mapBounds.west)
        )
          return false;
        if (
          mapPolygon.length >= 3 &&
          !pointInPolygon(listing.coordinates, mapPolygon)
        )
          return false;
        return true;
      }),
    [filteredItems, mapBounds, mapPolygon],
  );
  const items = useMemo(
    () => sortListings(spatialItems, filters.sort),
    [filters.sort, spatialItems],
  );
  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = items.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE,
  );
  const forcedState = params.get("estado");
  const formattedDate = filters.available
    ? new Intl.DateTimeFormat("es-ES", {
        day: "numeric",
        month: "short",
        year: "numeric",
      }).format(new Date(`${filters.available}T12:00:00`))
    : "Cualquier fecha";

  useEffect(() => {
    if (page <= totalPages) return;
    const next = new URLSearchParams(params);
    next.set("pagina", String(totalPages));
    setParams(next, { replace: true });
  }, [page, params, setParams, totalPages]);

  const updateParams = (
    mutate: (next: URLSearchParams) => void,
    replace = false,
  ) => {
    const next = new URLSearchParams(params);
    mutate(next);
    setParams(next, { replace });
  };
  const commitPolygon = (polygon: MapPolygonPoint[]) => {
    setMapPolygon(polygon);
    updateParams((next) => {
      next.delete("pagina");
      if (polygon.length >= 3)
        next.set(
          "poligono",
          polygon
            .map((point) => `${point.lat.toFixed(5)},${point.lng.toFixed(5)}`)
            .join(";"),
        );
      else next.delete("poligono");
    }, true);
  };
  const commitFilters = (nextFilters: Filters) => {
    setFilters(nextFilters);
    const next = filtersToParams(nextFilters, new URLSearchParams(params));
    next.delete("pagina");
    setParams(next);
  };
  const selectLocation = (nextQuery: string) => {
    const nextLocation = resolveTenerifeLocation(nextQuery);
    if (!nextLocation) return;
    const nextFilters = {
      ...filters,
      areas: nextLocation.type === 'area' || nextLocation.type === 'district' ? [nextLocation.normalizedValue] : [],
    };
    setQuery(nextLocation.normalizedValue);
    setFilters(nextFilters);
    const next = filtersToParams(nextFilters, new URLSearchParams(params));
    next.set('q', nextLocation.normalizedValue);
    next.delete('pagina');
    setParams(next);
  };
  const applyLocationAreas = (selectedAreas: string[]) => {
    const nextFilters = { ...filters, areas: selectedAreas };
    const nextQuery = selectedAreas.length === 1 ? selectedAreas[0] : 'Tenerife';
    setQuery(nextQuery);
    setFilters(nextFilters);
    const next = filtersToParams(nextFilters, new URLSearchParams(params));
    next.set('q', nextQuery);
    next.delete('pagina');
    setParams(next);
  };
  const changeView = (nextView: "list" | "map") =>
    updateParams((next) =>
      nextView === "map" ? next.set("vista", "mapa") : next.delete("vista"),
    );
  const changeSort = (value: string) => {
    setLoading(true);
    commitFilters({ ...filters, sort: value });
    window.setTimeout(() => setLoading(false), 180);
  };
  const changePage = (nextPage: number) => {
    updateParams((next) =>
      nextPage === 1
        ? next.delete("pagina")
        : next.set("pagina", String(nextPage)),
    );
    document
      .getElementById("results-title")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const clearAll = () => {
    resetFilters();
    setMapBounds(null);
    setMapPolygon([]);
    const next = filtersToParams(defaultFilters, new URLSearchParams(params));
    ["pagina", "poligono", "zonas"].forEach((name) => next.delete(name));
    next.set('q', 'Tenerife');
    setParams(next);
  };

  const setOne = <K extends keyof Filters>(key: K, value: Filters[K]) => {
    commitFilters({ ...filters, [key]: value });
  };
  const appliedFilters = useMemo(() => {
    const chips: { key: string; label: string; clear: () => void }[] = [];
    if (filters.areas.length)
      chips.push({
        key: "areas",
        label:
          filters.areas.length === 1
            ? filters.areas[0]
            : `${filters.areas.length} zonas`,
        clear: () => setOne("areas", []),
      });
    if (
      filters.minPrice !== defaultFilters.minPrice ||
      filters.maxPrice !== defaultFilters.maxPrice
    )
      chips.push({
        key: "price",
        label: `${filters.minPrice}–${filters.maxPrice} €`,
        clear: () =>
          commitFilters({
            ...filters,
            minPrice: defaultFilters.minPrice,
            maxPrice: defaultFilters.maxPrice,
          }),
      });
    const stringFields: [keyof Filters, string][] = [
      ["roomType", "Habitación"],
      ["available", "Fecha"],
      ["minStay", "Estancia"],
      ["tenantRequirement", "Requisito"],
      ["bathroom", "Baño"],
      ["kitchen", "Cocina"],
      ["deposit", "Fianza"],
      ["shower", "Ducha"],
      ["currentResidents", "Residentes"],
      ["roomCapacity", "Capacidad"],
      ["availableUntil", "Disponible hasta"],
      ["smoking", "Fumar"],
      ["pets", "Mascotas"],
      ["children", "Niños"],
      ["empadronamiento", "Empadronamiento"],
      ["publicationDate", "Publicado"],
      ["advertiserType", "Anunciante"],
    ];
    stringFields.forEach(([key, prefix]) => {
      if (filters[key] !== defaultFilters[key] && filters[key] !== "")
        chips.push({
          key: String(key),
          label: `${prefix}: ${key === "tenantRequirement" && filters.tenantRequirement !== "Cualquiera" ? tenantRequirementLabels[filters.tenantRequirement] : key === "currentResidents" && filters.currentResidents === "5+" ? "5 o más" : key === "roomCapacity" ? `${filters.roomCapacity} ${filters.roomCapacity === "1" ? "persona" : "personas"}` : String(filters[key])}`,
          clear: () => setOne(key, defaultFilters[key]),
        });
    });
    if (filters.roomSizeMin !== defaultFilters.roomSizeMin || filters.roomSizeMax !== defaultFilters.roomSizeMax)
      chips.push({ key: "roomSize", label: `${filters.roomSizeMin}–${filters.roomSizeMax} m²`, clear: () => commitFilters({ ...filters, roomSizeMin: defaultFilters.roomSizeMin, roomSizeMax: defaultFilters.roomSizeMax }) });
    if (filters.minimumNights !== defaultFilters.minimumNights)
      chips.push({ key: "minimumNights", label: `Estancia mínima: hasta ${filters.minimumNights} noches`, clear: () => setOne("minimumNights", defaultFilters.minimumNights) });
    (["furnished", "billsIncluded"] as const).forEach((key) => {
      if (filters[key])
        chips.push({
          key,
          label: key === "furnished" ? "Amueblada" : "Gastos incluidos",
          clear: () => setOne(key, false),
        });
    });
    filters.conditions.forEach((condition) =>
      chips.push({
        key: `condition-${condition}`,
        label: condition,
        clear: () =>
          setOne(
            "conditions",
            filters.conditions.filter((item) => item !== condition),
          ),
      }),
    );
    filters.amenities.forEach((amenity) =>
      chips.push({
        key: `amenity-${amenity}`,
        label: amenity,
        clear: () =>
          setOne(
            "amenities",
            filters.amenities.filter((item) => item !== amenity),
          ),
      }),
    );
    if (mapPolygon.length >= 3)
      chips.push({
        key: "polygon",
        label: "Zona dibujada",
        clear: () => commitPolygon([]),
      });
    if (mapBounds)
      chips.push({
        key: "bounds",
        label: "Área visible del mapa",
        clear: () => setMapBounds(null),
      });
    return chips;
    // setOne only closes over the latest filters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, mapBounds, mapPolygon]);

  if (view === 'map' && isMobile) {
    return <div className="mobile-map-screen" aria-label="Mapa de habitaciones en Tenerife">
      <header className="mobile-map-screen__header">
        <Button type="button" variant="ghost" size="icon" onClick={() => changeView('list')} aria-label="Volver a la lista"><ArrowLeft /></Button>
        <LocationSelector selected={filters.areas} currentQuery={query} onApply={applyLocationAreas} onLocationSelect={selectLocation} />
      </header>
      <div className="mobile-map-screen__canvas">
        <MapView
          items={items}
          selectedId={selected}
          onSelect={setSelected}
          fullScreen
          initialAction={initialMapAction}
          fitResultsKey={mapBounds ? 1 : 0}
          onBoundsSearch={(bounds) => { setMapBounds(bounds); updateParams((next) => next.delete('pagina'), true); }}
          onPolygonSearch={commitPolygon}
        />
      </div>
      <div className="mobile-map-screen__footer"><Button onClick={() => changeView('list')}><List data-icon="inline-start" />Mostrar {items.length} habitaciones</Button></div>
    </div>;
  }

  return (
    <div
      className={
        view === "map"
          ? "search-page idealista-search-page is-map-page"
          : "search-page idealista-search-page"
      }
    >
      <header className="mobile-results-topbar">
        <Button asChild variant="ghost" size="icon"><Link to="/" aria-label="Volver al inicio"><ArrowLeft /></Link></Button>
        <LocationSelector selected={filters.areas} currentQuery={query} onApply={applyLocationAreas} onLocationSelect={selectLocation} />
      </header>
      <div className="search-toolbar">
        <div className="container">
          <RentalTypeSwitch
            compact
            onChange={(mode) =>
              updateParams((next) => next.set("alquiler", mode))
            }
          />
          <SearchBar compact />
        </div>
      </div>
      <div className="container search-breadcrumb">
        <Link to="/">Inicio</Link>
        <ChevronRight aria-hidden="true" />
        <span>Habitaciones en {query || "Tenerife"}</span>
      </div>
      <div
        className={
          view === "map"
            ? "container idealista-results-layout is-map-view"
            : "container idealista-results-layout"
        }
      >
        <FilterSidebar
          resultCount={items.length}
          onFiltersChange={commitFilters}
        />
        <section className="idealista-results" aria-labelledby="results-title">
          {invalidLocation ? <div className="location-search-error" role="alert"><strong>Solo buscamos en Tenerife</strong><span>En esta versión solo puedes buscar habitaciones en Tenerife. Prueba Tenerife, Adeje, Arona, Santa Cruz o La Laguna.</span></div> : null}
          {params.get("alertas") === "1" ? (
            <div className="search-alert-panel">
              <Bell aria-hidden="true" />
              <div>
                <strong>Guarda esta búsqueda</strong>
                <span>Recibe avisos con los filtros y zona actuales.</span>
              </div>
              <Button
                onClick={() => {
                  saveCurrentSearch();
                  updateParams((next) => next.delete("alertas"), true);
                }}
              >
                Guardar
              </Button>
            </div>
          ) : null}
          <header className="results-head idealista-results-head">
            <div>
              <h1 id="results-title">
                {items.length}{" "}
                {items.length === 1 ? "habitación" : "habitaciones"} en{" "}
                {query || "Tenerife"}
              </h1>
              <p>
                <CalendarDays aria-hidden="true" />
                {formattedDate} ·{" "}
                {rentalMode === "long"
                  ? "Larga estancia"
                  : "Alquiler vacacional"}{" "}
                <button
                  type="button"
                  onClick={() =>
                    document
                      .querySelector<HTMLInputElement>(".search-toolbar input")
                      ?.focus()
                  }
                >
                  Modificar
                </button>
              </p>
            </div>
            <Button
              variant="outline"
              className="save-search-button"
              onClick={saveCurrentSearch}
            >
              <Heart data-icon="inline-start" />
              Guardar búsqueda
            </Button>
          </header>
          <QuickFilters
            resultCount={items.length}
            onFiltersChange={commitFilters}
          />
          {appliedFilters.length ? (
            <div className="applied-filters" aria-label="Filtros aplicados">
              {appliedFilters.map((filter) => (
                <button type="button" key={filter.key} onClick={filter.clear}>
                  {filter.label}
                  <X aria-hidden="true" />
                </button>
              ))}
              <button
                type="button"
                className="applied-filters__clear"
                onClick={clearAll}
              >
                Borrar filtros ({activeFilterCount})
              </button>
            </div>
          ) : null}
          <div className="idealista-results-toolbar">
            <div className="mobile-filter-control">
              <FilterButton resultCount={items.length} onFiltersChange={commitFilters} onRentalModeChange={(mode) => updateParams((next) => next.set("alquiler", mode))} />
            </div>
            <SortControl value={filters.sort} onChange={changeSort} />
            <label className="desktop-sort-control">
              <span>Ordenar:</span>
              <select
                aria-label="Ordenar resultados"
                value={filters.sort}
                onChange={(event) => changeSort(event.target.value)}
              >
                <option>Relevancia</option>
                <option>Más recientes</option>
                <option>Más antiguos</option>
                <option>Precio más bajo</option>
                <option>Precio más alto</option>
              </select>
            </label>
            <Button
              className="results-map-button"
              variant={view === "map" ? "default" : "outline"}
              onClick={() => changeView(view === "map" ? "list" : "map")}
              aria-pressed={view === "map"}
              aria-label={view === "map" ? "Mostrar lista de habitaciones" : "Mostrar habitaciones en el mapa"}
            >
              {view === "map" ? (
                <List data-icon="inline-start" />
              ) : (
                <Map data-icon="inline-start" />
              )}
              {view === "map" ? "Lista" : "Mapa"}
            </Button>
          </div>
          {view === "map" ? (
            <div className="map-results-split">
              <div
                className="map-results-cards"
                aria-label="Lista sincronizada con el mapa"
              >
                {items.map((listing) => (
                  <PropertyCard
                    key={listing.id}
                    listing={listing}
                    compact
                    selected={selected === listing.id}
                    onFocus={() => setSelected(listing.id)}
                  />
                ))}
              </div>
              <div className="idealista-map-view">
                <MapView
                  items={items}
                  selectedId={selected}
                  onSelect={setSelected}
                  fullScreen
                  initialAction={initialMapAction}
                  fitResultsKey={mapBounds ? 1 : 0}
                  onBoundsSearch={(bounds) => {
                    setMapBounds(bounds);
                    updateParams((next) => next.delete("pagina"), true);
                  }}
                  onPolygonSearch={(polygon: MapPolygonPoint[]) => {
                    commitPolygon(polygon);
                  }}
                />
              </div>
            </div>
          ) : forcedState === "error" ? (
            <ErrorState />
          ) : forcedState === "empty" || items.length === 0 ? (
            <EmptyState
              onReset={() => {
                clearAll();
                restoreDiscarded();
              }}
            />
          ) : loading || forcedState === "loading" ? (
            <LoadingSkeleton />
          ) : (
            <div className="results-list">
              {pageItems.map((listing) => (
                <PropertyCard
                  key={listing.id}
                  listing={listing}
                  selected={selected === listing.id}
                  onFocus={() => setSelected(listing.id)}
                />
              ))}
              <Pagination
                page={currentPage}
                totalPages={totalPages}
                onPage={changePage}
              />
              <section
                className="search-related"
                aria-labelledby="related-title"
              >
                <h2 id="related-title">También puede interesarte</h2>
                <div>
                  <Link to="/registro">Crea tu perfil</Link>
                  <Link to="/buscar?q=Adeje">Habitaciones en Adeje</Link>
                  <Link to="/buscar?q=Arona">Habitaciones en Arona</Link>
                  <Link to="/buscar?q=La%20Laguna">
                    Habitaciones en La Laguna
                  </Link>
                </div>
              </section>
            </div>
          )}
        </section>
      </div>
      <Button
        className="mobile-map-toggle"
        onClick={() => changeView(view === "map" ? "list" : "map")}
        aria-label={
          view === "map"
            ? "Mostrar lista de habitaciones"
            : "Mostrar habitaciones en el mapa"
        }
      >
        {view === "map" ? (
          <List data-icon="inline-start" />
        ) : (
          <Map data-icon="inline-start" />
        )}
        {view === "map" ? `Mostrar ${items.length} habitaciones` : "Ver mapa"}
      </Button>
    </div>
  );
}
