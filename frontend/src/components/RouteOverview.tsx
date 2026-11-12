import type { Pathlet } from '../types'
import { ROUTE_COLORS } from '../colors'

type Props = {
  routes: Pathlet[]
  hasSearched: boolean
  hoveredRoute: number | null
  setHoveredRoute: (index: number | null) => void
}

export default function RouteOverview({ routes, hasSearched, hoveredRoute, setHoveredRoute }: Props) {
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
      <ul className="route-list">
        {rows.map(({ route, index }) => (
          <li
            key={index}
            className={hoveredRoute === index ? 'route-row active' : 'route-row'}
            onMouseEnter={() => setHoveredRoute(index)}
            onMouseLeave={() => setHoveredRoute(null)}
          >
            <span
              className="swatch"
              style={{ backgroundColor: ROUTE_COLORS[index % ROUTE_COLORS.length] }}
            />
            <span className="route-name">Route {index + 1}</span>
            <span className="route-count">{route.count} journeys</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
