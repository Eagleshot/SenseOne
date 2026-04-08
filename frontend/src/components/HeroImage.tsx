import { useEffect, useRef, useState } from 'react';

import { motion } from 'framer-motion';
import {
  ArrowLeftRight,
  ImageOff,
  Images,
  Loader2,
  MapPin,
  Maximize2,
  Pause,
  Play,
  RefreshCw,
  SkipForward,
} from 'lucide-react';

import { Slider } from '@/components/ui/slider';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/dialog';
import { StatusSummary } from '@/components/StatusSummary';
import { QuickInfoCards } from '@/components/QuickInfoCards';

import { useApp } from '@/contexts/useApp';
import { formatDateTimeLabel } from '@/lib/datetime';
import { cn } from '@/lib/utils';
import { formatLocationWithFlag } from '@/lib/location';

export const HeroImage: React.FC = () => {
  const {
    activeWebcam,
    imageTimeline,
    currentImageIndex,
    setCurrentImageIndex,
    isPlaying,
    setIsPlaying,
    timezone,
    refreshImageTimeline,
  } = useApp();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isCompareOpen, setIsCompareOpen] = useState(false);
  const [compareValue, setCompareValue] = useState(50);
  const [compareIndex, setCompareIndex] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [isImageUnavailable, setIsImageUnavailable] = useState(false);
  const [displayImageUrl, setDisplayImageUrl] = useState('');
  const displayImageUrlRef = useRef('');
  const compareRef = useRef<HTMLDivElement | null>(null);
  const scrubRef = useRef<HTMLDivElement | null>(null);

  const hasTimeline = imageTimeline.length > 0;
  const currentImage = imageTimeline[currentImageIndex];
  const isLatest = hasTimeline && currentImageIndex === imageTimeline.length - 1;
  const latestIndex = Math.max(imageTimeline.length - 1, 0);
  const currentImageUrl = currentImage?.url || activeWebcam.currentImage;
  const compareImage = imageTimeline[compareIndex];
  const compareImageUrl = compareImage?.url || activeWebcam.currentImage;
  const hasDisplayImage = Boolean(displayImageUrl) && !isImageUnavailable;

  useEffect(() => {
    if (!hasTimeline) {
      setCompareIndex(0);
      return;
    }
    if (compareIndex > imageTimeline.length - 1) {
      setCompareIndex(imageTimeline.length - 1);
    }
  }, [compareIndex, hasTimeline, imageTimeline.length]);

  useEffect(() => {
    if (!currentImageUrl) {
      setDisplayImageUrl('');
      displayImageUrlRef.current = '';
      setIsImageUnavailable(true);
      return;
    }

    let cancelled = false;
    const preload = new Image();
    preload.onload = () => {
      if (cancelled) return;
      displayImageUrlRef.current = currentImageUrl;
      setDisplayImageUrl(currentImageUrl);
      setIsImageUnavailable(false);
    };
    preload.onerror = () => {
      if (cancelled) return;
      if (!displayImageUrlRef.current) {
        setIsImageUnavailable(true);
      }
    };
    preload.src = currentImageUrl;

    return () => {
      cancelled = true;
    };
  }, [currentImageUrl]);

  const updateCompareValue = (clientX: number) => {
    const rect = compareRef.current?.getBoundingClientRect();
    if (!rect) return;
    const next = ((clientX - rect.left) / rect.width) * 100;
    setCompareValue(Math.max(0, Math.min(100, next)));
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    setIsDragging(true);
    updateCompareValue(event.clientX);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    updateCompareValue(event.clientX);
  };

  const handlePointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    setIsDragging(false);
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const handlePointerCancel = (event: React.PointerEvent<HTMLDivElement>) => {
    setIsDragging(false);
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const scrubToClientX = (clientX: number) => {
    if (!hasTimeline || !scrubRef.current) return;
    const rect = scrubRef.current.getBoundingClientRect();
    if (!rect.width) return;
    const ratio = (clientX - rect.left) / rect.width;
    const clamped = Math.max(0, Math.min(1, ratio));
    const nextIndex = Math.round(clamped * latestIndex);
    setCurrentImageIndex(nextIndex);
    setIsPlaying(false);
  };

  const handleScrubPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!hasTimeline) return;
    setIsScrubbing(true);
    scrubToClientX(event.clientX);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handleScrubPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!isScrubbing) return;
    scrubToClientX(event.clientX);
  };

  const handleScrubPointerEnd = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!isScrubbing) return;
    setIsScrubbing(false);
    event.currentTarget.releasePointerCapture(event.pointerId);
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      if (!activeWebcam.id) {
        window.location.reload();
        return;
      }

      await refreshImageTimeline();
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleJumpToLatest = () => {
    setCurrentImageIndex(latestIndex);
    setIsPlaying(false);
  };

  const handleSliderChange = (value: number[]) => {
    setCurrentImageIndex(value[0]);
    setIsPlaying(false);
  };

  const controlIconButtonClass = 'transition-all border-0 bg-transparent hover:bg-transparent';
  const actionButtonClass =
    'gap-2 border-0 bg-[hsl(var(--sidebar-background))] text-foreground hover:bg-[hsl(var(--sidebar-accent))]';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl md:text-4xl font-semibold text-foreground text-balance">
              {activeWebcam.name}
            </h1>
          </div>
          <p className="text-muted-foreground flex items-center gap-1.5">
            <MapPin className="w-3 h-3" />
            {formatLocationWithFlag(activeWebcam.location, activeWebcam.country, activeWebcam.countryEmoji)}
          </p>
        </div>
        <StatusSummary />
      </div>

      {/* Hero Image */}
        <motion.div
          initial={{ opacity: 0.8 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="panel-shell"
        >
        <div className="aspect-video relative group">
            {hasDisplayImage ? (
              <img
                src={displayImageUrl}
                alt={`${activeWebcam.name} webcam view`}
                className="w-full h-full object-cover"
                onError={() => setIsImageUnavailable(true)}
            />
          ) : (
            <div className="absolute inset-0 overflow-hidden bg-[radial-gradient(circle_at_20%_20%,hsl(var(--primary)/0.22),transparent_45%),radial-gradient(circle_at_80%_0%,hsl(var(--accent)/0.18),transparent_45%),hsl(var(--background))]">
              <div className="pointer-events-none absolute -left-16 top-10 h-36 w-36 rounded-full border border-border/40 bg-background/30 blur-2xl" />
              <div className="pointer-events-none absolute -right-20 bottom-12 h-52 w-52 rounded-full border border-border/40 bg-background/30 blur-2xl" />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="mx-4 max-w-md text-center">
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-muted/50">
                    <ImageOff className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <p className="text-lg font-semibold text-foreground">No pictures available</p>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    Try refreshing later or switch to another camera.
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleRefresh}
                    disabled={isRefreshing}
                    className={cn("mt-4", actionButtonClass)}
                  >
                    <RefreshCw className={cn("w-4 h-4", isRefreshing && "animate-spin")} />
                    Refresh
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Enlarge button */}
          <Dialog>
            {hasDisplayImage && (
              <DialogTrigger asChild>
                <Button
                  variant="outline"
                  size="icon"
                  className="absolute top-4 right-4 z-10 bg-background/50 backdrop-blur-sm border border-border/50 hover:bg-background/80"
                >
                  <Maximize2 className="w-4 h-4" />
                  <span className="sr-only">Enlarge image</span>
                </Button>
              </DialogTrigger>
            )}
            <DialogContent className="max-w-[96vw] w-[96vw] max-h-[94vh] h-[94vh] p-0 overflow-hidden bg-black/90 border border-border/40 flex items-center justify-center">
              {hasDisplayImage ? (
                <img src={displayImageUrl} alt={`${activeWebcam.name} webcam view`} className="max-w-full max-h-full object-contain bg-black" />
              ) : (
                <div className="mx-4 max-w-md text-center">
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-white/10">
                    <ImageOff className="h-7 w-7 text-white/80" />
                  </div>
                  <p className="text-lg font-semibold text-white">No pictures available</p>
                  <p className="mt-2 text-sm leading-relaxed text-white/75">
                    Try another camera or check back soon.
                  </p>
                </div>
              )}
            </DialogContent>
          </Dialog>

          {/* Refreshing overlay */}
          {isRefreshing && (
            <div className="absolute inset-0 bg-background/50 backdrop-blur-sm flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-primary animate-spin" />
            </div>
          )}

          {/* Timestamp badge */}
          {currentImage && (
            <div className="absolute bottom-4 right-4 px-3 py-1.5 rounded-lg bg-background/50 backdrop-blur-sm border border-border/50 transition-all duration-200 group-hover:bottom-[5.5rem] group-focus-within:bottom-[5.5rem]">
              <p className="text-sm font-medium text-foreground">
                {formatDateTimeLabel(currentImage.timestamp, timezone)}
              </p>
            </div>
          )}

          {/* Controls Bar */}
          {hasDisplayImage && (
            <div className="absolute inset-x-4 bottom-4 rounded-2xl border border-border/50 bg-background/50 px-3 py-1 backdrop-blur-sm opacity-0 translate-y-2 transition-all duration-200 pointer-events-none group-hover:opacity-100 group-hover:translate-y-0 group-hover:pointer-events-auto group-focus-within:opacity-100 group-focus-within:translate-y-0 group-focus-within:pointer-events-auto">
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsPlaying(!isPlaying)}
                  disabled={!hasTimeline}
                  aria-label={isPlaying ? "Pause" : "Play"}
                  className={cn(
                    controlIconButtonClass,
                    isPlaying && 'text-primary-foreground'
                  )}
                >
                  {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </Button>

                <div
                  ref={scrubRef}
                  onPointerDown={handleScrubPointerDown}
                  onPointerMove={handleScrubPointerMove}
                  onPointerUp={handleScrubPointerEnd}
                  onPointerCancel={handleScrubPointerEnd}
                  className="flex-1 min-w-[200px] cursor-ew-resize"
                >
                  <Slider
                    value={[currentImageIndex]}
                    onValueChange={handleSliderChange}
                    max={latestIndex}
                    min={0}
                    step={1}
                    disabled={!hasTimeline}
                  />
                </div>

                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleJumpToLatest}
                  disabled={!hasTimeline || isLatest}
                  aria-label="Jump to latest"
                  className={controlIconButtonClass}
                >
                  <SkipForward className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </div>
      </motion.div>

      <div className="flex flex-wrap items-center gap-3">
        <QuickInfoCards />
        <div className="flex items-center gap-3 ml-auto">
          {hasDisplayImage && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              disabled={isRefreshing}
              className={actionButtonClass}
            >
              <RefreshCw className={cn("w-4 h-4", isRefreshing && "animate-spin")} />
              Refresh
            </Button>
          )}

          <Dialog
            open={isCompareOpen}
            onOpenChange={(open) => {
              setIsCompareOpen(open);
              if (open) setCompareValue(50);
              if (open && hasTimeline) setCompareIndex(latestIndex);
            }}
          >
            <DialogTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                disabled={!hasTimeline}
                className={actionButtonClass}
              >
                <Images className="w-4 h-4" />
                Compare
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-6xl w-[95vw] p-0 overflow-hidden bg-black/95 border border-border/40">
              <div
                ref={compareRef}
                className="relative aspect-video w-full bg-black select-none touch-none"
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerCancel}
              >
                <img
                  src={currentImageUrl}
                  alt={`${activeWebcam.name} selected timestamp`}
                  className="absolute inset-0 w-full h-full object-contain"
                  style={{ clipPath: `inset(0 ${100 - compareValue}% 0 0)` }}
                />
                <img
                  src={compareImageUrl}
                  alt={`${activeWebcam.name} comparison timestamp`}
                  className="absolute inset-0 w-full h-full object-contain"
                  style={{ clipPath: `inset(0 0 0 ${compareValue}%)` }}
                />
                <div
                  className="absolute inset-y-0"
                  style={{ left: `${compareValue}%` }}
                >
                  <div className="h-full w-[2px] bg-white/80 shadow-[0_0_0_1px_rgba(255,255,255,0.2)]" />
                  <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-10 w-10 rounded-full border border-white/70 bg-white text-foreground shadow-lg flex items-center justify-center">
                    <ArrowLeftRight className="h-5 w-5 text-foreground" />
                  </div>
                </div>

                {currentImage && (
                  <div className="absolute bottom-4 left-4 px-2.5 py-1 rounded-md bg-black/60 text-white text-xs">
                    {formatDateTimeLabel(currentImage.timestamp, timezone)}
                  </div>
                )}
                {compareImage && (
                  <div className="absolute bottom-4 right-4 px-2.5 py-1 rounded-md bg-black/60 text-white text-xs">
                    {formatDateTimeLabel(compareImage.timestamp, timezone)}
                  </div>
                )}
              </div>
              <div className="p-4 border-t border-border/40 bg-black/80">
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between text-xs text-white/80">
                    <span>Select right image</span>
                    <span>{compareImage ? formatDateTimeLabel(compareImage.timestamp, timezone) : "No data"}</span>
                  </div>
                  <Slider
                    value={[compareIndex]}
                    onValueChange={(value) => setCompareIndex(value[0])}
                    max={latestIndex}
                    min={0}
                    step={1}
                    disabled={!hasTimeline}
                  />
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>
    </div>
  );
};
