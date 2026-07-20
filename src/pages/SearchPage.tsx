import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import {
  Bell,
  CalendarDays,
  ChevronRight,
  Heart,
  List,
  Map,
  X,
} from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useApp } from "@/contexts/app-context";
import { areas, defaultFilters } from "@/data/listings";
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
  const view = params.get("vista") === "mapa" ? "map" : "list";
  const page = Math.max(1, Number(params.get("pagina") || 1));
  const query = params.get("q")?.trim() || "Tenerife";
  const rentalMode: RentalMode =
    params.get("alquiler") === "holiday" ? "holiday" : "long";
  const filters = useMemo(() => {
    const parsed = filtersFromParams(params);
    const exactArea = areas.find(
      (area) => area.toLocaleLowerCase() === query.toLocaleLowerCase(),
    );
    if (!parsed.areas.length && exactArea) parsed.areas = [exactArea];
    if (rentalMode === "holiday") {
      parsed.minPrice = Math.min(parsed.minPrice, 350);
      parsed.maxPrice = Math.min(parsed.maxPrice, 350);
    }
    return parsed;
    // paramString captures the complete serialized filter state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramString]);

  useLayoutEffect(() => {
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

  const filteredItems = useMemo(
    () =>
      filterListings(
        allListings.filter((listing) => !discarded.has(listing.id)),
        rentalMode,
        filters,
      ),
    [allListings, discarded, filters, rentalMode],
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
      ["gender", "Preferencia"],
      ["bathroom", "Baño"],
      ["kitchen", "Cocina"],
      ["deposit", "Fianza"],
      ["occupants", "Ocupantes"],
      ["shower", "Ducha"],
      ["currentResidents", "Residentes"],
      ["roomCapacity", "Capacidad"],
      ["availableUntil", "Disponible hasta"],
      ["smoking", "Fumar"],
      ["pets", "Mascotas"],
      ["couples", "Parejas"],
      ["children", "Niños"],
      ["empadronamiento", "Empadronamiento"],
      ["publicationDate", "Publicado"],
      ["advertiserType", "Anunciante"],
    ];
    stringFields.forEach(([key, prefix]) => {
      if (filters[key] !== defaultFilters[key] && filters[key] !== "")
        chips.push({
          key: String(key),
          label: `${prefix}: ${String(filters[key])}`,
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

  return (
    <div
      className={
        view === "map"
          ? "search-page idealista-search-page is-map-page"
          : "search-page idealista-search-page"
      }
    >
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
              <FilterButton resultCount={items.length} />
            </div>
            <label>
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
              variant={view === "map" ? "default" : "outline"}
              onClick={() => changeView(view === "map" ? "list" : "map")}
              aria-pressed={view === "map"}
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
        {view === "map" ? "Ver lista" : "Ver mapa"}
      </Button>
    </div>
  );
}
