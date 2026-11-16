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

// A stretch with a constant set of supporting source trajectories.
export type SupportInterval = {
  support_interval_id: number
  start_m: number
  end_m: number
  count: number
  trajectory_ids: number[]
  points: GpsPoint[]
}

export type Pathlet = {
  pathlet_id: number
  length_m: number
  points: GpsPoint[]
  count: number
  support: SupportInterval[]
}
