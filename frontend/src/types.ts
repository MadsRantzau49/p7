export type LatLng = {
  lat: number
  lng: number
}

// Sim level discrete values. 
export type SimilarityLevel = 'low' | 'mid' | 'high'

// One point of a route. 
export type GpsPoint = {
  latitude: number
  longitude: number
}

// How many journeys support one stretch of a route.
export type SupportInterval = {
  start_m: number
  end_m: number
  count: number
}

export type Pathlet = {
  points: GpsPoint[]
  count: number
  support: SupportInterval[]
}
