import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { DomEvent, latLngBounds } from 'leaflet'
import type { LeafletMouseEvent, Polyline as LeafletPolyline } from 'leaflet'
import { MapContainer, TileLayer, CircleMarker, Pane, Polyline, Rectangle, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import type { PolylineProps } from 'react-leaflet'
import type { Area, GpsPoint, LatLng, Pathlet, PickMode, Subtrajectory } from '../types'
import { CONTRIBUTION_COLOR, REPRESENTATIVE_COLOR, journeyColor, usageBands, usageColor } from '../colors'
import { areaFromCorners, contributingParts, supportSegments } from '../routeGeometry'

type Props = {
  startArea: Area | null
  endArea: Area | null
  pickMode: PickMode
  onPickArea: (area: Area) => boolean
  onCancelPick: () => void
  routes: Pathlet[]
  trajectories: Subtrajectory[]
}

// Retain the existing deployment's initial view; results are fitted automatically.
const DEFAULT_CENTER: [number, number] = [39.9, 116.4]
const positions = (points: GpsPoint[]): [number, number][] => points.map(p => [p.latitude, p.longitude])
const bounds = (area: Area): [[number, number], [number, number]] => [
  [area.min_latitude, area.min_longitude], [area.max_latitude, area.max_longitude],
]

function ClickableLine({ label, onActivate, ...props }: PolylineProps & { label: string; onActivate: () => void }) {
  const ref = useRef<LeafletPolyline>(null)
  useEffect(() => {
    const element = ref.current?.getElement()
    if (!element) return
    element.setAttribute('tabindex', '0')
    element.setAttribute('role', 'button')
    element.setAttribute('aria-label', label)
    const onKey = (event: Event) => {
      const key = (event as KeyboardEvent).key
      if (key === 'Enter' || key === ' ') { event.preventDefault(); onActivate() }
    }
    element.addEventListener('keydown', onKey)
    return () => element.removeEventListener('keydown', onKey)
  }, [label, onActivate])
  return <Polyline {...props} ref={ref} />
}

function MapBehaviour({ routes, onClear, onCancelPick }: {
  routes: Pathlet[]; onClear: () => void; onCancelPick: () => void
}) {
  const map = useMap()
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { onCancelPick(); onClear() }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClear, onCancelPick])
  useEffect(() => {
    if (!routes.length) return
    const extent = latLngBounds([])
    for (const route of routes) for (const point of route.points) extent.extend([point.latitude, point.longitude])
    if (extent.isValid()) map.fitBounds(extent, { padding: [35, 35], maxZoom: 16 })
  }, [routes, map])
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize())
    observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map])
  return null
}

function AreaPicker({ mode, onPick, onCancel }: {
  mode: Exclude<PickMode, null>; onPick: (area: Area) => boolean; onCancel: () => void
}) {
  const [first, setFirst] = useState<LatLng | null>(null)
  const [pointer, setPointer] = useState<LatLng | null>(null)
  const [tooSmall, setTooSmall] = useState(false)
  useMapEvents({
    click: event => {
      const point = { lat: event.latlng.lat, lng: event.latlng.lng }
      if (!first) { setFirst(point); setPointer(point); return }
      const area = areaFromCorners(first, point)
      if (area.min_latitude === area.max_latitude || area.min_longitude === area.max_longitude) {
        setTooSmall(true)
        return
      }
      setTooSmall(false)
      onPick(area)
    },
    mousemove: event => { if (first) setPointer({ lat: event.latlng.lat, lng: event.latlng.lng }) },
  })
  return <>
    <div className="map-message" role="status" ref={element => { if (element) DomEvent.disableClickPropagation(element) }}>
      {tooSmall ? 'Choose a larger rectangle.' : first ? 'Click the opposite corner.' : `Click the first corner of the ${mode === 'start' ? 'starting' : 'destination'} area.`}
      <button type="button" onClick={onCancel}>Cancel</button>
    </div>
    {first && <CircleMarker center={[first.lat, first.lng]} radius={4} interactive={false} />}
    {first && pointer && <Rectangle bounds={bounds(areaFromCorners(first, pointer))} interactive={false}
      pathOptions={{ color: mode === 'start' ? '#35754c' : '#79579c', dashArray: '5 5', fillOpacity: .12 }} />}
  </>
}

function JourneyLayers({ journeys, colors, selectedId, hoveredId, onSelect, onHover, picking }: {
  journeys: Subtrajectory[]; selectedId: number | null; hoveredId: number | null
  colors: ReadonlyMap<number, string>
  onSelect: (id: number) => void; onHover: (id: number | null) => void; picking: boolean
}) {
  const map = useMap()
  function selectNearest(event: LeafletMouseEvent) {
    if (picking) return
    const click = map.latLngToLayerPoint(event.latlng)
    const distances = journeys.map(journey => {
      const points = journey.points.map(point => map.latLngToLayerPoint([point.latitude, point.longitude]))
      let distance = Infinity
      for (let index = 1; index < points.length; index++) {
        const a = points[index - 1], b = points[index]
        const dx = b.x - a.x, dy = b.y - a.y
        const fraction = Math.max(0, Math.min(1, ((click.x - a.x) * dx + (click.y - a.y) * dy) / (dx * dx + dy * dy || 1)))
        distance = Math.min(distance, Math.hypot(click.x - a.x - fraction * dx, click.y - a.y - fraction * dy))
      }
      return { journey, distance }
    }).sort((a, b) => a.distance - b.distance || a.journey.subtrajectory_id - b.journey.subtrajectory_id)
    const nearest = distances.filter(item => item.distance <= distances[0].distance + 3)
    // Repeated clicks cycle through coincident journeys, without adding a list.
    const current = nearest.findIndex(item => item.journey.subtrajectory_id === selectedId)
    onSelect(nearest[(current + 1) % nearest.length].journey.subtrajectory_id)
  }
  return <Pane name="contributing-journeys" style={{ zIndex: 420 }}>
    {journeys.map(journey => <Fragment key={journey.subtrajectory_id}>
      <Polyline positions={positions(journey.points)} interactive={false}
        pathOptions={{ color: 'white', opacity: selectedId === null || selectedId === journey.subtrajectory_id ? .9 : .45, weight: hoveredId === journey.subtrajectory_id ? 8 : 6 }} />
      <Polyline positions={positions(journey.points)} interactive={false}
        pathOptions={{ color: colors.get(journey.subtrajectory_id), opacity: selectedId === null || selectedId === journey.subtrajectory_id ? .9 : .5, weight: hoveredId === journey.subtrajectory_id ? 6 : 4 }} />
      <ClickableLine positions={positions(journey.points)} bubblingMouseEvents={picking}
        label={`Journey ${journey.subtrajectory_id}`}
        onActivate={() => { if (!picking) onSelect(journey.subtrajectory_id) }}
        pathOptions={{ color: colors.get(journey.subtrajectory_id), opacity: 0, weight: 12 }}
        eventHandlers={{
          click: selectNearest,
          mouseover: () => onHover(journey.subtrajectory_id),
          mouseout: () => onHover(null),
        }}>
        <Tooltip>Click to follow this journey. Click again for overlapping journeys.</Tooltip>
      </ClickableLine>
    </Fragment>)}
  </Pane>
}

export default function RouteMap({ startArea, endArea, pickMode, onPickArea, onCancelPick, routes, trajectories }: Props) {
  const [selection, setSelection] = useState<{ route: Pathlet; journeyId: number | null } | null>(null)
  const [hoveredRoute, setHoveredRoute] = useState<Pathlet | null>(null)
  const [hoveredJourney, setHoveredJourney] = useState<number | null>(null)
  const selected = selection && routes.includes(selection.route) ? selection : null
  const segments = useMemo(() => routes.map(supportSegments), [routes])
  const maxCount = segments.reduce((max, parts) => parts.reduce((value, part) => Math.max(value, part.count), max), 1)
  const bands = useMemo(() => usageBands(maxCount), [maxCount])
  const contributors = useMemo(() => {
    const ids = new Set(selected?.route.sections.map(section => section.subtrajectory_id) ?? [])
    return trajectories.filter(journey => ids.has(journey.subtrajectory_id))
  }, [selected?.route, trajectories])
  const journeyColors = useMemo(() => new Map(
    [...contributors].sort((a, b) => a.subtrajectory_id - b.subtrajectory_id)
      .map((item, index) => [item.subtrajectory_id, journeyColor(index)]),
  ), [contributors])
  const journey = contributors.find(item => item.subtrajectory_id === selected?.journeyId)
  const matchedParts = selected && journey ? contributingParts(selected.route, journey) : []
  const clear = () => { setSelection(null); setHoveredJourney(null); setHoveredRoute(null) }
  const duration = journey ? Math.round((Date.parse(journey.entry_b_time) - Date.parse(journey.exit_a_time)) / 60000) : 0

  function selectRoute(route: Pathlet) {
    if (pickMode) return
    setSelection({ route, journeyId: null })
    setHoveredJourney(null)
    setHoveredRoute(null)
  }

  return <div className="map-card">
    <div className={`map-frame${pickMode ? ' picking-area' : ''}`}>
      {selected && !pickMode && <div className="map-message" role="status">
        <span>{selected.route.count} contributing {selected.route.count === 1 ? 'journey' : 'journeys'}
          {journey && <> · Journey {journey.subtrajectory_id} · {duration} min</>}
        </span>
        {journey && <button type="button" onClick={() => setSelection({ route: selected.route, journeyId: null })}>Clear journey</button>}
        <button type="button" onClick={clear} aria-label="Clear pathlet selection">× Back to all paths (Esc)</button>
      </div>}
      <MapContainer center={DEFAULT_CENTER} zoom={11} className="map">
        <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <MapBehaviour routes={routes} onClear={clear} onCancelPick={onCancelPick} />
        {pickMode && <AreaPicker key={pickMode} mode={pickMode} onPick={onPickArea} onCancel={onCancelPick} />}

        {!selected && routes.map((route, index) => <Fragment key={index}>
          {segments[index].map((segment, part) => segment.points.length >= 2 && <Fragment key={part}>
            <Polyline positions={positions(segment.points)} interactive={false}
              pathOptions={{ color: 'white', weight: hoveredRoute === route ? 11 : 9 }} />
            <Polyline positions={positions(segment.points)} interactive={false}
              pathOptions={{ color: '#292929', weight: hoveredRoute === route ? 9 : 7 }} />
            <Polyline positions={positions(segment.points)} interactive={false} pathOptions={{
              color: usageColor(segment.count, maxCount), weight: hoveredRoute === route ? 7 : 5,
            }} />
            <ClickableLine positions={positions(segment.points)} bubblingMouseEvents={Boolean(pickMode)}
              label={`Pathlet ${index + 1}, ${route.count} contributing journeys`}
              onActivate={() => selectRoute(route)}
              pathOptions={{ color: 'transparent', weight: 17 }} eventHandlers={{
                click: () => selectRoute(route),
                mouseover: () => setHoveredRoute(route), mouseout: () => setHoveredRoute(null),
              }}>
              <Tooltip>{segment.count} {segment.count === 1 ? 'journey' : 'journeys'} here · click to see contributing journeys</Tooltip>
            </ClickableLine>
          </Fragment>)}
        </Fragment>)}

        {selected && <JourneyLayers journeys={contributors} colors={journeyColors} selectedId={selected.journeyId} hoveredId={hoveredJourney}
          onSelect={id => { if (!pickMode) setSelection({ route: selected.route, journeyId: id }) }}
          onHover={setHoveredJourney} picking={Boolean(pickMode)} />}
        {selected && <Pane name="selected-pathlet" style={{ zIndex: 430, pointerEvents: 'none' }}>
          <Polyline positions={positions(selected.route.points)} interactive={false}
            pathOptions={{ color: 'white', weight: 8, dashArray: '10 12' }} />
          <Polyline positions={positions(selected.route.points)} interactive={false}
            pathOptions={{ color: REPRESENTATIVE_COLOR, weight: 4, dashArray: '10 12' }} />
        </Pane>}
        {journey && <Pane name="selected-journey" style={{ zIndex: 440, pointerEvents: 'none' }}>
          <Polyline positions={positions(journey.points)} interactive={false} pathOptions={{ color: 'white', weight: 10 }} />
          <Polyline positions={positions(journey.points)} interactive={false} pathOptions={{ color: journeyColors.get(journey.subtrajectory_id), weight: 6 }} />
          {matchedParts.map((points, index) => <Fragment key={index}>
            <Polyline positions={positions(points)} interactive={false} pathOptions={{ color: 'white', weight: 12 }} />
            <Polyline positions={positions(points)} interactive={false} pathOptions={{ color: CONTRIBUTION_COLOR, weight: 8 }} />
          </Fragment>)}
        </Pane>}
        {(!selected || pickMode) && <Pane name="areas" style={{ zIndex: 450, pointerEvents: 'none' }}>
          {([['A · Start', startArea, '#35754c'], ['B · Destination', endArea, '#79579c']] as const).map(([label, area, color]) => area &&
            <Rectangle key={label} bounds={bounds(area)} interactive={false} pathOptions={{ color, fillOpacity: .08, weight: 2 }}>
              <Tooltip permanent direction="top">{label}</Tooltip>
            </Rectangle>)}
        </Pane>}
      </MapContainer>
    </div>
    {routes.length > 0 && <div className="map-legend">
      {!selected ? <div className="usage-legend">
        <span>Journeys using this stretch</span>
        <div className="usage-bands">
          {bands.map(band => <span className="usage-band" key={band.min}>
            <i style={{ background: band.color }} />{band.min === band.max ? band.min : `${band.min}–${band.max}`}
          </span>)}
        </div>
      </div> : <div className="journey-key">
        <span><i className="representative-key" style={{ borderColor: REPRESENTATIVE_COLOR }} />Selected pathlet</span>
        <span>Different colours = different contributing journeys</span>
        {journey && <>
          <span><i style={{ background: journeyColors.get(journey.subtrajectory_id) }} />Selected journey</span>
          <span><i style={{ background: CONTRIBUTION_COLOR }} />Its contributing parts</span>
        </>}
      </div>}
    </div>}
  </div>
}
