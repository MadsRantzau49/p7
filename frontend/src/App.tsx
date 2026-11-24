import { useState } from 'react'
import type { ClusterSubtrajectory, LatLng, Route, SimilarityLevel } from './types'
import { fetchClusterSubtrajectories, findRoutes, type FindRoutesParams } from './api/subtrajectories'
import SearchPanel from './components/SearchPanel'
import RouteMap from './components/RouteMap'
import RouteOverview from './components/RouteOverview'

type PickMode = 'start' | 'end' | null


const EPSILON_BY_LEVEL: Record<SimilarityLevel, number> = {
  low: 50,
  mid: 100,
  high: 200,
}

// Pull a readable message out of whatever the request threw.
function readErrorMessage(err: unknown): string {
  const maybe = err as { response?: { data?: { detail?: unknown } } }
  const detail = maybe.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (item as { message?: string }).message ?? 'invalid input')
      .join('; ')
  }
  return 'Could not fetch routes.'
}

export default function App() {
  // location
  const [startPoint, setStartPoint] = useState<LatLng | null>(null)
  const [endPoint, setEndPoint] = useState<LatLng | null>(null)
  const [pickMode, setPickMode] = useState<PickMode>(null)

  // date
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')

  // daily time window (optional)
  const [fromHour, setFromHour] = useState('')
  const [toHour, setToHour] = useState('')

  // simi level + custom eplis
  const [similarityLevel, setSimilarityLevel] = useState<SimilarityLevel>('mid')
  const [useCustomEpsilon, setUseCustomEpsilon] = useState(false)
  const [customEpsilon, setCustomEpsilon] = useState(100)

  // Results
  const [routes, setRoutes] = useState<Route[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)
  const [hoveredRoute, setHoveredRoute] = useState<number | null>(null)

  // The opened cluster and the subtrajectories fetched for it.
  const [lastQuery, setLastQuery] = useState<FindRoutesParams | null>(null)
  const [selectedRoute, setSelectedRoute] = useState<number | null>(null)
  const [memberPaths, setMemberPaths] = useState<ClusterSubtrajectory[]>([])


  const epsilonMeters = useCustomEpsilon ? customEpsilon : EPSILON_BY_LEVEL[similarityLevel]

  // search guard, needs all 4 before we hit endpoint 
  const canSearch = Boolean(startPoint && endPoint && fromDate && toDate)

  // A map click lands here. We drop the point we are currently picking.
  function handlePickPoint(point: LatLng) {
    if (pickMode === 'start') setStartPoint(point)
    else if (pickMode === 'end') setEndPoint(point)
    setPickMode(null)
  }

  async function handleFindRoutes() {
    if (!startPoint || !endPoint) return

    const query: FindRoutesParams = {
      start: startPoint,
      end: endPoint,
      fromDate,
      toDate,
      fromHour,
      toHour,
      epsilon: epsilonMeters,
    }

    setLoading(true)
    setError(null)
    // A new search clears any opened cluster.
    setSelectedRoute(null)
    setMemberPaths([])
    try {
      const result = await findRoutes(query)
      setRoutes(result)
      setLastQuery(query)
      setHasSearched(true)
    } catch (err) {
      setError(readErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  // Open a cluster to see its subtrajectories, or close it when clicked again.
  async function handleSelectRoute(index: number) {
    if (selectedRoute === index) {
      setSelectedRoute(null)
      setMemberPaths([])
      return
    }
    setSelectedRoute(index)
    setMemberPaths([])
    const route = routes[index]
    if (!lastQuery || !route) return
    try {
      const paths = await fetchClusterSubtrajectories(lastQuery, route.members)
      setMemberPaths(paths)
    } catch (err) {
      setError(readErrorMessage(err))
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Route Explorer</h1>
      </header>

      <div className="app-body">
        <div className="left-column">
          <SearchPanel
            startPoint={startPoint}
            endPoint={endPoint}
            pickMode={pickMode}
            setPickMode={setPickMode}
            fromDate={fromDate}
            setFromDate={setFromDate}
            toDate={toDate}
            setToDate={setToDate}
            fromHour={fromHour}
            setFromHour={setFromHour}
            toHour={toHour}
            setToHour={setToHour}
            similarityLevel={similarityLevel}
            setSimilarityLevel={setSimilarityLevel}
            useCustomEpsilon={useCustomEpsilon}
            setUseCustomEpsilon={setUseCustomEpsilon}
            customEpsilon={customEpsilon}
            setCustomEpsilon={setCustomEpsilon}
            epsilonMeters={epsilonMeters}
            loading={loading}
            canSearch={canSearch}
            error={error}
            onFindRoutes={handleFindRoutes}
          />

          <RouteOverview
            routes={routes}
            hasSearched={hasSearched}
            hoveredRoute={hoveredRoute}
            setHoveredRoute={setHoveredRoute}
            selectedRoute={selectedRoute}
            onSelectRoute={handleSelectRoute}
          />
        </div>

        <RouteMap
          startPoint={startPoint}
          endPoint={endPoint}
          pickMode={pickMode}
          onPickPoint={handlePickPoint}
          routes={routes}
          hoveredRoute={hoveredRoute}
          setHoveredRoute={setHoveredRoute}
          selectedRoute={selectedRoute}
          memberPaths={memberPaths}
          onSelectRoute={handleSelectRoute}
        />
      </div>
    </div>
  )
}
