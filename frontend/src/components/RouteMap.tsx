import { useEffect, useState } from 'react'
import { DomEvent } from 'leaflet'
import { MapContainer, TileLayer, CircleMarker, Polyline, Rectangle, Tooltip, useMapEvents, } from 'react-leaflet'
import type { Area, ClusterSubtrajectory, LatLng, PickMode } from '../types'
import { routeColor } from '../colors'
import { areaBounds, areaFromCorners } from '../areaGeometry'
import { isRouteVisible, meetsMinimum, sameRoute, type RouteRef, type SearchResult } from '../searches'

type Props = {
  startArea: Area | null
  endArea: Area | null
  pickMode: PickMode
  onPickArea: (area: Area) => void
  onCancelPick: () => void
  searches: SearchResult[]
  searching: boolean
  checkedRoutes: Set<string>
  hoveredRoute: RouteRef | null
  setHoveredRoute: (ref: RouteRef | null) => void
  selectedRoute: RouteRef | null
  memberPaths: ClusterSubtrajectory[]
  memberLoading: boolean
  hoveredMember: number | null
  setHoveredMember: (index: number | null) => void
  onSelectRoute: (ref: RouteRef) => void
  minSubtrajectories: number
}

// Start at Porto.
// This is something, we should change per dataset, or even per search, but for now it's a reasonable default, as must data exists in porto.
const DEFAULT_CENTER: [number, number] = [41.1496, -8.6102]
const DEFAULT_ZOOM = 13

const MEMBER_COLOR = '#212529'  // Default color for subtrajectories in a cluster. Dark gray so it doesn't compete with the representative route.
const MEMBER_HOVER_COLOR = '#1971c2' // Color for a subtrajectory when hovered. Blue so it stands out from the representative route.

type AreaPickerProps = {
  mode: Exclude<PickMode, null>
  onPick: (area: Area) => void
  onCancel: () => void
}

function isValidArea(area: Area): boolean {
  const hasHeight = area.min_latitude !== area.max_latitude
  const hasWidth = area.min_longitude !== area.max_longitude

  return hasHeight && hasWidth
}

// The first search is drawn solid; later searches are dashed so compared searches stand apart.
// Simply to show a difference, between the first and later searches, not to indicate any particular meaning.
// But everything after search 2 is also dashed, so the first search is the only one drawn solid.
// Future work, should probably limit the amount of searches the user is allowed to make.
function searchDash(position: number): string | undefined {
  return position === 0 ? undefined : '10 8'
}

function AreaPicker({ mode, onPick, onCancel }: AreaPickerProps) {
  const [firstCorner, setFirstCorner] = useState<LatLng | null>(null)
  const [mousePosition, setMousePosition] = useState<LatLng | null>(null)
  const [isAreaTooSmall, setIsAreaTooSmall] = useState(false)

  useMapEvents({
    click: (event) => {
      const clickedPosition = {
        lat: event.latlng.lat,
        lng: event.latlng.lng,
      }

      // Select the first corner of the area.
      if (firstCorner === null) {
        setFirstCorner(clickedPosition)
        setMousePosition(clickedPosition)
        return
      }

      // Construct the area from the two selected corners.
      const area = areaFromCorners(firstCorner, clickedPosition)

      if (!isValidArea(area)) {
        setIsAreaTooSmall(true)
        return
      }

      setIsAreaTooSmall(false)
      onPick(area)
    },

    mousemove: (event) => {
      if (firstCorner !== null) {
        setMousePosition({
          lat: event.latlng.lat,
          lng: event.latlng.lng,
        })
      }
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
      <span>{isAreaTooSmall ? 'Choose a larger rectangle.' : firstCorner ? 'Click the opposite corner.'
        : `Click the first corner of the ${mode === 'start' ? 'starting' : 'destination'} area.`}</span>
      <button type="button" onClick={onCancel}>Cancel</button>
    </div>
    {firstCorner && <CircleMarker center={[firstCorner.lat, firstCorner.lng]} radius={4} interactive={false} />}
    {firstCorner && mousePosition && <Rectangle bounds={areaBounds(areaFromCorners(firstCorner, mousePosition))} interactive={false}
      pathOptions={{ color: mode === 'start' ? '#1e7e34' : '#b21f2d', dashArray: '5 5', fillOpacity: 0.12 }} />}
  </>
}

// Line size depending on # of trajectories counted and grouped together
// This calculates the thickness of the line to draw for a route, based on how many trajectories it represents, relative to the largest route in the current searches.
// Scale route thickness relative to the largest cluster.
function calculateRouteWeight(
  subtrajectoryCount: number,
  maxSubtrajectoryCount: number
): number {
  const minWeight = 3
  const maxWeight = 10

  if (maxSubtrajectoryCount <= 0) {
    return minWeight
  }

  const ratio = subtrajectoryCount / maxSubtrajectoryCount

  return minWeight + ratio * (maxWeight - minWeight)
}

export default function RouteMap({ startArea, endArea, pickMode, onPickArea, onCancelPick, searches, searching, checkedRoutes, hoveredRoute, setHoveredRoute, selectedRoute, memberPaths, memberLoading, hoveredMember, setHoveredMember, onSelectRoute, minSubtrajectories }: Props) {
  // Largest journey count - used to scale line thickness relative to biggest one.
  // Taken across all searches so line widths compare fairly between them.
  const maxCount = searches.reduce(
    (max, search) => search.routes.reduce((inner, route) => Math.max(inner, route.count), max),
    0,
  )
  const anyMemberHovered = hoveredMember !== null

  return (
    <div className={`map-card${pickMode ? ' picking-area' : ''}`}>
      {selectedRoute !== null && !pickMode && (
        <div className="map-message cluster-open" role="status">
          <span>Showing one cluster. Hover a trip to highlight it.</span>
          <button type="button" onClick={() => onSelectRoute(selectedRoute)}>Show all clusters</button>
        </div>
      )}
      {/* Covers the whole map while routes are being found, and blocks map interaction. */}
      {searching && (
        <div className="map-busy" role="status" aria-live="polite">
          <div className="map-busy-card">
            <span className="spinner spinner-dark spinner-large" aria-hidden="true" />
            <span>Finding routes...</span>
          </div>
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
            key={areaBounds(startArea).join()}
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
            key={areaBounds(endArea).join()}
            bounds={areaBounds(endArea)}
            interactive={false}
            pathOptions={{ color: '#b21f2d', fillColor: '#dc3545', fillOpacity: 0.12 }}
          >
            <Tooltip permanent direction="top">
              END
            </Tooltip>
          </Rectangle>
        )}

        {searches.map((search, position) =>
          search.routes.map((route, index) => {
            const ref: RouteRef = { searchId: search.id, index }
            // With a cluster open, hide every other cluster so only its routes show.
            if (selectedRoute !== null) {
              // Only display the selected cluster.
              if (!sameRoute(selectedRoute, ref)) {
                return null
              }
            } else {
              // Apply the route visibility filters.
              if (!isRouteVisible(ref, checkedRoutes)) {
                return null
              }

              if (!meetsMinimum(route, minSubtrajectories)) {
                return null
              }
            }

            const positions = route.points.map(
              (point) => [point.latitude, point.longitude] as [number, number],
            )

            if (positions.length < 2) return null

            const color = routeColor(position, index, searches.length)
            const isHovered = sameRoute(hoveredRoute, ref)
            const isSelected = sameRoute(selectedRoute, ref)

            // fade the others routes when one is hovered.
            const opacity = hoveredRoute === null || isHovered ? 1 : 0.35

            return (
              <Polyline
                key={`${search.id}-${index}-${Boolean(pickMode)}`}
                interactive={!pickMode}
                positions={positions}
                pathOptions={{
                  color,
                  weight: calculateRouteWeight(route.count, maxCount) + (isHovered || isSelected ? 3 : 0),
                  opacity,
                  dashArray: searchDash(position),
                }}
                eventHandlers={{
                  mouseover: () => setHoveredRoute(ref),
                  mouseout: () => setHoveredRoute(null),
                  click: () => onSelectRoute(ref),
                }}
              >
                <Tooltip permanent direction="center" className="count-label">
                  {route.count}
                </Tooltip>
              </Polyline>
            )
          }),
        )}

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
