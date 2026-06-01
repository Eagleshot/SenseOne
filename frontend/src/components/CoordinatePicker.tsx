import { useEffect } from "react";

import { LocateFixed } from "lucide-react";
import { CircleMarker, MapContainer, TileLayer, useMap, useMapEvents } from "react-leaflet";

import { Button } from "@/components/ui/button";

const TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>';
const DEFAULT_CENTER: [number, number] = [20, 0];

const round = (value: number) => Number(value.toFixed(5));

type CoordinatePickerProps = {
  lat: number | null;
  lon: number | null;
  onChange: (lat: number, lon: number) => void;
};

const ClickHandler: React.FC<{ onChange: (lat: number, lon: number) => void }> = ({ onChange }) => {
  useMapEvents({
    click(event) {
      onChange(round(event.latlng.lat), round(event.latlng.lng));
    },
  });
  return null;
};

// Recenters when the selection changes and fixes sizing when the map mounts
// inside the dialog (Leaflet measures 0×0 until the container is laid out).
const MapController: React.FC<{ lat: number | null; lon: number | null }> = ({ lat, lon }) => {
  const map = useMap();

  useEffect(() => {
    const timeoutId = window.setTimeout(() => map.invalidateSize(), 0);
    return () => window.clearTimeout(timeoutId);
  }, [map]);

  useEffect(() => {
    if (lat !== null && lon !== null) {
      map.setView([lat, lon], Math.max(map.getZoom(), 6), { animate: true });
    }
  }, [map, lat, lon]);

  return null;
};

export const CoordinatePicker: React.FC<CoordinatePickerProps> = ({ lat, lon, onChange }) => {
  const hasPoint = lat !== null && lon !== null;
  const center: [number, number] = lat !== null && lon !== null ? [lat, lon] : DEFAULT_CENTER;

  const useMyLocation = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((position) => {
      onChange(round(position.coords.latitude), round(position.coords.longitude));
    });
  };

  return (
    <div className="space-y-2">
      <div className="relative h-64 overflow-hidden rounded-md border border-input">
        <MapContainer center={center} zoom={hasPoint ? 6 : 2} scrollWheelZoom className="h-full w-full">
          <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
          <ClickHandler onChange={onChange} />
          <MapController lat={lat} lon={lon} />
          {lat !== null && lon !== null && (
            <CircleMarker
              center={[lat, lon]}
              radius={8}
              pathOptions={{
                color: "hsl(var(--primary))",
                fillColor: "hsl(var(--primary))",
                fillOpacity: 0.9,
                weight: 2,
              }}
            />
          )}
        </MapContainer>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={useMyLocation}
          className="btn-panel absolute right-2 top-2 z-[1000] h-8 gap-1.5 px-2.5 text-xs"
        >
          <LocateFixed className="h-3.5 w-3.5" />
          Use my location
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        {hasPoint
          ? `Selected: ${lat.toFixed(4)}, ${lon.toFixed(4)}`
          : "Click the map or use your location to set the coordinates."}
      </p>
    </div>
  );
};
