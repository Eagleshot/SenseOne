export interface Webcam {
  id: string;
  name: string;
  location: string;
  coordinates: {
    lat: number;
    lng: number;
    altitude: number;
  };
  thumbnail: string;
  currentImage: string;
  isOnline: boolean;
  lastUpdate: Date;
  nextUpdate: Date;
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
