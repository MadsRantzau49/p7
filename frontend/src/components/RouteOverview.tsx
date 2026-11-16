import type { Pathlet } from '../types'
import { ROUTE_COLORS } from '../colors'

type Props = {
  routes: Pathlet[]
  hasSearched: boolean
  hoveredRoute: number | null
  setHoveredRoute: (index: number | null) => void
  selectedRoute: number | null
  onSelectRoute: (index: number | null) => void
}

export default function RouteOverview({ routes, hasSearched, hoveredRoute, setHoveredRoute,
  selectedRoute, onSelectRoute }: Props) {
  if (!hasSearched) {
    return (
      <div className="overview">
        <p className="help-text">Set your journey and click "Find routes".</p>
      </div>
    )
  }

  if (routes.length === 0) {
    return (
      <div className="overview">
        <p className="help-text">No routes found for these settings.</p>
      </div>
    )
  }

  const rows = routes
    .map((route, index) => ({ route, index }))
    .sort((a, b) => b.route.count - a.route.count)

  return (
    <div className="overview">
      <h3>Routes found: {routes.length}</h3>
      <p className="help-text">Click a pathlet here or on the map to inspect its support.</p>
      <ul className="route-list">
        {rows.map(({ route, index }) => (
          <li
            key={route.pathlet_id}
            onMouseEnter={() => setHoveredRoute(index)}
            onMouseLeave={() => setHoveredRoute(null)}
          >
            <button type="button"
              className={`route-row${hoveredRoute === index ? ' active' : ''}${selectedRoute === index ? ' selected' : ''}`}
              aria-pressed={selectedRoute === index}
              onClick={() => onSelectRoute(index)}>
              <span
                className="swatch"
                style={{ backgroundColor: ROUTE_COLORS[index % ROUTE_COLORS.length] }}
              />
              <span className="route-name">Pathlet {route.pathlet_id}</span>
              <span className="route-count">{route.count} journeys</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
