import { useState } from 'react'
import type { Area, Pathlet, PickMode, SimilarityLevel, Subtrajectory } from './types'
import { findRoutes } from './api/subtrajectories'
import SearchPanel from './components/SearchPanel'
import RouteMap from './components/RouteMap'
import { areasOverlap } from './routeGeometry'


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
      .map((item) => (item as { msg?: string }).msg ?? 'invalid input')
      .join('; ')
  }
  return 'Could not fetch routes.'
}

export default function App() {
  // location
  const [startArea, setStartArea] = useState<Area | null>(null)
  const [endArea, setEndArea] = useState<Area | null>(null)
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
  const [routes, setRoutes] = useState<Pathlet[]>([])
  const [trajectories, setTrajectories] = useState<Subtrajectory[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)


  const epsilonMeters = useCustomEpsilon ? customEpsilon : EPSILON_BY_LEVEL[similarityLevel]

  const canSearch = Boolean(startArea && endArea && Number.isFinite(epsilonMeters) && epsilonMeters > 0)

  function handlePickArea(area: Area): boolean {
    const other = pickMode === 'start' ? endArea : startArea
    if (other && areasOverlap(area, other)) {
      setError('Start and destination areas must not overlap. Choose another corner.')
      return false
    }
    if (pickMode === 'start') setStartArea(area)
    else if (pickMode === 'end') setEndArea(area)
    setError(null)
    setPickMode(null)
    return true
  }

  async function handleFindRoutes() {
    if (!startArea || !endArea || !canSearch || loading) return
    if (fromDate && toDate && fromDate > toDate) {
      setError('From date must be on or before To date.')
      return
    }

    setLoading(true)
    setPickMode(null)
    setRoutes([])
    setTrajectories([])
    setHasSearched(false)
    setError(null)
    try {
      const result = await findRoutes({
        start: startArea,
        end: endArea,
        fromDate,
        toDate,
        fromHour,
        toHour,
        epsilon: epsilonMeters,
      })
      setRoutes(result.pathlets)
      setTrajectories(result.trajectories)
      setHasSearched(true)
    } catch (err) {
      setError(readErrorMessage(err))
    } finally {
      setLoading(false)
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
            startArea={startArea}
            endArea={endArea}
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

          <p className="help-text" role="status">
            {loading ? 'Finding journeys…' : hasSearched
              ? routes.length ? 'Click a path on the map to see its journeys.' : 'No journeys found for these areas and dates.'
              : 'Select two areas and find routes.'}
          </p>
        </div>

        <RouteMap
          startArea={startArea}
          endArea={endArea}
          pickMode={pickMode}
          onPickArea={handlePickArea}
          onCancelPick={() => setPickMode(null)}
          routes={routes}
          trajectories={trajectories}
        />
      </div>
    </div>
  )
}
