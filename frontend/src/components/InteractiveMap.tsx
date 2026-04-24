import { useEffect, useMemo, useState } from 'react';

import { motion } from 'framer-motion';
import { ExternalLink, Map, MapPin, Maximize2, Minimize2 } from 'lucide-react';
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap, ZoomControl } from 'react-leaflet';

import { FullscreenDialog } from '@/components/FullscreenDialog';
import { Button } from '@/components/ui/button';

import { useApp } from '@/contexts/useApp';
import { formatLocationWithFlag } from '@/lib/location';
import { cn } from '@/lib/utils';

const mapTileLayers = {
  satellite: {
    url: 'https://tiles.stadiamaps.com/tiles/alidade_satellite/{z}/{x}/{y}{r}.jpg',
    attribution:
      '&copy; <a href="https://stadiamaps.com/" target="_blank" rel="noreferrer">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank" rel="noreferrer">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> &copy; CNES, Distribution Airbus DS, &copy; Airbus DS, &copy; PlanetObserver (Contains Copernicus Data)',
  },
  abstractLight: {
    url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png',
    attribution:
      '&copy; <a href="https://stadiamaps.com/" target="_blank" rel="noreferrer">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank" rel="noreferrer">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>',
  },
  abstractDark: {
    url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
    attribution:
      '&copy; <a href="https://stadiamaps.com/" target="_blank" rel="noreferrer">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank" rel="noreferrer">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>',
  },
} as const;

const ActiveMarkerCenter: React.FC<{ lat: number; lng: number }> = ({ lat, lng }) => {
  const map = useMap();

  useEffect(() => {
    map.setView([lat, lng], map.getZoom(), { animate: true });
  }, [map, lat, lng]);

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
};

const MapCanvas: React.FC<MapCanvasProps> = ({ fullscreen = false }) => {
  const { activeWebcam, webcamList, setActiveWebcam, isDarkMode, mapStyle } = useApp();

  const tileLayer = useMemo(
    () => (mapStyle === 'satellite' ? mapTileLayers.satellite : isDarkMode ? mapTileLayers.abstractDark : mapTileLayers.abstractLight),
    [isDarkMode, mapStyle]
  );

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
        <TileLayer key={`${mapStyle}-${isDarkMode ? 'dark' : 'light'}`} attribution={tileLayer.attribution} url={tileLayer.url} />
        <ActiveMarkerCenter lat={activeWebcam.coordinates.lat} lng={activeWebcam.coordinates.lng} />

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
    </div>
  );
};

export const InteractiveMap: React.FC = () => {
  const { activeWebcam, mapStyle, setMapStyle } = useApp();
  const [isFullscreen, setIsFullscreen] = useState(false);

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
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Map className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-2xl font-bold text-foreground">Map</h2>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="chrome-shell-stroke inline-flex items-center gap-1 rounded-lg border border-input bg-background/70 p-1">
                <Button
                  type="button"
                  size="sm"
                  variant={mapStyle === 'abstract' ? 'default' : 'ghost'}
                  onClick={() => setMapStyle('abstract')}
                  aria-pressed={mapStyle === 'abstract'}
                  className={cn('h-8 px-3 text-xs sm:text-sm', mapStyle !== 'abstract' && 'text-muted-foreground')}
                >
                  Map
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={mapStyle === 'satellite' ? 'default' : 'ghost'}
                  onClick={() => setMapStyle('satellite')}
                  aria-pressed={mapStyle === 'satellite'}
                  className={cn('h-8 px-3 text-xs sm:text-sm', mapStyle !== 'satellite' && 'text-muted-foreground')}
                >
                  Satellite
                </Button>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsFullscreen(true)}
                className="btn-panel"
              >
                <Maximize2 className="w-4 h-4" />
                Fullscreen
              </Button>
            </div>
          </div>
        </div>

        <MapCanvas />

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
        contentClassName="bg-background p-0"
      >
        <div className="flex h-full min-h-0 flex-col">
          <div className="border-b border-border px-4 py-4 sm:px-6">
            <div className="flex flex-wrap items-center justify-between gap-3 pr-12">
              <div className="flex items-center gap-2">
                <Map className="h-5 w-5 text-muted-foreground" />
                <h2 className="text-xl font-semibold text-foreground">Map</h2>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <div className="chrome-shell-stroke inline-flex items-center gap-1 rounded-lg border border-input bg-background/70 p-1">
                  <Button
                    type="button"
                    size="sm"
                    variant={mapStyle === 'abstract' ? 'default' : 'ghost'}
                    onClick={() => setMapStyle('abstract')}
                    aria-pressed={mapStyle === 'abstract'}
                    className={cn('h-8 px-3 text-xs sm:text-sm', mapStyle !== 'abstract' && 'text-muted-foreground')}
                  >
                    Map
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={mapStyle === 'satellite' ? 'default' : 'ghost'}
                    onClick={() => setMapStyle('satellite')}
                    aria-pressed={mapStyle === 'satellite'}
                    className={cn('h-8 px-3 text-xs sm:text-sm', mapStyle !== 'satellite' && 'text-muted-foreground')}
                  >
                    Satellite
                  </Button>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setIsFullscreen(false)}
                  className="h-10 px-3 text-xs sm:text-sm"
                >
                  <Minimize2 className="h-4 w-4" />
                  Exit Fullscreen
                </Button>
              </div>
            </div>
          </div>
          <div className="min-h-0 flex-1">
            <MapCanvas fullscreen />
          </div>
        </div>
      </FullscreenDialog>
    </motion.div>
  );
};

