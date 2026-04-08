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
}

export interface SensorData {
  timestamp: Date;
  temperature: number;
  humidity: number;
  pressure: number;
  battery: number;
  windSpeed: number;
  windDirection: number;
  visibility: number;
  uvIndex: number;
  dewPoint: number;
  feelsLike: number;
}

export interface TimezoneOption {
  value: string;
  label: string;
}
