export type MapProviderConfig = {
  id: 'openstreetmap' | 'mapbox' | 'google'
  tileUrl: string
  attribution: string
  warning?: string
}

export interface MapProvider {
  configuration(): MapProviderConfig
}

class OpenStreetMapProvider implements MapProvider {
  configuration(): MapProviderConfig {
    return {
      id: 'openstreetmap',
      tileUrl: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      attribution: '&copy; OpenStreetMap contributors',
    }
  }
}

class MapboxProvider implements MapProvider {
  configuration(): MapProviderConfig {
    const token = import.meta.env.VITE_MAPBOX_ACCESS_TOKEN
    if (!token) return { ...new OpenStreetMapProvider().configuration(), warning: 'Mapbox is selected but VITE_MAPBOX_ACCESS_TOKEN is missing; using OpenStreetMap.' }
    return {
      id: 'mapbox',
      tileUrl: `https://api.mapbox.com/styles/v1/mapbox/streets-v12/tiles/256/{z}/{x}/{y}@2x?access_token=${token}`,
      attribution: '&copy; Mapbox &copy; OpenStreetMap contributors',
    }
  }
}

class GoogleMapProvider implements MapProvider {
  configuration(): MapProviderConfig {
    return { ...new OpenStreetMapProvider().configuration(), warning: 'Google Maps requires its JavaScript adapter and a restricted browser key; OpenStreetMap remains active for this session.' }
  }
}

export const resolveMapProvider = (provider = import.meta.env.VITE_MAP_PROVIDER || 'openstreetmap'): MapProviderConfig => {
  if (provider === 'mapbox') return new MapboxProvider().configuration()
  if (provider === 'google') return new GoogleMapProvider().configuration()
  return new OpenStreetMapProvider().configuration()
}
