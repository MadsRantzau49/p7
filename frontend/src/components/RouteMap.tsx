import { MapContainer, TileLayer, CircleMarker, Polyline, Tooltip, useMapEvents, } from 'react-leaflet'
import type { LatLng, Pathlet } from '../types'
import { ROUTE_COLORS } from '../colors'

type PickMode = 'start' | 'end' | null

type Props = {
  startPoint: LatLng | null
  endPoint: LatLng | null
  pickMode: PickMode
  onPickPoint: (point: LatLng) => void
  routes: Pathlet[]
  hoveredRoute: number | null
  setHoveredRoute: (index: number | null) => void
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

// Line size depending on # of trajectories counted and grouped together 
function lineWeight(count: number, maxCount: number): number {
  const minWeight = 3
  const maxWeight = 10
  if (maxCount <= 0) return minWeight
  return minWeight + (count / maxCount) * (maxWeight - minWeight)
}

export default function RouteMap({ startPoint, endPoint, pickMode, onPickPoint, routes, hoveredRoute, setHoveredRoute }: Props) {
  // Largest journey count - used to scale line thickness relative to biggest one. 
  const maxCount = routes.reduce((max, route) => Math.max(max, route.count), 0)

  return (
    <div className="map-card">
      <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} className="map">
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Check that we are choosing point */}
        {pickMode && <MapClickHandler onClick={onPickPoint} />}

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
          const opacity = hoveredRoute === null || isHovered ? 1 : 0.35

          return (
            <Polyline
              key={index}
              positions={positions}
              pathOptions={{
                color,
                weight: lineWeight(route.count, maxCount) + (isHovered ? 3 : 0),
                opacity,
              }}
              eventHandlers={{
                mouseover: () => setHoveredRoute(index),
                mouseout: () => setHoveredRoute(null),
              }}
            >
              <Tooltip permanent direction="center" className="count-label">
                {route.count}
              </Tooltip>
            </Polyline>
          )
        })}
      </MapContainer>
    </div>
  )
}
