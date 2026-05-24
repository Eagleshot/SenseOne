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
}

export interface SensorData {
  timestamp: Date;
  temperature: number | null;
  humidity: number | null;
  pressure: number | null;
  battery: number | null;
  windSpeed: number | null;
  windDirection: number | null;
  visibility: number | null;
  uvIndex: number | null;
  dewPoint: number | null;
  feelsLike: number | null;
  voltage?: number | null;
  deviceTemperature?: number | null;
  firmwareVersion?: string | null;
  nextStart?: string | null;
  cameraName?: string | null;
  wakeReason?: string | null;
}

export interface TimezoneOption {
  value: string;
  label: string;
}

