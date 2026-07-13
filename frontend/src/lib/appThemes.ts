export type ThemeVars = {
  primary: string;
  ring: string;
  chart1: string;
  chart2: string;
  chart3: string;
  sidebarRing: string;
  accent: string;
  accentForeground: string;
};

export type ColorThemeKey =
  | 'embernova'
  | 'ocean'
  | 'forest'
  | 'sunset'
  | 'auroraborealis'
  | 'polarinek';

type ThemePreset = {
  label: string;
  description: string;
  vars: ThemeVars;
};

export const colorThemePresets: Record<ColorThemeKey, ThemePreset> = {
  embernova: {
    label: 'Icelandic Ember',
    description: 'Volcanic warmth beneath arctic skies',
    vars: {
      primary: '13 80% 61%',
      ring: '13 80% 61%',
      chart1: '13 80% 61%',
      chart2: '8 92% 58%',
      chart3: '46 96% 57%',
      sidebarRing: '13 80% 61%',
      accent: '31 100% 94%',
      accentForeground: '12 80% 34%',
    },
  },
  ocean: {
    label: 'Ocean',
    description: 'Cool blue with cyan highlights',
    vars: {
      primary: '199 89% 48%',
      ring: '199 89% 48%',
      chart1: '199 89% 48%',
      chart2: '173 58% 39%',
      chart3: '214 95% 68%',
      sidebarRing: '199 89% 48%',
      accent: '203 92% 94%',
      accentForeground: '199 89% 32%',
    },
  },
  forest: {
    label: 'Forest',
    description: 'Natural greens and earth tones',
    vars: {
      primary: '146 63% 38%',
      ring: '146 63% 38%',
      chart1: '146 63% 38%',
      chart2: '83 63% 42%',
      chart3: '32 89% 54%',
      sidebarRing: '146 63% 38%',
      accent: '140 35% 93%',
      accentForeground: '146 63% 26%',
    },
  },
  sunset: {
    label: 'Vintage Sunset',
    description: 'Golden hour glow with seafoam and rose',
    vars: {
      primary: '35 100% 50%',
      ring: '35 100% 50%',
      chart1: '35 100% 50%',
      chart2: '166 60% 52%',
      chart3: '347 83% 60%',
      sidebarRing: '35 100% 50%',
      accent: '35 100% 90%',
      accentForeground: '35 70% 25%',
    },
  },
  auroraborealis: {
    label: 'Aurora Borealis',
    description: 'Purple, light green, and glacial blue',
    vars: {
      primary: '271 74% 62%',
      ring: '271 74% 62%',
      chart1: '271 74% 62%',
      chart2: '153 72% 68%',
      chart3: '199 95% 56%',
      sidebarRing: '199 95% 56%',
      accent: '188 70% 94%',
      accentForeground: '251 46% 34%',
    },
  },
  polarinek: {
    label: 'Polar Ink',
    description: 'Monochrome black and white contrast',
    vars: {
      primary: '0 0% 45%',
      ring: '0 0% 45%',
      chart1: '0 0% 45%',
      chart2: '0 0% 28%',
      chart3: '0 0% 15%',
      sidebarRing: '0 0% 45%',
      accent: '0 0% 94%',
      accentForeground: '0 0% 20%',
    },
  },
};

const cssVarMap: Record<keyof ThemeVars, string> = {
  primary: '--primary',
  ring: '--ring',
  chart1: '--chart-1',
  chart2: '--chart-2',
  chart3: '--chart-3',
  sidebarRing: '--sidebar-ring',
  accent: '--accent',
  accentForeground: '--accent-foreground',
};

const applyThemeVars = (vars: ThemeVars) => {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  for (const [key, cssVar] of Object.entries(cssVarMap) as Array<[keyof ThemeVars, string]>) {
    root.style.setProperty(cssVar, vars[key]);
  }
};

export const isColorThemeKey = (value: string | null): value is ColorThemeKey => {
  if (!value) return false;
  return value in colorThemePresets;
};

export const applyColorTheme = (theme: ColorThemeKey) => {
  applyThemeVars(colorThemePresets[theme].vars);
};

