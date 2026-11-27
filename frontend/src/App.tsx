import { useEffect, useRef, useState } from 'react'
import type { Area, ClusterSubtrajectory, PickMode, SimilarityLevel } from './types'
import { fetchClusterSubtrajectories, findRoutes, type FindRoutesParams } from './api/subtrajectories'
import SearchPanel from './components/SearchPanel'
import HealthBanner from './components/HealthBanner'
import { checkHealth, type HealthStatus } from './api/health'
import RouteMap from './components/RouteMap'
import RouteOverview from './components/RouteOverview'
import { datesAllowSearch } from './dateRange'
import { areasOverlap } from './areaGeometry'
import { routeKey, sameRoute, type RouteRef, type SearchResult } from './searches'


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

  // Results: one entry per search. A normal search replaces them all; in compare mode the
  // next search is added beside the ones already shown.
  const [searches, setSearches] = useState<SearchResult[]>([])
  const [compareMode, setCompareMode] = useState(false)
  const nextSearchId = useRef(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hoveredRoute, setHoveredRoute] = useState<RouteRef | null>(null)
  // Routes the user ticked in the list. When any are ticked, the map shows only those.
  const [checkedRoutes, setCheckedRoutes] = useState<Set<string>>(new Set())

  // The opened cluster and the subtrajectories fetched for it.
  const [selectedRoute, setSelectedRoute] = useState<RouteRef | null>(null)
  const [memberPaths, setMemberPaths] = useState<ClusterSubtrajectory[]>([])
  const [memberLoading, setMemberLoading] = useState(false)
  // Which subtrajectory of the open cluster is highlighted, shared by the list and the map.
  const [hoveredMember, setHoveredMember] = useState<number | null>(null)
  const [minSubtrajectories, setMinSubtrajectories] = useState(5)

  // Backend health, checked when the page loads. Until it passes, nothing can be used.
  const [healthStatus, setHealthStatus] = useState<HealthStatus>('checking')
  const backendReady = healthStatus === 'healthy'

  useEffect(() => {
    let cancelled = false
    void checkHealth().then((ok) => {
      if (!cancelled) setHealthStatus(ok ? 'healthy' : 'unhealthy')
    })
    return () => {
      cancelled = true
    }
  }, [])

  async function handleRetryHealth() {
    setHealthStatus('checking')
    setHealthStatus((await checkHealth()) ? 'healthy' : 'unhealthy')
  }


  let largestCluster = 1

  for (const search of searches) {
    for (const route of search.routes) {
      largestCluster = Math.max(largestCluster, route.members.length)
    }
  }
  
  const effectiveMin = Math.min(minSubtrajectories, largestCluster)

  const epsilonMeters = useCustomEpsilon ? customEpsilon : EPSILON_BY_LEVEL[similarityLevel]

  // Location and date requirements are checked separately.
  const canSearch = Boolean(startArea && endArea) && datesAllowSearch(fromDate, toDate)

  function handlePickArea(area: Area) {
    const other = pickMode === 'start' ? endArea : startArea
    if (other && areasOverlap(area, other)) {
      setError('Start and destination areas must not overlap. Choose another area.')
      return
    }
    if (pickMode === 'start') setStartArea(area)
    else if (pickMode === 'end') setEndArea(area)
    setError(null)
    setPickMode(null)
  }

  async function handleFindRoutes() {
    if (loading || !backendReady || !startArea || !endArea) return

    if (fromDate && toDate && fromDate > toDate) {
      setError('From date must be on or before To date.')
      return
    }

    const query: FindRoutesParams = {
      start: startArea,
      end: endArea,
      fromDate,
      toDate,
      fromHour,
      toHour,
      epsilon: epsilonMeters,
    }

    setLoading(true)
    setError(null)
    // Stop any area picking so the map is idle while the search runs.
    setPickMode(null)
    // A new search clears any opened cluster.
    setSelectedRoute(null)
    setHoveredRoute(null)
    setMemberPaths([])
    try {
      const routes = await findRoutes(query)
      const search: SearchResult = { id: nextSearchId.current++, query, routes }
      setSearches((previous) => (compareMode ? [...previous, search] : [search]))
      // A fresh search drops the old results, so their ticks go too; comparing keeps them.
      if (!compareMode) setCheckedRoutes(new Set())
      setCompareMode(false)
    } catch (err) {
      setError(readErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  function handleToggleChecked(ref: RouteRef) {
    setCheckedRoutes((previous) => {
      const next = new Set(previous)
      const key = routeKey(ref)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // Open a cluster to see its subtrajectories, or close it when clicked again.
  async function handleSelectRoute(ref: RouteRef) {
    setHoveredMember(null)
    if (sameRoute(selectedRoute, ref)) {
      setSelectedRoute(null)
      setMemberPaths([])
      return
    }
    setSelectedRoute(ref)
    setMemberPaths([])
    const search = searches.find((entry) => entry.id === ref.searchId)
    const route = search?.routes[ref.index]
    if (!search || !route) return
    setMemberLoading(true)
    try {
      const paths = await fetchClusterSubtrajectories(search.query, route.members)
      setMemberPaths(paths)
    } catch (err) {
      setError(readErrorMessage(err))
    } finally {
      setMemberLoading(false)
    }
  }

  function handleToggleCompare() {
    if (!compareMode && searches.length > 0) {
      const latest = searches[searches.length - 1]
      setPickMode(null)
      setStartArea(latest.query.start)
      setEndArea(latest.query.end)
    }
    setCompareMode(!compareMode)
  }

  function handleClear() {
    setStartArea(null)
    setEndArea(null)
    setPickMode(null)
    setSearches([])
    setCompareMode(false)
    setCheckedRoutes(new Set())
    setHoveredRoute(null)
    setSelectedRoute(null)
    setMemberPaths([])
    setHoveredMember(null)
    setError(null)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Route Explorer</h1>
      </header>

      <div className="app-body">
        {/* While a search runs, the side columns are inert (no clicks, focus or typing) and the
            map is covered by a loading overlay, so nothing can change mid-search. */}
        <div className={loading ? 'left-column busy' : 'left-column'} inert={loading}>
          <HealthBanner status={healthStatus} onRetry={handleRetryHealth} />

          {/* The controls stay inert until the health check passes. */}
          <div
            className={backendReady ? 'left-column-controls' : 'left-column-controls disabled'}
            inert={!backendReady}
          >
          <SearchPanel
            startArea={startArea}
            endArea={endArea}
            pickMode={pickMode}
            setPickMode={setPickMode}
            areasLocked={compareMode}
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
            canSearch={canSearch && backendReady}
            error={error}
            onFindRoutes={handleFindRoutes}
          />

          {/* Shown once there is a search to compare against. */}
          {searches.length > 0 && (
            <div className="compare-panel">
              <button
                type="button"
                className={compareMode ? 'compare-button active' : 'compare-button'}
                aria-pressed={compareMode}
                onClick={handleToggleCompare}
              >
                {compareMode ? 'Cancel compare' : 'Compare'}
              </button>
              <p className="help-text">
                {compareMode
                  ? 'Change the search settings and click "Find routes" to add a search beside the current ones.'
                  : 'Keep these results and add another search to compare with.'}
              </p>
            </div>
          )}
          </div>
        </div>

        {/* The map sits in the middle and takes all remaining width. */}
        <RouteMap
          startArea={startArea}
          endArea={endArea}
          pickMode={pickMode}
          onPickArea={handlePickArea}
          onCancelPick={() => setPickMode(null)}
          searches={searches}
          searching={loading}
          checkedRoutes={checkedRoutes}
          hoveredRoute={hoveredRoute}
          setHoveredRoute={setHoveredRoute}
          selectedRoute={selectedRoute}
          memberPaths={memberPaths}
          memberLoading={memberLoading}
          hoveredMember={hoveredMember}
          setHoveredMember={setHoveredMember}
          onSelectRoute={handleSelectRoute}
          minSubtrajectories={effectiveMin}
        />

        {/* Route list on the right of the map. */}
        {searches.length > 0 && (
          <div className={loading ? 'right-column busy' : 'right-column'} inert={loading}>
            <RouteOverview
              searches={searches}
              compareMode={compareMode}
              checkedRoutes={checkedRoutes}
              onToggleChecked={handleToggleChecked}
              hoveredRoute={hoveredRoute}
              setHoveredRoute={setHoveredRoute}
              selectedRoute={selectedRoute}
              onSelectRoute={handleSelectRoute}
              memberPaths={memberPaths}
              memberLoading={memberLoading}
              hoveredMember={hoveredMember}
              setHoveredMember={setHoveredMember}
              onClear={handleClear}
              minSubtrajectories={effectiveMin}
              setMinSubtrajectories={setMinSubtrajectories}
              largestCluster={largestCluster}
            />
          </div>
        )}
      </div>
    </div>
  )
}
