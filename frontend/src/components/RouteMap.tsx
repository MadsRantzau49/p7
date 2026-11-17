import { Fragment, memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, DomEvent, latLngBounds, tooltip as createTooltip } from 'leaflet'
import type { LatLngExpression, LatLngTuple, LeafletEventHandlerFnMap, LeafletMouseEvent, PathOptions } from 'leaflet'
import { MapContainer, TileLayer, CircleMarker, Pane, Polyline, Rectangle, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import type { Area, GpsPoint, LatLng, Pathlet, PickMode, Subtrajectory } from '../types'
import { CONTRIBUTION_COLOR, REPRESENTATIVE_COLOR, journeyColor, usageBand, usageBands } from '../colors'
import { areaFromCorners, contributingParts, supportSegments } from '../routeGeometry'

// Performance notes
// - The map uses preferCanvas: every pane is one <canvas> instead of one SVG element per line,
//   so thousands of lines stay smooth to pan and zoom. Lines are thin, so the cursor counts as
//   "on" a line within a few extra pixels.
// - react-leaflet calls setLatLngs/setStyle whenever `positions`/`pathOptions` are new objects,
//   so both are computed once (useMemo / constants) and never inline in JSX.
// - Hovering must not re-render the full set of lines: line components are memoised and the
//   hover highlight is drawn in its own small layer.
// - Panes stay mounted. Leaflet keeps a canvas renderer per pane, and remounting a pane leaves
//   the old renderer behind, redrawing on every pan.
// - Only the topmost canvas receives mouse events, so all clickable lines live in the default
//   overlay pane and every custom pane ignores the pointer.
// - Leaflet reads bubblingMouseEvents only when a line is created, so line layers are keyed on
//   picking mode and recreated when it changes.
Canvas.mergeOptions({ tolerance: 6 })

type Props = {
  startArea: Area | null
  endArea: Area | null
  pickMode: PickMode
  onPickArea: (area: Area) => boolean
  onCancelPick: () => void
  routes: Pathlet[]
  trajectories: Subtrajectory[]
}

type PathletLine = {
  key: string
  route: Pathlet
  positions: LatLngTuple[]
  count: number
  style: PathOptions
  hoverHalo: PathOptions
  hoverStyle: PathOptions
}

// Retain the existing deployment's initial view; results are fitted automatically.
const DEFAULT_CENTER: [number, number] = [39.9, 116.4]
const NO_POINTER = { pointerEvents: 'none' } as const
const toPositions = (points: GpsPoint[]): LatLngTuple[] => points.map(p => [p.latitude, p.longitude])
const bounds = (area: Area): [[number, number], [number, number]] => [
  [area.min_latitude, area.min_longitude], [area.max_latitude, area.max_longitude],
]
const journeysText = (count: number) => `${count} ${count === 1 ? 'journey' : 'journeys'}`

const SELECTED_PATHLET_HALO: PathOptions = { color: 'white', weight: 8, dashArray: '10 12' }
const SELECTED_PATHLET_LINE: PathOptions = { color: REPRESENTATIVE_COLOR, weight: 4, dashArray: '10 12' }
const SELECTED_JOURNEY_HALO: PathOptions = { color: 'white', weight: 10 }
const MATCHED_PART_HALO: PathOptions = { color: 'white', weight: 12 }
const MATCHED_PART_LINE: PathOptions = { color: CONTRIBUTION_COLOR, weight: 8 }
// A and B are only outlined (no fill), so the routes inside them stay visible.
const AREA_STYLES = {
  start: { color: '#35754c', fill: false, weight: 2, dashArray: '6 4' },
  end: { color: '#79579c', fill: false, weight: 2, dashArray: '6 4' },
} satisfies Record<string, PathOptions>

// One shared Leaflet tooltip that follows the cursor, instead of a <Tooltip> per line.
function useHoverTooltip() {
  const map = useMap()
  const tooltip = useMemo(() => createTooltip({ direction: 'top', offset: [0, -8] }), [])
  useEffect(() => () => { map.closeTooltip(tooltip) }, [map, tooltip])
  return useMemo(() => ({
    show(text: string, latlng: LatLngExpression) {
      tooltip.setContent(text).setLatLng(latlng)
      map.openTooltip(tooltip)
    },
    move(latlng: LatLngExpression) { tooltip.setLatLng(latlng) },
    hide() { map.closeTooltip(tooltip) },
  }), [map, tooltip])
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
  // The shapes go in the "areas" pane, so redrawing the rectangle as the mouse moves only
  // repaints that pane's small canvas, not the canvas holding every pathlet.
  return <>
    <div className="map-message" role="status" ref={element => { if (element) DomEvent.disableClickPropagation(element) }}>
      {tooSmall ? 'Choose a larger rectangle.' : first ? 'Click the opposite corner.' : `Click the first corner of the ${mode === 'start' ? 'starting' : 'destination'} area.`}
      <button type="button" onClick={onCancel}>Cancel</button>
    </div>
    {first && <CircleMarker pane="areas" center={[first.lat, first.lng]} radius={4} interactive={false} />}
    {first && pointer && <Rectangle pane="areas" bounds={bounds(areaFromCorners(first, pointer))} interactive={false}
      pathOptions={{ color: mode === 'start' ? '#35754c' : '#79579c', dashArray: '5 5', fillOpacity: .12 }} />}
  </>
}

// Every pathlet stretch: a dark casing plus a coloured line. Memoised, so it only re-renders
// when the search results or picking mode change, never on hover.
const PathletLines = memo(function PathletLines({ lines, picking, onSelect, onHover }: {
  lines: PathletLine[]; picking: boolean
  onSelect: (route: Pathlet) => void; onHover: (route: Pathlet | null) => void
}) {
  const tooltip = useHoverTooltip()
  const handlers = useMemo(() => lines.map((line): LeafletEventHandlerFnMap => ({
    mouseover: event => {
      if (picking) return
      onHover(line.route)
      tooltip.show(`${journeysText(line.count)} here · click to see contributing journeys`, event.latlng)
    },
    mousemove: event => tooltip.move(event.latlng),
    mouseout: () => { onHover(null); tooltip.hide() },
    click: () => {
      if (picking) return
      tooltip.hide()
      onSelect(line.route)
    },
  })), [lines, picking, onSelect, onHover, tooltip])
  return <>
    {lines.map((line, index) => <Polyline key={line.key} positions={line.positions} pathOptions={line.style}
      bubblingMouseEvents={picking} eventHandlers={handlers[index]} />)}
  </>
})

// The hovered pathlet, drawn on top with a white outline so it stands out from the rest.
const HoverHighlight = memo(function HoverHighlight({ lines }: { lines: PathletLine[] }) {
  return <>
    {lines.map(line => <Polyline key={line.key + ':halo'} positions={line.positions} interactive={false} pathOptions={line.hoverHalo} />)}
    {lines.map(line => <Polyline key={line.key} positions={line.positions} interactive={false} pathOptions={line.hoverStyle} />)}
  </>
})

const JourneyLine = memo(function JourneyLine({ positions, color, dimmed, hovered, picking, eventHandlers }: {
  positions: LatLngTuple[]; color: string | undefined; dimmed: boolean; hovered: boolean
  picking: boolean; eventHandlers: LeafletEventHandlerFnMap | undefined
}) {
  const halo = useMemo<PathOptions>(() => ({ color: 'white', opacity: dimmed ? .45 : .9, weight: hovered ? 8 : 6 }), [dimmed, hovered])
  const line = useMemo<PathOptions>(() => ({ color, opacity: dimmed ? .5 : .9, weight: hovered ? 6 : 4 }), [color, dimmed, hovered])
  return <>
    <Polyline positions={positions} interactive={false} pathOptions={halo} />
    <Polyline positions={positions} pathOptions={line} bubblingMouseEvents={picking} eventHandlers={eventHandlers} />
  </>
})

function JourneyLayers({ journeys, colors, selectedId, hoveredId, onSelect, onHover, picking }: {
  journeys: Subtrajectory[]; selectedId: number | null; hoveredId: number | null
  colors: ReadonlyMap<number, string>
  onSelect: (id: number) => void; onHover: (id: number | null) => void; picking: boolean
}) {
  const map = useMap()
  const tooltip = useHoverTooltip()
  // Click handlers read the latest selection through a ref, so they (and the memoised lines)
  // do not have to be recreated whenever the selected journey changes.
  const latest = useRef({ selectedId, onSelect })
  useEffect(() => { latest.current = { selectedId, onSelect } })

  const positionsById = useMemo(() => new Map(journeys.map(journey => [journey.subtrajectory_id, toPositions(journey.points)])), [journeys])

  const handlers = useMemo(() => {
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
      const current = nearest.findIndex(item => item.journey.subtrajectory_id === latest.current.selectedId)
      latest.current.onSelect(nearest[(current + 1) % nearest.length].journey.subtrajectory_id)
    }
    return new Map(journeys.map((journey): [number, LeafletEventHandlerFnMap] => [journey.subtrajectory_id, {
      mouseover: event => {
        if (picking) return
        onHover(journey.subtrajectory_id)
        tooltip.show('Click to follow this journey. Click again for overlapping journeys.', event.latlng)
      },
      mousemove: event => tooltip.move(event.latlng),
      mouseout: () => { onHover(null); tooltip.hide() },
      click: selectNearest,
    }]))
  }, [journeys, map, picking, onHover, tooltip])

  return <>
    {journeys.map(journey => <JourneyLine key={journey.subtrajectory_id}
      positions={positionsById.get(journey.subtrajectory_id)!}
      color={colors.get(journey.subtrajectory_id)}
      dimmed={selectedId !== null && selectedId !== journey.subtrajectory_id}
      hovered={hoveredId === journey.subtrajectory_id}
      picking={picking} eventHandlers={handlers.get(journey.subtrajectory_id)} />)}
  </>
}

export default function RouteMap({ startArea, endArea, pickMode, onPickArea, onCancelPick, routes, trajectories }: Props) {
  const [selection, setSelection] = useState<{ route: Pathlet; journeyId: number | null } | null>(null)
  const [hoveredRoute, setHoveredRoute] = useState<Pathlet | null>(null)
  const [hoveredJourney, setHoveredJourney] = useState<number | null>(null)
  const selected = selection && routes.includes(selection.route) ? selection : null
  const picking = Boolean(pickMode)

  // Split, colour and convert every pathlet once per search result.
  const { lines, maxCount } = useMemo(() => {
    const segments = routes.map(supportSegments)
    const maxCount = segments.reduce((max, parts) => parts.reduce((value, part) => Math.max(value, part.count), max), 1)
    const bands = usageBands(maxCount)
    const lines = routes.flatMap((route, routeIndex) => segments[routeIndex]
      .filter(segment => segment.points.length >= 2)
      .map((segment, part): PathletLine => {
        const { color, weight } = usageBand(segment.count, bands)
        return {
          key: `${routeIndex}-${part}`, route, positions: toPositions(segment.points), count: segment.count,
          style: { color, weight },
          hoverHalo: { color: 'white', weight: weight + 6 },
          hoverStyle: { color, weight: weight + 2 },
        }
      }))
      // Canvas draws in order: quiet stretches first, so the busy ones end up on top.
      .sort((a, b) => a.count - b.count)
    return { lines, maxCount }
  }, [routes])
  const bands = useMemo(() => usageBands(maxCount), [maxCount])
  const hoveredLines = useMemo(() => hoveredRoute ? lines.filter(line => line.route === hoveredRoute) : [], [lines, hoveredRoute])

  const contributors = useMemo(() => {
    const ids = new Set(selected?.route.sections.map(section => section.subtrajectory_id) ?? [])
    return trajectories.filter(journey => ids.has(journey.subtrajectory_id))
  }, [selected?.route, trajectories])
  const journeyColors = useMemo(() => new Map(
    [...contributors].sort((a, b) => a.subtrajectory_id - b.subtrajectory_id)
      .map((item, index) => [item.subtrajectory_id, journeyColor(index)]),
  ), [contributors])
  const journey = contributors.find(item => item.subtrajectory_id === selected?.journeyId)
  const selectedRoute = selected?.route ?? null
  const selectedPathletPositions = useMemo(() => selectedRoute ? toPositions(selectedRoute.points) : [], [selectedRoute])
  const journeyPositions = useMemo(() => journey ? toPositions(journey.points) : [], [journey])
  const journeyStyle = useMemo<PathOptions>(() => ({ color: journey && journeyColors.get(journey.subtrajectory_id), weight: 6 }), [journey, journeyColors])
  const matchedParts = useMemo(() => selectedRoute && journey ? contributingParts(selectedRoute, journey).map(toPositions) : [], [selectedRoute, journey])
  const duration = journey ? Math.round((Date.parse(journey.entry_b_time) - Date.parse(journey.exit_a_time)) / 60000) : 0

  const clear = useCallback(() => { setSelection(null); setHoveredJourney(null); setHoveredRoute(null) }, [])
  const selectRoute = useCallback((route: Pathlet) => {
    setSelection({ route, journeyId: null })
    setHoveredJourney(null)
    setHoveredRoute(null)
  }, [])
  const selectJourney = useCallback((id: number) => {
    setSelection(current => current && { route: current.route, journeyId: id })
  }, [])

  return <div className="map-card">
    <div className={`map-frame${pickMode ? ' picking-area' : ''}`}>
      {selected && !pickMode && <div className="map-message" role="status">
        <span>{selected.route.count} contributing {selected.route.count === 1 ? 'journey' : 'journeys'}
          {journey && <> · Journey {journey.subtrajectory_id} · {duration} min</>}
        </span>
        {journey && <button type="button" onClick={() => setSelection({ route: selected.route, journeyId: null })}>Clear journey</button>}
        <button type="button" onClick={clear} aria-label="Clear pathlet selection">× Back to all paths (Esc)</button>
      </div>}
      <MapContainer center={DEFAULT_CENTER} zoom={11} className="map" preferCanvas>
        <TileLayer className="basemap" attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <MapBehaviour routes={routes} onClear={clear} onCancelPick={onCancelPick} />
        {pickMode && <AreaPicker key={pickMode} mode={pickMode} onPick={onPickArea} onCancel={onCancelPick} />}

        {/* Interactive lines: default overlay pane (z-index 400). Only one of the two is shown at a time. */}
        {!selected && <PathletLines key={picking ? 'picking' : 'browsing'} lines={lines} picking={picking}
          onSelect={selectRoute} onHover={setHoveredRoute} />}
        {selected && <JourneyLayers key={picking ? 'picking' : 'browsing'} journeys={contributors} colors={journeyColors}
          selectedId={selected.journeyId} hoveredId={hoveredJourney}
          onSelect={selectJourney} onHover={setHoveredJourney} picking={picking} />}

        {/* Decoration panes: always mounted, never receive the pointer. */}
        <Pane name="hovered-pathlet" style={{ zIndex: 410, ...NO_POINTER }}>
          {!selected && <HoverHighlight lines={hoveredLines} />}
        </Pane>
        <Pane name="selected-pathlet" style={{ zIndex: 430, ...NO_POINTER }}>
          {selected && <>
            <Polyline positions={selectedPathletPositions} interactive={false} pathOptions={SELECTED_PATHLET_HALO} />
            <Polyline positions={selectedPathletPositions} interactive={false} pathOptions={SELECTED_PATHLET_LINE} />
          </>}
        </Pane>
        <Pane name="selected-journey" style={{ zIndex: 440, ...NO_POINTER }}>
          {journey && <>
            <Polyline positions={journeyPositions} interactive={false} pathOptions={SELECTED_JOURNEY_HALO} />
            <Polyline positions={journeyPositions} interactive={false} pathOptions={journeyStyle} />
            {matchedParts.map((points, index) => <Fragment key={index}>
              <Polyline positions={points} interactive={false} pathOptions={MATCHED_PART_HALO} />
              <Polyline positions={points} interactive={false} pathOptions={MATCHED_PART_LINE} />
            </Fragment>)}
          </>}
        </Pane>
        <Pane name="areas" style={{ zIndex: 450, ...NO_POINTER }}>
          {(!selected || pickMode) && ([['A', 'start', startArea], ['B', 'end', endArea]] as const)
            .map(([label, kind, area]) => area &&
              <Rectangle key={label} bounds={bounds(area)} interactive={false} pathOptions={AREA_STYLES[kind]}>
                <Tooltip permanent direction="top" offset={[0, -2]} className={`area-label area-label-${kind}`}>{label}</Tooltip>
              </Rectangle>)}
        </Pane>
      </MapContainer>
    </div>
    {routes.length > 0 && <div className="map-legend">
      {!selected ? <div className="usage-legend">
        <span>Journeys using this stretch</span>
        <div className="usage-bands">
          {bands.map(band => <span className="usage-band" key={band.min}>
            <i style={{ background: band.color, height: band.weight }} />{band.min === band.max ? band.min : `${band.min}–${band.max}`}
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
