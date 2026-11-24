import { Fragment } from 'react'
import type { ClusterSubtrajectory, Route } from '../types'
import { ROUTE_COLORS } from '../colors'

type Props = {
  routes: Route[]
  hasSearched: boolean
  hoveredRoute: number | null
  setHoveredRoute: (index: number | null) => void
  selectedRoute: number | null
  onSelectRoute: (index: number) => void
  memberPaths: ClusterSubtrajectory[]
  memberLoading: boolean
  hoveredMember: number | null
  setHoveredMember: (index: number | null) => void
}

export default function RouteOverview({
  routes,
  hasSearched,
  hoveredRoute,
  setHoveredRoute,
  selectedRoute,
  onSelectRoute,
  memberPaths,
  memberLoading,
  hoveredMember,
  setHoveredMember,
}: Props) {
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
          <Fragment key={index}>
            <li
              className={hoveredRoute === index || selectedRoute === index ? 'route-row active' : 'route-row'}
              onMouseEnter={() => setHoveredRoute(index)}
              onMouseLeave={() => setHoveredRoute(null)}
              onClick={() => onSelectRoute(index)}
            >
              <span
                className="swatch"
                style={{ backgroundColor: ROUTE_COLORS[index % ROUTE_COLORS.length] }}
              />
              <span className="route-name">Route {index + 1}</span>
              <span className="route-count">{route.count} journeys</span>
            </li>

            {selectedRoute === index && (
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
                        <span className="member-id">#{member.trajectory_id}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            )}
          </Fragment>
        ))}
      </ul>
    </div>
  )
}
