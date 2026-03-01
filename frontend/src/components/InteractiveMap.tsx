import React, { useEffect, useMemo, useState, useCallback } from 'react';

import { motion } from 'framer-motion';
import { ExternalLink, Map, MapPin, Maximize2, Minimize2 } from 'lucide-react';
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap, ZoomControl } from 'react-leaflet';

import { Button } from '@/components/ui/button';

import { useApp } from '@/contexts/AppContext';
import { formatLocationWithFlag } from '@/lib/location';
import { cn } from '@/lib/utils';

const ActiveMarkerCenter: React.FC<{ lat: number; lng: number }> = ({ lat, lng }) => {
  const map = useMap();

  useEffect(() => {
    map.setView([lat, lng], map.getZoom(), { animate: true });
  }, [map, lat, lng]);

  return null;
};

export const InteractiveMap: React.FC = () => {
  const { activeWebcam, webcamList, setActiveWebcam, isDarkMode } = useApp();
  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => !prev);
  }, []);

  // Handle Escape key to exit fullscreen
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    
    if (isFullscreen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    }
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isFullscreen]);

  const googleMapsUrl = `https://www.google.com/maps?q=${encodeURIComponent(
    `${activeWebcam.coordinates.lat},${activeWebcam.coordinates.lng}`
  )}`;
  const tileLayer = useMemo(
    () =>
      isDarkMode
        ? {
            url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
          }
        : {
            url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            attribution:
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          },
    [isDarkMode]
  );

  const defaultCenter: [number, number] = [
    activeWebcam.coordinates.lat,
    activeWebcam.coordinates.lng,
  ];

  return (
    <motion.div
      id="map"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.35 }}
      className={cn(
        "panel-shell",
        isFullscreen && "fixed inset-2 sm:inset-4 z-50 rounded-2xl"
      )}
    >
      {isFullscreen && (
        <div 
          className="fixed inset-0 bg-background/80 backdrop-blur-sm z-[-1]" 
          onClick={toggleFullscreen}
        />
      )}
      <div className="relative h-full flex flex-col">
        <div className="p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <Map className="h-5 w-5 text-muted-foreground" />
              <h2 className="text-2xl font-bold text-foreground">Map</h2>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={toggleFullscreen}
              className="btn-panel"
            >
              {isFullscreen ? (
                <>
                  <Minimize2 className="w-4 h-4" />
                  Exit Fullscreen
                </>
              ) : (
                <>
                  <Maximize2 className="w-4 h-4" />
                  Fullscreen
                </>
              )}
            </Button>
          </div>
        </div>

        <div className={cn("relative bg-muted", isFullscreen ? "flex-1" : "h-[320px] sm:h-[400px]")}>
          <MapContainer
            center={defaultCenter}
            zoom={8}
            scrollWheelZoom={true}
            zoomControl={false}
            className="w-full h-full relative z-0"
          >
            <ZoomControl position="topright" />
            <TileLayer key={isDarkMode ? 'dark' : 'light'} attribution={tileLayer.attribution} url={tileLayer.url} />
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
                : isOnline
                ? {
                    color: 'hsl(var(--success))',
                    fillColor: 'hsl(var(--success))',
                    fillOpacity: 0.85,
                    weight: 2,
                  }
                : {
                    color: 'hsl(var(--muted-foreground))',
                    fillColor: 'hsl(var(--muted-foreground))',
                    fillOpacity: 0.55,
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
                    <div className="text-[11px] text-muted-foreground">{formatLocationWithFlag(webcam.location)}</div>
                  </Tooltip>
                </CircleMarker>
              );
            })}
        </MapContainer>

        </div>

        <div className="p-4 sm:p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-start gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <MapPin className="w-3 h-3 text-muted-foreground flex-shrink-0" />
                  <p className="font-medium text-foreground">{formatLocationWithFlag(activeWebcam.location)}</p>
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
              className="w-full sm:w-auto gap-2 flex-shrink-0 border-border/70 bg-[hsl(var(--sidebar-background))] text-foreground hover:bg-[hsl(var(--sidebar-accent))]"
            >
              <a href={googleMapsUrl} target="_blank" rel="noopener noreferrer">
                Open in Google Maps
                <ExternalLink className="w-3.5 h-3.5" />
              </a>
            </Button>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

