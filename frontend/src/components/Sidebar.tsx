import { useMemo, useRef, useState } from "react";

import { AnimatePresence, motion } from "framer-motion";
import {
  Check,
  ChevronDown,
  Copy,
  ExternalLink,
  Eye,
  EyeOff,
  Globe,
  Lock,
  LogIn,
  LogOut,
  MapPin,
  Menu,
  Moon,
  Plus,
  Search,
  Settings,
  Sun,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { CoordinatePicker } from "@/components/CoordinatePicker";

import { useApp } from "@/contexts/AppContext";
import { useIsMobile } from "@/hooks/use-mobile";
import { formatLocationWithFlag, getCountryOptions, getFlagEmojiFromCountryName } from "@/lib/location";
import { OPEN_FULLSCREEN_MAP_EVENT } from "@/lib/mapEvents";
import { cn } from "@/lib/utils";

export const Sidebar: React.FC = () => {
  const {
    isSidebarOpen,
    toggleSidebar,
    setSidebarOpen,
    isDarkMode,
    toggleDarkMode,
    brandLogoUrl,
    timezone,
    setTimezone,
    timezones,
    activeWebcam,
    setActiveWebcam,
    webcamList,
    isAuthenticated,
    authenticatedEmail,
    authReady,
    login,
    logout,
    createStation,
    rotateDeviceSecret,
  } = useApp();
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [isSettingsOpen, setIsSettingsOpen] = useState(true);
  const [isLoginFormOpen, setIsLoginFormOpen] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [isCreateStationOpen, setIsCreateStationOpen] = useState(false);
  const [newStationTitle, setNewStationTitle] = useState("");
  const [newStationLocation, setNewStationLocation] = useState("");
  const [newStationCountry, setNewStationCountry] = useState("");
  const [newStationLat, setNewStationLat] = useState<number | null>(null);
  const [newStationLon, setNewStationLon] = useState<number | null>(null);
  const [newStationAlt, setNewStationAlt] = useState("");
  const [newStationIsPublic, setNewStationIsPublic] = useState(false);
  const [createStationError, setCreateStationError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ title?: string; coordinates?: string }>({});
  const [isCreatingStation, setIsCreatingStation] = useState(false);
  // Post-create one-time device secret view.
  const [createdStationId, setCreatedStationId] = useState<string | null>(null);
  const [createdSecret, setCreatedSecret] = useState<string | null>(null);
  const [createdSecretError, setCreatedSecretError] = useState<string | null>(null);
  const [isProvisioningSecret, setIsProvisioningSecret] = useState(false);
  const [secretCopied, setSecretCopied] = useState(false);
  const titleInputRef = useRef<HTMLInputElement>(null);
  const latInputRef = useRef<HTMLInputElement>(null);

  const newStationFlag = getFlagEmojiFromCountryName(newStationCountry.trim());
  const countryOptions = useMemo(() => getCountryOptions(), []);

  const sidebarInsetFocusClass =
    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-primary/35 focus-visible:ring-offset-0";
  const sidebarSurfaceClass =
    "border-sidebar-border/90 bg-sidebar-accent shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]";
  const sidebarActionButtonClass = `${sidebarSurfaceClass} text-sidebar-foreground hover:border-primary/25 hover:bg-sidebar-accent/80 ${sidebarInsetFocusClass}`;
  // Full-width "solid" variant (translucent page background) used by the New station / Logout buttons.
  const sidebarSolidActionButtonClass = `w-full justify-center gap-2 border-sidebar-border/90 bg-background/60 text-sidebar-foreground shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)] hover:border-primary/25 hover:bg-background/80 ${sidebarInsetFocusClass}`;
  const sidebarIconButtonClass = `chrome-shell-stroke rounded-lg border border-sidebar-border/80 bg-sidebar-accent/80 p-2 text-sidebar-foreground transition-colors hover:bg-sidebar-accent ${sidebarInsetFocusClass}`;
  const sidebarFieldClass = `${sidebarSurfaceClass} ${sidebarInsetFocusClass}`;

  const filteredWebcams = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const matched = query
      ? webcamList.filter(
          (cam) =>
            cam.name.toLowerCase().includes(query) ||
            cam.location.toLowerCase().includes(query) ||
            (cam.country?.toLowerCase().includes(query) ?? false)
        )
      : webcamList;
    // Stations the user can edit (own/admin) first, then public before private
    // within each group; stable sort keeps the backend slug order otherwise.
    return [...matched].sort((a, b) => {
      const ownerDiff = Number(Boolean(b.canEdit)) - Number(Boolean(a.canEdit));
      if (ownerDiff !== 0) return ownerDiff;
      return Number(b.isPublic !== false) - Number(a.isPublic !== false);
    });
  }, [searchQuery, webcamList]);

  const handleLoginSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoginError(null);
    setIsAuthenticating(true);

    const result = await login(loginEmail.trim(), loginPassword);
    setIsAuthenticating(false);

    if (!result.success) {
      setLoginError(result.error ?? "Unable to sign in.");
      return;
    }

    setLoginPassword("");
    setIsLoginFormOpen(false);
  };

  const handleLogout = async () => {
    await logout();
    setLoginPassword("");
    setLoginError(null);
  };

  const resetCreateStationForm = () => {
    setNewStationTitle("");
    setNewStationLocation("");
    setNewStationCountry("");
    setNewStationLat(null);
    setNewStationLon(null);
    setNewStationAlt("");
    setNewStationIsPublic(false);
    setCreateStationError(null);
    setFieldErrors({});
    setCreatedStationId(null);
    setCreatedSecret(null);
    setCreatedSecretError(null);
    setIsProvisioningSecret(false);
    setSecretCopied(false);
  };

  const handleCreateStationSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreateStationError(null);

    const title = newStationTitle.trim();
    const errors: { title?: string; coordinates?: string } = {};
    if (!title) {
      errors.title = "Station name is required.";
    }
    if (newStationLat === null || newStationLon === null) {
      errors.coordinates = "Pick the station location on the map.";
    }
    if (errors.title || errors.coordinates) {
      setFieldErrors(errors);
      if (errors.title) titleInputRef.current?.focus();
      else latInputRef.current?.focus();
      return;
    }
    setFieldErrors({});

    const altValue = newStationAlt.trim();
    const alt = altValue ? Number(altValue) : 0;
    if (!Number.isFinite(alt)) {
      setFieldErrors({ coordinates: "Altitude must be a valid number." });
      return;
    }

    setIsCreatingStation(true);
    const result = await createStation({
      title,
      location: newStationLocation.trim(),
      country: newStationCountry.trim(),
      countryEmoji: newStationFlag ?? "",
      lat: newStationLat as number,
      lon: newStationLon as number,
      alt,
      isPublic: newStationIsPublic,
    });
    setIsCreatingStation(false);

    if (!result.success || !result.stationId) {
      setCreateStationError(result.error ?? "Unable to create station.");
      return;
    }

    // Station exists; switch to the success view and provision its one-time
    // device secret so the camera can start sending data.
    setCreatedStationId(result.stationId);
    setIsProvisioningSecret(true);
    const secretResult = await rotateDeviceSecret(result.stationId);
    setIsProvisioningSecret(false);
    if (secretResult.success && secretResult.secret) {
      setCreatedSecret(secretResult.secret);
    } else {
      setCreatedSecretError(secretResult.error ?? "Unable to provision a device secret.");
    }
    if (isMobile) setSidebarOpen(false);
  };

  const handleCopySecret = async () => {
    if (!createdSecret) return;
    try {
      await navigator.clipboard.writeText(createdSecret);
      setSecretCopied(true);
      window.setTimeout(() => setSecretCopied(false), 2000);
    } catch {
      // Clipboard unavailable; the secret is still selectable in the field.
    }
  };

  const handleCloseCreateStation = () => {
    resetCreateStationForm();
    setIsCreateStationOpen(false);
  };

  const handleOpenFullscreenMap = () => {
    window.dispatchEvent(new Event(OPEN_FULLSCREEN_MAP_EVENT));
  };

  return (
    <>
      <AnimatePresence>
        {isSidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-sm lg:hidden"
            onClick={toggleSidebar}
          />
        )}
      </AnimatePresence>

      <motion.aside
        initial={false}
        animate={{
          width: isSidebarOpen ? (isMobile ? "100vw" : 320) : 0,
          opacity: isSidebarOpen ? 1 : 0,
        }}
        transition={{
          duration: 0.3,
          ease: [0.4, 0, 0.2, 1],
        }}
        className={cn(
          "chrome-shell-stroke fixed z-50 flex h-dvh max-w-[22rem] flex-col overflow-hidden border-r border-sidebar-border bg-sidebar lg:sticky lg:top-0 lg:h-screen",
          !isSidebarOpen && "pointer-events-none lg:pointer-events-auto"
        )}
      >
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center">
            <img
              src={brandLogoUrl || "/logo.png"}
              alt="Eagleshot"
              className={cn("h-8 w-auto", !brandLogoUrl && "dark:invert dark:brightness-0")}
            />
          </div>
          <button
            onClick={toggleSidebar}
            aria-label="Close sidebar"
            className={sidebarIconButtonClass}
          >
            <X className="h-5 w-5 text-sidebar-foreground" />
          </button>
        </div>

        <div className="p-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 z-10 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search stations..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              className={cn("pl-10 focus-visible:border-primary/55", sidebarFieldClass)}
            />
          </div>
        </div>

        <ScrollArea className="flex-1 px-4">
          <div className="space-y-2 pb-4">
            {filteredWebcams.map((webcam) => (
              <motion.button
                key={webcam.id}
                onClick={() => {
                  setActiveWebcam(webcam);
                  if (isMobile) setSidebarOpen(false);
                }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={cn(
                  `chrome-shell-stroke relative w-full rounded-xl border p-3 text-left transition-all duration-200 ${sidebarInsetFocusClass}`,
                  activeWebcam.id === webcam.id
                    ? "border-primary/60 bg-sidebar-accent shadow-[inset_0_0_0_1px_rgba(255,255,255,0.07),0_10px_24px_rgba(15,23,42,0.08)]"
                    : `${sidebarSurfaceClass} hover:border-primary/25 hover:bg-sidebar-accent`
                )}
              >
                <div className="flex gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 pr-16">
                      <h3 className="truncate text-sm font-medium text-sidebar-foreground">{webcam.name}</h3>
                      {/* Private badge is pinned to the default (embernova) theme orange so it stays orange across theme switches. */}
                      {webcam.canEdit && webcam.isPublic === false && (
                        <span
                          title="Private station"
                          className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-full border border-[hsl(13_80%_61%_/_0.3)] bg-[hsl(13_80%_61%_/_0.1)] px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[hsl(13_80%_61%)]"
                        >
                          Private
                          <Lock className="h-2.5 w-2.5" />
                        </span>
                      )}
                      {webcam.canEdit && webcam.isPublic === true && (
                        <span
                          title="Public station"
                          className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-full border border-sky-400/30 bg-sky-400/15 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-sky-500"
                        >
                          Public
                          <Globe className="h-2.5 w-2.5" />
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-1">
                      <MapPin className="h-3 w-3 flex-shrink-0 text-muted-foreground" />
                      <p className="truncate text-xs text-muted-foreground">
                        {formatLocationWithFlag(webcam.location, webcam.country, webcam.countryEmoji)}
                      </p>
                    </div>
                  </div>
                </div>
              </motion.button>
            ))}

            {filteredWebcams.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">No stations found.</div>}
          </div>
        </ScrollArea>

        <div className="mx-4 mb-3 h-px bg-sidebar-border/80" />

        <div className="px-4 pb-4">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleOpenFullscreenMap}
            className={cn("w-full justify-center gap-2", sidebarActionButtonClass)}
          >
            Open Map
            <ExternalLink className="h-3.5 w-3.5" />
          </Button>
        </div>

        <div className="space-y-2 px-4 pb-4">
          {!isAuthenticated && (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsLoginFormOpen((prev) => !prev)}
                disabled={!authReady || isAuthenticating}
                className={cn("w-full justify-center gap-2", sidebarActionButtonClass)}
              >
                <LogIn className="h-3.5 w-3.5" />
                Login / Sign up
              </Button>

              <p className="text-center text-xs text-muted-foreground">
                Sign in to add your own stations.
              </p>

              <AnimatePresence initial={false}>
                {isLoginFormOpen && (
                  <motion.form
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    onSubmit={handleLoginSubmit}
                    className="chrome-shell-stroke space-y-2 overflow-hidden rounded-lg border border-sidebar-border bg-sidebar-accent/70 p-3"
                  >
                    <Input
                      type="email"
                      placeholder="Email"
                      value={loginEmail}
                      onChange={(event) => setLoginEmail(event.target.value)}
                      className="h-9 bg-background/80"
                      autoComplete="email"
                      required
                    />
                    <div className="relative">
                      <Input
                        type={showPassword ? "text" : "password"}
                        placeholder="Password"
                        value={loginPassword}
                        onChange={(event) => setLoginPassword(event.target.value)}
                        className="h-9 bg-background/80 pr-9"
                        autoComplete="current-password"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((prev) => !prev)}
                        aria-label={showPassword ? "Hide password" : "Show password"}
                        className="absolute right-2 top-1/2 z-10 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {loginError && <p className="text-xs text-destructive">{loginError}</p>}
                    <Button type="submit" size="sm" disabled={isAuthenticating} className="w-full">
                      {isAuthenticating ? "Signing in..." : "Sign in"}
                    </Button>
                  </motion.form>
                )}
              </AnimatePresence>
            </>
          )}

          {isAuthenticated && (
            <div className="chrome-shell-stroke space-y-2 rounded-lg border border-sidebar-border bg-sidebar-accent/70 p-3">
              <p className="text-xs text-muted-foreground">
                Signed in as <span className="font-medium text-sidebar-foreground">{authenticatedEmail}</span>
              </p>
              <Dialog
                open={isCreateStationOpen}
                onOpenChange={(open) => {
                  setIsCreateStationOpen(open);
                  if (!open) {
                    setCreateStationError(null);
                    setFieldErrors({});
                    if (createdStationId) resetCreateStationForm();
                  }
                }}
              >
                <DialogTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className={sidebarSolidActionButtonClass}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    New station
                  </Button>
                </DialogTrigger>
                <DialogContent className="max-w-2xl">
                  <DialogHeader>
                    <DialogTitle>{createdStationId ? "Station created" : "New station"}</DialogTitle>
                  </DialogHeader>

                  {createdStationId ? (
                    <div className="space-y-4">
                      <p className="text-sm text-muted-foreground">
                        Your station is ready. Add this one-time device secret to the camera so it can start sending
                        data — it won&apos;t be shown again.
                      </p>
                      {isProvisioningSecret ? (
                        <p className="text-sm text-muted-foreground">Generating device secret…</p>
                      ) : createdSecret ? (
                        <div className="space-y-2">
                          <label className="text-xs font-medium text-muted-foreground" htmlFor="new-station-secret">
                            Device secret
                          </label>
                          <div className="flex items-center gap-2">
                            <Input
                              id="new-station-secret"
                              readOnly
                              value={createdSecret}
                              onFocus={(event) => event.target.select()}
                              className="font-mono text-xs"
                            />
                            <Button
                              type="button"
                              variant="outline"
                              size="icon"
                              onClick={handleCopySecret}
                              aria-label="Copy device secret"
                              className="btn-panel shrink-0"
                            >
                              {secretCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <p role="alert" className="text-sm text-destructive">
                          {createdSecretError ?? "Unable to provision a device secret."} You can generate one later
                          from the station settings.
                        </p>
                      )}
                      <DialogFooter>
                        <Button type="button" onClick={handleCloseCreateStation}>
                          Done
                        </Button>
                      </DialogFooter>
                    </div>
                  ) : (
                    <form className="space-y-4" onSubmit={handleCreateStationSubmit}>
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-muted-foreground" htmlFor="new-station-title">
                          Name
                        </label>
                        <Input
                          id="new-station-title"
                          ref={titleInputRef}
                          value={newStationTitle}
                          onChange={(event) => setNewStationTitle(event.target.value)}
                          placeholder="Ridge station"
                          maxLength={120}
                          required
                          aria-invalid={fieldErrors.title ? true : undefined}
                          aria-describedby={fieldErrors.title ? "new-station-title-error" : undefined}
                        />
                        {fieldErrors.title && (
                          <p id="new-station-title-error" role="alert" className="text-xs text-destructive">
                            {fieldErrors.title}
                          </p>
                        )}
                      </div>

                      <div className="grid gap-3 sm:grid-cols-[1fr_0.7fr]">
                        <div className="space-y-2">
                          <label className="text-xs font-medium text-muted-foreground" htmlFor="new-station-location">
                            Location
                          </label>
                          <Input
                            id="new-station-location"
                            value={newStationLocation}
                            onChange={(event) => setNewStationLocation(event.target.value)}
                            placeholder="Davos"
                            maxLength={160}
                          />
                        </div>
                        <div className="space-y-2">
                          <label className="text-xs font-medium text-muted-foreground" htmlFor="new-station-country">
                            Country
                          </label>
                          <Select value={newStationCountry} onValueChange={setNewStationCountry}>
                            <SelectTrigger id="new-station-country">
                              <SelectValue placeholder="Select country" />
                            </SelectTrigger>
                            <SelectContent>
                              {countryOptions.map((country) => (
                                <SelectItem key={country.code} value={country.name}>
                                  <span className="flex items-center gap-2">
                                    {country.flag && <span aria-hidden="true">{country.flag}</span>}
                                    {country.name}
                                  </span>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </div>

                      <div className="space-y-2">
                        <label className="text-xs font-medium text-muted-foreground">Location on map</label>
                        <CoordinatePicker
                          lat={newStationLat}
                          lon={newStationLon}
                          onChange={(lat, lon) => {
                            setNewStationLat(lat);
                            setNewStationLon(lon);
                          }}
                        />
                        <div className="grid gap-3 sm:grid-cols-3">
                          <div className="space-y-2">
                            <label className="text-xs font-medium text-muted-foreground" htmlFor="new-station-lat">
                              Lat
                            </label>
                            <Input
                              id="new-station-lat"
                              ref={latInputRef}
                              type="number"
                              inputMode="decimal"
                              value={newStationLat ?? ""}
                              onChange={(event) =>
                                setNewStationLat(event.target.value === "" ? null : Number(event.target.value))
                              }
                              min={-90}
                              max={90}
                              step="any"
                              placeholder="47.376"
                              aria-invalid={fieldErrors.coordinates ? true : undefined}
                              aria-describedby={fieldErrors.coordinates ? "new-station-coords-error" : undefined}
                            />
                          </div>
                          <div className="space-y-2">
                            <label className="text-xs font-medium text-muted-foreground" htmlFor="new-station-lon">
                              Lon
                            </label>
                            <Input
                              id="new-station-lon"
                              type="number"
                              inputMode="decimal"
                              value={newStationLon ?? ""}
                              onChange={(event) =>
                                setNewStationLon(event.target.value === "" ? null : Number(event.target.value))
                              }
                              min={-180}
                              max={180}
                              step="any"
                              placeholder="8.541"
                            />
                          </div>
                          <div className="space-y-2">
                            <label className="text-xs font-medium text-muted-foreground" htmlFor="new-station-alt">
                              Alt (m)
                            </label>
                            <Input
                              id="new-station-alt"
                              type="number"
                              inputMode="decimal"
                              value={newStationAlt}
                              onChange={(event) => setNewStationAlt(event.target.value)}
                              step="any"
                              placeholder="1200"
                            />
                          </div>
                        </div>
                        {fieldErrors.coordinates && (
                          <p id="new-station-coords-error" role="alert" className="text-xs text-destructive">
                            {fieldErrors.coordinates}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center justify-between rounded-md border border-border/70 bg-muted/30 px-3 py-2">
                        <label className="text-sm font-medium text-foreground" htmlFor="new-station-public">
                          Public station
                        </label>
                        <Switch
                          id="new-station-public"
                          checked={newStationIsPublic}
                          onCheckedChange={setNewStationIsPublic}
                        />
                      </div>

                      {createStationError && (
                        <p role="alert" className="text-sm text-destructive">
                          {createStationError}
                        </p>
                      )}

                      <DialogFooter>
                        <Button type="button" variant="outline" className="btn-panel" onClick={handleCloseCreateStation}>
                          Cancel
                        </Button>
                        <Button type="submit" disabled={isCreatingStation}>
                          {isCreatingStation ? "Creating..." : "Create station"}
                        </Button>
                      </DialogFooter>
                    </form>
                  )}
                </DialogContent>
              </Dialog>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleLogout}
                className={sidebarSolidActionButtonClass}
              >
                <LogOut className="h-3.5 w-3.5" />
                Logout
              </Button>
            </div>
          )}
        </div>

        <div className="p-4">
          <button
            type="button"
            onClick={() => setIsSettingsOpen((prev) => !prev)}
            aria-expanded={isSettingsOpen}
            className="flex w-full items-center justify-between text-sm font-medium text-sidebar-foreground"
          >
            <span className="flex items-center gap-2">
              <Settings className="h-4 w-4" />
              Settings
            </span>
            <ChevronDown className={cn("h-4 w-4 transition-transform", isSettingsOpen && "rotate-180")} />
          </button>

          <AnimatePresence initial={false}>
            {isSettingsOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="space-y-4 overflow-hidden pt-4"
              >
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Globe className="h-3.5 w-3.5" />
                    Timezone
                  </label>
                  <Select value={timezone} onValueChange={setTimezone}>
                    <SelectTrigger className={cn("text-sm focus:border-primary/55 data-[state=open]:border-primary/55", sidebarFieldClass)}>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {timezones.map((tz) => (
                        <SelectItem key={tz.value} value={tz.value}>
                          {tz.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-xs text-muted-foreground">
                    {isDarkMode ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
                    Dark Mode
                  </label>
                  <Switch checked={isDarkMode} onCheckedChange={toggleDarkMode} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.aside>

      <AnimatePresence>
        {!isSidebarOpen && (
          <motion.button
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            onClick={toggleSidebar}
            aria-label="Open sidebar"
            className={cn(
              "chrome-shell-stroke fixed left-3 top-3 z-50 rounded-xl border border-border bg-card p-3 shadow-soft-lg transition-all hover:shadow-soft-xl md:left-4 md:top-4",
              sidebarInsetFocusClass
            )}
          >
            <Menu className="h-5 w-5 text-foreground" />
          </motion.button>
        )}
      </AnimatePresence>
    </>
  );
};

