import { useEffect, useRef, useState } from 'react';

import { motion } from 'framer-motion';
import {
  ArrowLeftRight,
  Download,
  Image as ImageIcon,
  ImageOff,
  Images,
  Loader2,
  MapPin,
  Maximize2,
  Minimize2,
  Pause,
  Play,
  RefreshCw,
  SkipForward,
} from 'lucide-react';

import { FullscreenDialog } from '@/components/FullscreenDialog';
import { Slider } from '@/components/ui/slider';
import { Button } from '@/components/ui/button';
import { DialogClose } from '@/components/ui/dialog';
import { StatusSummary } from '@/components/StatusSummary';
import { QuickInfoCards } from '@/components/QuickInfoCards';

import { usePlayback, usePreferences, useStationData } from '@/contexts/AppContext';
import { formatDateTimeLabel } from '@/lib/datetime';
import { downloadBlob } from '@/lib/download';
import { cn } from '@/lib/utils';
import { formatLocationWithFlag } from '@/lib/location';

export const HeroImage: React.FC = () => {
  const { activeWebcam, imageTimeline, isStationLoading, refreshImageTimeline } = useStationData();
  const { currentImageIndex, setCurrentImageIndex, isPlaying, setIsPlaying } = usePlayback();
  const { timezone } = usePreferences();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isCompareOpen, setIsCompareOpen] = useState(false);
  const [compareValue, setCompareValue] = useState(50);
  const [compareLeftIndex, setCompareLeftIndex] = useState(0);
  const [compareIndex, setCompareIndex] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [isScrubbing, setIsScrubbing] = useState(false);
  const [hasLoadError, setHasLoadError] = useState(false);
  const compareRef = useRef<HTMLDivElement | null>(null);

  const hasTimeline = imageTimeline.length > 0;
  const currentImage = imageTimeline[currentImageIndex];
  const isLatest = hasTimeline && currentImageIndex === imageTimeline.length - 1;
  const latestIndex = Math.max(imageTimeline.length - 1, 0);
  const currentImageUrl = currentImage?.url || activeWebcam.currentImage || '';
  const compareLeftImage = imageTimeline[compareLeftIndex];
  const compareLeftImageUrl = compareLeftImage?.url || activeWebcam.currentImage || '';
  const compareImage = imageTimeline[compareIndex];
  const compareImageUrl = compareImage?.url || activeWebcam.currentImage || '';
  const hasDisplayImage = Boolean(currentImageUrl) && !hasLoadError;

  useEffect(() => {
    if (!hasTimeline) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: clamp the compare index when the timeline shrinks
      setCompareLeftIndex(0);
      setCompareIndex(0);
      return;
    }
    if (compareLeftIndex > imageTimeline.length - 1) {
      setCompareLeftIndex(imageTimeline.length - 1);
    }
    if (compareIndex > imageTimeline.length - 1) {
      setCompareIndex(imageTimeline.length - 1);
    }
  }, [compareIndex, compareLeftIndex, hasTimeline, imageTimeline.length]);

  // Reset the error flag whenever the current image URL changes; the new
  // src will retry, and onError will set the flag again if it really fails.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: retry the load when the image URL changes
    setHasLoadError(false);
  }, [currentImageUrl]);

  // Warm the whole timeline in the background so scrubbing hits the browser
  // cache instead of fetching frame-by-frame mid-drag. Newest-first (scrubs
  // start at the live end), a few requests at a time, and paused while the
  // user is actively dragging so warming never competes with the frame they
  // are looking at.
  const warmedUrlsRef = useRef<Set<string>>(new Set());
  const isScrubbingRef = useRef(false);
  useEffect(() => {
    isScrubbingRef.current = isScrubbing || isDragging;
  }, [isScrubbing, isDragging]);
  useEffect(() => {
    if (imageTimeline.length === 0) return;
    if (warmedUrlsRef.current.size > 500) warmedUrlsRef.current.clear();
    const queue = [...imageTimeline]
      .reverse()
      .map((item) => item.url)
      .filter((url) => !warmedUrlsRef.current.has(url));
    if (queue.length === 0) return;

    let cancelled = false;
    const loadNext = () => {
      if (cancelled) return;
      if (isScrubbingRef.current) {
        window.setTimeout(loadNext, 250); // wait out the drag
        return;
      }
      const url = queue.shift();
      if (!url) return;
      warmedUrlsRef.current.add(url);
      const image = new Image();
      image.onload = loadNext;
      image.onerror = loadNext;
      image.src = url;
    };
    const CONCURRENCY = 4;
    for (let i = 0; i < CONCURRENCY; i++) loadNext();
    return () => {
      cancelled = true;
    };
  }, [imageTimeline]);

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

  const scrubToClientX = (clientX: number, track: HTMLDivElement) => {
    if (!hasTimeline) return;
    const rect = track.getBoundingClientRect();
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
    scrubToClientX(event.clientX, event.currentTarget);
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handleScrubPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!isScrubbing) return;
    scrubToClientX(event.clientX, event.currentTarget);
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

  const handleDownload = async () => {
    if (!currentImageUrl) return;
    setIsDownloading(true);
    try {
      const response = await fetch(currentImageUrl);
      const blob = await response.blob();
      const rawName = currentImageUrl.split('/').pop()?.split('?')[0] ?? '';
      let urlFilename = '';
      try {
        urlFilename = decodeURIComponent(rawName);
      } catch {
        urlFilename = rawName;
      }
      downloadBlob(blob, urlFilename || `${activeWebcam.name}.jpg`);
    } catch {
      // silently ignore download errors
    } finally {
      setIsDownloading(false);
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
  const actionButtonClass = 'btn-panel';

  return (
    <div className="space-y-4">
      {/* Header — skeletons while the initial station resolves, instead of a
          literal "Loading..." headline. */}
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        {isStationLoading ? (
          <div className="space-y-2" aria-hidden="true">
            <div className="h-9 w-64 max-w-full animate-pulse rounded-lg bg-muted md:h-10" />
            <div className="h-4 w-44 animate-pulse rounded bg-muted" />
          </div>
        ) : (
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
        )}
        {isStationLoading ? (
          <div className="h-10 w-72 max-w-full animate-pulse rounded-lg bg-muted" aria-hidden="true" />
        ) : (
          <StatusSummary />
        )}
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
                src={currentImageUrl}
                alt={`${activeWebcam.name} webcam view`}
                className="w-full h-full object-cover"
                onError={() => setHasLoadError(true)}
            />
          ) : isStationLoading ? (
            // Don't claim "No pictures available" while the station is still
            // loading — pulse instead.
            <div className="absolute inset-0 animate-pulse bg-muted/60" aria-hidden="true" />
          ) : (
            <div className="absolute inset-0 overflow-hidden bg-[radial-gradient(circle_at_20%_20%,hsl(var(--primary)/0.22),transparent_45%),radial-gradient(circle_at_80%_0%,hsl(var(--accent)/0.18),transparent_45%),hsl(var(--background))]">
              <div className="pointer-events-none absolute -left-16 top-10 h-36 w-36 rounded-full border border-border/40 bg-background/30 blur-2xl" />
              <div className="pointer-events-none absolute -right-20 bottom-12 h-52 w-52 rounded-full border border-border/40 bg-background/30 blur-2xl" />
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="mx-4 max-w-md text-center">
                  <ImageOff className="mx-auto mb-4 h-7 w-7 text-muted-foreground" />
                  <p className="text-lg font-semibold text-foreground">No pictures available</p>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    Try refreshing later or switch to another station.
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
          <FullscreenDialog
            title={`${activeWebcam.name} image fullscreen`}
            edgeToEdge
            trigger={
              hasDisplayImage ? (
                <Button
                  variant="outline"
                  size="icon"
                  className="btn-icon-panel absolute top-4 right-4 z-10"
                >
                  <Maximize2 className="w-4 h-4" />
                  <span className="sr-only">Enlarge image</span>
                </Button>
              ) : undefined
            }
          >
            <div className="flex h-full min-h-0 flex-col">
              <div className="border-b border-border px-4 py-4 sm:px-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <ImageIcon className="h-5 w-5 text-muted-foreground" />
                    <h2 className="text-xl font-semibold text-foreground">Image</h2>
                  </div>
                  <DialogClose asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="btn-panel h-10 px-3 text-xs sm:text-sm"
                    >
                      <Minimize2 className="h-4 w-4" />
                      Exit Fullscreen
                    </Button>
                  </DialogClose>
                </div>
              </div>

              <div className="group relative min-h-0 flex-1 overflow-hidden bg-black">
                {hasDisplayImage ? (
                  <>
                    <img
                      src={currentImageUrl}
                      alt=""
                      aria-hidden="true"
                      className="absolute inset-0 block h-full w-full scale-110 object-cover opacity-70 blur-2xl"
                    />
                    <div className="absolute inset-0 bg-black/25" aria-hidden="true" />
                    <img
                      src={currentImageUrl}
                      alt={`${activeWebcam.name} webcam view`}
                      className="absolute inset-0 block h-full w-full object-contain"
                    />
                  </>
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="mx-4 max-w-md text-center">
                      <ImageOff className="mx-auto mb-4 h-7 w-7 text-white/80" />
                      <p className="text-lg font-semibold text-white">No pictures available</p>
                      <p className="mt-2 text-sm leading-relaxed text-white/75">
                        Try another station or check back soon.
                      </p>
                    </div>
                  </div>
                )}

                {currentImage && (
                  <div className="absolute bottom-4 right-4 rounded-lg border border-border/50 bg-background/50 px-3 py-1.5 backdrop-blur-sm transition-all duration-200 group-hover:bottom-[5.5rem] group-focus-within:bottom-[5.5rem] [@media(pointer:coarse)]:bottom-[5.5rem]">
                    <p className="text-sm font-medium text-foreground">
                      {formatDateTimeLabel(currentImage.timestamp, timezone)}
                    </p>
                  </div>
                )}

                {hasDisplayImage && (
                  <div className="pointer-events-none absolute inset-x-4 bottom-4 translate-y-2 rounded-2xl border border-border/50 bg-background/50 px-3 py-1 opacity-0 backdrop-blur-sm transition-all duration-200 group-hover:pointer-events-auto group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:translate-y-0 group-focus-within:opacity-100 [@media(pointer:coarse)]:pointer-events-auto [@media(pointer:coarse)]:translate-y-0 [@media(pointer:coarse)]:opacity-100">
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
                        onPointerDown={handleScrubPointerDown}
                        onPointerMove={handleScrubPointerMove}
                        onPointerUp={handleScrubPointerEnd}
                        onPointerCancel={handleScrubPointerEnd}
                        className="min-w-[200px] flex-1 cursor-ew-resize"
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
            </div>
          </FullscreenDialog>

          {/* Refreshing overlay */}
          {isRefreshing && (
            <div className="absolute inset-0 bg-background/50 backdrop-blur-sm flex items-center justify-center">
              <Loader2 className="w-8 h-8 text-primary animate-spin" />
            </div>
          )}

          {/* Timestamp badge */}
          {currentImage && (
            <div className="absolute bottom-4 right-4 px-3 py-1.5 rounded-lg bg-background/50 backdrop-blur-sm border border-border/50 transition-all duration-200 group-hover:bottom-[5.5rem] group-focus-within:bottom-[5.5rem] [@media(pointer:coarse)]:bottom-[5.5rem]">
              <p className="text-sm font-medium text-foreground">
                {formatDateTimeLabel(currentImage.timestamp, timezone)}
              </p>
            </div>
          )}

          {/* Controls Bar. Touch devices have no hover: keep the controls
              permanently visible there ([@media(pointer:coarse)]), since
              scrubbing is the page's core interaction. */}
          {hasDisplayImage && (
            <div className="absolute inset-x-4 bottom-4 rounded-2xl border border-border/50 bg-background/50 px-3 py-1 backdrop-blur-sm opacity-0 translate-y-2 transition-all duration-200 pointer-events-none group-hover:opacity-100 group-hover:translate-y-0 group-hover:pointer-events-auto group-focus-within:opacity-100 group-focus-within:translate-y-0 group-focus-within:pointer-events-auto [@media(pointer:coarse)]:opacity-100 [@media(pointer:coarse)]:translate-y-0 [@media(pointer:coarse)]:pointer-events-auto">
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

          <FullscreenDialog
            title={`${activeWebcam.name} image comparison`}
            open={isCompareOpen}
            onOpenChange={(open) => {
              setIsCompareOpen(open);
              if (open) setCompareValue(50);
              if (open && hasTimeline) setCompareLeftIndex(currentImageIndex);
              if (open && hasTimeline) setCompareIndex(latestIndex);
            }}
            edgeToEdge
            trigger={
              <Button
                variant="ghost"
                size="sm"
                disabled={!hasTimeline}
                className={actionButtonClass}
              >
                <Images className="w-4 h-4" />
                Compare
              </Button>
            }
          >
            <div className="flex h-full min-h-0 flex-col">
              <div className="border-b border-border px-4 py-4 sm:px-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Images className="h-5 w-5 text-muted-foreground" />
                    <h2 className="text-xl font-semibold text-foreground">Compare Images</h2>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setIsCompareOpen(false)}
                    className="btn-panel h-10 px-3 text-xs sm:text-sm"
                  >
                    <Minimize2 className="h-4 w-4" />
                    Exit Fullscreen
                  </Button>
                </div>
              </div>

              <div
                ref={compareRef}
                className="relative min-h-0 flex-1 overflow-hidden bg-black select-none touch-none"
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerUp}
                onPointerCancel={handlePointerCancel}
              >
                <img
                  src={compareLeftImageUrl}
                  alt=""
                  aria-hidden="true"
                  className="absolute inset-0 h-full w-full scale-110 object-cover opacity-70 blur-2xl"
                  style={{ clipPath: `inset(0 ${100 - compareValue}% 0 0)` }}
                />
                <img
                  src={compareImageUrl}
                  alt=""
                  aria-hidden="true"
                  className="absolute inset-0 h-full w-full scale-110 object-cover opacity-70 blur-2xl"
                  style={{ clipPath: `inset(0 0 0 ${compareValue}%)` }}
                />
                <div className="absolute inset-0 bg-black/25" aria-hidden="true" />
                <img
                  src={compareLeftImageUrl}
                  alt={`${activeWebcam.name} selected timestamp`}
                  className="absolute inset-0 h-full w-full object-contain"
                  style={{ clipPath: `inset(0 ${100 - compareValue}% 0 0)` }}
                />
                <img
                  src={compareImageUrl}
                  alt={`${activeWebcam.name} comparison timestamp`}
                  className="absolute inset-0 h-full w-full object-contain"
                  style={{ clipPath: `inset(0 0 0 ${compareValue}%)` }}
                />
                <div
                  className="absolute inset-y-0 z-10"
                  style={{ left: `${compareValue}%` }}
                >
                  <div className="h-full w-[2px] bg-white/80 shadow-[0_0_0_1px_rgba(255,255,255,0.2)]" />
                  <div className="absolute left-1/2 top-1/2 flex h-10 w-10 -translate-x-1/2 -translate-y-1/2 cursor-ew-resize items-center justify-center rounded-full border border-white/70 bg-white text-black shadow-lg">
                    <ArrowLeftRight className="h-5 w-5 text-black" aria-hidden="true" />
                  </div>
                </div>

                {compareLeftImage && (
                  <div className="absolute bottom-4 left-4 z-10 rounded-lg border border-border/50 bg-background/50 px-3 py-1.5 backdrop-blur-sm">
                    <p className="text-sm font-medium text-foreground">
                      {formatDateTimeLabel(compareLeftImage.timestamp, timezone)}
                    </p>
                  </div>
                )}
                {compareImage && (
                  <div className="absolute bottom-4 right-4 z-10 rounded-lg border border-border/50 bg-background/50 px-3 py-1.5 backdrop-blur-sm">
                    <p className="text-sm font-medium text-foreground">
                      {formatDateTimeLabel(compareImage.timestamp, timezone)}
                    </p>
                  </div>
                )}
              </div>

              <div className="border-t border-border px-4 py-4 sm:px-6">
                <div className="flex flex-col gap-3">
                  <div className="flex items-start justify-between gap-4 text-xs text-muted-foreground">
                    <div className="flex flex-col gap-1">
                      <span>Left image</span>
                      <span className="font-medium text-foreground">
                        {compareLeftImage ? formatDateTimeLabel(compareLeftImage.timestamp, timezone) : "No data"}
                      </span>
                    </div>
                    <div className="flex flex-col items-end gap-1 text-right">
                      <span>Right image</span>
                      <span className="font-medium text-foreground">
                        {compareImage ? formatDateTimeLabel(compareImage.timestamp, timezone) : "No data"}
                      </span>
                    </div>
                  </div>
                  <Slider
                    value={[compareLeftIndex, compareIndex]}
                    onValueChange={(value) => {
                      setCompareLeftIndex(value[0]);
                      setCompareIndex(value[1]);
                    }}
                    thumbLabels={["Select left image", "Select right image"]}
                    max={latestIndex}
                    min={0}
                    step={1}
                    disabled={!hasTimeline}
                  />
                </div>
              </div>
            </div>
          </FullscreenDialog>

          {hasDisplayImage && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDownload}
              disabled={isDownloading}
              className={actionButtonClass}
            >
              <Download className={cn("w-4 h-4", isDownloading && "animate-pulse")} />
              Download
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

