// Usage is a magnitude, so it gets one hue from light to dark (a sequential ramp), not a
// rainbow of unrelated colours. Steps 250–700 of a blue ramp; 250 is the lightest that still
// stands out against the (greyed) map.
export const USAGE_COLORS = [
  '#86b6ef', '#6da7ec', '#5598e7', '#3987e5', '#2a78d6',
  '#256abf', '#1c5cab', '#184f95', '#104281', '#0d366b',
]
export const REPRESENTATIVE_COLOR = '#383838'
export const CONTRIBUTION_COLOR = '#000000'

const MIN_WIDTH = 1.5
const MAX_WIDTH = 7

export type UsageBand = { min: number; max: number; color: string; weight: number }

// Band upper limits grow roughly ×4–5 (a logarithmic scale). Usage is very skewed: in a typical
// search about half the drawn length is used by a single journey, so equal-width bands
// (1–500, 501–1000, …) put almost everything in the first band.
const BAND_LIMITS = [1, 5, 20, 100, 500, 2000, 10000, 50000]

// For example, a maximum of 2555 gives 1, 2–5, 6–20, 21–100, 101–500, 501–2000, 2001–2555.
// Busier bands are darker and thicker, so the main routes stand out and one-offs recede.
export function usageBands(maxCount: number): UsageBand[] {
  const maximum = Math.max(1, Math.ceil(maxCount))
  const limits = BAND_LIMITS.filter(limit => limit < maximum).concat(maximum)
  // With only a few bands (small searches), take smaller steps instead of jumping from the
  // lightest to the darkest style between e.g. 1 and 2 journeys.
  const steps = Math.max(limits.length - 1, 4)
  return limits.map((max, index) => {
    const position = index / steps
    return {
      min: index === 0 ? 1 : limits[index - 1] + 1,
      max,
      color: USAGE_COLORS[Math.round(position * (USAGE_COLORS.length - 1))],
      weight: MIN_WIDTH + position * (MAX_WIDTH - MIN_WIDTH),
    }
  })
}

// Takes precomputed bands: computing them per call was costly with thousands of stretches.
export function usageBand(count: number, bands: UsageBand[]): UsageBand {
  return bands.find(band => count <= band.max) ?? bands[bands.length - 1]
}

const JOURNEY_COLORS = [
  '#1565c0', '#c2185b', '#00883d', '#7928ad', '#ce3e00', '#007e94',
  '#b18a00', '#3445b4', '#b51e22', '#007b70', '#9b3d83', '#745323',
]

// The ten-band limit applies to counts, not journey identities. Additional
// journeys receive distinct hues rather than cycling the same ten colours.
export function journeyColor(index: number): string {
  if (index < JOURNEY_COLORS.length) return JOURNEY_COLORS[index]
  const hue = ((index - JOURNEY_COLORS.length) * 137.508 + 20) % 360
  return `hsl(${hue.toFixed(1)}, 80%, ${index % 2 ? 36 : 46}%)`
}
