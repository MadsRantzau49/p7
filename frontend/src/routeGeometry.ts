import type { Area, GpsPoint, LatLng, Pathlet, Subtrajectory } from './types'

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

// Offsets come from the backend's projected geometry, not approximate GPS lengths.
export function supportSegments(route: Pathlet): { points: GpsPoint[]; count: number }[] {
  if (!route.support.length || route.distances_m.length !== route.points.length) {
    return [{ points: route.points, count: route.count }]
  }
  return route.support.map(interval => {
    const points: GpsPoint[] = []
    for (let index = 0; index < route.points.length - 1; index++) {
      const start = route.distances_m[index]
      const end = route.distances_m[index + 1]
      if (end <= start || end < interval.start_m || start > interval.end_m) continue
      const interpolate = (distance: number): GpsPoint => {
        const fraction = (distance - start) / (end - start)
        const a = route.points[index], b = route.points[index + 1]
        return {
          latitude: a.latitude + (b.latitude - a.latitude) * fraction,
          longitude: a.longitude + (b.longitude - a.longitude) * fraction,
        }
      }
      const from = Math.max(start, interval.start_m)
      const to = Math.min(end, interval.end_m)
      if (to <= from) continue
      if (!points.length) points.push(interpolate(from))
      points.push(interpolate(to))
    }
    return { points, count: interval.count }
  })
}

export function contributingParts(route: Pathlet, journey: Subtrajectory): GpsPoint[][] {
  return route.sections
    .filter(section => section.subtrajectory_id === journey.subtrajectory_id)
    .map(section => journey.points.slice(section.source_start_index, section.source_end_index + 1))
    .filter(points => points.length >= 2)
}
