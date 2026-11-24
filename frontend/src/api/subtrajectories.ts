import { apiClient } from './client'
import type { ClusterMember, ClusterSubtrajectory, LatLng, Route } from '../types'

// width of search node
const BOX_HALF_WIDTH_M = 50

export type FindRoutesParams = {
  start: LatLng
  end: LatLng
  fromDate: string
  toDate: string
  fromHour: string // "" = no time filter
  toHour: string // "" = no time filter
  epsilon: number
}

// routes between the two picked areas.
export async function findRoutes(params: FindRoutesParams): Promise<Route[]> {
  const response = await apiClient.get<Route[]>('/api/subtrajectories/get', {
    params: {
      a_longitude: params.start.lng,
      a_latitude: params.start.lat,
      b_longitude: params.end.lng,
      b_latitude: params.end.lat,
      start_date: params.fromDate,
      end_date: params.toDate,
      start_time: params.fromHour || undefined,
      end_time: params.toHour || undefined,
      epsilon: params.epsilon,
      box_half_width_m: BOX_HALF_WIDTH_M,
    },
  })
  return response.data
}

// the individual subtrajectories grouped into one cluster, fetched when it is opened.
export async function fetchClusterSubtrajectories(
  params: FindRoutesParams,
  members: ClusterMember[],
): Promise<ClusterSubtrajectory[]> {
  const response = await apiClient.post<ClusterSubtrajectory[]>('/api/subtrajectories/cluster', {
    a_longitude: params.start.lng,
    a_latitude: params.start.lat,
    b_longitude: params.end.lng,
    b_latitude: params.end.lat,
    start_date: params.fromDate,
    end_date: params.toDate,
    start_time: params.fromHour || undefined,
    end_time: params.toHour || undefined,
    box_half_width_m: BOX_HALF_WIDTH_M,
    members,
  })
  return response.data
}
