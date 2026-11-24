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

// One grouped route and how many journeys took it.
export type Route = {
  points: GpsPoint[]
  count: number
}
