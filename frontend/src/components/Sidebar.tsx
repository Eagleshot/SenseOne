import { useMemo, useState } from "react";

import { AnimatePresence, motion } from "framer-motion";
import {
  ChevronDown,
  ExternalLink,
  Globe,
  LogIn,
  LogOut,
  MapPin,
  Menu,
  Moon,
  Search,
  Settings,
  Sun,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

import { useApp } from "@/contexts/useApp";
import { useIsMobile } from "@/hooks/use-mobile";
import { formatLocationWithFlag } from "@/lib/location";
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
    authenticatedUsername,
    authReady,
    login,
    logout,
  } = useApp();
  const isMobile = useIsMobile();
  const [searchQuery, setSearchQuery] = useState("");
  const [isSettingsOpen, setIsSettingsOpen] = useState(true);
  const [isLoginFormOpen, setIsLoginFormOpen] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);

  const filteredWebcams = useMemo(() => {
    if (!searchQuery.trim()) return webcamList;
    const query = searchQuery.toLowerCase();
    return webcamList.filter(
      (cam) =>
        cam.name.toLowerCase().includes(query) ||
        cam.location.toLowerCase().includes(query) ||
        (cam.country?.toLowerCase().includes(query) ?? false)
    );
  }, [searchQuery, webcamList]);

  const handleLoginSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoginError(null);
    setIsAuthenticating(true);

    const result = await login(loginUsername.trim(), loginPassword);
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
          "fixed z-50 flex h-dvh max-w-[22rem] flex-col overflow-hidden border-r border-sidebar-border bg-sidebar lg:sticky lg:top-0 lg:h-screen",
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
            className="rounded-lg p-2 transition-colors hover:bg-sidebar-accent"
          >
            <X className="h-5 w-5 text-sidebar-foreground" />
          </button>
        </div>

        <div className="p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search webcams..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              className="border-sidebar-border bg-sidebar-accent pl-10"
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
                  "w-full rounded-xl border p-3 text-left transition-all duration-200",
                  activeWebcam.id === webcam.id
                    ? "border-primary/30 bg-sidebar-accent shadow-soft-md"
                    : "border-transparent bg-sidebar-accent hover:border-sidebar-border hover:bg-sidebar-accent"
                )}
              >
                <div className="flex gap-3">
                  <div className="min-w-0 flex-1">
                    <h3 className="truncate text-sm font-medium text-sidebar-foreground">{webcam.name}</h3>
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

            {filteredWebcams.length === 0 && <div className="py-8 text-center text-sm text-muted-foreground">No webcams found</div>}
          </div>
        </ScrollArea>

        <div className="mx-4 mb-3 h-px bg-sidebar-border/80" />

        <div className="px-4 pb-4">
          <Button
            asChild
            variant="outline"
            size="sm"
            className="w-full justify-center gap-2 border-sidebar-border bg-sidebar-accent text-sidebar-foreground hover:bg-sidebar-accent/80"
          >
            <a href="#map">
              Go to Map
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
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
                className="w-full justify-center gap-2 border-sidebar-border bg-sidebar-accent text-sidebar-foreground hover:bg-sidebar-accent/80"
              >
                <LogIn className="h-3.5 w-3.5" />
                Login
              </Button>

              <AnimatePresence initial={false}>
                {isLoginFormOpen && (
                  <motion.form
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    onSubmit={handleLoginSubmit}
                    className="space-y-2 overflow-hidden rounded-lg border border-sidebar-border bg-sidebar-accent/70 p-3"
                  >
                    <Input
                      type="text"
                      placeholder="Username"
                      value={loginUsername}
                      onChange={(event) => setLoginUsername(event.target.value)}
                      className="h-9 bg-background/80"
                      autoComplete="username"
                      required
                    />
                    <Input
                      type="password"
                      placeholder="Password"
                      value={loginPassword}
                      onChange={(event) => setLoginPassword(event.target.value)}
                      className="h-9 bg-background/80"
                      autoComplete="current-password"
                      required
                    />
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
            <div className="space-y-2 rounded-lg border border-sidebar-border bg-sidebar-accent/70 p-3">
              <p className="text-xs text-muted-foreground">
                Signed in as <span className="font-medium text-sidebar-foreground">{authenticatedUsername}</span>
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleLogout}
                className="w-full justify-center gap-2 border-sidebar-border bg-background/60 text-sidebar-foreground hover:bg-background/80"
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
                    <SelectTrigger className="border-sidebar-border bg-sidebar-accent text-sm">
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
            className="widget-shell-stroke fixed left-3 top-3 z-50 rounded-xl border border-border bg-card p-3 shadow-soft-lg transition-all hover:shadow-soft-xl md:left-4 md:top-4"
          >
            <Menu className="h-5 w-5 text-foreground" />
          </motion.button>
        )}
      </AnimatePresence>
    </>
  );
};
