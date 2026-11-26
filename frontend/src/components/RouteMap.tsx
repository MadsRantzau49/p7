import { useEffect, useState } from 'react'
import { DomEvent } from 'leaflet'
import { MapContainer, TileLayer, CircleMarker, Polyline, Rectangle, Tooltip, useMapEvents, } from 'react-leaflet'
import type { Area, ClusterSubtrajectory, LatLng, PickMode, Route } from '../types'
import { ROUTE_COLORS } from '../colors'
import { areaBounds, areaFromCorners } from '../areaGeometry'

type Props = {
  startArea: Area | null
  endArea: Area | null
  pickMode: PickMode
  onPickArea: (area: Area) => void
  onCancelPick: () => void
  routes: Route[]
  hoveredRoute: number | null
  setHoveredRoute: (index: number | null) => void
  selectedRoute: number | null
  memberPaths: ClusterSubtrajectory[]
  memberLoading: boolean
  hoveredMember: number | null
  setHoveredMember: (index: number | null) => void
  onSelectRoute: (index: number) => void
}

// Start at Beijing.
// TODO : Handle this depending on the dataset of the depolyment.
const DEFAULT_CENTER: [number, number] = [39.9, 116.4]
const DEFAULT_ZOOM = 11

// The individual subtrajectories of an opened cluster, drawn in one neutral colour so they
// stand apart from the coloured cluster representatives. A hovered one turns bright.
const MEMBER_COLOR = '#212529'
const MEMBER_HOVER_COLOR = '#1971c2'

function AreaPicker({ mode, onPick, onCancel }: {
  mode: Exclude<PickMode, null>
  onPick: (area: Area) => void
  onCancel: () => void
}) {
  const [first, setFirst] = useState<LatLng | null>(null)
  const [pointer, setPointer] = useState<LatLng | null>(null)
  const [tooSmall, setTooSmall] = useState(false)
  useMapEvents({
    click: (event) => {
      const point = { lat: event.latlng.lat, lng: event.latlng.lng }
      if (!first) {
        setFirst(point)
        setPointer(point)
        return
      }
      const area = areaFromCorners(first, point)
      if (area.min_latitude === area.max_latitude || area.min_longitude === area.max_longitude) {
        setTooSmall(true)
        return
      }
      setTooSmall(false)
      onPick(area)
    },
    mousemove: (event) => {
      if (first) setPointer({ lat: event.latlng.lat, lng: event.latlng.lng })
    },
  })

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') onCancel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onCancel])

  return <>
    <div className="map-message" role="status" ref={element => { if (element) DomEvent.disableClickPropagation(element) }}>
      <span>{tooSmall ? 'Choose a larger rectangle.' : first ? 'Click the opposite corner.'
        : `Click the first corner of the ${mode === 'start' ? 'starting' : 'destination'} area.`}</span>
      <button type="button" onClick={onCancel}>Cancel</button>
    </div>
    {first && <CircleMarker center={[first.lat, first.lng]} radius={4} interactive={false} />}
    {first && pointer && <Rectangle bounds={areaBounds(areaFromCorners(first, pointer))} interactive={false}
      pathOptions={{ color: mode === 'start' ? '#1e7e34' : '#b21f2d', dashArray: '5 5', fillOpacity: 0.12 }} />}
  </>
}

// Line size depending on # of trajectories counted and grouped together
function lineWeight(count: number, maxCount: number): number {
  const minWeight = 3
  const maxWeight = 10
  if (maxCount <= 0) return minWeight
  return minWeight + (count / maxCount) * (maxWeight - minWeight)
}

export default function RouteMap({ startArea, endArea, pickMode, onPickArea, onCancelPick, routes, hoveredRoute, setHoveredRoute, selectedRoute, memberPaths, memberLoading, hoveredMember, setHoveredMember, onSelectRoute }: Props) {
  // Largest journey count - used to scale line thickness relative to biggest one.
  const maxCount = routes.reduce((max, route) => Math.max(max, route.count), 0)
  const anyMemberHovered = hoveredMember !== null

  return (
    <div className={`map-card${pickMode ? ' picking-area' : ''}`}>
      {selectedRoute !== null && !pickMode && (
        <div className="map-message cluster-open" role="status">
          <span>Showing one cluster. Hover a trip to highlight it.</span>
          <button type="button" onClick={() => onSelectRoute(selectedRoute)}>Show all clusters</button>
        </div>
      )}
      {memberLoading && (
        <div className="map-loading" role="status">
          <span className="spinner spinner-dark" aria-hidden="true" />
          <span>Loading subtrajectories...</span>
        </div>
      )}
      <MapContainer center={DEFAULT_CENTER} zoom={DEFAULT_ZOOM} className="map" worldCopyJump={true}>
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {pickMode && <AreaPicker key={pickMode} mode={pickMode} onPick={onPickArea} onCancel={onCancelPick} />}

        {startArea && (
          <Rectangle
            bounds={areaBounds(startArea)}
            interactive={false}
            pathOptions={{ color: '#1e7e34', fillColor: '#28a745', fillOpacity: 0.12 }}
          >
            <Tooltip permanent direction="top">
              START
            </Tooltip>
          </Rectangle>
        )}

        {endArea && (
          <Rectangle
            bounds={areaBounds(endArea)}
            interactive={false}
            pathOptions={{ color: '#b21f2d', fillColor: '#dc3545', fillOpacity: 0.12 }}
          >
            <Tooltip permanent direction="top">
              END
            </Tooltip>
          </Rectangle>
        )}

        {routes.map((route, index) => {
          // With a cluster open, hide every other cluster so only its routes show.
          if (selectedRoute !== null && index !== selectedRoute) return null

          const positions = route.points.map(
            (point) => [point.latitude, point.longitude] as [number, number],
          )

          if (positions.length < 2) return null

          const color = ROUTE_COLORS[index % ROUTE_COLORS.length]
          const isHovered = hoveredRoute === index
          const isSelected = selectedRoute === index

          // fade the others routes when one is hovered.
          const opacity = hoveredRoute === null || isHovered ? 1 : 0.35

          return (
            <Polyline
              key={`${index}-${Boolean(pickMode)}`}
              interactive={!pickMode}
              positions={positions}
              pathOptions={{
                color,
                weight: lineWeight(route.count, maxCount) + (isHovered || isSelected ? 3 : 0),
                opacity,
              }}
              eventHandlers={{
                mouseover: () => setHoveredRoute(index),
                mouseout: () => setHoveredRoute(null),
                click: () => onSelectRoute(index),
              }}
            >
              <Tooltip permanent direction="center" className="count-label">
                {route.count}
              </Tooltip>
            </Polyline>
          )
        })}

        {/* The opened cluster's subtrajectories, drawn clearly over its representative. */}
        {selectedRoute !== null &&
          memberPaths.map((member, memberIndex) => {
            const positions = member.points.map(
              (point) => [point.latitude, point.longitude] as [number, number],
            )

            if (positions.length < 2) return null

            const isMemberHovered = hoveredMember === memberIndex
            // Fade the other trips when one is hovered so the hovered one stands out.
            const opacity = !anyMemberHovered ? 0.75 : isMemberHovered ? 1 : 0.2

            return (
              <Polyline
                key={`member-${memberIndex}`}
                interactive={!pickMode}
                positions={positions}
                pathOptions={{
                  color: isMemberHovered ? MEMBER_HOVER_COLOR : MEMBER_COLOR,
                  weight: isMemberHovered ? 6 : 3,
                  opacity,
                }}
                eventHandlers={{
                  mouseover: () => setHoveredMember(memberIndex),
                  mouseout: () => setHoveredMember(null),
                }}
              />
            )
          })}
      </MapContainer>
    </div>
  )
}
