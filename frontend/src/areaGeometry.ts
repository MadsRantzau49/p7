import type { Area, LatLng } from './types'

export function areaFromCorners(first: LatLng, second: LatLng): Area {
  return {
    min_longitude: Math.min(first.lng, second.lng),
    min_latitude: Math.min(first.lat, second.lat),
    max_longitude: Math.max(first.lng, second.lng),
    max_latitude: Math.max(first.lat, second.lat),
  }
}

export function areasOverlap(a: Area, b: Area): boolean {
  return a.min_longitude <= b.max_longitude && a.max_longitude >= b.min_longitude
    && a.min_latitude <= b.max_latitude && a.max_latitude >= b.min_latitude
}

export function areaBounds(area: Area): [[number, number], [number, number]] {
  return [[area.min_latitude, area.min_longitude], [area.max_latitude, area.max_longitude]]
}
