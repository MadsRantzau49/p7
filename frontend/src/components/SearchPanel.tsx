import type { Area, PickMode, SimilarityLevel } from '../types'

// The three similarity blocks, in order, with their labels.
const SIMILARITY_LEVELS: { value: SimilarityLevel; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'mid', label: 'Mid' },
  { value: 'high', label: 'High' },
]

type Props = {
  startArea: Area | null
  endArea: Area | null
  pickMode: PickMode
  setPickMode: (mode: PickMode) => void

  fromDate: string
  setFromDate: (value: string) => void
  toDate: string
  setToDate: (value: string) => void

  fromHour: string
  setFromHour: (value: string) => void
  toHour: string
  setToHour: (value: string) => void

  similarityLevel: SimilarityLevel
  setSimilarityLevel: (value: SimilarityLevel) => void
  useCustomEpsilon: boolean
  setUseCustomEpsilon: (value: boolean) => void
  customEpsilon: number
  setCustomEpsilon: (value: number) => void
  epsilonMeters: number

  loading: boolean
  canSearch: boolean
  error: string | null
  onFindRoutes: () => void
}

export default function SearchPanel({
  startArea,
  endArea,
  pickMode,
  setPickMode,
  fromDate,
  setFromDate,
  toDate,
  setToDate,
  fromHour,
  setFromHour,
  toHour,
  setToHour,
  similarityLevel,
  setSimilarityLevel,
  useCustomEpsilon,
  setUseCustomEpsilon,
  customEpsilon,
  setCustomEpsilon,
  epsilonMeters,
  loading,
  canSearch,
  error,
  onFindRoutes,
}: Props) {
  return (
    <aside className="search-panel">
      <h2>Choose your journey</h2>
      
      <section className="panel-section">
        <h3>1. Where?</h3>
        <button
          type="button"
          className={pickMode === 'start' ? 'pick-button active' : 'pick-button'}
          aria-pressed={pickMode === 'start'}
          disabled={loading}
          onClick={() => setPickMode(pickMode === 'start' ? null : 'start')}
        >
          {startArea ? 'A · Starting area selected — change' : 'A · Select starting area on map'}
        </button>

        <button
          type="button"
          className={pickMode === 'end' ? 'pick-button active' : 'pick-button'}
          aria-pressed={pickMode === 'end'}
          disabled={loading}
          onClick={() => setPickMode(pickMode === 'end' ? null : 'end')}
        >
          {endArea ? 'B · Destination area selected — change' : 'B · Select destination area on map'}
        </button>
      </section>

      {/* 2. When */}
      <section className="panel-section">
        <h3>2. When? (optional)</h3>
        <p className="help-text">Leave blank to include all dates and hours.</p>
        <div className="field-row">
          <label>
            From date
            <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          </label>
          <label>
            To date
            <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          </label>
        </div>

        <p className="field-group-title">Daily hours (each day)</p>
        <div className="field-row">
          <label>
            From
            <input type="time" value={fromHour} onChange={(e) => setFromHour(e.target.value)} />
          </label>
          <label>
            To
            <input type="time" value={toHour} onChange={(e) => setToHour(e.target.value)} />
          </label>
        </div>
        <p className="help-text">
          Optional. Only routes leaving the start area in this window are shown. If From is later
          than To, the window wraps past midnight (e.g. 22:00–02:00).
        </p>
      </section>

      {/* 3. Route preferences */}
      <section className="panel-section">
        <h3>3. Route preferences</h3>
        <div className="level-group">
          {SIMILARITY_LEVELS.map((level) => (
            <button
              key={level.value}
              type="button"
              className={similarityLevel === level.value ? 'level-button active' : 'level-button'}
              disabled={useCustomEpsilon}
              onClick={() => setSimilarityLevel(level.value)}
            >
              {level.label}
            </button>
          ))}
        </div>
        <p className="help-text">Grouping distance: {epsilonMeters} m</p>

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={useCustomEpsilon}
            onChange={(e) => setUseCustomEpsilon(e.target.checked)}
          />
          Custom metres
        </label>
        {useCustomEpsilon && (
          <input
            type="number"
            min={1}
            value={customEpsilon}
            onChange={(e) => setCustomEpsilon(Number(e.target.value))}
          />
        )}
      </section>

      <button
        type="button"
        className="find-button"
        disabled={!canSearch || loading}
        onClick={onFindRoutes}
      >
        {loading && <span className="spinner" />}
        {loading ? 'Finding...' : 'Find routes'}
      </button>

      {error && <p className="error-text" role="alert">{error}</p>}
    </aside>
  )
}
