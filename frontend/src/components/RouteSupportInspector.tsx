import type { Pathlet } from '../types'
import { supportColor } from '../colors'

type Props = {
  route: Pathlet
  selectedInterval: number | null
  onSelectInterval: (id: number | null) => void
  onClose: () => void
}

const meters = (value: number) => `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} m`

export default function RouteSupportInspector({ route, selectedInterval, onSelectInterval, onClose }: Props) {
  const selected = route.support.find((interval) => interval.support_interval_id === selectedInterval)

  return (
    <section className="support-inspector" aria-label={`Pathlet ${route.pathlet_id} support`}>
      <div className="support-heading">
        <h2>Pathlet {route.pathlet_id}</h2>
        <button type="button" className="support-close" onClick={onClose}>Close</button>
      </div>
      <p className="support-summary">
        {meters(route.length_m)} · {route.count} distinct supporting {route.count === 1 ? 'trajectory' : 'trajectories'}
      </p>
      <p className="help-text">
        Distances follow this pathlet from its start (0 m). Each interval has the same supporters
        throughout. IDs identify the original trajectories, not other result pathlets.
        Pathlet and interval IDs are local to this search.
      </p>

      {route.length_m > 0 && (
        <>
          <div className="support-timeline" role="group" aria-label="Support along the pathlet">
            {route.support.map((interval) => (
              <button key={interval.support_interval_id} type="button"
                aria-label={`Interval ${interval.support_interval_id}: ${meters(interval.start_m)} to ${meters(interval.end_m)}`}
                aria-pressed={interval.support_interval_id === selectedInterval}
                onClick={() => onSelectInterval(interval.support_interval_id)}
                style={{
                  left: `${100 * interval.start_m / route.length_m}%`,
                  width: `${100 * (interval.end_m - interval.start_m) / route.length_m}%`,
                  backgroundColor: supportColor(interval.support_interval_id),
                }} />
            ))}
          </div>
          <div className="support-scale"><span>0 m</span><span>{meters(route.length_m)}</span></div>
        </>
      )}

      {selected ? (
        <div className="support-selection" role="status">
          <h3>Interval {route.pathlet_id}.{selected.support_interval_id}</h3>
          <p>{meters(selected.start_m)}–{meters(selected.end_m)} is highlighted on the map.
            The filled marker is the start; the hollow marker is the end.</p>
          <h3>Supporting trajectory IDs ({selected.count})</h3>
          <p className="support-ids">{selected.trajectory_ids.length ? selected.trajectory_ids.join(', ') : 'None'}</p>
          <button type="button" className="support-close" onClick={() => onSelectInterval(null)}>
            Show all intervals
          </button>
        </div>
      ) : (
        <p className="help-text">Select an interval below or on the map to see its supporters and endpoints.</p>
      )}

      <ul className="support-list">
        {route.support.map((interval) => (
          <li key={interval.support_interval_id}>
            <button type="button" className="support-interval"
              aria-pressed={interval.support_interval_id === selectedInterval}
              onClick={() => onSelectInterval(interval.support_interval_id)}>
              <span className="support-interval-heading">
                <i className="swatch" style={{ backgroundColor: supportColor(interval.support_interval_id) }} />
                <strong>Interval {route.pathlet_id}.{interval.support_interval_id}</strong>
                <span>{interval.count} {interval.count === 1 ? 'supporter' : 'supporters'}</span>
              </span>
              <span className="support-distances">
                <span>Start<strong>{meters(interval.start_m)}</strong></span>
                <span>End<strong>{meters(interval.end_m)}</strong></span>
                <span>Length<strong>{meters(interval.end_m - interval.start_m)}</strong></span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
