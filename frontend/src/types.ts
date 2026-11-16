export type LatLng = {
  lat: number
  lng: number
}

export type Area = {
  min_longitude: number
  min_latitude: number
  max_longitude: number
  max_latitude: number
}

export type PickMode = 'start' | 'end' | null

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
  distances_m: number[]
  sections: TrajectorySection[]
}

export type TrajectorySection = {
  subtrajectory_id: number
  source_start_index: number
  source_end_index: number
}

export type Subtrajectory = {
  subtrajectory_id: number
  trajectory_id: number
  exit_a_time: string
  entry_b_time: string
  points: GpsPoint[]
}

export type RouteSearchResult = {
  pathlets: Pathlet[]
  trajectories: Subtrajectory[]
}
