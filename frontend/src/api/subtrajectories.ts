import { apiClient } from './client'
import type { Area, RouteSearchResult } from '../types'

export type FindRoutesParams = {
  start: Area
  end: Area
  fromDate: string 
  toDate: string 
  fromHour: string // "" = no time filter
  toHour: string // "" = no time filter
  epsilon: number
}

// pathlets between the two picked areas.
export async function findRoutes(params: FindRoutesParams): Promise<RouteSearchResult> {
  const response = await apiClient.get<RouteSearchResult>('/api/subtrajectories/get', {
    params: {
      a_longitude: params.start.min_longitude,
      a_latitude: params.start.min_latitude,
      a_max_longitude: params.start.max_longitude,
      a_max_latitude: params.start.max_latitude,
      b_longitude: params.end.min_longitude,
      b_latitude: params.end.min_latitude,
      b_max_longitude: params.end.max_longitude,
      b_max_latitude: params.end.max_latitude,
      start_date: params.fromDate || undefined,
      end_date: params.toDate || undefined,
      start_time: params.fromHour || undefined,
      end_time: params.toHour || undefined,
      epsilon: params.epsilon,
    },
  })
  return response.data
}
