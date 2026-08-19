import { useMemo, useState } from "react";

import { AnimatePresence, motion } from "framer-motion";
import {
  ChevronDown,
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
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { CreateStationDialog } from "@/components/CreateStationDialog";
import { TimezonePicker } from "@/components/TimezonePicker";

import { useAuth, useMapUi, usePreferences, useSidebar, useStationData } from "@/contexts/AppContext";
import { useIsMobile } from "@/hooks/use-mobile";
import { formatLocationWithFlag } from "@/lib/location";
import { STATION_LOCAL_TIMEZONE } from "@/lib/stationTimezone";
import { cn } from "@/lib/utils";

export const Sidebar: React.FC = () => {
  const { isSidebarOpen, toggleSidebar, setSidebarOpen } = useSidebar();
  const {
    isDarkMode,
    toggleDarkMode,
    setTimezone,
    timezones,
    timezonePreference,
    stationTimezone,
  } = usePreferences();
  const { isAuthenticated, authenticatedEmail, authReady, login, logout } = useAuth();
  const { activeWebcam, setActiveWebcam, webcamList } = useStationData();
  const { setMapFullscreen } = useMapUi();
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [isSettingsOpen, setIsSettingsOpen] = useState(true);
  const [isLoginFormOpen, setIsLoginFormOpen] = useState(false);
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const sidebarInsetFocusClass =
    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-primary/35 focus-visible:ring-offset-0";
  const sidebarSurfaceClass =
    "border-sidebar-border/90 bg-sidebar-accent shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)]";
  const sidebarActionButtonClass = `${sidebarSurfaceClass} text-sidebar-foreground hover:border-primary/25 hover:bg-sidebar-accent/80 ${sidebarInsetFocusClass}`;
  // Full-width "solid" variant (translucent page background) used by the New station / Logout buttons.
  const sidebarSolidActionButtonClass = `w-full justify-center gap-2 border-sidebar-border/90 bg-background/60 text-sidebar-foreground shadow-[inset_0_0_0_1px_rgba(255,255,255,0.04)] hover:border-primary/25 hover:bg-background/80 ${sidebarInsetFocusClass}`;
  const sidebarIconButtonClass = `chrome-shell-stroke rounded-lg border border-sidebar-border/80 bg-sidebar-accent/80 p-2 text-sidebar-foreground transition-colors duration-200 ease-out hover:bg-sidebar-accent ${sidebarInsetFocusClass}`;
  const sidebarFieldClass = `${sidebarSurfaceClass} ${sidebarInsetFocusClass}`;

  // "Station local" leads the list (it is also the default preference); its
  // label names the active station's resolved zone so the effect is visible.
  const timezoneOptions = useMemo(
    () => [
      {
        value: STATION_LOCAL_TIMEZONE,
        label: stationTimezone ? `Station local (${stationTimezone})` : "Station local (auto)",
      },
      ...timezones,
    ],
    [stationTimezone, timezones]
  );

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

  const handleOpenFullscreenMap = () => {
    setMapFullscreen(true);
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
        {/* Fixed-width inner column: the open/close width animation only clips
            this (via overflow-hidden) instead of re-wrapping its content per frame. */}
        <div className="flex h-full w-screen max-w-[22rem] flex-col lg:w-[320px]">
          <div className="flex items-center justify-between p-4">
            <div className="flex items-center">
              <img src="/logo.png" alt="Eagleshot" className="h-8 w-auto dark:invert dark:brightness-0" />
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
                  whileTap={{ scale: 0.98 }}
                  className={cn(
                    `chrome-shell-stroke relative w-full rounded-xl border p-3 text-left transition-colors duration-200 ease-out ${sidebarInsetFocusClass}`,
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
                        {webcam.canEdit && typeof webcam.isPublic === "boolean" && (
                          <span
                            title={webcam.isPublic ? "Public station" : "Private station"}
                            className={cn(
                              "absolute right-2 top-2 inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                              webcam.isPublic
                                ? "border-sky-400/30 bg-sky-400/15 text-sky-500"
                                : "border-[hsl(13_80%_61%_/_0.3)] bg-[hsl(13_80%_61%_/_0.1)] text-[hsl(13_80%_61%)]"
                            )}
                          >
                            {webcam.isPublic ? "Public" : "Private"}
                            {webcam.isPublic ? <Globe className="h-2.5 w-2.5" /> : <Lock className="h-2.5 w-2.5" />}
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
                  Sign in
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
                          className="absolute right-2 top-1/2 z-10 -translate-y-1/2 text-muted-foreground transition-colors duration-200 ease-out hover:text-foreground"
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
                <CreateStationDialog
                  trigger={
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className={sidebarSolidActionButtonClass}
                    >
                      <Plus className="h-3.5 w-3.5" />
                      New station
                    </Button>
                  }
                  onCreated={() => {
                    if (isMobile) setSidebarOpen(false);
                  }}
                />
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
              <ChevronDown className={cn("h-4 w-4 transition-transform duration-200 ease-out", isSettingsOpen && "rotate-180")} />
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
                    <TimezonePicker
                      value={timezonePreference}
                      options={timezoneOptions}
                      onChange={setTimezone}
                      triggerClassName={cn(
                        "text-sm hover:bg-primary/10 hover:text-sidebar-foreground",
                        sidebarFieldClass,
                      )}
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <label htmlFor="dark-mode-toggle" className="flex items-center gap-2 text-xs text-muted-foreground">
                      {isDarkMode ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
                      Dark Mode
                    </label>
                    <Switch id="dark-mode-toggle" checked={isDarkMode} onCheckedChange={toggleDarkMode} />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
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
              "chrome-shell-stroke fixed left-3 top-3 z-50 rounded-xl border border-border bg-card p-3 shadow-soft-lg transition-shadow duration-200 ease-out hover:shadow-soft-xl md:left-4 md:top-4",
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

