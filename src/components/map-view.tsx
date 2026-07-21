import { useEffect, useRef, useState } from "react";
import { Check, Crosshair, Heart, MapPin, Pencil, Search, Trash2, X } from "lucide-react";
import { Link } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { MediaImage } from "@/components/media-image";
import { useApp } from "@/contexts/app-context";
import { getCriticalRestrictions, getPrimaryCadence, getPrimaryPrice } from "@/lib/listings";
import { cn } from "@/lib/utils";
import type { Coordinates, Listing, MapPolygonPoint } from "@/types";

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
  fitResultsKey?: number;
}

const tenerifeCenter: L.LatLngExpression = [28.2916, -16.6291];
const tenerifeBounds = L.latLngBounds(
  [27.92, -17.02],
  [28.68, -16.01],
);
const priceLabel = (listing: Listing) => `${getPrimaryPrice(listing)} €`;
const markerIcon = (listing: Listing, selected = false) => L.divIcon({
  className: "price-marker-shell",
  html: `<span class="price-marker${selected ? " is-selected" : ""}">${priceLabel(listing)}</span>`,
  iconSize: [64, 32],
  iconAnchor: [32, 32],
});
const boundsAreEqual = (left: MapBounds, right: MapBounds) =>
  (Object.keys(left) as (keyof MapBounds)[]).every((key) => Math.abs(left[key] - right[key]) < 0.00001);

export function ApproximateLocationMap({ coordinates, onChange }: { coordinates: Coordinates; onChange: (coordinates: Coordinates) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const onChangeRef = useRef(onChange);
  const initialCoordinatesRef = useRef(coordinates);

  useEffect(() => { onChangeRef.current = onChange; }, [onChange]);
  useEffect(() => {
    if (!containerRef.current) return;
    const initial = initialCoordinatesRef.current;
    const map = L.map(containerRef.current, {
      zoomControl: true,
      minZoom: 10,
      maxZoom: 18,
      maxBounds: tenerifeBounds,
      maxBoundsViscosity: 1,
    }).setView([initial.lat, initial.lng], 14);
    const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    const marker = L.marker([initial.lat, initial.lng], { draggable: true, keyboard: true, title: "Ubicación pública aproximada" }).addTo(map);
    const handleDragEnd = () => {
      const point = marker.getLatLng();
      onChangeRef.current({ lat: point.lat, lng: point.lng });
    };
    marker.on("dragend", handleDragEnd);
    mapRef.current = map;
    markerRef.current = marker;
    const timer = window.setTimeout(() => map.invalidateSize(), 0);
    return () => {
      window.clearTimeout(timer);
      marker.off("dragend", handleDragEnd);
      tiles.off();
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
    };
  }, []);
  useEffect(() => {
    markerRef.current?.setLatLng([coordinates.lat, coordinates.lng]);
    mapRef.current?.panTo([coordinates.lat, coordinates.lng], { animate: false });
  }, [coordinates.lat, coordinates.lng]);

  return <div ref={containerRef} className="approximate-location-map" aria-label="Mapa para mover el punto público aproximado" />;
}

export function LeafletMapView({ items, selectedId, onSelect, fullScreen = false, showPreview = true, onBoundsSearch, onPolygonSearch, fitResultsKey = 0 }: MapViewProps) {
  const { mapPolygon, setMapPolygon, clearMapPolygon, saveCurrentSearch } = useApp();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const clusterRef = useRef<ReturnType<typeof L.markerClusterGroup> | null>(null);
  const markersRef = useRef(new Map<string, L.Marker>());
  const selectedMarkerRef = useRef<L.Marker | null>(null);
  const polygonLayerRef = useRef<L.Polygon | null>(null);
  const drawingRef = useRef(false);
  const onSelectRef = useRef(onSelect);
  const itemsRef = useRef(items);
  const selectedIdRef = useRef(selectedId);
  const programmaticMoveRef = useRef(false);
  const manualViewportRef = useRef(false);
  const fittedResultsRef = useRef(false);
  const previousItemIdsRef = useRef<string[]>([]);
  const lastSearchedBoundsRef = useRef<MapBounds | null>(null);
  const previousFitResultsKeyRef = useRef(fitResultsKey);
  const programmaticTimerRef = useRef<number | null>(null);
  const [drawing, setDrawing] = useState(false);
  const [draftPolygon, setDraftPolygon] = useState<MapPolygonPoint[]>(mapPolygon);
  const [bounds, setBounds] = useState<MapBounds | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [boundsDirty, setBoundsDirty] = useState(false);
  const selected = items.find((item) => item.id === selectedId);
  const itemSignature = items.map((item) => `${item.id}:${item.coordinates.lat}:${item.coordinates.lng}:${getPrimaryPrice(item)}:${item.area}:${item.title}`).join("|");
  itemsRef.current = items;
  selectedIdRef.current = selectedId;

  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);
  useEffect(() => { drawingRef.current = drawing; }, [drawing]);

  useEffect(() => {
    if (!containerRef.current) return;
    setError("");
    const map = L.map(containerRef.current, {
      zoomControl: true, preferCanvas: true, minZoom: 8,
      maxBounds: tenerifeBounds, maxBoundsViscosity: 1,
      zoomAnimation: false, fadeAnimation: false, markerZoomAnimation: false,
    }).setView(tenerifeCenter, 9);
    containerRef.current.dataset.mapInstance = String((map as L.Map & { _leaflet_id?: number })._leaflet_id ?? "ready");
    mapRef.current = map;
    const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    });
    const handleTileError = () => setError("Las teselas de OpenStreetMap no respondieron. Puedes usar la lista textual.");
    tiles.on("tileerror", handleTileError).addTo(map);
    const cluster = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 48,
      iconCreateFunction: (group) => L.divIcon({ className: "room-cluster-shell", html: `<span class="room-cluster">${group.getChildCount()}</span>`, iconSize: [42, 42] }),
    });
    clusterRef.current = cluster;
    const markers = markersRef.current;
    map.addLayer(cluster);
    const updateBounds = () => {
      const current = map.getBounds();
      const center = map.getCenter();
      if (containerRef.current) {
        containerRef.current.dataset.mapCenter = `${center.lat.toFixed(6)},${center.lng.toFixed(6)}`;
        containerRef.current.dataset.mapZoom = String(map.getZoom());
      }
      setBounds({ north: current.getNorth(), south: current.getSouth(), east: current.getEast(), west: current.getWest() });
    };
    const markManualMove = () => {
      if (programmaticMoveRef.current) return;
      manualViewportRef.current = true;
      setBoundsDirty(true);
    };
    const addPoint = (event: L.LeafletMouseEvent) => {
      if (!drawingRef.current) return;
      setDraftPolygon((current) => [...current, { lat: event.latlng.lat, lng: event.latlng.lng }]);
    };
    map.on("moveend", updateBounds);
    map.on("dragend", markManualMove);
    map.on("zoomend", markManualMove);
    map.on("click", addPoint);
    updateBounds();
    setReady(true);
    const invalidateTimer = window.setTimeout(() => map.invalidateSize(), 0);
    return () => {
      window.clearTimeout(invalidateTimer);
      if (programmaticTimerRef.current !== null) window.clearTimeout(programmaticTimerRef.current);
      programmaticTimerRef.current = null;
      programmaticMoveRef.current = false;
      manualViewportRef.current = false;
      fittedResultsRef.current = false;
      previousItemIdsRef.current = [];
      tiles.off("tileerror", handleTileError);
      map.off("moveend", updateBounds);
      map.off("dragend", markManualMove);
      map.off("zoomend", markManualMove);
      map.off("click", addPoint);
      markers.forEach((marker) => marker.off());
      selectedMarkerRef.current?.remove();
      cluster.clearLayers();
      map.remove();
      mapRef.current = null;
      clusterRef.current = null;
      markers.clear();
      selectedMarkerRef.current = null;
      polygonLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const cluster = clusterRef.current;
    if (!map || !cluster) return;
    const currentItems = itemsRef.current;
    const currentSelectedId = selectedIdRef.current;
    const markers = markersRef.current;
    const nextIds = new Set(currentItems.map((item) => item.id));
    markers.forEach((marker, id) => {
      if (nextIds.has(id)) return;
      marker.off();
      cluster.removeLayer(marker);
      markers.delete(id);
    });
    currentItems.forEach((listing) => {
      const existing = markers.get(listing.id);
      if (existing) {
        existing.setLatLng([listing.coordinates.lat, listing.coordinates.lng]);
        existing.setIcon(markerIcon(listing, listing.id === currentSelectedId));
        existing.unbindTooltip().bindTooltip(`${listing.area} · ${listing.title}`, { direction: "top", offset: [0, -28] });
        return;
      }
      const marker = L.marker([listing.coordinates.lat, listing.coordinates.lng], {
        icon: markerIcon(listing, listing.id === currentSelectedId), keyboard: true, title: `${listing.area}, ${priceLabel(listing)}`,
      });
      marker.on("click", () => onSelectRef.current(listing.id));
      marker.bindTooltip(`${listing.area} · ${listing.title}`, { direction: "top", offset: [0, -28] });
      cluster.addLayer(marker);
      markers.set(listing.id, marker);
    });
    const previousIds = previousItemIdsRef.current;
    const sharedCount = previousIds.filter((id) => nextIds.has(id)).length;
    const substantialChange = previousIds.length > 0 && sharedCount / Math.max(previousIds.length, currentItems.length, 1) < 0.5;
    if (currentItems.length && (!fittedResultsRef.current || (substantialChange && !manualViewportRef.current))) {
      programmaticMoveRef.current = true;
      map.fitBounds(L.latLngBounds(currentItems.map((item) => L.latLng(item.coordinates.lat, item.coordinates.lng))), { padding: [34, 34], maxZoom: 12, animate: false });
      fittedResultsRef.current = true;
      if (programmaticTimerRef.current !== null) window.clearTimeout(programmaticTimerRef.current);
      programmaticTimerRef.current = window.setTimeout(() => { programmaticMoveRef.current = false; }, 0);
    }
    previousItemIdsRef.current = [...nextIds];
  }, [itemSignature]);

  useEffect(() => {
    const previous = previousFitResultsKeyRef.current;
    previousFitResultsKeyRef.current = fitResultsKey;
    if (previous === fitResultsKey || fitResultsKey !== 0 || !mapRef.current || !itemsRef.current.length) return;
    manualViewportRef.current = false;
    programmaticMoveRef.current = true;
    mapRef.current.fitBounds(L.latLngBounds(itemsRef.current.map((item) => L.latLng(item.coordinates.lat, item.coordinates.lng))), { padding: [34, 34], maxZoom: 12, animate: false });
    if (programmaticTimerRef.current !== null) window.clearTimeout(programmaticTimerRef.current);
    programmaticTimerRef.current = window.setTimeout(() => { programmaticMoveRef.current = false; }, 0);
  }, [fitResultsKey]);

  useEffect(() => {
    const listings = new Map(itemsRef.current.map((item) => [item.id, item]));
    markersRef.current.forEach((marker, id) => {
      const listing = listings.get(id);
      if (listing) marker.setIcon(markerIcon(listing, id === selectedId));
      marker.setZIndexOffset(id === selectedId ? 1000 : 0);
    });
    selectedMarkerRef.current?.remove();
    selectedMarkerRef.current = null;
    const selectedListing = selectedId ? listings.get(selectedId) : undefined;
    if (selectedListing && mapRef.current) {
      const overlay = L.marker([selectedListing.coordinates.lat, selectedListing.coordinates.lng], {
        icon: markerIcon(selectedListing, true), keyboard: true, title: `${selectedListing.area}, ${priceLabel(selectedListing)}`,
        zIndexOffset: 2000,
      });
      overlay.on("click", () => onSelectRef.current(selectedListing.id));
      overlay.addTo(mapRef.current);
      selectedMarkerRef.current = overlay;
    }
    return () => {
      selectedMarkerRef.current?.remove();
      selectedMarkerRef.current = null;
    };
  }, [itemSignature, selectedId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    polygonLayerRef.current?.remove();
    polygonLayerRef.current = null;
    if (draftPolygon.length >= 2) {
      polygonLayerRef.current = L.polygon(draftPolygon.map((point) => [point.lat, point.lng]), {
        color: "#006b72", fillColor: "#d7f20b", fillOpacity: 0.22, weight: 3,
      }).addTo(map);
    }
    return () => {
      polygonLayerRef.current?.remove();
      polygonLayerRef.current = null;
    };
  }, [draftPolygon]);

  const startDrawing = () => { setDraftPolygon([]); setDrawing(true); toast.info("Pulsa en el mapa para añadir al menos 3 puntos"); };
  const cancelDrawing = () => { setDraftPolygon(mapPolygon); setDrawing(false); };
  const addKeyboardPoint = () => {
    const map = mapRef.current;
    if (!map) return;
    const center = map.getCenter();
    const offsets = [[-0.08, -0.1], [0.07, -0.08], [0.08, 0.1], [-0.06, 0.11]];
    const offset = offsets[draftPolygon.length % offsets.length];
    setDraftPolygon((current) => [...current, { lat: center.lat + offset[0], lng: center.lng + offset[1] }]);
  };
  const finishDrawing = () => {
    if (draftPolygon.length < 3) return;
    setDrawing(false); setMapPolygon(draftPolygon); onPolygonSearch?.(draftPolygon);
    toast.success(`Zona aplicada: ${draftPolygon.length} puntos`);
  };
  const deletePolygon = () => { setDraftPolygon([]); clearMapPolygon(); onPolygonSearch?.([]); toast.success("Zona eliminada"); };
  const useCurrentLocation = () => {
    if (!navigator.geolocation) { toast.error("Tu navegador no ofrece geolocalización"); return; }
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      mapRef.current?.setView([coords.latitude, coords.longitude], 13);
      manualViewportRef.current = true;
      setBoundsDirty(true);
    }, () => toast.error("No pudimos obtener tu ubicación. Puedes mover el mapa manualmente."), { timeout: 7000 });
  };
  const searchBounds = () => {
    if (!bounds || !onBoundsSearch || !boundsDirty) return;
    if (lastSearchedBoundsRef.current && boundsAreEqual(bounds, lastSearchedBoundsRef.current)) { setBoundsDirty(false); return; }
    onBoundsSearch(bounds);
    lastSearchedBoundsRef.current = bounds;
    setBoundsDirty(false);
    toast.success("Resultados actualizados para el área visible");
  };

  return (
    <section className={cn("leaflet-map-shell", fullScreen && "leaflet-map-shell--fullscreen")} aria-label="Mapa de habitaciones">
      <div className="leaflet-map-canvas" ref={containerRef} aria-label="Mapa OpenStreetMap con precios aproximados" />
      {!ready && !error ? <div className="map-loading" role="status" aria-live="polite"><span aria-hidden="true" /><strong>Cargando mapa</strong></div> : null}
      {error ? <div className="map-error" role="alert"><strong>No se pudo cargar el mapa</strong><p>{error}</p></div> : null}
      {fullScreen ? (
        <div className="map-search-tools" aria-label="Herramientas de búsqueda en mapa">
          {onBoundsSearch ? <Button onClick={searchBounds} disabled={!boundsDirty || !bounds} aria-disabled={!boundsDirty || !bounds} data-dirty={boundsDirty || undefined} variant={boundsDirty ? "default" : "outline"}><Search data-icon="inline-start" />Buscar en esta zona</Button> : null}
          <Button variant="outline" size="icon" onClick={useCurrentLocation} aria-label="Usar mi ubicación"><Crosshair /></Button>
          {drawing ? <>
            <Button variant="outline" onClick={addKeyboardPoint}><MapPin data-icon="inline-start" />Añadir punto</Button>
            <Button variant="outline" onClick={cancelDrawing}><X data-icon="inline-start" />Cancelar</Button>
            <Button disabled={draftPolygon.length < 3} onClick={finishDrawing}><Check data-icon="inline-start" />Finalizar ({draftPolygon.length})</Button>
          </> : mapPolygon.length >= 3 ? <>
            <Button variant="outline" onClick={() => { saveCurrentSearch(); toast.success("Zona añadida a la búsqueda guardada"); }}><Heart data-icon="inline-start" />Guardar zona</Button>
            <Button variant="outline" onClick={deletePolygon}><Trash2 data-icon="inline-start" />Eliminar zona</Button>
          </> : <Button variant="outline" onClick={startDrawing}><Pencil data-icon="inline-start" />Dibujar zona</Button>}
        </div>
      ) : null}
      {selected && showPreview ? (
        <article className="map-selected-card" aria-label={`Habitación seleccionada en ${selected.area}`}>
          <MediaImage src={selected.images[0]} alt="" width="176" height="120" />
          <div><span>{selected.area}</span><strong>{priceLabel(selected)}/{getPrimaryCadence(selected)}</strong><Link to={`/habitacion/${selected.id}`}>{selected.title}</Link><small>{getCriticalRestrictions(selected).slice(0, 2).join(" · ")}</small></div>
          <button type="button" onClick={() => onSelect("")} aria-label="Cerrar vista previa"><X /></button>
        </article>
      ) : null}
      <div className="map-list-alternative" aria-label="Alternativa textual al mapa">
        {items.map((item) => <button key={item.id} type="button" onFocus={() => onSelect(item.id)} onMouseEnter={() => onSelect(item.id)} onClick={() => onSelect(item.id)} aria-pressed={item.id === selectedId}><MapPin aria-hidden="true" /><span><strong>{item.area}</strong><small>{priceLabel(item)}/{getPrimaryCadence(item)}</small></span></button>)}
      </div>
    </section>
  );
}
