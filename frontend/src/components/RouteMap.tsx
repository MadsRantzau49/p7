import { useEffect } from 'react'
import { latLngBounds } from 'leaflet'
import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import type { GpsPoint, LatLng, Pathlet } from '../types'
import { ROUTE_COLORS, supportColor } from '../colors'

type PickMode = 'start' | 'end' | null

type Props = {
  startPoint: LatLng | null
  endPoint: LatLng | null
  pickMode: PickMode
  onPickPoint: (point: LatLng) => void
  routes: Pathlet[]
  hoveredRoute: number | null
  setHoveredRoute: (index: number | null) => void
  selectedRoute: number | null
  onSelectRoute: (index: number) => void
  selectedInterval: number | null
  onSelectInterval: (id: number) => void
}

// Start at Beijing. 
// TODO : Handle this depending on the dataset of the depolyment. 
const DEFAULT_CENTER: [number, number] = [39.9, 116.4]
const DEFAULT_ZOOM = 11

// listens for clicks on the map.
function MapClickHandler({ onClick }: { onClick: (point: LatLng) => void }) {
  useMapEvents({
    click: (event) => {
      onClick({ lat: event.latlng.lat, lng: event.latlng.lng })
    },
  })
  return null
}

function FocusSelection({ points }: { points: GpsPoint[] | undefined }) {
  const map = useMap()
  useEffect(() => {
    function fitSelection() {
      map.invalidateSize({ pan: false })
      if (points?.length) {
        map.fitBounds(latLngBounds(points.map((point) => [point.latitude, point.longitude])), {
          padding: [65, 45], maxZoom: 21, animate: false,
        })
      }
    }
    const observer = new ResizeObserver(fitSelection)
    observer.observe(map.getContainer())
    fitSelection()
    return () => observer.disconnect()
  }, [map, points])
  return null
}

// Line size depending on # of trajectories counted and grouped together 
function lineWeight(count: number, maxCount: number): number {
  const minWeight = 3
  const maxWeight = 10
  if (maxCount <= 0) return minWeight
  return minWeight + (count / maxCount) * (maxWeight - minWeight)
}

export default function RouteMap({ startPoint, endPoint, pickMode, onPickPoint, routes, hoveredRoute,
  setHoveredRoute, selectedRoute, onSelectRoute, selectedInterval, onSelectInterval }: Props) {
  // Largest journey count - used to scale line thickness relative to biggest one. 
  const maxCount = routes.reduce((max, route) => Math.max(max, route.count), 0)
  const selected = selectedRoute === null ? undefined : routes[selectedRoute]
  const interval = selected?.support.find((item) => item.support_interval_id === selectedInterval)
  const focusedRoute = selectedRoute ?? hoveredRoute

  return (
    <div className="map-card">
      <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} maxZoom={21} className="map">
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          maxNativeZoom={19}
          maxZoom={21}
        />

        {/* Check that we are choosing point */}
        {pickMode && <MapClickHandler onClick={onPickPoint} />}
        <FocusSelection points={interval?.points ?? selected?.points} />

        {startPoint && (
          <CircleMarker
            center={[startPoint.lat, startPoint.lng]}
            radius={9}
            pathOptions={{ color: '#1e7e34', fillColor: '#28a745', fillOpacity: 1 }}
          >
            <Tooltip permanent direction="top">
              START
            </Tooltip>
          </CircleMarker>
        )}

        {endPoint && (
          <CircleMarker
            center={[endPoint.lat, endPoint.lng]}
            radius={9}
            pathOptions={{ color: '#b21f2d', fillColor: '#dc3545', fillOpacity: 1 }}
          >
            <Tooltip permanent direction="top">
              END
            </Tooltip>
          </CircleMarker>
        )}

        {routes.map((route, index) => {
          const positions = route.points.map(
            (point) => [point.latitude, point.longitude] as [number, number],
          )

          if (positions.length < 2) return null

          const color = ROUTE_COLORS[index % ROUTE_COLORS.length]
          const isHovered = hoveredRoute === index

          // fade the others routes when one is hovered.
          const opacity = focusedRoute === null || focusedRoute === index ? 1 : 0.2

          return (
            <Polyline
              key={route.pathlet_id}
              positions={positions}
              bubblingMouseEvents={Boolean(pickMode)}
              pathOptions={{
                color: selectedRoute === index ? '#17212f' : color,
                weight: selectedRoute === index ? 11 : lineWeight(route.count, maxCount) + (isHovered ? 3 : 0),
                opacity,
              }}
              eventHandlers={{
                mouseover: () => setHoveredRoute(index),
                mouseout: () => setHoveredRoute(null),
                click: () => { if (!pickMode) onSelectRoute(index) },
              }}
            >
              <Tooltip permanent direction="center" className="count-label">
                Pathlet {route.pathlet_id} · {route.count}
              </Tooltip>
            </Polyline>
          )
        })}

        {selected?.support.map((support) => (
          <Polyline key={`support-${selected.pathlet_id}-${support.support_interval_id}`}
            positions={support.points.map((point) => [point.latitude, point.longitude])}
            bubblingMouseEvents={Boolean(pickMode)}
            pathOptions={{
              color: supportColor(support.support_interval_id),
              weight: support.support_interval_id === selectedInterval ? 9 : 6,
              opacity: selectedInterval === null || support.support_interval_id === selectedInterval ? 1 : 0.2,
            }}
            eventHandlers={{ click: () => { if (!pickMode) onSelectInterval(support.support_interval_id) } }}>
            <Tooltip>
              Interval {selected.pathlet_id}.{support.support_interval_id} · {support.start_m.toFixed(1)}–{support.end_m.toFixed(1)} m
              {' · '}{support.count} {support.count === 1 ? 'supporter' : 'supporters'}
            </Tooltip>
          </Polyline>
        ))}

        {interval && interval.points.length > 0 && [
          { point: interval.points[0], label: 'Start', meters: interval.start_m },
          { point: interval.points[interval.points.length - 1], label: 'End', meters: interval.end_m },
        ].map(({ point, label, meters }) => (
          <CircleMarker key={`interval-${label}`} center={[point.latitude, point.longitude]} radius={7}
            pathOptions={{ color: '#17212f', weight: 2, fillOpacity: 1,
              fillColor: label === 'Start' ? supportColor(interval.support_interval_id) : '#fff' }}>
            <Tooltip permanent direction={label === 'Start' ? 'top' : 'bottom'}>
              {label}: {meters.toFixed(1)} m
            </Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  )
}
