export type WeatherTheme = {
  container: string;
  overlay: string;
  iconImage?: string;
  surface: string;
  card: string;
  mutedText: string;
  foregroundText: string;
  divider: string;
  iconMuted: string;
  placeholder: string;
  linkHover: string;
};

export const baseWeatherTheme: WeatherTheme = {
  container:
    "border border-border/70 bg-secondary/90 text-foreground shadow-[0_18px_45px_rgba(0,0,0,0.336)] dark:border-transparent dark:bg-card dark:shadow-[0_24px_60px_rgba(0,0,0,0.54)]",
  overlay:
    "bg-[radial-gradient(circle_at_top,_hsl(var(--primary)/0.18),_transparent_55%)] dark:bg-[radial-gradient(circle_at_top,_hsl(var(--foreground)/0.08),_transparent_55%)]",
  surface: "bg-[hsl(var(--sidebar-background))] shadow-[inset_0_0_0_1px_hsl(var(--border)/0.6)]",
  card: "bg-[hsl(var(--sidebar-background))] shadow-[inset_0_0_0_1px_hsl(var(--border)/0.5)]",
  mutedText: "text-muted-foreground",
  foregroundText: "text-foreground",
  divider: "bg-[hsl(var(--muted-foreground))]/60",
  iconMuted: "text-muted-foreground",
  placeholder: "bg-muted/60 dark:bg-muted/50",
  linkHover: "hover:text-foreground",
};

const thunderstormTheme: WeatherTheme = {
  container:
    "border border-[rgba(109,40,217,0.24)] bg-[#0d0f1d] text-white shadow-[0_24px_80px_rgba(0,0,0,0.88)]",
  overlay:
    "bg-[radial-gradient(ellipse_at_50%_0%,_rgba(109,40,217,0.2),_transparent_58%),_radial-gradient(circle_at_82%_8%,_rgba(148,163,184,0.16),_transparent_36%)]",
  surface: "bg-[rgba(109,40,217,0.08)] shadow-[inset_0_0_0_1px_rgba(167,139,250,0.14)]",
  card: "bg-[rgba(109,40,217,0.08)] shadow-[inset_0_0_0_1px_rgba(167,139,250,0.14)]",
  mutedText: "text-[rgba(221,214,254,0.64)]",
  foregroundText: "text-white",
  divider: "bg-[rgba(167,139,250,0.2)]",
  iconMuted: "text-[rgba(221,214,254,0.64)]",
  placeholder: "bg-[rgba(109,40,217,0.14)]",
  linkHover: "hover:text-white",
};

const clearNightTheme: WeatherTheme = {
  container:
    "border border-[rgba(30,58,138,0.5)] bg-[#08101c] text-white shadow-[0_24px_60px_rgba(0,0,0,0.82)]",
  overlay: "bg-[radial-gradient(circle_at_top,_rgba(30,64,175,0.28),_transparent_55%)]",
  surface: "bg-[rgba(30,64,175,0.18)] shadow-[inset_0_0_0_1px_rgba(96,165,250,0.12)]",
  card: "bg-[rgba(30,64,175,0.18)] shadow-[inset_0_0_0_1px_rgba(96,165,250,0.12)]",
  mutedText: "text-[rgba(147,197,253,0.65)]",
  foregroundText: "text-white",
  divider: "bg-[rgba(96,165,250,0.2)]",
  iconMuted: "text-[rgba(147,197,253,0.65)]",
  placeholder: "bg-[rgba(30,64,175,0.25)]",
  linkHover: "hover:text-white",
};

const clearDayTheme: WeatherTheme = {
  container:
    "border border-[rgba(96,165,250,0.2)] bg-[#1a3a5c] text-white shadow-[0_24px_60px_rgba(0,0,0,0.55)]",
  overlay: "bg-[radial-gradient(circle_at_top,_rgba(96,165,250,0.2),_transparent_55%)]",
  surface: "bg-[rgba(96,165,250,0.1)] shadow-[inset_0_0_0_1px_rgba(147,197,253,0.2)]",
  card: "bg-[rgba(96,165,250,0.1)] shadow-[inset_0_0_0_1px_rgba(147,197,253,0.2)]",
  mutedText: "text-[rgba(186,230,253,0.7)]",
  foregroundText: "text-white",
  divider: "bg-[rgba(186,230,253,0.2)]",
  iconMuted: "text-[rgba(186,230,253,0.7)]",
  placeholder: "bg-[rgba(96,165,250,0.15)]",
  linkHover: "hover:text-white",
};

const drizzleNightTheme: WeatherTheme = {
  container:
    "border border-[rgba(71,85,105,0.5)] bg-[#0e1520] text-white shadow-[0_24px_60px_rgba(0,0,0,0.72)]",
  overlay: "bg-[radial-gradient(circle_at_top,_rgba(71,85,105,0.3),_transparent_55%)]",
  surface: "bg-[rgba(100,116,139,0.15)] shadow-[inset_0_0_0_1px_rgba(148,163,184,0.15)]",
  card: "bg-[rgba(100,116,139,0.15)] shadow-[inset_0_0_0_1px_rgba(148,163,184,0.15)]",
  mutedText: "text-[rgba(186,230,253,0.6)]",
  foregroundText: "text-white",
  divider: "bg-[rgba(148,163,184,0.25)]",
  iconMuted: "text-[rgba(186,230,253,0.6)]",
  placeholder: "bg-[rgba(71,85,105,0.25)]",
  linkHover: "hover:text-white",
};

const drizzleDayTheme: WeatherTheme = {
  container:
    "border border-[rgba(148,163,184,0.3)] bg-[#2a4060] text-white shadow-[0_18px_45px_rgba(0,0,0,0.45)]",
  overlay: "bg-[radial-gradient(circle_at_top,_rgba(148,163,184,0.2),_transparent_55%)]",
  surface: "bg-[rgba(148,163,184,0.12)] shadow-[inset_0_0_0_1px_rgba(186,230,253,0.18)]",
  card: "bg-[rgba(148,163,184,0.12)] shadow-[inset_0_0_0_1px_rgba(186,230,253,0.18)]",
  mutedText: "text-[rgba(186,230,253,0.7)]",
  foregroundText: "text-white",
  divider: "bg-[rgba(186,230,253,0.2)]",
  iconMuted: "text-[rgba(186,230,253,0.7)]",
  placeholder: "bg-[rgba(148,163,184,0.18)]",
  linkHover: "hover:text-white",
};

const cloudsDayTheme: WeatherTheme = {
  container:
    "border border-[rgba(148,163,184,0.45)] bg-[#c5d1dc] text-slate-800 shadow-[0_18px_45px_rgba(15,23,42,0.18)]",
  overlay:
    "bg-[radial-gradient(circle_at_20%_0%,_rgba(255,255,255,0.85),_transparent_48%),_radial-gradient(circle_at_85%_10%,_rgba(226,232,240,0.55),_transparent_42%)]",
  surface: "bg-white/65 shadow-[inset_0_0_0_1px_rgba(148,163,184,0.38)]",
  card: "bg-white/65 shadow-[inset_0_0_0_1px_rgba(148,163,184,0.34)]",
  mutedText: "text-slate-600",
  foregroundText: "text-slate-900",
  divider: "bg-[rgba(100,116,139,0.28)]",
  iconMuted: "text-slate-500",
  placeholder: "bg-slate-200/80",
  linkHover: "hover:text-slate-950",
};

const cloudsNightTheme: WeatherTheme = {
  container:
    "border border-[rgba(148,163,184,0.5)] bg-[#1d2634] text-white shadow-[0_24px_60px_rgba(0,0,0,0.68)]",
  overlay:
    "bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.28),_transparent_58%),_radial-gradient(circle_at_85%_12%,_rgba(226,232,240,0.2),_transparent_42%)]",
  surface: "bg-[rgba(255,255,255,0.13)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.18)]",
  card: "bg-[rgba(255,255,255,0.13)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.18)]",
  mutedText: "text-slate-200",
  foregroundText: "text-white",
  divider: "bg-[rgba(226,232,240,0.28)]",
  iconMuted: "text-slate-200",
  placeholder: "bg-[rgba(226,232,240,0.18)]",
  linkHover: "hover:text-white",
};

const atmosphereNightTheme: WeatherTheme = {
  container:
    "border border-[rgba(120,113,108,0.3)] bg-[#141210] text-white shadow-[0_24px_60px_rgba(0,0,0,0.72)]",
  overlay: "bg-[radial-gradient(circle_at_top,_rgba(120,113,108,0.18),_transparent_55%)]",
  surface: "bg-[rgba(120,113,108,0.12)] shadow-[inset_0_0_0_1px_rgba(168,162,158,0.15)]",
  card: "bg-[rgba(120,113,108,0.12)] shadow-[inset_0_0_0_1px_rgba(168,162,158,0.15)]",
  mutedText: "text-[rgba(214,211,209,0.65)]",
  foregroundText: "text-white",
  divider: "bg-[rgba(168,162,158,0.25)]",
  iconMuted: "text-[rgba(214,211,209,0.65)]",
  placeholder: "bg-[rgba(120,113,108,0.18)]",
  linkHover: "hover:text-white",
};

const atmosphereDayTheme: WeatherTheme = {
  container:
    "border border-[rgba(161,152,143,0.3)] bg-[#5a544d] text-white shadow-[0_18px_45px_rgba(0,0,0,0.42)]",
  overlay: "bg-[radial-gradient(circle_at_top,_rgba(214,211,209,0.18),_transparent_55%)]",
  iconImage: "contrast-[1.38] saturate-[1.08] brightness-[0.92] drop-shadow-[0_12px_22px_rgba(0,0,0,0.52)]",
  surface: "bg-[rgba(214,211,209,0.12)] shadow-[inset_0_0_0_1px_rgba(214,211,209,0.2)]",
  card: "bg-[rgba(214,211,209,0.12)] shadow-[inset_0_0_0_1px_rgba(214,211,209,0.2)]",
  mutedText: "text-[rgba(231,229,228,0.7)]",
  foregroundText: "text-white",
  divider: "bg-[rgba(231,229,228,0.25)]",
  iconMuted: "text-[rgba(231,229,228,0.7)]",
  placeholder: "bg-[rgba(214,211,209,0.2)]",
  linkHover: "hover:text-white",
};

const fallbackNightTheme: WeatherTheme = {
  container:
    "border border-[rgba(71,85,105,0.4)] bg-[#0e1420] text-white shadow-[0_24px_60px_rgba(0,0,0,0.72)]",
  overlay: "bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.05),_transparent_55%)]",
  surface: "bg-[rgba(255,255,255,0.08)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.12)]",
  card: "bg-[rgba(255,255,255,0.08)] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.12)]",
  mutedText: "text-[rgba(203,213,225,0.65)]",
  foregroundText: "text-white",
  divider: "bg-[rgba(100,116,139,0.4)]",
  iconMuted: "text-[rgba(203,213,225,0.65)]",
  placeholder: "bg-[rgba(71,85,105,0.35)]",
  linkHover: "hover:text-white",
};

const ATMOSPHERE_CONDITIONS = new Set([
  "mist",
  "fog",
  "haze",
  "smoke",
  "dust",
  "sand",
  "ash",
]);

export const resolveWeatherTheme = (main: string | undefined, isNight: boolean): WeatherTheme => {
  const condition = (main ?? "").toLowerCase();

  // Thunderstorm — always dramatic regardless of time of day
  if (condition === "thunderstorm" || condition === "squall" || condition === "tornado") {
    return thunderstormTheme;
  }
  if (condition === "clear") return isNight ? clearNightTheme : clearDayTheme;
  if (condition === "rain" || condition === "drizzle") {
    return isNight ? drizzleNightTheme : drizzleDayTheme;
  }
  if (condition === "clouds" || condition === "snow") return isNight ? cloudsNightTheme : cloudsDayTheme;
  if (ATMOSPHERE_CONDITIONS.has(condition)) {
    return isNight ? atmosphereNightTheme : atmosphereDayTheme;
  }
  return isNight ? fallbackNightTheme : baseWeatherTheme;
};
