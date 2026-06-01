export interface Webcam {
  id: string;
  name: string;
  description?: string;
  location: string;
  country?: string;
  countryEmoji?: string;
  battery?: number | null;
  coordinates: {
    lat: number;
    lng: number;
    altitude: number;
  };
  currentImage?: string | null;
  isOnline?: boolean;
  lastUpdate?: Date | null;
  nextUpdate?: Date | null;
  isPublic?: boolean;
  firmwareVersion?: string | null;
  wakeReason?: string | null;
}

export type SensorMetricValue = number | string | null;

// A reading is a timestamp plus whatever metrics the device reported. Metric
// keys are not fixed: a station can send any field (battery, reception, soil
// moisture, …) and it is rendered from the metric catalog. Weather-derived
// values are not part of readings — they come live from the weather proxy.
export interface SensorData {
  timestamp: Date;
  [metric: string]: SensorMetricValue | Date | undefined;
}

export interface TimezoneOption {
  value: string;
  label: string;
}

