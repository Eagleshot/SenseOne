// CARTO Positron ("light") raster basemap — free, keyless, attribution required.
// Shared by the station map and the coordinate picker so the tile URL and
// attribution stay in one place.
export const cartoLightTile = {
  url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noreferrer">CARTO</a>',
} as const;
