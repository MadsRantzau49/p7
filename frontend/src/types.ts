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

// Identifies one subtrajectory in a cluster, sent back to fetch it on demand.
export type ClusterMember = {
  trajectory_id: number
  exit_a_time: string
  entry_b_time: string
}

// One grouped route, how many journeys took it, and the members behind it.
export type Route = {
  points: GpsPoint[]
  count: number
  members: ClusterMember[]
}

// One subtrajectory of a cluster, fetched when the cluster is opened.
export type ClusterSubtrajectory = {
  trajectory_id: number
  points: GpsPoint[]
}
