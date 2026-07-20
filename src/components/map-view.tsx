import { useEffect, useRef, useState } from "react";
import {
  Check,
  Crosshair,
  Heart,
  MapPin,
  Pencil,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { Link } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useApp } from "@/contexts/app-context";
import { cn } from "@/lib/utils";
import { getCriticalRestrictions, getPrimaryCadence, getPrimaryPrice } from "@/lib/listings";
import { MediaImage } from "@/components/media-image";
import type { Listing, MapPolygonPoint } from "@/types";

export interface MapBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

interface MapViewProps {
  items: Listing[];
  selectedId?: string;
  onSelect: (id: string) => void;
  fullScreen?: boolean;
  showPreview?: boolean;
  onBoundsSearch?: (bounds: MapBounds) => void;
  onPolygonSearch?: (polygon: MapPolygonPoint[]) => void;
}

const tenerifeCenter: L.LatLngExpression = [28.2916, -16.6291];
const priceLabel = (listing: Listing) => `${getPrimaryPrice(listing)} €`;
const markerIcon = (listing: Listing, selected = false) =>
  L.divIcon({
    className: "price-marker-shell",
    html: `<span class="price-marker${selected ? " is-selected" : ""}">${priceLabel(listing)}</span>`,
    iconSize: [64, 32],
    iconAnchor: [32, 32],
  });

export function LeafletMapView({
  items,
  selectedId,
  onSelect,
  fullScreen = false,
  showPreview = true,
  onBoundsSearch,
  onPolygonSearch,
}: MapViewProps) {
  const { mapPolygon, setMapPolygon, clearMapPolygon, saveCurrentSearch } =
    useApp();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const clusterRef = useRef<ReturnType<typeof L.markerClusterGroup> | null>(
    null,
  );
  const markersRef = useRef(new Map<string, L.Marker>());
  const polygonLayerRef = useRef<L.Polygon | null>(null);
  const drawingRef = useRef(false);
  const [drawing, setDrawing] = useState(false);
  const [draftPolygon, setDraftPolygon] =
    useState<MapPolygonPoint[]>(mapPolygon);
  const [bounds, setBounds] = useState<MapBounds | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [boundsDirty, setBoundsDirty] = useState(false);
  const selected = items.find((item) => item.id === selectedId);

  useEffect(() => {
    drawingRef.current = drawing;
  }, [drawing]);

  useEffect(() => {
    if (!containerRef.current) return;
    setError("");
    const map = L.map(containerRef.current, {
      zoomControl: true,
      preferCanvas: true,
      minZoom: 8,
      zoomAnimation: false,
      fadeAnimation: false,
      markerZoomAnimation: false,
    }).setView(tenerifeCenter, 9);
    mapRef.current = map;
    const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    });
    tiles.on("tileerror", () => setError("Las teselas de OpenStreetMap no respondieron. Puedes usar la lista textual."));
    tiles.addTo(map);
    const cluster = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 48,
      iconCreateFunction: (group) =>
        L.divIcon({
          className: "room-cluster-shell",
          html: `<span class="room-cluster">${group.getChildCount()}</span>`,
          iconSize: [42, 42],
        }),
    });
    clusterRef.current = cluster;
    const markers = markersRef.current;
    markers.clear();
    items.forEach((listing) => {
      const marker = L.marker(
        [listing.coordinates.lat, listing.coordinates.lng],
        {
          icon: markerIcon(listing),
          keyboard: true,
          title: `${listing.area}, ${priceLabel(listing)}`,
        },
      );
      marker.on("click", () => onSelect(listing.id));
      marker.bindTooltip(`${listing.area} · ${listing.title}`, {
        direction: "top",
        offset: [0, -28],
      });
      cluster.addLayer(marker);
      markers.set(listing.id, marker);
    });
    map.addLayer(cluster);
    if (items.length) {
      const points = items.map((item) =>
        L.latLng(item.coordinates.lat, item.coordinates.lng),
      );
      map.fitBounds(L.latLngBounds(points), {
        padding: [34, 34],
        maxZoom: 12,
        animate: false,
      });
    }
    const updateBounds = () => {
      const current = map.getBounds();
      setBounds({
        north: current.getNorth(),
        south: current.getSouth(),
        east: current.getEast(),
        west: current.getWest(),
      });
    };
    const addPoint = (event: L.LeafletMouseEvent) => {
      if (!drawingRef.current) return;
      setDraftPolygon((current) => [
        ...current,
        { lat: event.latlng.lat, lng: event.latlng.lng },
      ]);
    };
    map.on("moveend", updateBounds);
    map.on("dragend", () => setBoundsDirty(true));
    map.on("zoomend", () => { if (mapRef.current) setBoundsDirty(true); });
    map.on("click", addPoint);
    updateBounds();
    setBoundsDirty(false);
    setReady(true);
    const invalidateTimer = window.setTimeout(() => map.invalidateSize(), 0);
    return () => {
      window.clearTimeout(invalidateTimer);
      setReady(false);
      map.off();
      map.remove();
      mapRef.current = null;
      clusterRef.current = null;
      markers.clear();
    };
  }, [items, onSelect]);

  useEffect(() => {
    markersRef.current.forEach((marker, id) => {
      const listing = items.find((item) => item.id === id);
      if (listing) marker.setIcon(markerIcon(listing, id === selectedId));
    });
    const marker = selectedId ? markersRef.current.get(selectedId) : undefined;
    if (marker && mapRef.current) {
      marker.setZIndexOffset(1000);
      clusterRef.current?.zoomToShowLayer(marker, () => marker.setZIndexOffset(1000));
    }
  }, [items, selectedId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (polygonLayerRef.current) {
      polygonLayerRef.current.remove();
      polygonLayerRef.current = null;
    }
    if (draftPolygon.length >= 2) {
      polygonLayerRef.current = L.polygon(
        draftPolygon.map((point) => [point.lat, point.lng]),
        {
          color: "#006b72",
          fillColor: "#d7f20b",
          fillOpacity: 0.22,
          weight: 3,
        },
      ).addTo(map);
    }
  }, [draftPolygon]);

  const startDrawing = () => {
    setDraftPolygon([]);
    setDrawing(true);
    toast.info("Pulsa en el mapa para añadir al menos 3 puntos");
  };
  const cancelDrawing = () => {
    setDraftPolygon(mapPolygon);
    setDrawing(false);
  };
  const addKeyboardPoint = () => {
    const map = mapRef.current;
    if (!map) return;
    const center = map.getCenter();
    const offsets = [
      [-0.08, -0.1],
      [0.07, -0.08],
      [0.08, 0.1],
      [-0.06, 0.11],
    ];
    const offset = offsets[draftPolygon.length % offsets.length];
    setDraftPolygon((current) => [
      ...current,
      { lat: center.lat + offset[0], lng: center.lng + offset[1] },
    ]);
  };
  const finishDrawing = () => {
    if (draftPolygon.length < 3) return;
    setDrawing(false);
    setMapPolygon(draftPolygon);
    onPolygonSearch?.(draftPolygon);
    toast.success(`Zona aplicada: ${draftPolygon.length} puntos`);
  };
  const deletePolygon = () => {
    setDraftPolygon([]);
    clearMapPolygon();
    onPolygonSearch?.([]);
    toast.success("Zona eliminada");
  };
  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      toast.error("Tu navegador no ofrece geolocalización");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) =>
        mapRef.current?.setView([coords.latitude, coords.longitude], 13),
      () =>
        toast.error(
          "No pudimos obtener tu ubicación. Puedes mover el mapa manualmente.",
        ),
      { timeout: 7000 },
    );
  };
  const searchBounds = () => {
    if (!bounds || !onBoundsSearch) return;
    onBoundsSearch(bounds);
    setBoundsDirty(false);
    toast.success("Resultados actualizados para el área visible");
  };

  return (
    <section
      className={cn(
        "leaflet-map-shell",
        fullScreen && "leaflet-map-shell--fullscreen",
      )}
      aria-label="Mapa de habitaciones"
    >
      <div
        className="leaflet-map-canvas"
        ref={containerRef}
        aria-label="Mapa OpenStreetMap con precios aproximados"
      />
      {!ready && !error ? (
        <div className="map-loading" role="status" aria-live="polite">
          <span aria-hidden="true" />
          <strong>Cargando mapa</strong>
        </div>
      ) : null}
      {error ? (
        <div className="map-error" role="alert">
          <strong>No se pudo cargar el mapa</strong>
          <p>{error}</p>
        </div>
      ) : null}
      {fullScreen ? (
        <div
          className="map-search-tools"
          aria-label="Herramientas de búsqueda en mapa"
        >
          {onBoundsSearch ? (
            <Button onClick={searchBounds} data-dirty={boundsDirty || undefined} variant={boundsDirty ? "default" : "outline"}>
              <Search data-icon="inline-start" />
              Buscar en esta zona
            </Button>
          ) : null}
          <Button
            variant="outline"
            size="icon"
            onClick={useCurrentLocation}
            aria-label="Usar mi ubicación"
          >
            <Crosshair />
          </Button>
          {drawing ? (
            <>
              <Button variant="outline" onClick={addKeyboardPoint}>
                <MapPin data-icon="inline-start" />
                Añadir punto
              </Button>
              <Button variant="outline" onClick={cancelDrawing}>
                <X data-icon="inline-start" />
                Cancelar
              </Button>
              <Button
                disabled={draftPolygon.length < 3}
                onClick={finishDrawing}
              >
                <Check data-icon="inline-start" />
                Finalizar ({draftPolygon.length})
              </Button>
            </>
          ) : mapPolygon.length >= 3 ? (
            <>
              <Button
                variant="outline"
                onClick={() => {
                  saveCurrentSearch();
                  toast.success("Zona añadida a la búsqueda guardada");
                }}
              >
                <Heart data-icon="inline-start" />
                Guardar zona
              </Button>
              <Button variant="outline" onClick={deletePolygon}>
                <Trash2 data-icon="inline-start" />
                Eliminar zona
              </Button>
            </>
          ) : (
            <Button variant="outline" onClick={startDrawing}>
              <Pencil data-icon="inline-start" />
              Dibujar zona
            </Button>
          )}
        </div>
      ) : null}
      {selected && showPreview ? (
        <article
          className="map-selected-card"
          aria-label={`Habitación seleccionada en ${selected.area}`}
        >
          <MediaImage src={selected.images[0]} alt="" width="176" height="120" />
          <div>
            <span>{selected.area}</span>
            <strong>
              {priceLabel(selected)}/{getPrimaryCadence(selected)}
            </strong>
            <Link to={`/habitacion/${selected.id}`}>{selected.title}</Link>
            <small>{getCriticalRestrictions(selected).slice(0, 2).join(" · ")}</small>
          </div>
          <button
            type="button"
            onClick={() => onSelect("")}
            aria-label="Cerrar vista previa"
          >
            <X />
          </button>
        </article>
      ) : null}
      <div
        className="map-list-alternative"
        aria-label="Alternativa textual al mapa"
      >
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            onFocus={() => onSelect(item.id)}
            onMouseEnter={() => onSelect(item.id)}
            onClick={() => onSelect(item.id)}
            aria-pressed={item.id === selectedId}
          >
            <MapPin aria-hidden="true" />
            <span>
              <strong>{item.area}</strong>
              <small>
                {priceLabel(item)}/{getPrimaryCadence(item)}
              </small>
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
