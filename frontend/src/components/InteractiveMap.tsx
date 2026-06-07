import { useEffect, useMemo, useState } from 'react';

import { motion } from 'framer-motion';
import { CloudRain, ExternalLink, Map, MapPin, Maximize2, Minimize2 } from 'lucide-react';
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap, ZoomControl } from 'react-leaflet';

import { FullscreenDialog } from '@/components/FullscreenDialog';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

import { useApp } from '@/contexts/AppContext';
import { apiBaseUrl } from '@/lib/apiClient';
import { formatLocationWithFlag } from '@/lib/location';
import { OPEN_FULLSCREEN_MAP_EVENT } from '@/lib/mapEvents';
import { cn } from '@/lib/utils';

const WEATHER_OFF = 'off';

// OpenWeather Maps 1.0 "_new" styled layers (the values are the upstream layer ids).
const WEATHER_LAYERS = [
  { value: 'precipitation_new', label: 'Precipitation' },
  { value: 'clouds_new', label: 'Clouds' },
  { value: 'temp_new', label: 'Temperature' },
  { value: 'wind_new', label: 'Wind' },
  { value: 'pressure_new', label: 'Pressure' },
] as const;

type WeatherControlsProps = {
  value: string; // a layer value, or WEATHER_OFF when the overlay is hidden
  onChange: (value: string) => void;
};

// A single dropdown that both enables the overlay and picks the layer: choosing
// a layer turns it on, choosing "No overlay" turns it off.
const WeatherControls: React.FC<WeatherControlsProps> = ({ value, onChange }) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger className="btn-panel h-9 w-[170px]">
      <CloudRain className="h-4 w-4 shrink-0" />
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value={WEATHER_OFF}>No overlay</SelectItem>
      {WEATHER_LAYERS.map((option) => (
        <SelectItem key={option.value} value={option.value}>
          {option.label}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);

// The Map/Satellite segmented toggle, shared by the inline and fullscreen headers.
const MapStyleToggle: React.FC = () => {
  const { mapStyle, setMapStyle } = useApp();
  return (
    <div className="chrome-shell-stroke inline-flex items-center gap-1 rounded-lg border border-sidebar-border/90 bg-[hsl(var(--sidebar-accent))]">
      <Button
        type="button"
        size="sm"
        variant={mapStyle === 'abstract' ? 'default' : 'ghost'}
        onClick={() => setMapStyle('abstract')}
        aria-pressed={mapStyle === 'abstract'}
        className={cn(mapStyle !== 'abstract' && 'text-sidebar-foreground')}
      >
        Map
      </Button>
      <Button
        type="button"
        size="sm"
        variant={mapStyle === 'satellite' ? 'default' : 'ghost'}
        onClick={() => setMapStyle('satellite')}
        aria-pressed={mapStyle === 'satellite'}
        className={cn(mapStyle !== 'satellite' && 'text-sidebar-foreground')}
      >
        Satellite
      </Button>
    </div>
  );
};

type MapToolbarProps = {
  // The inline and fullscreen headers differ only in their row layout, heading
  // size, and trailing action button — everything else (title, style toggle,
  // weather control) is identical, so it lives here once.
  rowClassName: string;
  headingClassName: string;
  weatherSelection: string;
  onWeatherChange: (value: string) => void;
  action: React.ReactNode;
};

const MapToolbar: React.FC<MapToolbarProps> = ({
  rowClassName,
  headingClassName,
  weatherSelection,
  onWeatherChange,
  action,
}) => (
  <div className={rowClassName}>
    <div className="flex items-center gap-2">
      <Map className="h-5 w-5 text-muted-foreground" />
      <h2 className={headingClassName}>Map</h2>
    </div>
    <div className="flex flex-wrap items-center gap-2">
      <MapStyleToggle />
      <WeatherControls value={weatherSelection} onChange={onWeatherChange} />
      {action}
    </div>
  </div>
);

// OpenWeather's official Maps 1.0 default palettes (see /api/map_legend),
// mirrored for the on-map legend. Keys are the layer ids in WEATHER_LAYERS; the
// labels are the layer's real units/range. Pressure is shown in hPa (OpenWeather
// stores it in Pa: 94000–108000 Pa = 940–1080 hPa). Clouds uses a grey ramp so
// the legend reads regardless of theme (the tiles themselves are near-white).
const WEATHER_LEGENDS: Record<string, { gradient: string; labels: string[] }> = {
  temp_new: {
    gradient: 'linear-gradient(to right, #821692, #8257DB, #208CEC, #20C4E8, #23DDDD, #C2FF28, #FFF028, #FFC228, #FC8014)',
    labels: ['-65°C', '0°C', '30°C'],
  },
  precipitation_new: {
    gradient: 'linear-gradient(to right, rgba(200,150,150,0), rgba(110,110,205,0.3), rgba(80,80,225,0.7), rgba(20,20,255,0.9))',
    labels: ['0 mm', '140 mm'],
  },
  clouds_new: {
    gradient: 'linear-gradient(to right, rgba(120,124,135,0), rgba(120,124,135,0.55), #6b7280)',
    labels: ['0%', '100%'],
  },
  wind_new: {
    gradient: 'linear-gradient(to right, rgba(238,206,204,0.3), #B364BC, #744CAC, #4600AF, #0D1126)',
    labels: ['1 m/s', '50 m/s', '200 m/s'],
  },
  pressure_new: {
    gradient: 'linear-gradient(to right, #0073FF, #B0F720, #C60000)',
    labels: ['940 hPa', '1010 hPa', '1080 hPa'],
  },
};

const WeatherLegend: React.FC<{ layer: string }> = ({ layer }) => {
  const legend = WEATHER_LEGENDS[layer];
  if (!legend) return null;
  const label = WEATHER_LAYERS.find((option) => option.value === layer)?.label ?? 'Weather';
  return (
    <div className="pointer-events-none absolute bottom-3 left-3 z-10 rounded-md border border-border/60 bg-background/85 px-2.5 py-1.5 shadow-soft-lg backdrop-blur-sm">
      <p className="mb-1 text-[11px] font-medium text-foreground">{label}</p>
      <div className="h-2 w-32 rounded-sm" style={{ background: legend.gradient }} />
      <div className="mt-0.5 flex justify-between text-[10px] text-muted-foreground">
        {legend.labels.map((tick) => (
          <span key={tick}>{tick}</span>
        ))}
      </div>
    </div>
  );
};

// Free, keyless raster tile providers (attribution required):
// - "Map" styles use CARTO Positron / Dark Matter basemaps.
// - "Satellite" uses Esri World Imagery (note the {z}/{y}/{x} order and no {r}).
const mapTileLayers = {
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution:
      'Tiles &copy; <a href="https://www.esri.com/" target="_blank" rel="noreferrer">Esri</a> &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community',
  },
  abstractLight: {
    url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>',
  },
  abstractDark: {
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>',
  },
} as const;

// Transparent Esri reference overlays (place labels + boundaries, and roads)
// layered over World Imagery to make the Satellite view a labeled "hybrid".
const esriReferenceLayers = {
  boundaries:
    'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
  transportation:
    'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}',
} as const;

type ActiveMarkerCenterProps = {
  webcamId: string;
  lat: number;
  lng: number;
};

const ActiveMarkerCenter: React.FC<ActiveMarkerCenterProps> = ({ webcamId, lat, lng }) => {
  const map = useMap();

  // Only re-center when the active station changes â€” not on every coordinate
  // update â€” so a manual pan isn't snapped back when station data refreshes.
  useEffect(() => {
    map.setView([lat, lng], map.getZoom(), { animate: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, webcamId]);

  return null;
};

const InvalidateMapSize: React.FC<{ enabled: boolean }> = ({ enabled }) => {
  const map = useMap();

  useEffect(() => {
    if (!enabled) return;

    const timeoutId = window.setTimeout(() => {
      map.invalidateSize(true);
    }, 0);

    return () => {
      window.clearTimeout(timeoutId);
    };
  }, [enabled, map]);

  return null;
};

type MapCanvasProps = {
  fullscreen?: boolean;
  weatherLayer?: string | null;
};

const MapCanvas: React.FC<MapCanvasProps> = ({ fullscreen = false, weatherLayer = null }) => {
  const { activeWebcam, webcamList, setActiveWebcam, isDarkMode, mapStyle } = useApp();

  // The base map always follows the theme + Map/Satellite toggle, including when a
  // weather overlay is on (the overlay just renders on top of it).
  const tileLayer = useMemo(() => {
    return mapStyle === 'satellite'
      ? mapTileLayers.satellite
      : isDarkMode
        ? mapTileLayers.abstractDark
        : mapTileLayers.abstractLight;
  }, [isDarkMode, mapStyle]);

  const defaultCenter: [number, number] = [
    activeWebcam.coordinates.lat,
    activeWebcam.coordinates.lng,
  ];

  return (
    <div className={cn("relative bg-muted", fullscreen ? "h-full min-h-0" : "h-[320px] sm:h-[400px]")}>
      <MapContainer
        center={defaultCenter}
        zoom={8}
        scrollWheelZoom={true}
        zoomControl={false}
        className="relative z-0 h-full w-full"
      >
        <InvalidateMapSize enabled={fullscreen} />
        <ZoomControl position="topright" />
        <TileLayer
          key={`${mapStyle}-${isDarkMode ? 'dark' : 'light'}`}
          attribution={tileLayer.attribution}
          url={tileLayer.url}
        />
        {mapStyle === 'satellite' && (
          <>
            <TileLayer key="sat-roads" url={esriReferenceLayers.transportation} zIndex={5} />
            <TileLayer key="sat-labels" url={esriReferenceLayers.boundaries} zIndex={6} />
          </>
        )}
        {weatherLayer && (
          <TileLayer
            key={`weather-${weatherLayer}`}
            url={`${apiBaseUrl}/weather/map/${weatherLayer}/{z}/{x}/{y}`}
            className={cn(
              'weather-overlay-tiles',
              // clouds_new is near-white, so darken it only on the light base.
              weatherLayer === 'clouds_new' &&
                !isDarkMode &&
                mapStyle !== 'satellite' &&
                'weather-overlay-clouds-on-light',
            )}
            opacity={1}
            zIndex={10}
            // Render a failed/empty tile as blank (1x1 transparent gif) instead of
            // leaving a stale tile from a previous zoom/layer on screen — the
            // mismatched-scale "patchwork", most visible on the mostly-transparent
            // precipitation layer. keepBuffer/updateWhenZooming reduce how many
            // stale tiles linger while the new ones load through the proxy.
            errorTileUrl="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
            keepBuffer={2}
            updateWhenZooming={false}
          />
        )}
        <ActiveMarkerCenter
          webcamId={activeWebcam.id}
          lat={activeWebcam.coordinates.lat}
          lng={activeWebcam.coordinates.lng}
        />

        {webcamList.map((webcam) => {
          const isActive = webcam.id === activeWebcam.id;
          const isOnline = webcam.isOnline;
          const pathOptions = isActive
            ? {
                color: 'hsl(var(--primary))',
                fillColor: 'hsl(var(--primary))',
                fillOpacity: 0.9,
                weight: 2,
              }
            : isOnline === true
              ? {
                  color: 'hsl(var(--success))',
                  fillColor: 'hsl(var(--success))',
                  fillOpacity: 0.85,
                  weight: 2,
                }
              : isOnline === false
                ? {
                    color: 'hsl(var(--muted-foreground))',
                    fillColor: 'hsl(var(--muted-foreground))',
                    fillOpacity: 0.55,
                    weight: 1,
                  }
                : {
                    color: 'hsl(var(--accent))',
                    fillColor: 'hsl(var(--accent))',
                    fillOpacity: 0.65,
                    weight: 1,
                  };

          return (
            <CircleMarker
              key={webcam.id}
              center={[webcam.coordinates.lat, webcam.coordinates.lng]}
              radius={isActive ? 10 : 7}
              pathOptions={pathOptions}
              eventHandlers={{
                click: () => setActiveWebcam(webcam),
              }}
            >
              <Tooltip direction="top" offset={[0, -6]} opacity={1}>
                <div className="text-xs font-medium">{webcam.name}</div>
                <div className="text-[11px] text-muted-foreground">
                  {formatLocationWithFlag(webcam.location, webcam.country, webcam.countryEmoji)}
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}
      </MapContainer>
      {weatherLayer && <WeatherLegend layer={weatherLayer} />}
    </div>
  );
};

export const InteractiveMap: React.FC = () => {
  const { activeWebcam } = useApp();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [weatherEnabled, setWeatherEnabled] = useState(false);
  const [weatherLayer, setWeatherLayer] = useState<string>(WEATHER_LAYERS[0].value);
  const activeWeatherLayer = weatherEnabled ? weatherLayer : null;
  const weatherSelection = weatherEnabled ? weatherLayer : WEATHER_OFF;
  const handleWeatherChange = (value: string) => {
    if (value === WEATHER_OFF) {
      setWeatherEnabled(false);
      return;
    }
    setWeatherLayer(value);
    setWeatherEnabled(true);
  };

  useEffect(() => {
    const openFullscreenMap = () => setIsFullscreen(true);

    window.addEventListener(OPEN_FULLSCREEN_MAP_EVENT, openFullscreenMap);
    return () => window.removeEventListener(OPEN_FULLSCREEN_MAP_EVENT, openFullscreenMap);
  }, []);

  const googleMapsUrl = `https://www.google.com/maps?q=${encodeURIComponent(
    `${activeWebcam.coordinates.lat},${activeWebcam.coordinates.lng}`
  )}`;

  return (
    <motion.div
      id="map"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.35 }}
      className="panel-shell"
    >
      <div className="relative h-full flex flex-col">
        <div className="p-6">
          <MapToolbar
            rowClassName="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
            headingClassName="text-2xl font-bold text-foreground"
            weatherSelection={weatherSelection}
            onWeatherChange={handleWeatherChange}
            action={
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsFullscreen(true)}
                className="btn-panel"
              >
                <Maximize2 className="w-4 h-4" />
                Fullscreen
              </Button>
            }
          />
        </div>

        <MapCanvas weatherLayer={activeWeatherLayer} />

        <div className="p-4 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <MapPin className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                  <p className="font-medium text-foreground">
                    {formatLocationWithFlag(activeWebcam.location, activeWebcam.country, activeWebcam.countryEmoji)}
                  </p>
                </div>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Lat: {activeWebcam.coordinates.lat.toFixed(4)} deg
                  <span className="hidden sm:inline"> | </span>
                  <br className="sm:hidden" />
                  Lon: {activeWebcam.coordinates.lng.toFixed(4)} deg
                  <span className="hidden sm:inline"> | </span>
                  <br className="sm:hidden" />
                  Alt: {activeWebcam.coordinates.altitude}m
                </p>
              </div>
            </div>

            <Button
              asChild
              variant="outline"
              size="sm"
              className="btn-panel w-full sm:w-auto flex-shrink-0"
            >
              <a href={googleMapsUrl} target="_blank" rel="noopener noreferrer">
                Open in Google Maps
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </Button>
          </div>
        </div>
      </div>
      <FullscreenDialog
        title={`${activeWebcam.name} map fullscreen`}
        open={isFullscreen}
        onOpenChange={setIsFullscreen}
        edgeToEdge
      >
        <div className="flex h-full min-h-0 flex-col">
          <div className="border-b border-border px-4 py-4 sm:px-6">
            <MapToolbar
              rowClassName="flex flex-wrap items-center justify-between gap-3"
              headingClassName="text-xl font-semibold text-foreground"
              weatherSelection={weatherSelection}
              onWeatherChange={handleWeatherChange}
              action={
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setIsFullscreen(false)}
                  className="btn-panel h-10 px-3 text-xs sm:text-sm"
                >
                  <Minimize2 className="h-4 w-4" />
                  Exit Fullscreen
                </Button>
              }
            />
          </div>
          <div className="min-h-0 flex-1">
            <MapCanvas fullscreen weatherLayer={activeWeatherLayer} />
          </div>
        </div>
      </FullscreenDialog>
    </motion.div>
  );
};


