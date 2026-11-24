import { useState } from 'react'
import type { Area, Pathlet, PickMode, SimilarityLevel } from './types'
import { findRoutes } from './api/subtrajectories'
import SearchPanel from './components/SearchPanel'
import RouteMap from './components/RouteMap'
import RouteOverview from './components/RouteOverview'
import { datesAllowSearch } from './dateRange'
import { areasOverlap } from './areaGeometry'


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
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hasSearched, setHasSearched] = useState(false)
  const [hoveredRoute, setHoveredRoute] = useState<number | null>(null)


  const epsilonMeters = useCustomEpsilon ? customEpsilon : EPSILON_BY_LEVEL[similarityLevel]

  // Location and date requirements are checked separately.
  const canSearch = Boolean(startArea && endArea) && datesAllowSearch(fromDate, toDate)

  function handlePickArea(area: Area) {
    const other = pickMode === 'start' ? endArea : startArea
    if (other && areasOverlap(area, other)) {
      setError('Start and destination areas must not overlap. Choose another corner.')
      return
    }
    if (pickMode === 'start') setStartArea(area)
    else if (pickMode === 'end') setEndArea(area)
    setError(null)
    setPickMode(null)
  }

  async function handleFindRoutes() {
    if (loading || !startArea || !endArea) return

    if (fromDate && toDate && fromDate > toDate) {
      setError('From date must be on or before To date.')
      return
    }

    setLoading(true)
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
      setRoutes(result)
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

          <RouteOverview
            routes={routes}
            hasSearched={hasSearched}
            hoveredRoute={hoveredRoute}
            setHoveredRoute={setHoveredRoute}
          />
        </div>

        <RouteMap
          startArea={startArea}
          endArea={endArea}
          pickMode={pickMode}
          onPickArea={handlePickArea}
          onCancelPick={() => setPickMode(null)}
          routes={routes}
          hoveredRoute={hoveredRoute}
          setHoveredRoute={setHoveredRoute}
        />
      </div>
    </div>
  )
}
