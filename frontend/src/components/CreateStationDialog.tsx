import { useRef, useState, type ReactNode } from "react";

import { AlertTriangle, Check, Copy, Globe, Lock, RefreshCw } from "lucide-react";

import { CoordinatePicker } from "@/components/CoordinatePicker";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { reverseGeocode } from "@/api/geo";
import { useStationData } from "@/contexts/AppContext";
import { getCountryNameFromCode, getCountryOptions, getFlagEmojiFromCountryName } from "@/lib/location";
import { cn } from "@/lib/utils";

type FieldErrors = { title?: string; coordinates?: string };

type CreatedStation = { stationId: string; title: string };

type CreateStationDialogProps = {
  /** Element that opens the dialog (rendered via DialogTrigger asChild). */
  trigger: ReactNode;
  /** Called once after a station was successfully created (e.g. close the mobile sidebar). */
  onCreated?: () => void;
};

// One copyable provisioning value (station id / device secret). Shared with
// the settings panel's secret-rotation dialog.
export const ProvisioningValue: React.FC<{
  id: string;
  label: string;
  hint: string;
  value: string;
  copied: boolean;
  onCopy: () => void;
}> = ({ id, label, hint, value, copied, onCopy }) => (
  <div className="space-y-1.5">
    <label className="text-xs font-medium text-muted-foreground" htmlFor={id}>
      {label}
    </label>
    <div className="flex items-center gap-2">
      <Input
        id={id}
        readOnly
        value={value}
        onFocus={(event) => event.target.select()}
        className="font-mono text-xs"
      />
      <Button
        type="button"
        variant="outline"
        size="icon"
        onClick={onCopy}
        aria-label={`Copy ${label.toLowerCase()}`}
        className="btn-panel shrink-0"
      >
        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
      </Button>
    </div>
    <p className="text-xs text-muted-foreground">{hint}</p>
  </div>
);

/**
 * The "New station" flow: a form dialog that, on success, becomes a one-time
 * provisioning screen showing the station id and the freshly minted device
 * secret (the secret is never retrievable again, so that screen can only be
 * left through its Done button).
 */
export const CreateStationDialog: React.FC<CreateStationDialogProps> = ({ trigger, onCreated }) => {
  const { createStation, rotateDeviceSecret } = useStationData();

  const [isOpen, setIsOpen] = useState(false);
  // Form state
  const [title, setTitle] = useState("");
  const [location, setLocation] = useState("");
  const [country, setCountry] = useState("");
  const [lat, setLat] = useState<number | null>(null);
  const [lon, setLon] = useState<number | null>(null);
  const [alt, setAlt] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [createError, setCreateError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  // Post-create provisioning state
  const [created, setCreated] = useState<CreatedStation | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [secretError, setSecretError] = useState<string | null>(null);
  const [isProvisioning, setIsProvisioning] = useState(false);
  const [copiedField, setCopiedField] = useState<"id" | "secret" | null>(null);

  const titleInputRef = useRef<HTMLInputElement>(null);
  const latInputRef = useRef<HTMLInputElement>(null);
  const copyResetRef = useRef<number | undefined>(undefined);
  const geocodeAbortRef = useRef<AbortController | null>(null);
  // What the last reverse-geocode wrote, so a later map pick may replace its
  // own values but never something the user typed.
  const lastAutofillRef = useRef<{ location: string; country: string }>({ location: "", country: "" });

  const countryFlag = getFlagEmojiFromCountryName(country.trim());
  const countryOptions = getCountryOptions();

  const resetAll = () => {
    setTitle("");
    setLocation("");
    setCountry("");
    setLat(null);
    setLon(null);
    setAlt("");
    setIsPublic(true);
    setFieldErrors({});
    setCreateError(null);
    setIsCreating(false);
    setCreated(null);
    setSecret(null);
    setSecretError(null);
    setIsProvisioning(false);
    setCopiedField(null);
    geocodeAbortRef.current?.abort();
    geocodeAbortRef.current = null;
    lastAutofillRef.current = { location: "", country: "" };
  };

  // Best-effort prefill of Location/Country from the picked map point, via the
  // backend's reverse-geocoding proxy. Only fills fields that are empty or
  // still hold a previous autofill — never anything the user typed.
  const prefillFromCoordinates = async (nextLat: number, nextLon: number) => {
    geocodeAbortRef.current?.abort();
    const controller = new AbortController();
    geocodeAbortRef.current = controller;
    try {
      const result = await reverseGeocode(nextLat, nextLon, controller.signal);
      if (controller.signal.aborted || !result) return;
      const nextLocation = result.name ?? "";
      const nextCountry = result.countryCode ? getCountryNameFromCode(result.countryCode) ?? "" : "";
      const previous = lastAutofillRef.current;
      lastAutofillRef.current = { location: nextLocation, country: nextCountry };
      if (nextLocation) {
        setLocation((current) => (current === "" || current === previous.location ? nextLocation : current));
      }
      if (nextCountry) {
        setCountry((current) => (current === "" || current === previous.country ? nextCountry : current));
      }
    } catch {
      // Network errors / aborts: the user just types the fields themselves.
    }
  };

  const handleOpenChange = (open: boolean) => {
    // While the one-time secret screen is up, the dialog only closes through
    // its Done button (outside clicks / Escape are blocked on DialogContent).
    if (!open && created) return;
    setIsOpen(open);
    if (!open) resetAll();
  };

  const handleDone = () => {
    setIsOpen(false);
    resetAll();
  };

  const provisionSecret = async (stationId: string) => {
    setIsProvisioning(true);
    setSecretError(null);
    const result = await rotateDeviceSecret(stationId);
    setIsProvisioning(false);
    if (result.success && result.secret) {
      setSecret(result.secret);
    } else {
      setSecretError(result.error ?? "Unable to provision a device secret.");
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCreateError(null);

    const cleanTitle = title.trim();
    const errors: FieldErrors = {};
    if (!cleanTitle) errors.title = "Station name is required.";
    if (lat === null || lon === null) errors.coordinates = "Pick the station location on the map.";
    const altValue = alt.trim();
    const altNumber = altValue ? Number(altValue) : 0;
    if (!Number.isFinite(altNumber)) {
      errors.coordinates = "Altitude must be a valid number.";
    }
    if (errors.title || errors.coordinates) {
      setFieldErrors(errors);
      if (errors.title) titleInputRef.current?.focus();
      else latInputRef.current?.focus();
      return;
    }
    setFieldErrors({});

    setIsCreating(true);
    const result = await createStation({
      title: cleanTitle,
      location: location.trim(),
      country: country.trim(),
      countryEmoji: countryFlag ?? "",
      lat: lat as number,
      lon: lon as number,
      alt: altNumber,
      isPublic,
    });
    setIsCreating(false);

    if (!result.success || !result.stationId) {
      setCreateError(result.error ?? "Unable to create station.");
      return;
    }

    // Station exists; flip to the provisioning screen and mint its one-time
    // device secret so the camera can be flashed right away.
    setCreated({ stationId: result.stationId, title: cleanTitle });
    onCreated?.();
    await provisionSecret(result.stationId);
  };

  const handleCopy = async (field: "id" | "secret", value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(field);
      window.clearTimeout(copyResetRef.current);
      copyResetRef.current = window.setTimeout(() => setCopiedField(null), 2000);
    } catch {
      // Clipboard unavailable; the value is still selectable in the field.
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent
        className="max-h-[90dvh] max-w-2xl overflow-y-auto"
        hideCloseButton={Boolean(created)}
        onInteractOutside={(event) => created && event.preventDefault()}
        onEscapeKeyDown={(event) => created && event.preventDefault()}
      >
        {created ? (
          <div className="space-y-4">
            <DialogHeader>
              <DialogTitle>“{created.title}” is ready</DialogTitle>
              <DialogDescription>
                Flash these two values into the device firmware (e.g. <code>main.py</code>) so the
                camera can start sending data.
              </DialogDescription>
            </DialogHeader>

            <ProvisioningValue
              id="created-station-id"
              label="1. Station ID"
              hint="Set STATION_ID to this value. It is stable and never changes."
              value={created.stationId}
              copied={copiedField === "id"}
              onCopy={() => void handleCopy("id", created.stationId)}
            />

            {isProvisioning ? (
              <p className="text-sm text-muted-foreground">Generating device secret…</p>
            ) : secret ? (
              <ProvisioningValue
                id="created-station-secret"
                label="2. Device secret"
                hint="Set STATION_SECRET_B64 to this value. The device signs every request with it."
                value={secret}
                copied={copiedField === "secret"}
                onCopy={() => void handleCopy("secret", secret)}
              />
            ) : (
              <div className="space-y-2">
                <p role="alert" className="text-sm text-destructive">
                  {secretError ?? "Unable to provision a device secret."}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void provisionSecret(created.stationId)}
                  className="btn-panel"
                >
                  <RefreshCw className="h-4 w-4" />
                  Try again
                </Button>
              </div>
            )}

            {secret && (
              <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 px-3 py-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                <p className="text-xs text-foreground">
                  This secret is shown <span className="font-semibold">only once</span>. Copy it
                  now — after closing, a lost secret can only be replaced by flashing a new one to
                  the device.
                </p>
              </div>
            )}

            <DialogFooter>
              <Button type="button" onClick={handleDone} disabled={isProvisioning}>
                Done
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form className="space-y-5" onSubmit={(event) => void handleSubmit(event)}>
            <DialogHeader>
              <DialogTitle>New station</DialogTitle>
            </DialogHeader>

            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground" htmlFor="new-station-title">
                Name <span aria-hidden="true" className="text-destructive">*</span>
              </label>
              <Input
                id="new-station-title"
                ref={titleInputRef}
                value={title}
                onChange={(event) => {
                  setTitle(event.target.value);
                  if (fieldErrors.title) setFieldErrors((current) => ({ ...current, title: undefined }));
                }}
                placeholder="Ridge station"
                maxLength={120}
                disabled={isCreating}
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
                  value={location}
                  onChange={(event) => setLocation(event.target.value)}
                  placeholder="Davos"
                  maxLength={160}
                  disabled={isCreating}
                />
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium text-muted-foreground" htmlFor="new-station-country">
                  Country
                </label>
                <Select value={country} onValueChange={setCountry} disabled={isCreating}>
                  <SelectTrigger id="new-station-country">
                    <SelectValue placeholder="Select country" />
                  </SelectTrigger>
                  <SelectContent>
                    {countryOptions.map((option) => (
                      <SelectItem key={option.code} value={option.name}>
                        <span className="flex items-center gap-2">
                          {option.flag && <span aria-hidden="true">{option.flag}</span>}
                          {option.name}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-medium text-muted-foreground">
                Location on map <span aria-hidden="true" className="text-destructive">*</span>
              </label>
              <CoordinatePicker
                lat={lat}
                lon={lon}
                onChange={(nextLat, nextLon) => {
                  setLat(nextLat);
                  setLon(nextLon);
                  if (fieldErrors.coordinates) {
                    setFieldErrors((current) => ({ ...current, coordinates: undefined }));
                  }
                  void prefillFromCoordinates(nextLat, nextLon);
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
                    value={lat ?? ""}
                    onChange={(event) => setLat(event.target.value === "" ? null : Number(event.target.value))}
                    min={-90}
                    max={90}
                    step="any"
                    placeholder="47.376"
                    disabled={isCreating}
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
                    value={lon ?? ""}
                    onChange={(event) => setLon(event.target.value === "" ? null : Number(event.target.value))}
                    min={-180}
                    max={180}
                    step="any"
                    placeholder="8.541"
                    disabled={isCreating}
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
                    value={alt}
                    onChange={(event) => setAlt(event.target.value)}
                    min={-500}
                    max={9000}
                    step="any"
                    placeholder="1200"
                    disabled={isCreating}
                  />
                </div>
              </div>
              {fieldErrors.coordinates && (
                <p id="new-station-coords-error" role="alert" className="text-xs text-destructive">
                  {fieldErrors.coordinates}
                </p>
              )}
            </div>

            <fieldset className="space-y-2" disabled={isCreating}>
              <legend className="text-xs font-medium text-muted-foreground">Visibility</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  {
                    value: true,
                    icon: Globe,
                    label: "Public",
                    description: "Anyone can view this station, its images, and its history.",
                  },
                  {
                    value: false,
                    icon: Lock,
                    label: "Private",
                    description: "Only you and admins can see this station. Changeable later.",
                  },
                ].map(({ value, icon: Icon, label, description }) => {
                  const active = isPublic === value;
                  return (
                    <button
                      key={label}
                      type="button"
                      onClick={() => setIsPublic(value)}
                      aria-pressed={active}
                      className={cn(
                        "selector-tile p-3 text-left",
                        active && "border-primary bg-primary/5 shadow-soft-md"
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                          <Icon className="h-3.5 w-3.5" />
                          {label}
                        </p>
                        {active && <Check className="h-4 w-4 text-primary" />}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{description}</p>
                    </button>
                  );
                })}
              </div>
            </fieldset>

            {createError && (
              <p role="alert" className="text-sm text-destructive">
                {createError}
              </p>
            )}

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                className="btn-panel"
                onClick={() => handleOpenChange(false)}
                disabled={isCreating}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={isCreating}>
                {isCreating ? "Creating..." : "Create station"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
};
