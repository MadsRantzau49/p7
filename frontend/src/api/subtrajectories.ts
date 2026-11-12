import { apiClient } from './client'
import type { LatLng, Pathlet } from '../types'

// width of search node 
const BOX_HALF_WIDTH_M = 50

export type FindRoutesParams = {
  start: LatLng
  end: LatLng
  fromDate: string 
  toDate: string 
  epsilon: number
}

// pathlets between the two picked areas.
export async function findRoutes(params: FindRoutesParams): Promise<Pathlet[]> {
  const response = await apiClient.get<Pathlet[]>('/api/subtrajectories/get', {
    params: {
      a_longitude: params.start.lng,
      a_latitude: params.start.lat,
      b_longitude: params.end.lng,
      b_latitude: params.end.lat,
      start_date: params.fromDate,
      end_date: params.toDate,
      epsilon: params.epsilon,
      box_half_width_m: BOX_HALF_WIDTH_M,
    },
  })
  return response.data
}
