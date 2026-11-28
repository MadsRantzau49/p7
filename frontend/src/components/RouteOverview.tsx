import { Fragment, useState } from 'react'
import type { ClusterSubtrajectory } from '../types'
import { routeColor, searchColor } from '../colors'
import { filterRoutes, meetsMinimum, routeKey, sameRoute, searchConstraints, totalSubtrajectories, type RouteRef, type SearchResult } from '../searches'

type Props = {
  searches: SearchResult[]
  compareMode: boolean
  checkedRoutes: Set<string>
  onToggleChecked: (ref: RouteRef) => void
  hoveredRoute: RouteRef | null
  setHoveredRoute: (ref: RouteRef | null) => void
  selectedRoute: RouteRef | null
  onSelectRoute: (ref: RouteRef) => void
  memberPaths: ClusterSubtrajectory[]
  memberLoading: boolean
  hoveredMember: number | null
  setHoveredMember: (index: number | null) => void
  onClear: () => void
  minSubtrajectories: number
  setMinSubtrajectories: (value: number) => void
  largestCluster: number
}

export default function RouteOverview({
  searches,
  compareMode,
  checkedRoutes,
  onToggleChecked,
  hoveredRoute,
  setHoveredRoute,
  selectedRoute,
  onSelectRoute,
  memberPaths,
  memberLoading,
  hoveredMember,
  setHoveredMember,
  onClear,
  minSubtrajectories,
  setMinSubtrajectories,
  largestCluster,
}: Props) {
  // Which searches the user has expanded. Search entries will start collapsed.
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const [minDraft, setMinDraft] = useState<string | null>(null)

  function handleMinTyped(text: string) {
    setMinDraft(text)
    const value = Number(text)
    if (text !== '' && Number.isInteger(value) && value >= 1) {
      setMinSubtrajectories(Math.min(value, largestCluster))
    }
  }

  function toggleExpanded(searchId: number) {
    setExpanded((previous) => {
      const next = new Set(previous)
      if (next.has(searchId)) {
        next.delete(searchId)
      }
      else{
        next.add(searchId)
      } 
      return next
    })
  }

  const routeProps = {
    checkedRoutes,
    onToggleChecked,
    hoveredRoute,
    setHoveredRoute,
    selectedRoute,
    onSelectRoute,
    memberPaths,
    memberLoading,
    hoveredMember,
    setHoveredMember,
    minSubtrajectories,
  }

  const controls = (
    <>
      <button type="button" className="clear-button" onClick={onClear}>
        Clear map
      </button>
      <div className="min-filter">
        <span className="min-filter-label">
          Minimum subtrajectories in each route
          <input
            type="number"
            className="min-filter-number"
            min={1}
            max={largestCluster}
            step={1}
            value={minDraft ?? minSubtrajectories}
            onChange={(event) => handleMinTyped(event.target.value)}
            onBlur={() => setMinDraft(null)}
            aria-label="Minimum subtrajectories per route"
          />
        </span>
        <input
          type="range"
          min={1}
          max={largestCluster}
          step={1}
          value={minSubtrajectories}
          disabled={largestCluster <= 1}
          onChange={(event) => {
            setMinDraft(null)
            setMinSubtrajectories(Number(event.target.value))
          }}
          aria-label="Minimum subtrajectories per route"
        />
      </div>
    </>
  )

  // A single search, outside compare mode, lists its routes directly. Searches are only
  // grouped into collapsible entries once the user starts comparing.
  if (searches.length === 1 && !compareMode) {
    const [search] = searches
    return (
      <div className="overview">
        {controls}
        <h3>
          Routes shown: {filterRoutes(search.routes, minSubtrajectories).length} of {search.routes.length}
          <span className="overview-total">
            {' '}· {totalSubtrajectories(filterRoutes(search.routes, minSubtrajectories))} subtrajectories
          </span>
        </h3>
        <p className="overview-meta">Grouping distance: {search.query.epsilon} m</p>
        <SearchRoutes search={search} position={0} searchCount={1} {...routeProps} />
      </div>
    )
  }

  return (
    <div className="overview">
      {controls}
      <h3>Searches: {searches.length}</h3>
      <ul className="search-list">
        {searches.map((search, position) => {
          // A search holding the opened cluster stays open, so its trip list is visible
          // even when the cluster was clicked on the map.
          const isOpen = expanded.has(search.id) || selectedRoute?.searchId === search.id
          return (
            <li key={search.id} className="search-entry">
              <button
                type="button"
                className="search-header"
                aria-expanded={isOpen}
                onClick={() => toggleExpanded(search.id)}
              >
                <span className={isOpen ? 'chevron open' : 'chevron'} aria-hidden="true">
                  ▸
                </span>
                <span className="swatch" style={{ backgroundColor: searchColor(position) }} />
                <span className="search-name">Search {position + 1}</span>
                <span className="search-constraints">
                  {searchConstraints(search).map(({ label, value }) => (
                    <Fragment key={label}>
                      <span className="constraint-label">{label}</span>
                      <span className="constraint-value">{value}</span>
                    </Fragment>
                  ))}
                </span>
                <span className="search-summary">
                  {filterRoutes(search.routes, minSubtrajectories).length} routes · {totalSubtrajectories(filterRoutes(search.routes, minSubtrajectories))} subtrajectories
                </span>
              </button>

              {isOpen && (
                <SearchRoutes search={search} position={position} searchCount={searches.length} {...routeProps} />
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// The routes of one search, each with its share of the search's subtrajectories.
function SearchRoutes({
  search,
  position,
  searchCount,
  checkedRoutes,
  onToggleChecked,
  hoveredRoute,
  setHoveredRoute,
  selectedRoute,
  onSelectRoute,
  memberPaths,
  memberLoading,
  hoveredMember,
  setHoveredMember,
  minSubtrajectories,
}: Omit<Props, 'searches' | 'compareMode' | 'onClear' | 'setMinSubtrajectories' | 'largestCluster'> & { search: SearchResult; position: number; searchCount: number }) {
  const { routes } = search
  if (routes.length === 0) {
    return <p className="help-text search-empty">No routes found for these settings.</p>
  }

  // The total is summed from the returned routes, so it only covers subtrajectories that
  // ended up in a route the backend sent back.
  const total = totalSubtrajectories(filterRoutes(routes, minSubtrajectories))
  const rows = routes
    .map((route, index) => ({ route, index }))
    .filter(({ route, index }) =>
      meetsMinimum(route, minSubtrajectories) || sameRoute(selectedRoute, { searchId: search.id, index }))
    .sort((a, b) => b.route.members.length - a.route.members.length)

  if (rows.length === 0) {
    return (
      <p className="help-text search-empty">
        No clusters with at least {minSubtrajectories} subtrajectories.
      </p>
    )
  }

  return (
    <ul className="route-list">
      {rows.map(({ route, index }) => {
        const ref: RouteRef = { searchId: search.id, index }
        const isSelected = sameRoute(selectedRoute, ref)
        const share = total === 0 ? 0 : (route.members.length / total) * 100
        return (
          <Fragment key={index}>
            <li
              className={sameRoute(hoveredRoute, ref) || isSelected ? 'route-row active' : 'route-row'}
              onMouseEnter={() => setHoveredRoute(ref)}
              onMouseLeave={() => setHoveredRoute(null)}
              onClick={() => onSelectRoute(ref)}
            >
              <input
                type="checkbox"
                className="route-check"
                checked={checkedRoutes.has(routeKey(ref))}
                onChange={() => onToggleChecked(ref)}
                // Ticking must not also open the cluster, which a row click does.
                onClick={(event) => event.stopPropagation()}
                aria-label={`Show route ${index + 1} on the map`}
              />
              <span
                className="swatch"
                style={{ backgroundColor: routeColor(position, index, searchCount) }}
              />
              <span className="route-name">Route {index + 1}</span>
              <span className="route-count">{route.count} subtrajectories</span>
              <span
                className="route-share"
                title={`${route.members.length} of ${total} subtrajectories`}
              >
                {share.toFixed(1)}%
              </span>
            </li>

            {isSelected && (
              <li className="member-list-item">
                {memberLoading ? (
                  <p className="member-loading">Loading trips...</p>
                ) : memberPaths.length === 0 ? (
                  <p className="member-loading">No trips to show.</p>
                ) : (
                  <ul className="member-list">
                    {memberPaths.map((member, memberIndex) => (
                      <li
                        key={memberIndex}
                        className={hoveredMember === memberIndex ? 'member-row active' : 'member-row'}
                        onMouseEnter={() => setHoveredMember(memberIndex)}
                        onMouseLeave={() => setHoveredMember(null)}
                      >
                        <span className="member-name">Trip {memberIndex + 1}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            )}
          </Fragment>
        )
      })}
    </ul>
  )
}
