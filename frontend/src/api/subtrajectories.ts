import { apiClient } from './client'
import type { Area, ClusterMember, ClusterSubtrajectory, Route } from '../types'
import { dateQueryParams } from '../dateRange'

export type FindRoutesParams = {
  start: Area
  end: Area
  fromDate: string
  toDate: string
  fromHour: string
  toHour: string
  epsilon: number
}

function areaParams(params: FindRoutesParams) {
  return {
    a_longitude: params.start.min_longitude,
    a_latitude: params.start.min_latitude,
    a_max_longitude: params.start.max_longitude,
    a_max_latitude: params.start.max_latitude,
    b_longitude: params.end.min_longitude,
    b_latitude: params.end.min_latitude,
    b_max_longitude: params.end.max_longitude,
    b_max_latitude: params.end.max_latitude,
  }
}

// the backend will return a list of routes, each with its subtrajectories and their timestamps.
export async function findRoutes(params: FindRoutesParams): Promise<Route[]> {
  const response = await apiClient.get<Route[]>('subtrajectories/get', {
    params: {
      ...dateQueryParams(params.fromDate, params.toDate),
      ...areaParams(params),
      start_time: params.fromHour || undefined,
      end_time: params.toHour || undefined,
      epsilon: params.epsilon,
    },
  })
  return response.data
}

// the backend will return a list of subtrajectories, each with its timestamps.
export async function fetchClusterSubtrajectories(
  params: FindRoutesParams,
  members: ClusterMember[],
): Promise<ClusterSubtrajectory[]> {
  const response = await apiClient.post<ClusterSubtrajectory[]>('subtrajectories/cluster', {
    ...dateQueryParams(params.fromDate, params.toDate),
    ...areaParams(params),
    start_time: params.fromHour || undefined,
    end_time: params.toHour || undefined,
    members,
  })
  return response.data
}
